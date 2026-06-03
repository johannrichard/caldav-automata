"""
iCalendar mutation actions executed by the rule engine.

Each public function takes a VEVENT component as its first argument and
modifies it in-place.  The ``apply_action`` dispatcher maps the action
name from the parsed Lisp form to the appropriate function.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from icalendar import Alarm, vCalAddress

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attendee_emails(event) -> set[str]:
    """Return the set of lower-case email addresses already on *event*."""
    prop = event.get('attendee')
    if prop is None:
        return set()
    if not isinstance(prop, list):
        prop = [prop]
    return {str(a).lower().removeprefix('mailto:') for a in prop}


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def add_attendee(event, email: str, name: str = '') -> None:
    """
    Add an ATTENDEE to *event* (skipped silently if already present).

    Parameters
    ----------
    event:
        The VEVENT component to modify.
    email:
        E-mail address of the attendee.
    name:
        Optional display name (CN).  Defaults to the e-mail address.
    """
    if email.lower() in _attendee_emails(event):
        logger.debug('Attendee %s already present — skipping', email)
        return

    addr = vCalAddress(f'mailto:{email}')
    addr.params['CN'] = name or email
    addr.params['ROLE'] = 'REQ-PARTICIPANT'
    addr.params['PARTSTAT'] = 'NEEDS-ACTION'
    addr.params['RSVP'] = 'TRUE'
    event.add('attendee', addr, encode=False)
    logger.info('Added attendee %s (%s)', email, name or email)


def set_alert(
    event,
    minutes: int,
    action_type: str = 'DISPLAY',
    description: str = 'Reminder',
) -> None:
    """
    Attach a VALARM to *event*.

    If a VALARM with the same ACTION already exists it is replaced, keeping
    rules idempotent when applied on update.

    Parameters
    ----------
    event:
        The VEVENT component to modify.
    minutes:
        How many minutes *before* the event start to trigger the alarm.
    action_type:
        ``DISPLAY`` (default), ``EMAIL``, or ``AUDIO``.
    description:
        The alarm description / message text.
    """
    action_type = action_type.upper()

    # Remove any existing alarm of the same type so we don't accumulate duplicates.
    event.subcomponents = [
        c for c in event.subcomponents
        if not (
            isinstance(c, Alarm)
            and str(c.get('ACTION', '')).upper() == action_type
        )
    ]

    alarm = Alarm()
    alarm.add('ACTION', action_type)
    alarm.add('TRIGGER', timedelta(minutes=-abs(minutes)))
    alarm.add('DESCRIPTION', description)
    event.add_component(alarm)
    logger.info('Set %s alert at -%d min ("%s")', action_type, minutes, description)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def apply_action(event, action: list) -> None:
    """
    Dispatch a parsed Lisp action form to the matching handler.

    Unknown action names are logged and ignored so that a single bad
    rule does not prevent other rules from running.
    """
    if not isinstance(action, list) or not action:
        return

    name = str(action[0])
    args = action[1:]

    if name == 'add-attendee':
        if not args:
            logger.warning('add-attendee: at least one argument required')
            return
        email = str(args[0])
        display_name = str(args[1]) if len(args) > 1 else ''
        add_attendee(event, email, display_name)

    elif name == 'set-alert':
        if not args:
            logger.warning('set-alert: at least one argument required')
            return
        try:
            minutes = int(args[0])
        except (TypeError, ValueError):
            logger.warning('set-alert: invalid minutes value %r', args[0])
            return
        alert_action = str(args[1]).upper() if len(args) > 1 else 'DISPLAY'
        desc = str(args[2]) if len(args) > 2 else 'Reminder'
        set_alert(event, minutes, alert_action, desc)

    else:
        logger.warning('Unknown action %r — ignoring', name)
