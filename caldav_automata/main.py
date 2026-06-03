"""
CalDAV Automata — FastAPI entry point.

Runs a transparent HTTP proxy in front of Radicale that intercepts PUT
requests containing iCalendar data, applies LISP-defined rules to every
VEVENT, and forwards the (possibly modified) payload to Radicale.

All other CalDAV / WebDAV methods (PROPFIND, REPORT, MKCALENDAR, …) are
forwarded unchanged.
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import FastAPI, Request, Response

from .proxy import process_ical

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
)
logger = logging.getLogger(__name__)

RADICALE_URL: str = os.environ.get('RADICALE_URL', 'http://127.0.0.1:5233').rstrip('/')

app = FastAPI(title='CalDAV Automata', version='1.0.0')

# CalDAV uses a superset of HTTP verbs.
_CALDAV_METHODS = {
    'GET', 'HEAD', 'OPTIONS',
    'PUT', 'DELETE',
    'PROPFIND', 'PROPPATCH', 'REPORT',
    'MKCALENDAR', 'MKCOL',
}

# Headers that must not be forwarded verbatim.
_HOP_BY_HOP = frozenset({
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade',
})


async def _forward(request: Request, body: bytes) -> Response:
    """Forward *request* with *body* to Radicale and return its response."""
    url = RADICALE_URL + request.url.path
    if request.url.query:
        url += f'?{request.url.query}'

    # Strip hop-by-hop and host headers; recalculate content-length.
    skip = _HOP_BY_HOP | {'host', 'content-length'}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in skip}
    if body:
        headers['content-length'] = str(len(body))

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            follow_redirects=False,
            timeout=30.0,
        )

    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
    )


@app.api_route('/{path:path}', methods=list(_CALDAV_METHODS))
async def handle(request: Request, path: str) -> Response:  # noqa: D401
    """Main request handler — apply rules on PUT, proxy everything else."""
    body = await request.body()

    if request.method == 'PUT':
        content_type = request.headers.get('content-type', '')
        if 'text/calendar' in content_type or path.endswith('.ics'):
            # Detect new vs update: a new resource has no If-Match header.
            is_new = 'if-match' not in request.headers
            try:
                body = process_ical(body, f'/{path}', is_new)
            except Exception:
                logger.exception('Rule processing failed — forwarding original body')

    return await _forward(request, body)
