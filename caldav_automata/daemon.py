"""
CalDAV Automata — polling daemon.

Watches one or more CalDAV accounts and their calendars.  On every poll
cycle it tries to fetch only changed events via CalDAV sync-tokens
(``sync-collection`` REPORT), compares ETags against a persistent state
file, and — for events that are new or changed — applies the matching
LISP rules before writing the modified event back to the server.

Change detection
----------------
CalDAV servers attach an ETag to every resource.  The daemon stores the
most-recently-seen ETag for each event URL in a local SQLite state DB so it
survives restarts.  The decision tree per event is:

    URL not in state  ->  on-create rules, write back, store new ETag
    ETag changed      ->  on-update rules, write back, store new ETag
    ETag unchanged    ->  skip

After a successful write-back the server issues a fresh ETag; the daemon
reads it from the response and stores it so the next poll is a no-op.

Self-write avoidance
--------------------
When the daemon writes a modified event back to the server, the server
assigns a new ETag.  If the CalDAV library can retrieve that ETag from
the PUT response, it is stored immediately and the next poll sees no
change — all is well.

If the server does not return the new ETag in the response the daemon
falls back to the *old* ETag.  The next poll would then see a mismatched
ETag and — without any guard — re-process the event the daemon itself
just wrote, potentially looping.

To prevent this the daemon maintains an in-memory set of URLs it wrote
in the current process lifetime (``_EventState._self_written``).  When a
poll cycle encounters a changed ETag for a URL in that set it knows the
change was self-caused, skips rule evaluation, updates the stored ETag
to the current one, and clears the entry.  The set is intentionally
not persisted: on a cold restart the daemon will process every event
once (applying rules is idempotent for already-correct events), then
settle into no-op cycles.

Multiple accounts / calendars
------------------------------
Each entry under ``accounts:`` in the configuration file is polled
independently.  The ``calendars:`` list inside each account is a list of
calendar display-names to watch (supports ``fnmatch`` wildcards; ``"*"``
matches every calendar on that account).
"""

from __future__ import annotations

import fnmatch
import glob as glob_module
import logging
import os
import signal
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

import caldav
from icalendar import Calendar

from .actions import apply_action
from .lisp import Rule, load_rules

logger = logging.getLogger(__name__)
_MAX_CALENDAR_ALIASES_IN_LOG = 2


# ---------------------------------------------------------------------------
# ETag state  (persisted to disk)
# ---------------------------------------------------------------------------


class _EventState:
    """SQLite-backed state storage for event/inbox ETags and sync tokens."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=MEMORY")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS event_etags ("
            "url TEXT PRIMARY KEY, "
            "etag TEXT NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS inbox_etags ("
            "url TEXT PRIMARY KEY, "
            "etag TEXT NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS calendar_sync_tokens ("
            "calendar_url TEXT PRIMARY KEY, "
            "sync_token TEXT NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS ics_feed_state ("
            "feed_url TEXT PRIMARY KEY, "
            "etag TEXT, "
            "last_modified TEXT"
            ")"
        )
        self._conn.commit()
        # In-memory set of URLs written by this process; used to skip the
        # apparent ETag change caused by our own write-back (see module docs).
        self._self_written: set[str] = set()
        logger.debug("State DB ready at %s", self._path)

    def save(self) -> None:
        self._conn.commit()

    def get_etag(self, url: str) -> str | None:
        row = self._conn.execute(
            "SELECT etag FROM event_etags WHERE url = ?", (url,)
        ).fetchone()
        return row[0] if row else None

    def set_etag(self, url: str, etag: str) -> None:
        self._conn.execute(
            "INSERT INTO event_etags(url, etag) VALUES(?, ?) "
            "ON CONFLICT(url) DO UPDATE SET etag = excluded.etag",
            (url, etag),
        )

    def clear_etag(self, url: str) -> None:
        self._conn.execute("DELETE FROM event_etags WHERE url = ?", (url,))

    def is_known(self, url: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM event_etags WHERE url = ?", (url,)
        ).fetchone()
        return row is not None

    def get_inbox_etag(self, url: str) -> str | None:
        row = self._conn.execute(
            "SELECT etag FROM inbox_etags WHERE url = ?", (url,)
        ).fetchone()
        return row[0] if row else None

    def set_inbox_etag(self, url: str, etag: str) -> None:
        self._conn.execute(
            "INSERT INTO inbox_etags(url, etag) VALUES(?, ?) "
            "ON CONFLICT(url) DO UPDATE SET etag = excluded.etag",
            (url, etag),
        )

    def is_known_inbox(self, url: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM inbox_etags WHERE url = ?", (url,)
        ).fetchone()
        return row is not None

    def get_calendar_sync_token(self, calendar_url: str) -> str | None:
        row = self._conn.execute(
            "SELECT sync_token FROM calendar_sync_tokens WHERE calendar_url = ?",
            (calendar_url,),
        ).fetchone()
        return row[0] if row else None

    def set_calendar_sync_token(self, calendar_url: str, token: str) -> None:
        self._conn.execute(
            "INSERT INTO calendar_sync_tokens(calendar_url, sync_token) "
            "VALUES(?, ?) "
            "ON CONFLICT(calendar_url) DO UPDATE "
            "SET sync_token = excluded.sync_token",
            (calendar_url, token),
        )

    def get_feed_state(self, feed_url: str) -> tuple[str | None, str | None]:
        """Return *(etag, last_modified)* for a previously-fetched ICS feed."""
        row = self._conn.execute(
            "SELECT etag, last_modified FROM ics_feed_state WHERE feed_url = ?",
            (feed_url,),
        ).fetchone()
        return (row[0], row[1]) if row else (None, None)

    def set_feed_state(
        self, feed_url: str, etag: str | None, last_modified: str | None
    ) -> None:
        """Persist HTTP caching headers for an ICS feed URL."""
        self._conn.execute(
            "INSERT INTO ics_feed_state(feed_url, etag, last_modified) "
            "VALUES(?, ?, ?) "
            "ON CONFLICT(feed_url) DO UPDATE "
            "SET etag = excluded.etag, last_modified = excluded.last_modified",
            (feed_url, etag, last_modified),
        )

    def mark_self_written(self, url: str) -> None:
        self._self_written.add(url)

    def is_self_written(self, url: str) -> bool:
        return url in self._self_written

    def clear_self_written(self, url: str) -> None:
        self._self_written.discard(url)


# ---------------------------------------------------------------------------
# Rule loading  (re-read every cycle for live hot-reload)
# ---------------------------------------------------------------------------


def _load_all_rules(rules_dir: str) -> list[Rule]:
    rules: list[Rule] = []
    for path in _iter_rule_files(rules_dir):
        try:
            loaded = load_rules(path)
            rules.extend(loaded)
        except Exception:
            logger.exception("Failed to load rules from %s", path)
    return rules


def _iter_rule_files(rules_dir: str) -> list[str]:
    """Return sorted rule file paths that should be considered for reloads."""
    pattern = os.path.join(rules_dir, "**", "*.lisp")
    return [
        path
        for path in sorted(glob_module.glob(pattern, recursive=True))
        if not path.endswith(".example.lisp")
    ]


def _rule_files_snapshot(rules_dir: str) -> dict[str, tuple[int, int]]:
    """Return a fingerprint map for current rule files.

    The tuple stores ``(mtime_ns, size)`` per path to detect edits,
    creations, and deletions.
    """
    snapshot: dict[str, tuple[int, int]] = {}
    for path in _iter_rule_files(rules_dir):
        try:
            st = os.stat(path)
        except OSError:
            # File may disappear between glob and stat.
            continue
        snapshot[path] = (st.st_mtime_ns, st.st_size)
    return snapshot


def _describe_rule_changes(
    previous: dict[str, tuple[int, int]],
    current: dict[str, tuple[int, int]],
) -> list[str]:
    """Describe added/removed/modified rule files for logging."""
    added = sorted(path for path in current if path not in previous)
    removed = sorted(path for path in previous if path not in current)
    modified = sorted(
        path for path in current if path in previous and current[path] != previous[path]
    )

    changes: list[str] = []
    changes.extend(f"added {Path(path).name}" for path in added)
    changes.extend(f"removed {Path(path).name}" for path in removed)
    changes.extend(f"modified {Path(path).name}" for path in modified)
    return changes


def _resolve_date_spec(spec: str) -> date:
    if spec.lower() == "today":
        return datetime.now().astimezone().date()
    return date.fromisoformat(spec)


def _event_start_date(component) -> date | None:
    value = component.get("DTSTART")
    if value is None:
        return None

    start = getattr(value, "dt", value)
    if isinstance(start, datetime):
        return start.astimezone().date() if start.tzinfo else start.date()
    if isinstance(start, date):
        return start
    return None


def _matches_date_specs(
    event_date: date | None, specs: list[str], operator: str
) -> bool:
    if not specs:
        return True
    if event_date is None:
        return False

    for spec in specs:
        target = _resolve_date_spec(spec)
        if operator == "on" and event_date == target:
            return True
        if operator == "before" and event_date < target:
            return True
        if operator == "after" and event_date > target:
            return True
    return False


def _organizer_candidates(value: str) -> set[str]:
    """Return organizer forms usable for matching fnmatch patterns."""
    raw = str(value).strip().lower()
    if not raw:
        return set()
    return {raw, raw.removeprefix("mailto:")}


def _normalise_calendar_address(value: str) -> str:
    """Normalise organizer/attendee addresses to a Cal-Address string."""
    raw = str(value).strip()
    if not raw:
        return ""
    if ":" in raw:
        return raw
    return f"mailto:{raw}"


def _principal_owner_email(principal) -> str | None:
    """Return a principal calendar user address preferring mailto: forms."""
    try:
        addresses = principal.calendar_user_address_set()
    except Exception:
        return None

    if not isinstance(addresses, list):
        addresses = [addresses]

    fallback = None
    for raw in addresses:
        text = str(raw).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered.startswith("mailto:"):
            return _normalise_calendar_address(text)
        if fallback is None:
            fallback = _normalise_calendar_address(text)
    return fallback


def _matches(
    rule: Rule,
    calendar_name: str,
    subject: str = "",
    note: str = "",
    organizer: str = "",
    start_date: date | None = None,
) -> bool:
    if rule.calendars and not any(
        pat == "*" or fnmatch.fnmatch(calendar_name.lower(), pat.lower())
        for pat in rule.calendars
    ):
        return False
    if rule.subjects and not any(
        fnmatch.fnmatch(subject.lower(), pat.lower()) for pat in rule.subjects
    ):
        return False
    if rule.notes and not any(
        fnmatch.fnmatch(note.lower(), pat.lower()) for pat in rule.notes
    ):
        return False
    if rule.organizers:
        organizer_values = _organizer_candidates(organizer)
        if not organizer_values:
            return False
        if not any(
            fnmatch.fnmatch(value, pat.lower())
            for pat in rule.organizers
            for value in organizer_values
        ):
            return False
    if not _matches_date_specs(start_date, rule.date_on, "on"):
        return False
    if not _matches_date_specs(start_date, rule.date_before, "before"):
        return False
    if not _matches_date_specs(start_date, rule.date_after, "after"):
        return False
    return True


def _get_event_info(raw_ical: str) -> tuple[str, str]:
    """Return *(title, date_str)* for the first VEVENT in *raw_ical*.

    Both values are safe to use in log messages.  *date_str* is an
    ISO-8601 date string or ``'unknown'`` when the start date cannot be
    determined.
    """
    try:
        cal = Calendar.from_ical(raw_ical)
    except Exception:
        return "", "unknown"

    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        title = str(component.get("SUMMARY", ""))
        start_date = _event_start_date(component)
        date_str = start_date.isoformat() if start_date is not None else "unknown"
        return title, date_str

    return "", "unknown"


# ---------------------------------------------------------------------------
# iCalendar mutation
# ---------------------------------------------------------------------------


def _apply_rules(
    raw_ical: str,
    calendar_name: str | list[str],
    is_new: bool,
    rules: list[Rule],
    owner_email: str | None = None,
    calendar_getter=None,
) -> str | None:
    """
    Apply matching rules to *raw_ical*.

    Returns the modified iCal string when at least one action ran, or
    ``None`` when the event should be left unchanged.

    Parameters
    ----------
    calendar_name:
        A single calendar name or multiple aliases used for rule matching.
        A rule matches when any provided calendar name matches its
        ``(calendar "...")`` filter.
    calendar_getter:
        Optional callable ``(name: str) -> caldav.Calendar | None`` forwarded
        to ``apply_action`` for use by the ``copy-to-calendar`` action.
    """
    try:
        cal = Calendar.from_ical(raw_ical)
    except Exception:
        logger.exception("Could not parse iCal payload — skipping event")
        return None

    raw_calendar_names = (
        [calendar_name] if isinstance(calendar_name, str) else calendar_name
    )
    calendar_names = _normalise_calendar_names(raw_calendar_names)

    changed = False
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        subject = str(component.get("SUMMARY", ""))
        note = str(component.get("DESCRIPTION", ""))
        organizer = str(component.get("ORGANIZER", ""))
        start_date = _event_start_date(component)
        for rule in rules:
            if not any(
                _matches(rule, name, subject, note, organizer, start_date)
                for name in calendar_names
            ):
                continue
            actions = rule.on_create if is_new else rule.on_update
            for action in actions:
                try:
                    changed = (
                        apply_action(
                            component,
                            action,
                            owner_email=owner_email,
                            get_calendar=calendar_getter,
                        )
                        or changed
                    )
                except Exception:
                    logger.exception("Error applying action %r", action)

    if not changed:
        return None

    try:
        return cal.to_ical().decode("utf-8")
    except Exception:
        logger.exception("Could not serialise modified iCal — skipping write-back")
        return None


def _has_invite_rules(rules: list[Rule]) -> bool:
    """Return True when any rule has scheduling inbox actions."""
    return any(
        rule.on_invite_request
        or rule.on_invite_reply
        or rule.on_invite_cancel
        or rule.on_invite_add
        for rule in rules
    )


def _first_vevent(raw_ical: str):
    """Return the first VEVENT component from an iCal payload."""
    try:
        cal = Calendar.from_ical(raw_ical)
    except Exception:
        return None
    for component in cal.walk():
        if component.name == "VEVENT":
            return component
    return None


def _apply_inbox_rules(
    raw_ical: str,
    invite_type: str,
    inbox_item,
    rules: list[Rule],
    calendar_getter=None,
) -> bool:
    """
    Apply invite-request/reply actions to a scheduling inbox item.

    Returns True when at least one action executed successfully.

    Parameters
    ----------
    calendar_getter:
        Optional callable ``(name: str) -> caldav.Calendar | None`` forwarded
        to ``apply_action`` for use by the ``copy-to-calendar`` action.
    """
    component = _first_vevent(raw_ical)
    if component is None:
        logger.debug("Inbox item has no VEVENT component — skipping")
        return False

    subject = str(component.get("SUMMARY", ""))
    note = str(component.get("DESCRIPTION", ""))
    organizer = str(component.get("ORGANIZER", ""))
    start_date = _event_start_date(component)

    changed = False
    for rule in rules:
        if not _matches(rule, "inbox", subject, note, organizer, start_date):
            continue
        if invite_type == "request":
            actions = rule.on_invite_request
        elif invite_type == "reply":
            actions = rule.on_invite_reply
        elif invite_type == "cancel":
            actions = rule.on_invite_cancel
        elif invite_type == "add":
            actions = rule.on_invite_add
        else:
            actions = []
        for action in actions:
            try:
                changed = (
                    apply_action(
                        component,
                        action,
                        inbox_item=inbox_item,
                        get_calendar=calendar_getter,
                    )
                    or changed
                )
            except Exception:
                logger.exception("Error applying inbox action %r", action)

    return changed


# ---------------------------------------------------------------------------
# Per-calendar polling
# ---------------------------------------------------------------------------


def _normalise_etag(etag: str | None) -> str:
    """Strip surrounding quotes that some servers add to ETags."""
    if etag is None:
        return ""
    return etag.strip('"')


# ---------------------------------------------------------------------------
# ICS feed fetching and polling
# ---------------------------------------------------------------------------


def _fetch_ics_feed(
    url: str,
    prev_etag: str | None = None,
    prev_last_modified: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """
    Fetch an ICS feed from *url* using conditional GET when possible.

    Returns *(ics_text, etag, last_modified)*.  When the server responds with
    ``304 Not Modified``, *ics_text* is ``None`` and the cached header values
    are returned unchanged so the caller can skip processing.
    """
    headers: dict[str, str] = {
        "User-Agent": "CalDAV Automata/1.0",
        "Accept": "text/calendar, */*",
    }
    if prev_etag:
        headers["If-None-Match"] = prev_etag
    if prev_last_modified:
        headers["If-Modified-Since"] = prev_last_modified

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            ics_bytes = resp.read()
            # Honour charset from Content-Type when present; fall back to UTF-8.
            content_type = resp.headers.get("Content-Type", "")
            charset = "utf-8"
            for part in content_type.split(";"):
                part = part.strip()
                if part.lower().startswith("charset="):
                    charset = part.split("=", 1)[1].strip().strip('"') or charset
                    break
            ics_text = ics_bytes.decode(charset, errors="replace")
            etag = resp.headers.get("ETag") or None
            last_modified = resp.headers.get("Last-Modified") or None
            return ics_text, etag, last_modified
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None, prev_etag, prev_last_modified
        raise


def _extract_ics_calendar_names(
    ics_text: str, configured_name: str | None, url: str
) -> list[str]:
    """Return candidate calendar names for an ICS feed.

    Names are de-duplicated while preserving order:
    ``X-WR-CALNAME`` from the feed, then configured ``name``, then *url* when
    no human-readable name is available.
    """
    names: list[str | None] = []

    try:
        cal = Calendar.from_ical(ics_text)
        for component in cal.walk():
            if component.name == "VCALENDAR":
                names.append(component.get("X-WR-CALNAME"))
                break
    except Exception:
        pass

    names.append(configured_name)
    return _normalise_calendar_names(names, fallback=url)


def _normalise_calendar_names(
    names: list[str | None], fallback: str | None = None
) -> list[str]:
    """Normalise and de-duplicate calendar name aliases."""
    normalised: list[str] = []
    for name in names:
        if name is None:
            continue
        text = str(name).strip()
        if text and text not in normalised:
            normalised.append(text)
    if not normalised and fallback:
        fallback_text = str(fallback).strip()
        if fallback_text:
            normalised.append(fallback_text)
    return normalised


def _format_calendar_display_name(calendar_names: list[str]) -> str:
    """Format calendar aliases for concise log output."""
    if len(calendar_names) <= _MAX_CALENDAR_ALIASES_IN_LOG:
        return " | ".join(calendar_names)
    return f"{' | '.join(calendar_names[:_MAX_CALENDAR_ALIASES_IN_LOG])} | ..."


def _poll_ics_feed(
    feed: dict,
    state: _EventState,
    rules: list[Rule],
    calendar_getter=None,
) -> int:
    """
    Fetch an ICS feed and apply rules to events that have not been seen before.

    ICS feeds are read-only: any iCal string returned by ``_apply_rules`` is
    discarded.  The only lasting side-effect is produced by actions such as
    ``copy-to-calendar`` that operate through *calendar_getter*.

    Returns the number of events on which at least one action ran.
    """
    feed_url = feed.get("url", "")
    configured_name = feed.get("name")

    if not feed_url:
        logger.warning("ICS feed entry has no URL — skipping")
        return 0

    logger.debug("Polling ICS feed %r", feed_url)
    prev_etag, prev_last_modified = state.get_feed_state(feed_url)

    try:
        ics_text, etag, last_modified = _fetch_ics_feed(
            feed_url, prev_etag, prev_last_modified
        )
    except Exception:
        logger.exception("Could not fetch ICS feed %r", feed_url)
        return 0

    if ics_text is None:
        logger.debug("ICS feed %r unchanged (304 Not Modified)", feed_url)
        return 0

    calendar_names = _extract_ics_calendar_names(ics_text, configured_name, feed_url)
    calendar_display_name = _format_calendar_display_name(calendar_names)
    logger.info("[%s] Fetched ICS feed", calendar_display_name)

    # Persist the updated HTTP caching headers immediately so that even if
    # processing fails partway through we do not re-fetch on the next poll.
    state.set_feed_state(feed_url, etag, last_modified)
    state.save()

    try:
        cal = Calendar.from_ical(ics_text)
    except Exception:
        logger.exception("[%s] Could not parse ICS feed", cal_name)
        return 0

    # Pre-collect VTIMEZONE components so they can be included when wrapping
    # individual VEVENTs.  This preserves timezone info for copied events.
    vtimezones = [c for c in cal.walk() if c.name == "VTIMEZONE"]

    acted = 0
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID", "")).strip()
        if not uid:
            logger.debug("[%s] Skipping VEVENT without UID", cal_name)
            continue

        # Use a namespaced state key so ICS UIDs never collide with CalDAV URLs.
        state_key = f"ics:{feed_url}#{uid}"
        if state.is_known(state_key):
            # Already processed in a previous cycle — skip.
            continue

        title = str(component.get("SUMMARY", ""))
        start_date = _event_start_date(component)
        date_str = start_date.isoformat() if start_date is not None else "unknown"

        if title:
            logger.info(
                '[%s] New ICS event: "%s" (%s)',
                calendar_display_name,
                title,
                date_str,
            )
        else:
            logger.info(
                "[%s] New ICS event (date: %s)", calendar_display_name, date_str
            )

        # Wrap the single VEVENT in a minimal VCALENDAR (with any VTIMEZONEs)
        # so that _apply_rules can parse it via its standard code path.
        per_event_cal = Calendar()
        per_event_cal.add("prodid", "-//CalDAV Automata//EN")
        per_event_cal.add("version", "2.0")
        for vtz in vtimezones:
            per_event_cal.add_component(vtz)
        per_event_cal.add_component(component)
        try:
            raw_ical = per_event_cal.to_ical().decode("utf-8")
        except Exception:
            logger.exception(
                "[%s] Could not serialise VEVENT %s — skipping",
                calendar_display_name,
                uid,
            )
            continue

        # Apply rules.  The result is intentionally discarded (read-only feed).
        # copy-to-calendar and similar side-effecting actions still execute.
        _apply_rules(
            raw_ical,
            calendar_names,
            is_new=True,
            rules=rules,
            calendar_getter=calendar_getter,
        )

        # Mark this UID as seen so it is not re-processed on the next cycle.
        state.set_etag(state_key, "seen")
        state.save()
        acted += 1

    return acted


def _poll_calendar(
    calendar: caldav.Calendar,
    state: _EventState,
    rules: list[Rule],
    owner_email: str | None = None,
    calendar_getter=None,
) -> int:
    """
    Fetch all events in *calendar*, apply rules to new/changed ones, and
    write modifications back.

    Returns the number of events that were modified and saved.

    Parameters
    ----------
    calendar_getter:
        Optional callable ``(name: str) -> caldav.Calendar | None`` forwarded
        to ``_apply_rules`` for use by the ``copy-to-calendar`` action.
    """
    cal_name = calendar.name or str(calendar.url)
    cal_url = str(calendar.url)
    saved = 0

    events = None
    sync_token = state.get_calendar_sync_token(cal_url)

    if hasattr(calendar, "get_objects_by_sync_token"):
        try:
            changes = calendar.get_objects_by_sync_token(
                sync_token=sync_token, load_objects=False
            )
            events = list(changes)
            new_sync_token = getattr(changes, "sync_token", None)
            if isinstance(new_sync_token, str) and new_sync_token:
                state.set_calendar_sync_token(cal_url, new_sync_token)
            logger.debug(
                "[%s] Delta sync returned %d changed item(s) (token: %s)",
                cal_name,
                len(events),
                "present" if new_sync_token else "missing",
            )
        except Exception:
            logger.exception(
                "[%s] Delta sync failed; falling back to full calendar scan",
                cal_name,
            )

    if events is None:
        try:
            events = calendar.events()
        except Exception:
            logger.exception("Could not fetch events from calendar %r", cal_name)
            return 0

    for event in events:
        url = str(event.url)
        state_changed = False

        # Sync-collection responses often include only href+etag with no body.
        # Load the object lazily when needed. If that fails or still yields
        # no payload, treat it as deleted/unavailable and drop stale state.
        raw_ical = getattr(event, "data", None)
        if not raw_ical and hasattr(event, "load"):
            try:
                event.load()
                raw_ical = getattr(event, "data", None)
            except Exception:
                raw_ical = None
        if not raw_ical:
            state.clear_etag(url)
            state.clear_self_written(url)
            state_changed = True
            logger.debug(
                "[%s] Event deleted or unavailable, dropped from state: %s",
                cal_name,
                url,
            )
            if state_changed:
                state.save()
            continue

        etag = _normalise_etag(getattr(event, "etag", None))

        is_new = not state.is_known(url)
        is_changed = not is_new and state.get_etag(url) != etag

        if not is_new and not is_changed:
            continue

        verb = "new" if is_new else "updated"
        uid = url.rstrip("/").split("/")[-1]
        title, date_str = _get_event_info(raw_ical)

        # Self-write guard: if we wrote this event ourselves in this process
        # lifetime and its ETag now looks changed, the change is self-caused.
        # Update the stored ETag and skip re-processing.
        if state.is_self_written(url):
            state.clear_self_written(url)
            state.set_etag(url, etag)
            state_changed = True
            logger.debug(
                "[%s] Skipping self-modified event (ETag refreshed): %s",
                cal_name,
                uid,
            )
            if state_changed:
                state.save()
            continue

        if title:
            logger.info('[%s] %s event: "%s" (%s)', cal_name, verb, title, date_str)
        else:
            logger.info("[%s] %s event (date: %s)", cal_name, verb, date_str)
        logger.debug("[%s] %s event detected: %s", cal_name, verb, uid)

        modified_ical = _apply_rules(
            raw_ical,
            cal_name,
            is_new,
            rules,
            owner_email=owner_email,
            calendar_getter=calendar_getter,
        )

        if modified_ical is not None:
            try:
                event.data = modified_ical
                event.save()
                new_etag = _normalise_etag(getattr(event, "etag", None))
                if new_etag:
                    state.set_etag(url, new_etag)
                else:
                    # Server did not return the new ETag in the response.
                    # Store the pre-write ETag as a placeholder and mark
                    # this URL so the next poll skips the apparent change.
                    state.set_etag(url, etag)
                    state.mark_self_written(url)
                state_changed = True
                if title:
                    logger.info(
                        '[%s] Wrote back modified event: "%s" (%s)',
                        cal_name,
                        title,
                        date_str,
                    )
                else:
                    logger.info(
                        "[%s] Wrote back modified event (date: %s)", cal_name, date_str
                    )
                logger.debug("[%s] Wrote back modified event: %s", cal_name, uid)
                saved += 1
            except Exception:
                logger.exception(
                    "Failed to save event %s in calendar %r", uid, cal_name
                )
                # Record the original ETag so we do not loop on failure.
                state.set_etag(url, etag)
                state_changed = True
        else:
            # Rules matched nothing — just record that we have seen this ETag.
            state.set_etag(url, etag)
            state_changed = True

        if state_changed:
            state.save()

    return saved


def _poll_inbox(
    principal: caldav.Principal,
    state: _EventState,
    rules: list[Rule],
    label: str,
    calendar_getter=None,
) -> int:
    """
    Poll the account scheduling inbox and apply invite request/reply rules.

    Returns the number of inbox items that triggered at least one action.

    Parameters
    ----------
    calendar_getter:
        Optional callable ``(name: str) -> caldav.Calendar | None`` forwarded
        to ``_apply_inbox_rules`` for use by the ``copy-to-calendar`` action.
    """
    try:
        inbox = principal.schedule_inbox()
        items = inbox.get_items()
    except Exception:
        logger.exception("[%s] Could not fetch scheduling inbox", label)
        return 0

    handled = 0

    def _classify_invite_type(item, raw_ical: str) -> str | None:
        # Prefer caldav-python helpers when available.
        probes = (
            ("request", "is_invite_request"),
            ("reply", "is_invite_reply"),
            ("cancel", "is_invite_cancel"),
            ("add", "is_invite_add"),
        )
        for invite_type, method_name in probes:
            method = getattr(item, method_name, None)
            if callable(method):
                try:
                    if bool(method()):
                        return invite_type
                except Exception:
                    logger.debug(
                        "[%s] Inbox classifier %s failed for %s",
                        label,
                        method_name,
                        getattr(item, "url", "?"),
                        exc_info=True,
                    )

        # Fallback: inspect VCALENDAR METHOD directly.
        try:
            cal = Calendar.from_ical(raw_ical)
            method = str(cal.get("METHOD", "")).strip().upper()
            if method in {"REQUEST", "REPLY", "CANCEL", "ADD"}:
                return method.lower()
        except Exception:
            logger.debug(
                "[%s] Could not parse inbox item method for %s",
                label,
                getattr(item, "url", "?"),
                exc_info=True,
            )

        return None

    for item in items:
        url = str(item.url)
        etag = _normalise_etag(getattr(item, "etag", None))

        is_new = not state.is_known_inbox(url)
        is_changed = not is_new and state.get_inbox_etag(url) != etag
        if not is_new and not is_changed:
            continue

        title, date_str = _get_event_info(item.data)
        uid = url.rstrip("/").split("/")[-1]

        invite_type = _classify_invite_type(item, item.data)
        if invite_type is None:
            state.set_inbox_etag(url, etag)
            continue

        if title:
            logger.info(
                '[%s] %s inbox item: "%s" (%s)', label, invite_type, title, date_str
            )
        else:
            logger.info("[%s] %s inbox item (date: %s)", label, invite_type, date_str)
        logger.debug("[%s] Processing inbox item: %s", label, uid)

        acted = _apply_inbox_rules(
            item.data, invite_type, item, rules, calendar_getter=calendar_getter
        )
        if acted:
            handled += 1
        state.set_inbox_etag(url, etag)

    return handled


# ---------------------------------------------------------------------------
# Per-account polling
# ---------------------------------------------------------------------------


def _normalise_watch_entries(raw_watch: Any) -> list[str]:
    """Return normalised calendar watch patterns (string entries only)."""
    patterns: list[str] = []

    if isinstance(raw_watch, str):
        items = [raw_watch]
    elif isinstance(raw_watch, list):
        items = raw_watch
    else:
        items = ["*"]

    for item in items:
        if isinstance(item, str):
            patterns.append(item.strip() or "*")
            continue

        logger.warning(
            "Ignoring invalid calendar watch entry %r; expected string pattern",
            item,
        )

    return patterns or ["*"]


def _matches_watch_pattern(name: str, patterns: list[str]) -> bool:
    """Return True when *name* matches at least one watch pattern."""
    lowered = name.lower()
    for pattern in patterns:
        if pattern == "*" or fnmatch.fnmatch(lowered, pattern.lower()):
            return True
    return False


def _configured_organizer_fallbacks(accounts: list[dict]) -> list[str]:
    """Return human-readable account organizer fallback values for logs."""
    fallbacks: list[str] = []
    for account in accounts:
        label = str(account.get("name", account.get("url", "?")))
        organizer = str(account.get("organizer", "")).strip()
        if not organizer:
            continue
        cal_address = _normalise_calendar_address(organizer)
        fallbacks.append(f"account={label!r} organizer={cal_address!r}")
    return fallbacks


def _make_calendar_getter(all_calendars):
    """Return a callable that looks up a caldav Calendar by display name.

    The returned function performs a case-insensitive match and returns the
    first matching calendar, or ``None`` when no match is found.  It captures
    *all_calendars* by reference so that calendars discovered or added during a
    poll cycle are visible to actions.
    """

    def _get(name: str):
        lowered = name.lower()
        for cal in all_calendars:
            if (cal.name or "").lower() == lowered:
                return cal
        return None

    return _get


def _poll_account(
    account: dict,
    state: _EventState,
    rules: list[Rule],
    owner_email_cache: dict[str, str | None],
) -> list:
    """Poll one CalDAV account and return the list of discovered calendars.

    Returns an empty list when the account cannot be reached so that callers
    can still build a cross-account ``calendar_getter`` from whatever accounts
    did connect successfully.
    """
    label = account.get("name", account.get("url", "?"))
    url = account.get("url", "")
    username = account.get("username", "")
    secret = account.get("password", "")
    watch_patterns = _normalise_watch_entries(account.get("calendars", ["*"]))
    organizer_fallback = str(account.get("organizer", "")).strip()

    # Optional per-account DAVClient knobs — useful for iCloud and other
    # servers that require non-default TLS or authentication settings.
    # iCloud works with the generic base URL (https://caldav.icloud.com/)
    # and lets the library discover the user-specific principal and
    # calendar-home-set via PROPFIND, which is what client.principal() does.
    # Pass ssl_verify_cert, auth_type, or headers in the account config to
    # customise the connection when needed.
    client_kwargs: dict[str, Any] = {}
    if "ssl_verify_cert" in account:
        client_kwargs["ssl_verify_cert"] = account["ssl_verify_cert"]
    if "auth_type" in account:
        client_kwargs["auth_type"] = account["auth_type"]
    if "headers" in account:
        client_kwargs["headers"] = account["headers"]

    logger.debug("Polling account %r", label)

    try:
        client = caldav.DAVClient(
            url=url, username=username, password=secret, **client_kwargs
        )
        principal = client.principal()
        all_calendars = principal.calendars()
    except Exception:
        logger.exception("Could not connect to account %r (%s)", label, url)
        return []

    cal_names = ", ".join(f'"{c.name or "(unnamed)"}"' for c in all_calendars)
    logger.info("[%s] Available calendars: %s", label, cal_names or "(none)")

    # Build a calendar-lookup callable for the copy-to-calendar action.
    # It covers all calendars on the account, not just the watched ones, so
    # that events can be copied to any calendar regardless of watch patterns.
    calendar_getter = _make_calendar_getter(all_calendars)

    account_key = f"{url}|{username}"
    if account_key in owner_email_cache:
        owner_email = owner_email_cache[account_key]
        logger.debug("[%s] Using cached principal organizer email", label)
    else:
        owner_email = _principal_owner_email(principal)
        if owner_email:
            logger.info(
                "[%s] Principal organizer email detected: %s", label, owner_email
            )
        elif organizer_fallback:
            owner_email = _normalise_calendar_address(organizer_fallback)
            logger.warning(
                "[%s] Could not resolve principal calendar-user-address-set; "
                "falling back to configured organizer %s",
                label,
                owner_email,
            )
        else:
            logger.warning(
                "[%s] Could not resolve principal calendar-user-address-set and no "
                "organizer fallback configured",
                label,
            )
        owner_email_cache[account_key] = owner_email

    scheduling_supported = False

    try:
        if hasattr(client, "supports_scheduling"):
            scheduling_supported = bool(client.supports_scheduling())
        else:
            scheduling_supported = bool(client.check_scheduling_support())
    except Exception:
        logger.exception("[%s] Could not determine scheduling support", label)
    logger.debug("[%s] Scheduling support: %s", label, scheduling_supported)

    watched_count = 0
    for calendar in all_calendars:
        cal_name = calendar.name or ""
        if not _matches_watch_pattern(cal_name, watch_patterns):
            logger.debug(
                "[%s] Skipping calendar %r (not in watch list)", label, cal_name
            )
            continue
        watched_count += 1
        count = _poll_calendar(
            calendar,
            state,
            rules,
            owner_email=owner_email,
            calendar_getter=calendar_getter,
        )
        if count:
            logger.info(
                "[%s] Applied rules to %d event(s) in calendar %r",
                label,
                count,
                cal_name,
            )

    if _has_invite_rules(rules):
        if scheduling_supported:
            inbox_count = _poll_inbox(
                principal, state, rules, label, calendar_getter=calendar_getter
            )
            if inbox_count:
                logger.info(
                    "[%s] Applied invite actions to %d inbox item(s)",
                    label,
                    inbox_count,
                )
        else:
            logger.warning(
                "[%s] Invite rules configured but server has no scheduling support; "
                "skipping inbox processing",
                label,
            )

    logger.debug("Account %r: polled %d calendar(s)", label, watched_count)
    return list(all_calendars)


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------


class Daemon:
    """The main polling daemon."""

    def __init__(self, config: dict) -> None:
        self._config = config
        self._running = True
        self._sigint_count = 0
        state_db_file = config.get("state_db_file")
        state_folder = config.get("state_folder")
        if not state_db_file and state_folder:
            state_db_file = str(Path(state_folder) / "state.db")
        if not state_db_file:
            legacy_state = config.get("state_file", "/data/state.json")
            state_db_file = str(Path(legacy_state).with_suffix(".db"))
        logger.debug("Resolved SQLite state DB path: %s", state_db_file)
        self._state = _EventState(state_db_file)

        signal.signal(signal.SIGTERM, self._handle_stop)
        signal.signal(signal.SIGINT, self._handle_stop)

    def _handle_stop(self, signum: int, *_: Any) -> None:
        if signum == signal.SIGINT:
            self._sigint_count += 1
            if self._sigint_count == 1:
                logger.warning(
                    "Ctrl-C received — stopping after current cycle "
                    "(press Ctrl-C once more to force abort)"
                )
                self._running = False
                return
            logger.error("Second Ctrl-C received — aborting immediately")
            raise SystemExit(130)

        logger.info("SIGTERM received — terminating now for systemd stop")
        raise SystemExit(0)

    def run(self) -> None:
        interval = int(self._config.get("poll_interval", 30))
        rules_dir = self._config.get("rules_dir", "/rules")
        accounts: list[dict] = self._config.get("accounts", [])
        ics_feeds: list[dict] = self._config.get("ics_feeds", [])
        rules: list[Rule] = []
        rules_snapshot: dict[str, tuple[int, int]] = {}
        owner_email_cache: dict[str, str | None] = {}

        logger.info(
            "CalDAV Automata started — %d account(s), %d ICS feed(s), "
            "poll every %ds, rules: %s",
            len(accounts),
            len(ics_feeds),
            interval,
            rules_dir,
        )

        organizer_fallbacks = _configured_organizer_fallbacks(accounts)
        if organizer_fallbacks:
            logger.info(
                "Configured %d account organizer fallback(s)",
                len(organizer_fallbacks),
            )
            for entry in organizer_fallbacks[:20]:
                logger.info("Organizer fallback: %s", entry)
            if len(organizer_fallbacks) > 20:
                logger.info(
                    "Organizer fallback: +%d more",
                    len(organizer_fallbacks) - 20,
                )
        else:
            logger.info("No account organizer fallbacks configured")

        while self._running:
            current_snapshot = _rule_files_snapshot(rules_dir)
            needs_reload = not rules or current_snapshot != rules_snapshot
            if needs_reload:
                if rules_snapshot:
                    changes = _describe_rule_changes(rules_snapshot, current_snapshot)
                    change_msg = ", ".join(changes[:5])
                    if len(changes) > 5:
                        change_msg += f", +{len(changes) - 5} more"
                    if not change_msg:
                        change_msg = "timestamp-only change"
                    logger.warning(
                        "Rule files changed on disk — reloading rules (%s)",
                        change_msg,
                    )

                rules = _load_all_rules(rules_dir)
                rules_snapshot = current_snapshot
                logger.debug("Rules loaded: %d", len(rules))

            # Poll CalDAV accounts and accumulate their calendars so that
            # copy-to-calendar from ICS feed rules can target any account.
            all_caldav_calendars: list = []
            for account in accounts:
                if not self._running:
                    break
                account_cals = _poll_account(
                    account, self._state, rules, owner_email_cache
                )
                all_caldav_calendars.extend(account_cals)

            # Poll ICS feeds using a unified getter that spans all accounts.
            if ics_feeds and self._running:
                shared_getter = _make_calendar_getter(all_caldav_calendars)
                for feed in ics_feeds:
                    if not self._running:
                        break
                    count = _poll_ics_feed(
                        feed, self._state, rules, calendar_getter=shared_getter
                    )
                    if count:
                        logger.info(
                            "Applied rules to %d ICS event(s) from %r",
                            count,
                            feed.get("url", "?"),
                        )

            self._state.save()

            # Sleep in one-second increments so SIGTERM is handled promptly.
            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("CalDAV Automata stopped")
