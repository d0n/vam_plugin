"""Tiny HTTP client on the standard library, used by the cloud engines.

Network access exists ONLY in this companion app; the VaM plugin never talks to the network.
The opener is injectable so the tests run against a fake server (no real keys, no network).
API keys travel only in request headers and are never logged.

Version 36 (latency): connections are kept alive and reused (one shared pool for STT, LLM and TTS). Before, every
request opened a new TCP + TLS connection (urllib), which costs about 2-3 network round trips per request (DNS,
TCP, TLS 1.3) - three requests per spoken turn. `warm(url)` opens connections ahead of time (the app calls it when
the user starts talking), so the first request of a turn does not wait for a handshake either. A connection the
server has closed is noticed before use (select) or on the first read, and the request is then sent once more on
a fresh connection. With a proxy set in the environment (HTTPS_PROXY ...) the old urllib path is used unchanged.
"""
from __future__ import annotations

import http.client
import io
import json
import select
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from typing import Any

Opener = Callable[[urllib.request.Request, float], Any]


class ApiError(Exception):
    """A failed request. status 0 = no answer (network, timeout)."""

    def __init__(self, service: str, status: int, message: str):
        super().__init__(f"{service}: HTTP {status}: {message}" if status else f"{service}: {message}")
        self.service = service
        self.status = status
        self.message = message


def is_key_rejection(status: int, message: str) -> bool:
    """True if the server refused the API key. xAI answers a wrong key with HTTP 400 and
    "Incorrect API key provided" (seen on /v1/tts, /v1/stt and the realtime handshake, 17.11.2026),
    other services with 401 / 403."""
    return status in (401, 403) or (status == 400 and "api key" in str(message).lower())


def _urllib_opener(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310 (https URLs from config)


IDLE_MAX_S = 55.0  # idle connections older than this are dropped (servers close idle keep-alive connections)
MAX_IDLE_PER_HOST = 4
_RETRYABLE = (http.client.RemoteDisconnected, http.client.CannotSendRequest, http.client.BadStatusLine,
              ConnectionResetError, ConnectionAbortedError, BrokenPipeError)


class ConnectionPool:
    """Keep-alive connections per (scheme, host, port), shared by all engines; thread safe."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._idle: dict[tuple[str, str, int], list[tuple[http.client.HTTPConnection, float]]] = {}
        self._ctx = ssl.create_default_context()
        self.opened = 0  # new connections (counted for the tests)
        self.reused = 0

    @staticmethod
    def key(url: str) -> tuple[str, str, int]:
        parts = urllib.parse.urlsplit(url)
        scheme = parts.scheme.lower() or "https"
        return scheme, parts.hostname or "", parts.port or (443 if scheme == "https" else 80)

    def _new(self, key: tuple[str, str, int], timeout: float) -> http.client.HTTPConnection:
        scheme, host, port = key
        self.opened += 1
        if scheme == "https":
            return http.client.HTTPSConnection(host, port, timeout=timeout, context=self._ctx)
        return http.client.HTTPConnection(host, port, timeout=timeout)

    @staticmethod
    def _usable(conn: http.client.HTTPConnection) -> bool:
        sock = conn.sock
        if sock is None:
            return False
        try:
            readable, _, _ = select.select([sock], [], [], 0)
        except (OSError, ValueError):
            return False
        return not readable  # an idle connection that is readable was closed by the server (EOF)

    def take(self, key: tuple[str, str, int], timeout: float) -> tuple[http.client.HTTPConnection, bool]:
        """An idle connection to `key` (reused=True) or a new, not yet connected one."""
        now = self._clock()
        with self._lock:
            idle = self._idle.get(key, [])
            while idle:
                conn, since = idle.pop()
                if now - since <= IDLE_MAX_S and self._usable(conn):
                    self.reused += 1
                    if conn.sock is not None:
                        conn.sock.settimeout(timeout)
                    conn.timeout = timeout
                    return conn, True
                conn.close()
        return self._new(key, timeout), False

    def give_back(self, key: tuple[str, str, int], conn: http.client.HTTPConnection) -> None:
        with self._lock:
            idle = self._idle.setdefault(key, [])
            if len(idle) >= MAX_IDLE_PER_HOST or conn.sock is None:
                conn.close()
                return
            idle.append((conn, self._clock()))

    def idle_count(self, url: str) -> int:
        with self._lock:
            return len(self._idle.get(self.key(url), []))

    def warm(self, url: str, count: int = 1, timeout: float = 10.0) -> None:
        """Opens connections to `url`'s host in the background until `count` idle ones exist (no request is sent)."""
        key = self.key(url)
        missing = count - self.idle_count(url)
        if missing <= 0:
            return

        def job() -> None:
            for _ in range(missing):
                conn = self._new(key, timeout)
                try:
                    conn.connect()
                except (OSError, http.client.HTTPException):
                    conn.close()
                    return
                self.give_back(key, conn)

        threading.Thread(target=job, name="aibody-http-warm", daemon=True).start()

    def close_all(self) -> None:
        with self._lock:
            for idle in self._idle.values():
                for conn, _ in idle:
                    conn.close()
            self._idle.clear()


POOL = ConnectionPool()


class PooledResponse:
    """The parts of urllib's response the engines use (context manager, read, readline, headers, status).
    Closing it gives the connection back to the pool if the answer was read completely, else closes it."""

    def __init__(self, pool: ConnectionPool, key: tuple[str, str, int], conn: http.client.HTTPConnection,
                 resp: http.client.HTTPResponse):
        self._pool, self._key, self._conn, self._resp = pool, key, conn, resp
        self.headers = resp.headers
        self.status = resp.status
        self._done = False

    def read(self, amt: int | None = None) -> bytes:
        return self._resp.read(amt)

    def readline(self, limit: int = -1) -> bytes:
        return self._resp.readline(limit)

    def __iter__(self):
        return iter(self._resp.readline, b"")

    def close(self) -> None:
        if self._done:
            return
        self._done = True
        reusable = self._resp.isclosed() and not self._resp.will_close
        self._resp.close()
        if reusable:
            self._pool.give_back(self._key, self._conn)
        else:
            self._conn.close()

    def __enter__(self) -> PooledResponse:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def pooled_opener(request: urllib.request.Request, timeout: float, pool: ConnectionPool | None = None) -> Any:
    """Sends `request` on a kept-alive connection. Raises urllib.error.HTTPError for HTTP >= 400 (like urlopen)."""
    pool = pool or POOL
    url = request.full_url
    if urllib.request.getproxies().get(urllib.parse.urlsplit(url).scheme):
        return _urllib_opener(request, timeout)  # a proxy is configured: keep urllib's proxy handling
    key = pool.key(url)
    parts = urllib.parse.urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    headers = dict(request.header_items())
    if not any(k.lower() == "user-agent" for k in headers):
        headers["User-Agent"] = "aibody-companion"
    body = request.data
    for attempt in (1, 2):
        conn, reused = pool.take(key, timeout)
        try:
            conn.request(request.get_method(), path, body=body, headers=headers)
            resp = conn.getresponse()
        except _RETRYABLE:
            conn.close()
            if reused and attempt == 1:
                continue  # the server closed the idle connection: once more on a fresh one
            raise
        except BaseException:
            conn.close()
            raise
        if resp.status >= 400:
            data = resp.read()
            if resp.will_close:
                conn.close()
            else:
                pool.give_back(key, conn)
            raise urllib.error.HTTPError(url, resp.status, resp.reason, resp.headers, io.BytesIO(data))
        return PooledResponse(pool, key, conn, resp)
    raise http.client.CannotSendRequest("no connection")  # not reached


def warm(url: str, count: int = 1) -> None:
    POOL.warm(url, count)


_default_opener = pooled_opener


def _error_text(body: bytes) -> str:
    text = body.decode("utf-8", "replace").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:300]
    if isinstance(data, dict):
        for key in ("error", "detail", "message"):
            value = data.get(key)
            if isinstance(value, dict):
                value = value.get("message") or value.get("status") or json.dumps(value)
            if value:
                return str(value)[:300]
    return text[:300]


class HttpClient:
    def __init__(self, opener: Opener | None = None):
        self._open = opener or _default_opener
        self.pooled = opener is None  # real network with the shared keep-alive pool (warm() makes sense)

    def open(self, service: str, method: str, url: str, headers: dict[str, str], body: bytes | None,
             timeout: float) -> Any:
        """Sends the request and returns the open response (a context manager)."""
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            return self._open(request, timeout)
        except urllib.error.HTTPError as e:
            try:
                detail = _error_text(e.read())
            except Exception:  # noqa: BLE001 - best effort only
                detail = str(e.reason)
            raise ApiError(service, e.code, detail) from None
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
            reason = getattr(e, "reason", e)
            raise ApiError(service, 0, f"no connection ({reason})") from None

    def post_json(self, service: str, url: str, headers: dict[str, str], payload: dict[str, Any],
                  timeout: float) -> tuple[bytes, str]:
        """POSTs JSON; returns (body, content type)."""
        h = {**headers, "Content-Type": "application/json"}
        with self.open(service, "POST", url, h, json.dumps(payload).encode("utf-8"), timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "") if resp.headers else ""

    def post_multipart(self, service: str, url: str, headers: dict[str, str], fields: list[tuple[str, str]],
                       file_field: str, file_name: str, file_type: str, file_data: bytes,
                       timeout: float) -> bytes:
        """POSTs multipart/form-data; the file is the LAST part (xAI STT requires that)."""
        boundary = "aibody" + uuid.uuid4().hex
        parts: list[bytes] = []
        for name, value in fields:
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
                         .encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
                     f'filename="{file_name}"\r\nContent-Type: {file_type}\r\n\r\n'.encode())
        parts.append(file_data)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        h = {**headers, "Content-Type": f"multipart/form-data; boundary={boundary}"}
        with self.open(service, "POST", url, h, b"".join(parts), timeout) as resp:
            return resp.read()


def iter_sse(lines: Iterator[bytes]) -> Iterator[tuple[str, str]]:
    """Parses a Server-Sent-Events stream into (event name, data) pairs. "data: [DONE]" ends it."""
    event, data = "", []
    for raw in lines:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if data:
                payload = "\n".join(data)
                if payload.strip() == "[DONE]":
                    return
                yield event, payload
            event, data = "", []
            continue
        if line.startswith(":"):
            continue  # comment / keep-alive
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)
    if data and "\n".join(data).strip() != "[DONE]":
        yield event, "\n".join(data)
