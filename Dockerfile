FROM python:3.13-slim

LABEL org.opencontainers.image.title="CalDAV Automata" \
      org.opencontainers.image.description="CalDAV polling daemon with a LISP rule engine" \
      org.opencontainers.image.source="https://github.com/johannrichard/caldav-automata"

ARG BUILD_VERSION=dev
ENV APP_VERSION=${BUILD_VERSION}

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY caldav_automata/ ./caldav_automata/

# Runtime directories (overridden by Docker volumes in production)
RUN mkdir -p /data /rules /config

# /data  — persistent state (state.json)
# /rules — LISP rule files (hot-reloaded every cycle)
# /config — calendar.yaml configuration
# VOLUME ["/data", "/rules", "/config"]

CMD ["python", "-m", "caldav_automata.main"]
