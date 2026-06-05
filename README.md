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
│   Family calendar  ──┐                │
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

The recommended approach is to mount your password as a Docker secret file
instead of passing it through the container environment:

```sh
mkdir -p secrets
printf '%s' 'your-app-specific-password-here' > secrets/icloud_password.txt
chmod 600 secrets/icloud_password.txt
```

> `./secrets/` is listed in `.gitignore` and will never be committed.

If you prefer environment variables, the old `.env` flow still works:

```sh
cp .env.example .env
chmod 600 .env
```

```sh
ICLOUD_PASSWORD=your-app-specific-password-here
```

> `.env` is listed in `.gitignore` and will never be committed.

### 3 — Configure your calendars

Copy the template and edit your real config file:

```sh
cp config/calendar.example.yaml config/calendar.yaml
```

Then edit `config/calendar.yaml` with your iCloud address and the calendar
names you want to watch:

```yaml
# config/calendar.yaml
poll_interval: 30          # seconds between poll cycles
rules_dir: /rules          # path inside the container
state_file: /data/state.json

accounts:
  - name: "iCloud"
    url: "https://caldav.icloud.com/"
    username: "you@icloud.com"
    password_file: "/run/secrets/icloud_password"
    calendars:
      - "Family"
      - "Work"
```

If you prefer environment variables instead of a mounted secret file:

```yaml
accounts:
  - name: "iCloud"
    url: "https://caldav.icloud.com/"
    username: "you@icloud.com"
    password: "${ICLOUD_PASSWORD}"   # resolved from .env at runtime
    calendars:
      - "Family"
      - "Work"
```

**iCloud URL discovery** — Use the generic base URL `https://caldav.icloud.com/`
as-is. The CalDAV library automatically discovers your user-specific
principal and calendar-home-set via `PROPFIND`, so you never need to
hard-code a personal path. iCloud always requires Basic authentication with
an App-Specific Password (see step 1).

Calendar names support `fnmatch` wildcards. Use `["*"]` to watch every
calendar on an account.

### 4 — Write your first rule

Copy the rules template, then create your real `.lisp` rule files:

```sh
cp rules/example.lisp.example rules/my-rules.lisp
```

Only `*.lisp` files are loaded at runtime; `*.example.lisp` files are ignored.
Create additional `.lisp` files anywhere inside `./rules/`:

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

The shipped `docker-compose.yml` mounts `./secrets/icloud_password.txt` as the
Docker secret `/run/secrets/icloud_password`, which matches the
`password_file` example above. To build the image locally instead of pulling
from GHCR, swap the `image:` line in `docker-compose.yml` for the commented-out
`build: .` line.

For additional accounts, add more entries under `secrets:` in
`docker-compose.yml` and point each account's `password_file` at the matching
`/run/secrets/...` path.

### 5a — Docker Compose secret example

```yaml
services:
  caldav-automata:
    image: ghcr.io/johannrichard/caldav-automata:latest
    secrets:
      - icloud_password
    volumes:
      - caldav-state:/data
      - ./rules:/rules:ro
      - ./config:/config:ro

secrets:
  icloud_password:
    file: ./secrets/icloud_password.txt
```

### 5b — Secret injection options

- **Best default**: mount a secret file from Docker Compose, Docker Swarm,
  Kubernetes, ECS, or another orchestrator and use `password_file`.
- **Good with Proton Pass / `pass-cli`**: fetch the secret on the **host**
  before `docker compose up`, write it into `./secrets/icloud_password.txt`,
  then let Docker mount that file into the container.
- **Not recommended**: run `pass-cli`, a desktop keychain helper, or similar
  secret tooling *inside* the application container. That couples the image to a
  specific secret provider, adds extra credentials or device state into the
  container, and makes unattended restarts harder.
- **If you need dynamic retrieval**: use a small sidecar or entrypoint wrapper
  that writes a file into a mounted secret volume, then point `password_file`
  at that file. Keep the main app unaware of the secret provider.

### 6 — Pick a pinned image version in production

Published images are semantically versioned (`X.Y.Z`) and pushed with matching
floating tags (`X.Y`, `X`, and `latest`).

For production, pin `docker-compose.yml` to an explicit release tag:

```yaml
image: ghcr.io/johannrichard/caldav-automata:1.2.3
```

> Note: GHCR retention keeps only the 5 most recent releases, so older pinned
> tags are eventually pruned.

---

## Docker image publishing and retention

- Release tags are created automatically on `main` by
  `.github/workflows/release.yml` using `python-semantic-release`.
- Docker images are published from `.github/workflows/docker-publish.yml`
  directly from the semantic release workflow, and only when semantic-release
  actually creates a new release.
- Docker tags are derived by `docker/metadata-action` semver rules
  (`X.Y.Z`, `X.Y`, `X`, and `latest`) without custom bash parsing.
- Each published image also gets a GitHub artifact attestation pushed to GHCR.
- After each publish, GHCR housekeeping prunes old releases and keeps only the
  latest 5 image versions for this package.

## Rule language

Rules are written in a simple S-expression dialect (LISP). Each rule
specifies which events/inbox items it applies to and what actions to run
when an event is created or updated, or when scheduling inbox messages arrive.

### Structure

```lisp
(rule
  (when
    (calendar "<name>")  ; one or more (calendar ...) clauses = OR match
    (calendar "<name>")) ; omit the (when ...) block entirely to match all

  (on-create             ; actions that run when a new event appears
    <action> …)

  (on-update             ; actions that run when an existing event changes
    <action> …)

  (on-invite-request     ; actions for inbox METHOD:REQUEST items
    <action> …)

  (on-invite-reply       ; actions for inbox METHOD:REPLY items
    <action> …))
```

The `when` block can also filter on the event **subject** (SUMMARY), **note**
(DESCRIPTION), and **start date** (`DTSTART`). Subject and note filters use
`fnmatch` patterns, where `*` matches any sequence of characters:

```lisp
(rule
  (when
    (calendar "Work")       ; must be in the Work calendar
    (subject "*standup*")   ; AND SUMMARY must contain "standup"
    (note "*action item*")) ; AND DESCRIPTION must contain "action item"
  …)
```

Date filters compare by calendar day. They accept either an ISO date like
`"2026-05-21"` or the relative value `"today"`:

```lisp
(rule
  (when
    (date-on "today"))
  …)

(rule
  (when
    (date-after "2026-05-21")
    (date-before "2026-06-01"))
  …)
```

Multiple values within the same condition type are OR'd; different condition
types are AND'd. A condition type that is omitted matches everything.

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

; Matches events that start within a fixed date window.
(rule
  (when
    (date-after "2026-05-21")
    (date-before "2026-06-01"))
  …)
```

### Actions

| Action | Description |
|---|---|
| `(add-attendee "email@example.com")` | Add an attendee to the event (idempotent, defaults `SCHEDULE-AGENT` to `SERVER`) |
| `(add-attendee "email@example.com" "Name" role "OPT-PARTICIPANT" partstat "NEEDS-ACTION" rsvp "TRUE" schedule-agent "SERVER")` | Add attendee with optional attendee/scheduling parameters |
| `(set-alert <minutes> "<type>")` | Add or replace an alert. Type is `DISPLAY`, `EMAIL`, or `AUDIO` |
| `(accept-invite)` | Accept inbox invite request (`METHOD:REQUEST`) |
| `(decline-invite)` | Decline inbox invite request (`METHOD:REQUEST`) |
| `(tentative-invite)` | Tentatively accept inbox invite request (`METHOD:REQUEST`) |
| `(delete-inbox-item)` | Delete current inbox item after processing |

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

; Add a reminder only for events after a cutoff date.
(rule
  (when
    (calendar "Work")
    (date-after "2026-05-21"))
  (on-create
    (set-alert 30 "DISPLAY")))

; Auto-accept specific invites from scheduling inbox and clean them up.
(rule
  (when
    (subject "*standup*"))
  (on-invite-request
    (accept-invite)
    (delete-inbox-item)))

; Remove organizer reply notifications from inbox.
(rule
  (on-invite-reply
    (delete-inbox-item)))
```

### Debug logging

Set `LOG_LEVEL=DEBUG` to see extra trace output, including the title of each
new or updated event as it is processed.

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
| `ssl_verify_cert` | *(optional)* `true` (default) or `false` to skip TLS verification for self-signed certs |
| `auth_type` | *(optional)* HTTP authentication type, e.g. `"basic"` (iCloud default) or `"digest"` |
| `headers` | *(optional)* Map of extra HTTP headers to send with every request |

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
| `CONFIG_FILE` | `/config/calendar.yaml` | Path to the configuration file |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, …) |
| Any `${VAR}` used in the config | — | Expanded at load time from the container environment |

---

## Compatible CalDAV servers

- **Apple iCloud** — uses App-Specific Passwords; principal discovery is
  handled automatically. Scheduling/invite inbox rules run only when
  scheduling support is detected for the account.
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
  calendar.example.yaml   example configuration template (not loaded)
rules/
  example.lisp.example    starter rule template (not loaded)
Dockerfile        single-process container image
docker-compose.yml  example Compose deployment
```

---

## Licence

MIT — see [LICENSE](LICENSE).
