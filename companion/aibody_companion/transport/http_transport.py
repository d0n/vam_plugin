"""HTTP transport: a tiny local HTTP server the plugin polls.

Requires "Allow Plugins Network Access" in VaM. Binds to 127.0.0.1 only.

  GET  /v1/health
  GET  /v1/commands?channel=<c>&after=<seq>  -> {"commands": [...], "last": <seq>}
  POST /v1/events?channel=<c>                 body: one event object or an array
"""
from __future__ import annotations

import collections
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .base import Transport

log = logging.getLogger(__name__)

MAX_BUFFERED_COMMANDS = 500
MAX_BODY_BYTES = 1_000_000
# Commands older than this are not delivered, so a plugin that (re)starts late does not
# replay old speech or gestures.
COMMAND_TTL_S = 10.0


class HttpTransport(Transport):
    def __init__(self, channel: str, host: str = "127.0.0.1", port: int = 8765):
        self.channel = channel
        self.host = host
        self.port = port
        # (sequence number, monotonic time, command)
        self._commands: collections.deque[tuple[int, float, dict[str, Any]]] = collections.deque(
            maxlen=MAX_BUFFERED_COMMANDS
        )
        self._events: list[dict[str, Any]] = []
        self._seq = 0
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- Transport API -------------------------------------------------------------------

    def start(self) -> None:
        transport = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:  # quiet default logging
                log.debug("http: " + fmt, *args)

            def _reply(self, code: int, payload: Any) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _channel_ok(self, query: dict[str, list[str]]) -> bool:
                return query.get("channel", [transport.channel])[0] == transport.channel

            def do_GET(self) -> None:  # noqa: N802
                url = urlparse(self.path)
                query = parse_qs(url.query)
                if url.path == "/v1/health":
                    self._reply(200, {"ok": True, "channel": transport.channel})
                elif url.path == "/v1/commands":
                    if not self._channel_ok(query):
                        self._reply(200, {"commands": [], "last": transport._seq})
                        return
                    try:
                        after = int(query.get("after", ["0"])[0])
                    except ValueError:
                        after = 0
                    self._reply(200, transport._commands_after(after))
                else:
                    self._reply(404, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                url = urlparse(self.path)
                if url.path != "/v1/events":
                    self._reply(404, {"error": "not found"})
                    return
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length <= 0 or length > MAX_BODY_BYTES:
                    self._reply(400, {"error": "bad length"})
                    return
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._reply(400, {"error": "bad json"})
                    return
                if self._channel_ok(parse_qs(url.query)):
                    transport._add_events(data)
                self._reply(200, {"ok": True})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self._server.server_address[1]  # resolves port 0 in tests
        self._thread = threading.Thread(target=self._server.serve_forever, name="aibody-http", daemon=True)
        self._thread.start()
        log.info("HTTP transport listening on http://%s:%d (channel %s)", self.host, self.port, self.channel)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def send(self, command: dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            self._commands.append((self._seq, time.monotonic(), command))

    def poll_events(self) -> list[dict[str, Any]]:
        with self._lock:
            events, self._events = self._events, []
        return events

    # -- internals -----------------------------------------------------------------------

    def _commands_after(self, after: int) -> dict[str, Any]:
        with self._lock:
            if after > self._seq:
                # Plugin is ahead of us: the companion restarted. Resync from the start.
                after = 0
            cutoff = time.monotonic() - COMMAND_TTL_S
            commands = [c for seq, t, c in self._commands if seq > after and t >= cutoff]
            return {"commands": commands, "last": self._seq}

    def _add_events(self, data: Any) -> None:
        items = data if isinstance(data, list) else [data]
        with self._lock:
            self._events.extend(i for i in items if isinstance(i, dict))
