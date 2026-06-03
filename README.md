# CalDAV Automata

A lightweight Docker daemon that watches your CalDAV calendars — including
Apple iCloud — and automatically applies small LISP-defined rules whenever
events are created or updated by *any* client or user.

No proxy required. No server port exposed. Just connect your calendar apps
directly to iCloud (or any CalDAV server) as usual, and let CalDAV Automata
handle the automation in the background.

---

## How it works

CalDAV Automata polls your CalDAV accounts on a configurable interval. For
each calendar event it compares a cryptographic fingerprint (ETag) against a
local state file. When it finds something new or changed it runs your rules,
applies any actions (add attendees, set alerts, …), and writes the modified
event back to the server. The next poll picks up the server-assigned ETag and
the cycle becomes a no-op until the event changes again.

```
┌───────────────────────────────────────┐
│  Apple iCloud / any CalDAV server     │
│                                       │
│   Family calendar ──┐                 │
│   Work calendar    ──┼──► poll (ETag) │
│   …                ──┘                │
└───────────────────────────────────────┘
              │ new / changed?
              ▼
    ┌─────────────────────┐
    │  LISP rules engine  │
    │  rules/*.lisp       │
    └─────────────────────┘
              │ modified iCal
              ▼
    write back to CalDAV server
```

Rules are hot-reloaded from the `/rules` directory on every poll cycle — no
restart required.

---

## Quick start

### 1 — Create an App-Specific Password (iCloud)

If you are connecting to iCloud you must use an
[App-Specific Password](https://support.apple.com/en-gb/HT204397), not your
regular Apple ID password. Create one at
<https://appleid.apple.com/account/manage>.

### 2 — Set up your secrets

Copy the environment template and fill in your credentials:

```sh
cp .env.example .env
chmod 600 .env        # readable only by your user — keep it that way
```

Open `.env` and replace the placeholder with your real password:

```sh
ICLOUD_PASSWORD=your-app-specific-password-here
```

> `.env` is listed in `.gitignore` and will never be committed.

### 3 — Configure your calendars

Edit `config/calendars.yml` with your iCloud address and the calendar names
you want to watch:

```yaml
# config/calendars.yml
poll_interval: 30          # seconds between poll cycles
rules_dir: /rules          # path inside the container
state_file: /data/state.json

accounts:
  - name: "iCloud"
    url: "https://caldav.icloud.com/"
    username: "you@icloud.com"
    password: "${ICLOUD_PASSWORD}"   # resolved from .env at runtime
    calendars:
      - "Family"
      - "Work"
```

Calendar names support `fnmatch` wildcards. Use `["*"]` to watch every
calendar on an account.

### 4 — Write your first rule

Create a `.lisp` file anywhere inside `./rules/`:

```lisp
; rules/family.lisp
(rule
  (when
    (calendar "Family"))

  (on-create
    (add-attendee "partner@example.com")
    (set-alert 15 "DISPLAY"))

  (on-update
    (add-attendee "partner@example.com")))
```

Rules are composable: a single `.lisp` file can contain multiple `rule`
blocks, and any number of files can live in the `rules/` directory.

### 5 — Start the daemon

```sh
docker compose up -d
```

Docker Compose reads `.env` automatically and passes the variables into the
container. To build the image locally instead of pulling from GHCR, swap the
`image:` line in `docker-compose.yml` for the commented-out `build: .` line.

---

## Rule language

Rules are written in a simple S-expression dialect (LISP). Each rule
specifies which calendars it applies to and what actions to run when an
event is created or updated.

### Structure

```lisp
(rule
  (when
    (calendar "<name>")  ; one or more (calendar ...) clauses = OR match
    (calendar "<name>")) ; omit the (when ...) block entirely to match all

  (on-create             ; actions that run when a new event appears
    <action> …)

  (on-update             ; actions that run when an existing event changes
    <action> …))
```

The `when` block can also filter on the event **subject** (SUMMARY) and **note**
(DESCRIPTION) using `fnmatch` patterns, where `*` matches any sequence of
characters:

```lisp
(rule
  (when
    (calendar "Work")       ; must be in the Work calendar
    (subject "*standup*")   ; AND SUMMARY must contain "standup"
    (note "*action item*")) ; AND DESCRIPTION must contain "action item"
  …)
```

Multiple values within the same condition type are OR'd; different condition
types are AND'd.  A condition type that is omitted matches everything.

```lisp
; Matches the Work OR Team calendar, with any subject and any note.
(rule
  (when
    (calendar "Work")
    (calendar "Team"))
  …)

; Matches any calendar whose subject contains "urgent" OR "ASAP".
(rule
  (when
    (subject "*urgent*")
    (subject "*ASAP*"))
  …)
```

### Actions

| Action | Description |
|---|---|
| `(add-attendee "email@example.com")` | Add an attendee to the event (idempotent) |
| `(set-alert <minutes> "<type>")` | Add or replace an alert. Type is `DISPLAY`, `EMAIL`, or `AUDIO` |

### Examples

```lisp
; Invite a colleague to every new Work event and set a 30-minute alert.
(rule
  (when
    (calendar "Work"))
  (on-create
    (add-attendee "colleague@work.com")
    (set-alert 30 "DISPLAY")))

; Notify a family group for any calendar that starts with "Family".
(rule
  (when
    (calendar "Family*"))
  (on-create
    (add-attendee "family-group@example.com")
    (set-alert 10 "DISPLAY"))
  (on-update
    (add-attendee "family-group@example.com")))

; Set a default alert on every new event regardless of calendar.
(rule
  (on-create
    (set-alert 15 "DISPLAY")))
```

---

## Configuration reference

| Key | Default | Description |
|---|---|---|
| `poll_interval` | `30` | Seconds between poll cycles |
| `rules_dir` | `/rules` | Directory scanned for `*.lisp` rule files |
| `state_file` | `/data/state.json` | ETag state persistence file |
| `accounts` | *(required)* | List of CalDAV account objects |

**Account object**

| Key | Description |
|---|---|
| `name` | Display name used in log output |
| `url` | CalDAV base URL (e.g. `https://caldav.icloud.com/`) |
| `username` | Account username / Apple ID |
| `password` | Account password or `${ENV_VAR}` reference |
| `calendars` | List of calendar display-names to watch; supports wildcards; `["*"]` watches all |

---

## Docker volumes

| Volume | Purpose |
|---|---|
| `/data` | Persistent state file (`state.json`) — mount a named volume |
| `/rules` | LISP rule files — mount read-only from your project |
| `/config` | Configuration directory — mount read-only |

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `CONFIG_FILE` | `/config/calendars.yml` | Path to the configuration file |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, …) |
| Any `${VAR}` used in the config | — | Expanded at load time from the container environment |

---

## Compatible CalDAV servers

- **Apple iCloud** — uses App-Specific Passwords; principal discovery is
  handled automatically.
- **Nextcloud** — use the CalDAV URL shown in the *Settings › Personal info*
  section.
- **Baikal**, **Radicale**, **DAViCal**, **Fastmail**, and any other
  CalDAV-compliant server.

---

## Project layout

```
caldav_automata/
  __init__.py     package init
  config.py       YAML config loader with ${ENV_VAR} expansion
  daemon.py       polling daemon — ETag tracking, rule dispatch, write-back
  lisp.py         S-expression parser and rule compiler
  actions.py      add-attendee, set-alert, and other action handlers
  main.py         entry point (python -m caldav_automata.main)
config/
  calendars.yml   example configuration
rules/
  example.lisp    starter rule set
Dockerfile        single-process container image
docker-compose.yml  example Compose deployment
```

---

## Licence

MIT — see [LICENSE](LICENSE).
