"""
CalDAV Automata — polling daemon.

Watches one or more CalDAV accounts and their calendars.  On every poll
cycle it fetches all events, compares their ETags against a persistent
state file, and — for events that are new or changed — applies the
matching LISP rules before writing the modified event back to the server.

Change detection
----------------
CalDAV servers attach an ETag to every resource.  The daemon stores the
most-recently-seen ETag for each event URL in a JSON state file so it
survives restarts.  The decision tree per event is:

    URL not in state  ->  on-create rules, write back, store new ETag
    ETag changed      ->  on-update rules, write back, store new ETag
    ETag unchanged    ->  skip

After a successful write-back the server issues a fresh ETag; the daemon
reads it from the response and stores it so the next poll is a no-op.

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
import json
import logging
import os
import signal
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import caldav
from icalendar import Calendar

from .actions import apply_action
from .lisp import Rule, load_rules

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ETag state  (persisted to disk)
# ---------------------------------------------------------------------------

class _EventState:
    """Persistent mapping of event URL -> last-seen ETag."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding='utf-8'))
                logger.debug(
                    'State loaded: %d known event(s) from %s',
                    len(self._data), self._path,
                )
            except Exception:
                logger.exception('Could not read state file %s — starting fresh', self._path)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2), encoding='utf-8')

    def get_etag(self, url: str) -> str | None:
        return self._data.get(url)

    def set_etag(self, url: str, etag: str) -> None:
        self._data[url] = etag

    def is_known(self, url: str) -> bool:
        return url in self._data


# ---------------------------------------------------------------------------
# Rule loading  (re-read every cycle for live hot-reload)
# ---------------------------------------------------------------------------

def _load_all_rules(rules_dir: str) -> list[Rule]:
    rules: list[Rule] = []
    pattern = os.path.join(rules_dir, '**', '*.lisp')
    for path in sorted(glob_module.glob(pattern, recursive=True)):
        if path.endswith('.example.lisp'):
            continue
        try:
            loaded = load_rules(path)
            rules.extend(loaded)
        except Exception:
            logger.exception('Failed to load rules from %s', path)
    return rules


def _resolve_date_spec(spec: str) -> date:
    if spec.lower() == 'today':
        return datetime.now().astimezone().date()
    return date.fromisoformat(spec)


def _event_start_date(component) -> date | None:
    value = component.get('DTSTART')
    if value is None:
        return None

    start = getattr(value, 'dt', value)
    if isinstance(start, datetime):
        return start.astimezone().date() if start.tzinfo else start.date()
    if isinstance(start, date):
        return start
    return None


def _matches_date_specs(event_date: date | None, specs: list[str], operator: str) -> bool:
    if not specs:
        return True
    if event_date is None:
        return False

    for spec in specs:
        target = _resolve_date_spec(spec)
        if operator == 'on' and event_date == target:
            return True
        if operator == 'before' and event_date < target:
            return True
        if operator == 'after' and event_date > target:
            return True
    return False


def _matches(
    rule: Rule,
    calendar_name: str,
    subject: str = '',
    note: str = '',
    start_date: date | None = None,
) -> bool:
    if rule.calendars and not any(
        pat == '*' or fnmatch.fnmatch(calendar_name.lower(), pat.lower())
        for pat in rule.calendars
    ):
        return False
    if rule.subjects and not any(
        fnmatch.fnmatch(subject.lower(), pat.lower())
        for pat in rule.subjects
    ):
        return False
    if rule.notes and not any(
        fnmatch.fnmatch(note.lower(), pat.lower())
        for pat in rule.notes
    ):
        return False
    if not _matches_date_specs(start_date, rule.date_on, 'on'):
        return False
    if not _matches_date_specs(start_date, rule.date_before, 'before'):
        return False
    if not _matches_date_specs(start_date, rule.date_after, 'after'):
        return False
    return True


def _debug_log_event_title(calendar_name: str, verb: str, uid: str, raw_ical: str) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return

    try:
        cal = Calendar.from_ical(raw_ical)
    except Exception:
        logger.debug('[%s] Could not parse event title for %s event %s', calendar_name, verb, uid)
        return

    for component in cal.walk():
        if component.name != 'VEVENT':
            continue
        title = str(component.get('SUMMARY', ''))
        if title:
            logger.debug('[%s] %s event title: %s', calendar_name, verb, title)
        else:
            logger.debug('[%s] %s event %s has no title', calendar_name, verb, uid)
        return


# ---------------------------------------------------------------------------
# iCalendar mutation
# ---------------------------------------------------------------------------

def _apply_rules(
    raw_ical: str,
    calendar_name: str,
    is_new: bool,
    rules: list[Rule],
) -> str | None:
    """
    Apply matching rules to *raw_ical*.

    Returns the modified iCal string when at least one action ran, or
    ``None`` when the event should be left unchanged.
    """
    try:
        cal = Calendar.from_ical(raw_ical)
    except Exception:
        logger.exception('Could not parse iCal payload — skipping event')
        return None

    changed = False
    for component in cal.walk():
        if component.name != 'VEVENT':
            continue
        subject = str(component.get('SUMMARY', ''))
        note = str(component.get('DESCRIPTION', ''))
        start_date = _event_start_date(component)
        for rule in rules:
            if not _matches(rule, calendar_name, subject, note, start_date):
                continue
            actions = rule.on_create if is_new else rule.on_update
            for action in actions:
                try:
                    apply_action(component, action)
                    changed = True
                except Exception:
                    logger.exception('Error applying action %r', action)

    if not changed:
        return None

    try:
        return cal.to_ical().decode('utf-8')
    except Exception:
        logger.exception('Could not serialise modified iCal — skipping write-back')
        return None


# ---------------------------------------------------------------------------
# Per-calendar polling
# ---------------------------------------------------------------------------

def _normalise_etag(etag: str | None) -> str:
    """Strip surrounding quotes that some servers add to ETags."""
    if etag is None:
        return ''
    return etag.strip('"')


def _poll_calendar(
    calendar: caldav.Calendar,
    state: _EventState,
    rules: list[Rule],
) -> int:
    """
    Fetch all events in *calendar*, apply rules to new/changed ones, and
    write modifications back.

    Returns the number of events that were modified and saved.
    """
    cal_name = calendar.name or str(calendar.url)
    saved = 0

    try:
        events = calendar.events()
    except Exception:
        logger.exception('Could not fetch events from calendar %r', cal_name)
        return 0

    for event in events:
        url = str(event.url)
        etag = _normalise_etag(getattr(event, 'etag', None))

        is_new = not state.is_known(url)
        is_changed = not is_new and state.get_etag(url) != etag

        if not is_new and not is_changed:
            continue

        verb = 'new' if is_new else 'updated'
        uid = url.rstrip('/').split('/')[-1]
        logger.info('[%s] %s event detected: %s', cal_name, verb, uid)
        _debug_log_event_title(cal_name, verb, uid, event.data)

        modified_ical = _apply_rules(event.data, cal_name, is_new, rules)

        if modified_ical is not None:
            try:
                event.data = modified_ical
                event.save()
                new_etag = _normalise_etag(getattr(event, 'etag', None))
                state.set_etag(url, new_etag or etag)
                logger.info('[%s] Wrote back modified event: %s', cal_name, uid)
                saved += 1
            except Exception:
                logger.exception('Failed to save event %s in calendar %r', uid, cal_name)
                # Record the original ETag so we do not loop on failure.
                state.set_etag(url, etag)
        else:
            # Rules matched nothing — just record that we have seen this ETag.
            state.set_etag(url, etag)

    return saved


# ---------------------------------------------------------------------------
# Per-account polling
# ---------------------------------------------------------------------------

def _should_watch(name: str, patterns: list[str]) -> bool:
    return any(
        pat == '*' or fnmatch.fnmatch(name.lower(), pat.lower())
        for pat in patterns
    )


def _poll_account(account: dict, state: _EventState, rules: list[Rule]) -> None:
    label = account.get('name', account.get('url', '?'))
    url = account.get('url', '')
    username = account.get('username', '')
    secret = account.get('password', '')
    watched = account.get('calendars', ['*'])

    # Optional per-account DAVClient knobs — useful for iCloud and other
    # servers that require non-default TLS or authentication settings.
    # iCloud works with the generic base URL (https://caldav.icloud.com/)
    # and lets the library discover the user-specific principal and
    # calendar-home-set via PROPFIND, which is what client.principal() does.
    # Pass ssl_verify_cert, auth_type, or headers in the account config to
    # customise the connection when needed.
    client_kwargs: dict[str, Any] = {}
    if 'ssl_verify_cert' in account:
        client_kwargs['ssl_verify_cert'] = account['ssl_verify_cert']
    if 'auth_type' in account:
        client_kwargs['auth_type'] = account['auth_type']
    if 'headers' in account:
        client_kwargs['headers'] = account['headers']

    logger.debug('Polling account %r', label)

    try:
        client = caldav.DAVClient(
            url=url, username=username, password=secret, **client_kwargs
        )
        principal = client.principal()
        all_calendars = principal.calendars()
    except Exception:
        logger.exception('Could not connect to account %r (%s)', label, url)
        return

    watched_count = 0
    for calendar in all_calendars:
        cal_name = calendar.name or ''
        if not _should_watch(cal_name, watched):
            logger.debug('[%s] Skipping calendar %r (not in watch list)', label, cal_name)
            continue
        watched_count += 1
        count = _poll_calendar(calendar, state, rules)
        if count:
            logger.info(
                '[%s] Applied rules to %d event(s) in calendar %r',
                label, count, cal_name,
            )

    logger.debug('Account %r: polled %d calendar(s)', label, watched_count)


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------

class Daemon:
    """The main polling daemon."""

    def __init__(self, config: dict) -> None:
        self._config = config
        self._running = True
        self._state = _EventState(config.get('state_file', '/data/state.json'))

        signal.signal(signal.SIGTERM, self._handle_stop)
        signal.signal(signal.SIGINT, self._handle_stop)

    def _handle_stop(self, *_: Any) -> None:
        logger.info('Shutdown signal received — stopping after current cycle')
        self._running = False

    def run(self) -> None:
        interval = int(self._config.get('poll_interval', 30))
        rules_dir = self._config.get('rules_dir', '/rules')
        accounts: list[dict] = self._config.get('accounts', [])

        logger.info(
            'CalDAV Automata started — %d account(s), poll every %ds, rules: %s',
            len(accounts), interval, rules_dir,
        )

        while self._running:
            rules = _load_all_rules(rules_dir)
            logger.debug('Rules loaded: %d', len(rules))

            for account in accounts:
                if not self._running:
                    break
                _poll_account(account, self._state, rules)

            self._state.save()

            # Sleep in one-second increments so SIGTERM is handled promptly.
            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info('CalDAV Automata stopped')
