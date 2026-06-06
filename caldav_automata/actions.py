"""
iCalendar mutation actions executed by the rule engine.

Event actions take a VEVENT component and modify it in-place. Inbox actions
operate on scheduling inbox items. The ``apply_action`` dispatcher maps the
action name from the parsed Lisp form to the appropriate function.
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
    prop = event.get("attendee")
    if prop is None:
        return set()
    if not isinstance(prop, list):
        prop = [prop]
    return {_normalise_email(str(a)) for a in prop}


def _normalise_email(value: str) -> str:
    """Normalise e-mail URI/addresses for case-insensitive comparison."""
    return str(value).strip().lower().removeprefix("mailto:")


def _sent_by_email(value) -> str | None:
    """Return normalised SENT-BY value from an iCal property, if present."""
    sent_by = getattr(value, "params", {}).get("SENT-BY")
    if not sent_by:
        return None
    return _normalise_email(str(sent_by))


def _sender_emails(event) -> set[str]:
    """Return sender addresses from organizer and SENT-BY metadata."""
    senders: set[str] = set()

    organizer = event.get("organizer")
    if organizer is not None:
        senders.add(_normalise_email(str(organizer)))
        sent_by = _sent_by_email(organizer)
        if sent_by:
            senders.add(sent_by)

    attendees = event.get("attendee")
    if attendees is not None:
        if not isinstance(attendees, list):
            attendees = [attendees]
        for attendee in attendees:
            sent_by = _sent_by_email(attendee)
            if sent_by:
                senders.add(sent_by)

    return senders


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def _to_ical_bool(value: str | bool) -> str:
    """Convert bool-ish input to iCalendar TRUE/FALSE string."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    lowered = str(value).strip().lower()
    if lowered in {"true", "yes", "1"}:
        return "TRUE"
    if lowered in {"false", "no", "0"}:
        return "FALSE"
    return str(value).upper()


def add_attendee(
    event,
    email: str,
    name: str = "",
    role: str = "REQ-PARTICIPANT",
    partstat: str = "NEEDS-ACTION",
    rsvp: str | bool = "TRUE",
    schedule_agent: str = "SERVER",
) -> bool:
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
    normalised_email = _normalise_email(email)

    if normalised_email in _attendee_emails(event):
        logger.debug("Attendee %s already present — skipping", email)
        return False

    if normalised_email in _sender_emails(event):
        logger.debug(
            "Attendee %s matches event sender/organizer metadata — skipping",
            email,
        )
        return False

    addr = vCalAddress(f"mailto:{email}")
    addr.params["CN"] = name or email
    addr.params["ROLE"] = role.upper()
    addr.params["PARTSTAT"] = partstat.upper()
    addr.params["RSVP"] = _to_ical_bool(rsvp)
    if schedule_agent:
        addr.params["SCHEDULE-AGENT"] = str(schedule_agent).upper()
    event.add("attendee", addr, encode=False)
    logger.info("Added attendee %s (%s)", email, name or email)
    return True


def set_alert(
    event,
    minutes: int,
    action_type: str = "DISPLAY",
    description: str = "Reminder",
) -> bool:
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
        c
        for c in event.subcomponents
        if not (
            isinstance(c, Alarm) and str(c.get("ACTION", "")).upper() == action_type
        )
    ]

    alarm = Alarm()
    alarm.add("ACTION", action_type)
    alarm.add("TRIGGER", timedelta(minutes=-abs(minutes)))
    alarm.add("DESCRIPTION", description)
    event.add_component(alarm)
    logger.info('Set %s alert at -%d min ("%s")', action_type, minutes, description)
    return True


def accept_invite(_event, inbox_item=None) -> bool:
    """Accept an invite from a scheduling inbox item."""
    if inbox_item is None:
        logger.warning("accept-invite: action requires inbox context")
        return False
    inbox_item.accept_invite()
    logger.info("Accepted invite from inbox item %s", getattr(inbox_item, "url", "?"))
    return True


def decline_invite(_event, inbox_item=None) -> bool:
    """Decline an invite from a scheduling inbox item."""
    if inbox_item is None:
        logger.warning("decline-invite: action requires inbox context")
        return False
    inbox_item.decline_invite()
    logger.info("Declined invite from inbox item %s", getattr(inbox_item, "url", "?"))
    return True


def tentative_invite(_event, inbox_item=None) -> bool:
    """Tentatively accept an invite from a scheduling inbox item."""
    if inbox_item is None:
        logger.warning("tentative-invite: action requires inbox context")
        return False
    inbox_item.tentatively_accept_invite()
    logger.info(
        "Tentatively accepted invite from inbox item %s",
        getattr(inbox_item, "url", "?"),
    )
    return True


def delete_inbox_item(_event, inbox_item=None) -> bool:
    """Delete a scheduling inbox item after processing."""
    if inbox_item is None:
        logger.warning("delete-inbox-item: action requires inbox context")
        return False
    inbox_item.delete()
    logger.info("Deleted inbox item %s", getattr(inbox_item, "url", "?"))
    return True


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def apply_action(event, action: list, inbox_item=None) -> bool:
    """
    Dispatch a parsed Lisp action form to the matching handler.

    Unknown action names are logged and ignored so that a single bad
    rule does not prevent other rules from running.
    """
    if not isinstance(action, list) or not action:
        return False

    name = str(action[0])
    args = action[1:]

    if name == "add-attendee":
        if event is None:
            logger.warning("add-attendee: action requires VEVENT context")
            return False
        if not args:
            logger.warning("add-attendee: at least one argument required")
            return False
        email = str(args[0])
        option_keys = {"role", "partstat", "rsvp", "schedule-agent", "schedule_agent"}
        display_name = ""
        options_start = 1
        if len(args) > 1 and str(args[1]).lower() not in option_keys:
            display_name = str(args[1])
            options_start = 2

        options = {}
        extra = args[options_start:]
        if extra:
            if len(extra) % 2 != 0:
                logger.warning(
                    "add-attendee: options must be key/value pairs, got %r",
                    extra,
                )
                return False
            for i in range(0, len(extra), 2):
                key = str(extra[i]).lower()
                value = extra[i + 1]
                if key not in option_keys:
                    logger.warning("add-attendee: unknown option %r", key)
                    return False
                canonical = (
                    "schedule_agent"
                    if key in {"schedule-agent", "schedule_agent"}
                    else key
                )
                options[canonical] = value

        return add_attendee(event, email, display_name, **options)

    elif name == "set-alert":
        if event is None:
            logger.warning("set-alert: action requires VEVENT context")
            return False
        if not args:
            logger.warning("set-alert: at least one argument required")
            return False
        try:
            minutes = int(args[0])
        except (TypeError, ValueError):
            logger.warning("set-alert: invalid minutes value %r", args[0])
            return False
        alert_action = str(args[1]).upper() if len(args) > 1 else "DISPLAY"
        desc = str(args[2]) if len(args) > 2 else "Reminder"
        return set_alert(event, minutes, alert_action, desc)

    elif name == "accept-invite":
        return accept_invite(event, inbox_item=inbox_item)

    elif name == "decline-invite":
        return decline_invite(event, inbox_item=inbox_item)

    elif name == "tentative-invite":
        return tentative_invite(event, inbox_item=inbox_item)

    elif name == "delete-inbox-item":
        return delete_inbox_item(event, inbox_item=inbox_item)

    else:
        logger.warning("Unknown action %r — ignoring", name)
        return False
