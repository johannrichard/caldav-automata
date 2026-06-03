FROM python:3.12-slim

LABEL org.opencontainers.image.title="CalDAV Automata" \
      org.opencontainers.image.description="CalDAV proxy with a LISP rule engine" \
      org.opencontainers.image.source="https://github.com/johannrichard/caldav-automata"

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY caldav_automata/ ./caldav_automata/
COPY config/           ./config/
COPY entrypoint.sh     ./entrypoint.sh

# Prepare runtime directories and copy default Radicale config
RUN chmod +x entrypoint.sh \
 && mkdir -p /data/collections /rules /etc/radicale \
 && cp config/radicale.cfg /etc/radicale/config

# Proxy port — CalDAV clients connect here
EXPOSE 5232

VOLUME ["/data", "/rules"]

ENTRYPOINT ["./entrypoint.sh"]
