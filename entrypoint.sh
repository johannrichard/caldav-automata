#!/bin/sh
# CalDAV Automata entrypoint
# Starts Radicale (CalDAV backend) then the FastAPI rule-engine proxy.

set -e

RADICALE_PID=
UVICORN_PID=

stop() {
    echo '[entrypoint] Shutting down...'
    [ -n "$UVICORN_PID"  ] && kill "$UVICORN_PID"  2>/dev/null || true
    [ -n "$RADICALE_PID" ] && kill "$RADICALE_PID" 2>/dev/null || true
}
trap stop TERM INT

# ---- Start Radicale (internal CalDAV backend on 127.0.0.1:5233) ----
radicale --config /etc/radicale/config &
RADICALE_PID=$!
echo "[entrypoint] Radicale started (PID=$RADICALE_PID)"

# ---- Wait until Radicale is accepting connections ----
python3 - <<'PY'
import sys, time, urllib.request, urllib.error

url = "http://127.0.0.1:5233/.well-known/caldav"
for i in range(30):
    try:
        urllib.request.urlopen(url, timeout=2)
        break                   # 200 OK (no-auth mode)
    except urllib.error.HTTPError:
        break                   # any HTTP response means Radicale is up
    except Exception:
        time.sleep(1)
else:
    print("[entrypoint] WARNING: Radicale did not respond in 30 s — proceeding anyway",
          file=sys.stderr)

print("[entrypoint] Radicale is ready")
PY

# ---- Start the rule-engine proxy ----
uvicorn caldav_automata.main:app \
    --host 0.0.0.0 \
    --port  "${PROXY_PORT:-5232}" \
    --log-level "${LOG_LEVEL:-info}" &
UVICORN_PID=$!
echo "[entrypoint] CalDAV Automata proxy started (PID=$UVICORN_PID)"

# ---- Wait for the proxy to exit (restart policy handles recovery) ----
wait "$UVICORN_PID"
