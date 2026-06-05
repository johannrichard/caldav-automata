---
name: rule-file-helper
description: >
  Assistant skill for creating and refining CalDAV Automata .lisp rule files.
  Helps users translate natural-language scheduling goals into valid `rule`
  blocks with `when`, event actions, and inbox invite actions.
  Trigger: "create a rule file", "write caldav rules", "help with rules.lisp",
  "generate inbox invite rule", "explain my rule syntax".
---

# Rule File Helper

Use this skill when users want to create or improve `*.lisp` rule files for CalDAV Automata.

## What this skill does

1. Clarifies intent:
   - Which calendars (or inbox) should match.
   - Which filters should apply (`calendar`, `subject`, `note`, `organizer`, date filters).
   - Which trigger blocks are needed (`on-create`, `on-update`, `on-invite-request`, `on-invite-reply`).
2. Produces valid rule blocks in repository syntax.
3. Explains each generated rule briefly in plain language.
4. Flags risky or destructive actions (for example unconditional inbox deletion).

## Output format

- Prefer returning:
  - A short summary.
  - One or more complete `(rule ...)` blocks ready to paste.
  - A brief validation checklist (what to verify in user environment).

## Guardrails

- Keep rules idempotent where possible.
- Do not invent unsupported actions or condition keys.
- If user intent is ambiguous, ask for missing details before generating final rules.
