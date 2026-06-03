"""
Rule-processing layer.

Loads ``.lisp`` rule files from ``RULES_DIR``, matches them against the
target calendar, and applies their actions to every VEVENT in the payload.
"""

from __future__ import annotations

import fnmatch
import glob
import logging
import os

from icalendar import Calendar

from .actions import apply_action
from .lisp import Rule, load_rules

logger = logging.getLogger(__name__)

RULES_DIR: str = os.environ.get('RULES_DIR', '/rules')


# ---------------------------------------------------------------------------
# Rules loading  (re-read on every request for live rule reloads)
# ---------------------------------------------------------------------------

def _load_all_rules() -> list[Rule]:
    rules: list[Rule] = []
    pattern = os.path.join(RULES_DIR, '**', '*.lisp')
    for path in sorted(glob.glob(pattern, recursive=True)):
        try:
            loaded = load_rules(path)
            rules.extend(loaded)
            logger.debug('Loaded %d rule(s) from %s', len(loaded), path)
        except Exception:
            logger.exception('Failed to load rules from %s', path)
    return rules


# ---------------------------------------------------------------------------
# Calendar name extraction
# ---------------------------------------------------------------------------

def _calendar_name(path: str) -> str:
    """
    Derive the calendar collection name from a CalDAV URL path.

    Standard CalDAV layout::

        /<principal>/<calendar-name>/<event>.ics

    The calendar name is the segment immediately before the ``.ics`` file.
    """
    parts = [p for p in path.split('/') if p]
    if len(parts) >= 2 and parts[-1].endswith('.ics'):
        return parts[-2]
    if parts:
        return parts[-1]
    return ''


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------

def _matches(rule: Rule, calendar_name: str) -> bool:
    if not rule.calendars:
        return True  # No calendar filter → match every calendar
    return any(
        pattern == '*' or fnmatch.fnmatch(calendar_name.lower(), pattern.lower())
        for pattern in rule.calendars
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def process_ical(body: bytes, path: str, is_new: bool) -> bytes:
    """
    Parse *body* as iCalendar data, apply all matching rules, and return
    the (possibly modified) iCalendar bytes.

    Returns the original *body* unchanged if parsing fails or no rules are
    defined, so the proxy never drops a valid client request.

    Parameters
    ----------
    body:
        Raw iCalendar payload from the client PUT request.
    path:
        Request path used to derive the calendar collection name.
    is_new:
        ``True`` when the event is being created; ``False`` on update.
    """
    rules = _load_all_rules()
    if not rules:
        return body

    cal_name = _calendar_name(path)
    logger.info(
        'Processing iCal for calendar %r  path=%s  new=%s  rules=%d',
        cal_name, path, is_new, len(rules),
    )

    try:
        cal = Calendar.from_ical(body)
    except Exception:
        logger.exception('Could not parse iCalendar payload — passing through unchanged')
        return body

    for component in cal.walk():
        if component.name != 'VEVENT':
            continue
        for rule in rules:
            if not _matches(rule, cal_name):
                continue
            actions = rule.on_create if is_new else rule.on_update
            for action in actions:
                try:
                    apply_action(component, action)
                except Exception:
                    logger.exception('Error applying action %r', action)

    try:
        return cal.to_ical()
    except Exception:
        logger.exception('Could not serialise modified iCalendar — returning original')
        return body
