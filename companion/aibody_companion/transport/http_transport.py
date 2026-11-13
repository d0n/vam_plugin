"""HTTP transport: a small local HTTP server the plugin talks to (primary transport).

Requires "Allow Plugins Network Access" in VaM. Binds to 127.0.0.1 by default.

  GET  /v1/health
  GET  /v1/hello?channel=<c>&plugin=<version>        -> {"session", "protocol", "server", "long_poll_max"}
  GET  /v1/commands?channel=<c>&after=<seq>&wait=<s> -> {"commands": [...], "last": <seq>, "session": "..."}
       long-poll: answers as soon as a command newer than `after` exists, else after `wait` s
  POST /v1/events?channel=<c>                        body: one event object or an array
  GET  /v1/audio/<file>                              speech audio from the audio folder

The session id changes with every companion start; the plugin uses it to detect restarts.
"""
from __future__ import annotations

import collections
import json
import logging
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .. import PROTOCOL_VERSION, __version__
from .base import Transport

log = logging.getLogger(__name__)

MAX_BUFFERED_COMMANDS = 500
MAX_BODY_BYTES = 1_000_000
MAX_LONG_POLL_S = 25.0
# Commands older than this are not delivered, so a plugin that (re)starts late does not
# replay old speech or gestures.
COMMAND_TTL_S = 10.0
# Plugin counts as connected while a poll is open or it was seen this recently.
ALIVE_S = 5.0
AUDIO_NAME = re.compile(r"^[A-Za-z0-9._-]+\.(wav|ogg|mp3)$")
AUDIO_TYPES = {"wav": "audio/wav", "ogg": "audio/ogg", "mp3": "audio/mpeg"}


class HttpTransport(Transport):
    name = "http"

    def __init__(self, channel: str, host: str = "127.0.0.1", port: int = 8765, audio_dir: Path | None = None):
        self.channel = channel
        self.host = host
        self.port = port
        self.audio_dir = Path(audio_dir) if audio_dir else None
        self.session = uuid.uuid4().hex[:12]
        # (sequence number, monotonic time, command)
        self._commands: collections.deque[tuple[int, float, dict[str, Any]]] = collections.deque(
            maxlen=MAX_BUFFERED_COMMANDS
        )
        self._events: list[dict[str, Any]] = []
        self._seq = 0
        self._cond = threading.Condition()
        self._stopping = False
        self._open_polls = 0
        self._last_seen = 0.0
        self.plugin_version: str | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- Transport API -------------------------------------------------------------------

    def start(self) -> None:
        self._stopping = False
        self._server = ThreadingHTTPServer((self.host, self.port), self._make_handler())
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]  # resolves port 0 in tests
        self._thread = threading.Thread(target=self._server.serve_forever, name="aibody-http", daemon=True)
        self._thread.start()
        log.info("HTTP transport listening on http://%s:%d (channel %s)", self.host, self.port, self.channel)

    def stop(self) -> None:
        with self._cond:
            self._stopping = True
            self._cond.notify_all()
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def send(self, command: dict[str, Any]) -> None:
        with self._cond:
            self._seq += 1
            self._commands.append((self._seq, time.monotonic(), command))
            self._cond.notify_all()

    def poll_events(self) -> list[dict[str, Any]]:
        with self._cond:
            events, self._events = self._events, []
        return events

    @property
    def connected(self) -> bool:
        with self._cond:
            return self._open_polls > 0 or (self._last_seen > 0 and time.monotonic() - self._last_seen < ALIVE_S)

    def audio_url(self, file_name: str) -> str | None:
        return f"/v1/audio/{file_name}" if self.audio_dir else None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # -- internals -----------------------------------------------------------------------

    def _touch(self) -> None:
        self._last_seen = time.monotonic()

    def _commands_after(self, after: int, wait: float) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.0, min(wait, MAX_LONG_POLL_S))
        with self._cond:
            self._open_polls += 1
            try:
                if after > self._seq:
                    after = 0  # plugin is ahead of us: it talked to an earlier session
                while True:
                    cutoff = time.monotonic() - COMMAND_TTL_S
                    commands = [c for seq, t, c in self._commands if seq > after and t >= cutoff]
                    remaining = deadline - time.monotonic()
                    if commands or remaining <= 0 or self._stopping:
                        return {"commands": commands, "last": self._seq, "session": self.session}
                    self._cond.wait(remaining)
            finally:
                self._open_polls -= 1
                self._touch()

    def _add_events(self, data: Any) -> None:
        items = data if isinstance(data, list) else [data]
        with self._cond:
            self._touch()
            self._events.extend(i for i in items if isinstance(i, dict))

    def _hello(self, query: dict[str, list[str]]) -> dict[str, Any]:
        version = query.get("plugin", [""])[0]
        with self._cond:
            self._touch()
            first = self.plugin_version is None
            self.plugin_version = version
        log.info("Plugin %s over HTTP (plugin %s)", "connected" if first else "reconnected", version or "?")
        return {
            "session": self.session,
            "protocol": PROTOCOL_VERSION,
            "server": f"aibody-companion/{__version__}",
            "channel": self.channel,
            "long_poll_max": MAX_LONG_POLL_S,
        }

    def _audio_file(self, raw_name: str) -> Path | None:
        name = unquote(raw_name)
        if not self.audio_dir or not AUDIO_NAME.match(name):
            return None
        path = (self.audio_dir / name).resolve()
        if path.parent != self.audio_dir.resolve() or not path.is_file():
            return None
        return path

    def _make_handler(self):
        transport = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

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
                    self._reply(200, {"ok": True, "channel": transport.channel, "session": transport.session})
                elif url.path == "/v1/hello":
                    if not self._channel_ok(query):
                        self._reply(409, {"error": f"companion serves channel {transport.channel!r}"})
                        return
                    self._reply(200, transport._hello(query))
                elif url.path == "/v1/commands":
                    if not self._channel_ok(query):
                        self._reply(409, {"error": f"companion serves channel {transport.channel!r}"})
                        return
                    try:
                        after = int(query.get("after", ["0"])[0])
                        wait = float(query.get("wait", ["0"])[0])
                    except ValueError:
                        self._reply(400, {"error": "bad after/wait"})
                        return
                    self._reply(200, transport._commands_after(after, wait))
                elif url.path.startswith("/v1/audio/"):
                    self._send_audio(url.path[len("/v1/audio/"):])
                else:
                    self._reply(404, {"error": "not found"})

            def _send_audio(self, name: str) -> None:
                path = transport._audio_file(name)
                if path is None:
                    self._reply(404, {"error": "audio not found"})
                    return
                data = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", AUDIO_TYPES[path.suffix[1:].lower()])
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

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
                if not self._channel_ok(parse_qs(url.query)):
                    self._reply(409, {"error": f"companion serves channel {transport.channel!r}"})
                    return
                transport._add_events(data)
                self._reply(200, {"ok": True})

        return Handler
