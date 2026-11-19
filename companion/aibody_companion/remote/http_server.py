"""Local web page and HTTP API (standard library only), bound to 127.0.0.1.

Protection, all of it on by default and not configurable:
- binds 127.0.0.1 only (never 0.0.0.0, never a configurable address);
- every /api/ call needs the token (header "Authorization: Bearer <token>" or "X-AIBody-Token",), compared in
  constant time; a wrong token is answered after a short delay;
- the Host header must name this server (127.0.0.1 / localhost with its port) and a browser Origin must be this server:
  other web pages (also through DNS rebinding) cannot drive it, there are no CORS headers;
- POST bodies are JSON objects of at most 16 KB with the content type application/json;
- the page itself (GET /) holds no secret; it reads the token from the address fragment (#token=...), which a browser
  never sends to a server.
"""
from __future__ import annotations

import hmac
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

from .core import ACTIONS, LOOPBACK, RemoteError
from .panel import PANEL_HTML

if TYPE_CHECKING:
    from .core import RemoteControl

log = logging.getLogger(__name__)

MAX_BODY_BYTES = 16 * 1024
WRONG_TOKEN_DELAY_S = 0.25


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class HttpServer:
    def __init__(self, remote: RemoteControl, port: int):
        self.remote = remote
        self._wanted = port
        self._server: _Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._server.server_address[1] if self._server is not None else 0

    def start(self) -> None:
        remote = self.remote
        server = _Server((LOOPBACK, self._wanted), _make_handler(remote))  # raises OSError if the port is taken
        server.timeout = 0.5
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2},
                                        name="aibody-remote-http", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None


def _make_handler(remote: RemoteControl) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AIBodyRemote"
        sys_version = ""

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature of the base class
            log.debug("remote http: " + format, *args)

        # -- helpers ---------------------------------------------------------------------------

        @property
        def _own_port(self) -> int:
            return int(self.server.server_address[1])

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                             "connect-src 'self'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _fail(self, status: int, message: str) -> None:
            self._json(status, {"ok": False, "error": message})

        def _same_origin_ok(self) -> bool:
            port = self._own_port
            host = (self.headers.get("Host") or "").strip().lower()
            if host not in (f"{LOOPBACK}:{port}", f"localhost:{port}"):
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin.strip().lower() in (f"http://{LOOPBACK}:{port}", f"http://localhost:{port}")

        def _token_ok(self, query: dict[str, list[str]]) -> bool:
            supplied = ""
            auth = self.headers.get("Authorization") or ""
            if auth.lower().startswith("bearer "):
                supplied = auth[7:].strip()
            if not supplied:
                supplied = (self.headers.get("X-AIBody-Token") or "").strip()
            ok = bool(supplied) and hmac.compare_digest(supplied.encode("utf-8"), remote.token.encode("utf-8"))
            if not ok:
                time.sleep(WRONG_TOKEN_DELAY_S)
            return ok

        def _gate(self, query: dict[str, list[str]], need_token: bool) -> bool:
            if not self._same_origin_ok():
                self._fail(403, "forbidden: this server answers only requests addressed to 127.0.0.1 / localhost from its own page")
                return False
            if need_token and not self._token_ok(query):
                self._fail(401, "missing or wrong token (remote.token in config.json)")
                return False
            return True

        # -- routes ----------------------------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802
            parts = urlsplit(self.path)
            query = parse_qs(parts.query)
            if parts.path in ("/", "/index.html"):
                if self._gate(query, need_token=False):
                    self._send(200, PANEL_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif parts.path == "/api/status":
                if self._gate(query, need_token=True):
                    self._json(200, {"ok": True, **remote.status()})
            elif parts.path.startswith("/api/") and parts.path[5:] in ACTIONS:
                self._fail(405, "use POST for actions")
            else:
                self._fail(404, "not found")

        def do_POST(self) -> None:  # noqa: N802
            parts = urlsplit(self.path)
            query = parse_qs(parts.query)
            if not (parts.path.startswith("/api/") and parts.path[5:] in ACTIONS):
                self._fail(404, "not found")
                return
            if not self._gate(query, need_token=True):
                return
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY_BYTES:
                self._fail(413, f"the body must be at most {MAX_BODY_BYTES} bytes")
                return
            params: Any = {}
            if length:
                if ctype != "application/json":
                    self._fail(415, "send the parameters as application/json")
                    return
                try:
                    params = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._fail(400, "the body is not valid JSON")
                    return
            try:
                remote.submit(parts.path[5:], params, source="http")
            except RemoteError as e:
                self._fail(400, str(e))
                return
            self._json(200, {"ok": True})

        def _method_not_allowed(self) -> None:
            self._fail(405, "method not allowed")

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _method_not_allowed  # noqa: N815 - no CORS preflight answers

    return Handler
