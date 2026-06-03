# CalDAV Automata

A lightweight CalDAV server with a built-in rule engine.  You drop it into a Docker container, point your calendar app at it, and write small LISP snippets that run whenever events are created or updated — adding attendees, setting reminders, or anything else you need to happen automatically.

Works with Apple Calendar on iOS and macOS, and with any CalDAV-compliant client.

---

## How it works

CalDAV Automata runs two processes in a single container:

1. **Radicale** — a well-established, standards-compliant CalDAV/WebDAV server that stores your calendars on disk.
2. **A FastAPI proxy** — sits in front of Radicale, intercepts `PUT` requests (new and updated events), runs your LISP rules against each event, then forwards the (possibly modified) payload to Radicale.

Everything else — `PROPFIND`, `REPORT`, `MKCALENDAR`, calendar listing, free-busy queries — passes through untouched.  Your calendar app never knows the rule engine is there.

```
Apple Calendar / any CalDAV client
          │  CalDAV (HTTP :5232)
          ▼
  ┌─────────────────────────┐
  │   CalDAV Automata proxy │  ← apply LISP rules on PUT
  └────────────┬────────────┘
               │  HTTP (127.0.0.1:5233)
               ▼
         ┌──────────┐
         │ Radicale │  ← stores calendars on disk
         └──────────┘
```

---

## Quick start

```bash
git clone <repository-url>
cd caldav-automata
docker compose up --build
```

The server starts on port **5232**.  Edit `rules/example.lisp` (mounted read-only into the container) and your changes take effect on the very next event write — no restart needed.

---

## Connect Apple Calendar

### macOS

1. Open **Calendar → Settings → Accounts → Add Account → Other CalDAV account**.
2. Set **Account type** to *Manual*.
3. Fill in:
   | Field | Value |
   |---|---|
   | Username | *(any name, e.g. `me`)* |
   | Password | *(leave blank if auth is disabled)* |
   | Server address | `http://your-server:5232` |
4. Click **Sign In**.  Your calendars appear within a few seconds.

### iOS

1. Go to **Settings → Calendar → Accounts → Add Account → Other → Add CalDAV account**.
2. Enter the same server address, username, and password as above.

> **Tip:** Radicale auto-creates a personal calendar collection the first time you connect.  You can also create additional calendars directly from the Calendar app, or with any WebDAV client.

---

## Writing rules

Rules live in `rules/` and use a small LISP dialect.  Files are re-read on every event write, so you can iterate without restarting the container.

### Rule shape

```lisp
(rule
  (when
    (calendar "Calendar Name"))   ; which calendar(s) to match
  (on-create                      ; runs when a new event is saved
    <action> ...)
  (on-update                      ; runs when an existing event is saved
    <action> ...))
```

`(when ...)` accepts multiple `(calendar ...)` clauses — they are OR-ed together.  Use `"*"` to match every calendar.

### Available actions

#### `add-attendee`

```lisp
(add-attendee "email@example.com" "Full Name")
```

Adds the person as a `NEEDS-ACTION / REQ-PARTICIPANT` attendee.  Safe to use in `on-update` — the attendee is never added twice.

#### `set-alert`

```lisp
(set-alert <minutes> "DISPLAY"|"EMAIL" "Optional description")
```

Attaches a `VALARM` component to the event.  If an alarm of the same type already exists it is replaced, so the rule stays idempotent across edits.

`<minutes>` is how many minutes *before* the event start to trigger the alarm.

### Examples

```lisp
; 15-minute reminder on every new event, in every calendar
(rule
  (when
    (calendar "*"))
  (on-create
    (set-alert 15 "DISPLAY" "Reminder")))


; Invite the whole family to "Family" calendar events
(rule
  (when
    (calendar "Family"))
  (on-create
    (add-attendee "partner@example.com" "Partner")
    (add-attendee "child@example.com" "Child")
    (set-alert 60 "DISPLAY" "Family event coming up")))


; 30-minute work reminder, and keep attendees topped up on edits
(rule
  (when
    (calendar "Work"))
  (on-create
    (set-alert 30 "DISPLAY" "Work reminder"))
  (on-update
    (add-attendee "manager@example.com" "Manager")))
```

Comments start with `;` and run to the end of the line.

---

## Configuration

### Authentication

By default Radicale runs with no authentication.  To enable password protection:

1. Generate an `htpasswd` file:

   ```bash
   # Using htpasswd (from Apache httpd-tools)
   htpasswd -B config/htpasswd myusername

   # Or with Python only
   python3 -c "
   import bcrypt, getpass, sys
   user = input('Username: ')
   pw   = getpass.getpass()
   print(user + ':' + bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode())
   " >> config/htpasswd
   ```

2. Edit `config/radicale.cfg`:

   ```ini
   [auth]
   type                = htpasswd
   htpasswd_filename   = /etc/radicale/htpasswd
   htpasswd_encryption = bcrypt
   ```

3. Mount the file in `docker-compose.yml`:

   ```yaml
   volumes:
     - ./config/htpasswd:/etc/radicale/htpasswd:ro
   ```

4. Restart the container.

> `config/htpasswd` is excluded from version control via `.gitignore`.  Never commit credential files.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `PROXY_PORT` | `5232` | Port the CalDAV proxy listens on |
| `LOG_LEVEL` | `info` | Logging verbosity (`debug`, `info`, `warning`, `error`) |
| `RULES_DIR` | `/rules` | Directory scanned (recursively) for `*.lisp` rule files |
| `RADICALE_URL` | `http://127.0.0.1:5233` | Internal Radicale base URL |

### Persistent storage

Calendar data is stored in the `caldav-data` Docker volume (mapped to `/data/collections` inside the container).  Back it up like any ordinary directory.

---

## Development

```bash
# Install dependencies into a virtual environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run Radicale separately (adjust the config path as needed)
radicale --config config/radicale.cfg &

# Run the proxy with live reload
RADICALE_URL=http://127.0.0.1:5233 RULES_DIR=rules \
  uvicorn caldav_automata.main:app --reload --port 5232
```

---

## License

MIT — see [LICENSE](LICENSE).