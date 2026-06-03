"""
Minimal Lisp / S-expression parser and rule compiler for CalDAV Automata.

Supported rule syntax
---------------------

    (rule
      (when
        (calendar "Name")      ; exact name, or "*" for every calendar
        (calendar "Other")     ; multiple (calendar ...) = OR
        (subject "*meeting*")  ; fnmatch pattern on SUMMARY; multiple = OR
        (note "*urgent*")       ; fnmatch pattern on DESCRIPTION; multiple = OR
        (date-on "2026-05-21")  ; event DTSTART on this day; multiple = OR
        (date-before "today")   ; event DTSTART before this day; multiple = OR
        (date-after "today"))   ; event DTSTART after this day; multiple = OR
      (on-create              ; triggered when a new event is stored
        (add-attendee "email@example.com" "Full Name")
        (set-alert 15 "DISPLAY" "Reminder"))
      (on-update              ; triggered when an existing event is updated
        (add-attendee "email@example.com" "Full Name")))

Within each condition type (calendar, subject, note, date-on, date-before,
date-after) multiple values are OR'd.
Different condition types are AND'd: all non-empty condition groups must match.

Comments start with `;` and run to the end of the line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r'(?P<COMMENT>;[^\n]*)'
    r'|(?P<LPAREN>\()'
    r'|(?P<RPAREN>\))'
    r'|(?P<STRING>"(?:[^"\\]|\\.)*")'
    r'|(?P<NUMBER>-?\d+(?:\.\d+)?)'
    r'|(?P<SYMBOL>[^\s\(\)"]+)'
    r'|(?P<WS>\s+)'
)


def _tokenise(src: str):
    for m in _TOKEN_RE.finditer(src):
        kind = m.lastgroup
        if kind in ('WS', 'COMMENT'):
            continue
        raw = m.group()
        if kind == 'STRING':
            yield ('ATOM', raw[1:-1].replace('\\"', '"'))
        elif kind == 'NUMBER':
            yield ('ATOM', float(raw) if '.' in raw else int(raw))
        elif kind == 'LPAREN':
            yield ('LPAREN', None)
        elif kind == 'RPAREN':
            yield ('RPAREN', None)
        else:  # SYMBOL
            yield ('ATOM', raw)


# ---------------------------------------------------------------------------
# Parser  →  nested Python lists / scalars
# ---------------------------------------------------------------------------

def _parse_expr(tokens: list, pos: int):
    if pos >= len(tokens):
        raise SyntaxError('Unexpected end of input')
    kind, val = tokens[pos]
    if kind == 'ATOM':
        return val, pos + 1
    if kind == 'LPAREN':
        pos += 1
        items = []
        while pos < len(tokens) and tokens[pos][0] != 'RPAREN':
            item, pos = _parse_expr(tokens, pos)
            items.append(item)
        if pos >= len(tokens):
            raise SyntaxError('Missing closing )')
        return items, pos + 1  # consume RPAREN
    raise SyntaxError(f'Unexpected token kind {kind!r}')


def parse(src: str) -> list:
    """Parse *src* as Lisp source; return a list of top-level forms."""
    tokens = list(_tokenise(src))
    forms, pos = [], 0
    while pos < len(tokens):
        form, pos = _parse_expr(tokens, pos)
        forms.append(form)
    return forms


# ---------------------------------------------------------------------------
# Rule model
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    """A compiled rule ready to be matched and executed."""

    calendars: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    date_on: list[str] = field(default_factory=list)
    date_before: list[str] = field(default_factory=list)
    date_after: list[str] = field(default_factory=list)
    on_create: list = field(default_factory=list)
    on_update: list = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f'Rule(calendars={self.calendars!r}, '
            f'subjects={self.subjects!r}, '
            f'notes={self.notes!r}, '
            f'date_on={self.date_on!r}, '
            f'date_before={self.date_before!r}, '
            f'date_after={self.date_after!r}, '
            f'on_create={self.on_create!r}, '
            f'on_update={self.on_update!r})'
        )


# ---------------------------------------------------------------------------
# Compiler  →  Rule objects
# ---------------------------------------------------------------------------

def _parse_date_spec(value) -> str:
    spec = str(value).strip()
    if spec.lower() == 'today':
        return spec
    try:
        date.fromisoformat(spec)
    except ValueError as exc:
        raise SyntaxError(
            f'Unsupported date literal {value!r}; use YYYY-MM-DD or "today"'
        ) from exc
    return spec


def _compile_form(form) -> Rule | None:
    if not isinstance(form, list) or not form or form[0] != 'rule':
        return None
    rule = Rule()
    for clause in form[1:]:
        if not isinstance(clause, list) or not clause:
            continue
        head = clause[0]
        if head == 'when':
            for cond in clause[1:]:
                if not isinstance(cond, list) or len(cond) < 2:
                    continue
                if cond[0] == 'calendar':
                    rule.calendars.append(str(cond[1]))
                elif cond[0] == 'subject':
                    rule.subjects.append(str(cond[1]))
                elif cond[0] == 'note':
                    rule.notes.append(str(cond[1]))
                elif cond[0] == 'date-on':
                    rule.date_on.append(_parse_date_spec(cond[1]))
                elif cond[0] == 'date-before':
                    rule.date_before.append(_parse_date_spec(cond[1]))
                elif cond[0] == 'date-after':
                    rule.date_after.append(_parse_date_spec(cond[1]))
        elif head == 'on-create':
            rule.on_create = [c for c in clause[1:] if isinstance(c, list)]
        elif head == 'on-update':
            rule.on_update = [c for c in clause[1:] if isinstance(c, list)]
    return rule


def compile_rules(forms: list) -> list[Rule]:
    """Compile a list of parsed forms into Rule objects."""
    return [r for form in forms if (r := _compile_form(form)) is not None]


def load_rules(path: str) -> list[Rule]:
    """Load and compile rules from a ``.lisp`` file."""
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    return compile_rules(parse(src))
