"""Minimal WebSocket client (RFC 6455) on the standard library, for the xAI realtime API.

Only what a client needs: the HTTP upgrade handshake with extra headers (Authorization),
masked text/binary frames out, text/binary/ping/pong/close frames in (fragmented messages are
reassembled), and a clean close. No extensions (no permessage-deflate), no proxies.

The API key travels only in the Authorization header of the handshake and is never logged.
"""
from __future__ import annotations

import base64
import hashlib
import os
import select
import socket
import ssl
import struct
import threading
from urllib.parse import urlsplit

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONT, OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
MAX_MESSAGE = 16 * 1024 * 1024  # larger messages are a protocol error here
READ_TIMEOUT_S = 30.0  # a started frame must arrive within this time


class WebSocketError(Exception):
    """Handshake failed, connection lost or protocol error. `status` is the HTTP status of a
    refused handshake (401 = bad key), else 0."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")


def encode_frame(opcode: int, payload: bytes, mask: bool = True, fin: bool = True) -> bytes:
    head = bytearray([(0x80 if fin else 0) | opcode])
    n = len(payload)
    mbit = 0x80 if mask else 0
    if n < 126:
        head.append(mbit | n)
    elif n < 65536:
        head.append(mbit | 126)
        head += struct.pack(">H", n)
    else:
        head.append(mbit | 127)
        head += struct.pack(">Q", n)
    if not mask:
        return bytes(head) + payload
    key = os.urandom(4)
    return bytes(head) + key + _xor(payload, key)


def _xor(data: bytes, key: bytes) -> bytes:
    if not data:
        return b""
    n = len(data)
    k = (key * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "little") ^ int.from_bytes(k, "little")).to_bytes(n, "little")


class FrameReader:
    """Reads frames from a socket-like object with recv(n)."""

    def __init__(self, sock):
        self.sock = sock

    def _exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise WebSocketError("connection closed")
            buf += chunk
        return bytes(buf)

    def read_frame(self) -> tuple[bool, int, bytes]:
        b1, b2 = self._exact(2)
        fin, opcode = bool(b1 & 0x80), b1 & 0x0F
        masked, n = bool(b2 & 0x80), b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self._exact(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._exact(8))[0]
        if n > MAX_MESSAGE:
            raise WebSocketError(f"frame too large ({n} bytes)")
        key = self._exact(4) if masked else b""
        payload = self._exact(n) if n else b""
        return fin, opcode, (_xor(payload, key) if masked else payload)


class WebSocket:
    """A connected client. recv() returns str (text), bytes (binary) or None (timeout);
    raises WebSocketError when the connection is gone."""

    def __init__(self, sock):
        self.sock = sock
        self.reader = FrameReader(sock)
        self._send_lock = threading.Lock()
        self.closed = False

    @classmethod
    def connect(cls, url: str, headers: dict[str, str] | None = None, timeout: float = 15.0) -> WebSocket:
        parts = urlsplit(url)
        if parts.scheme not in ("ws", "wss"):
            raise WebSocketError(f"not a WebSocket URL: {parts.scheme}://")
        secure = parts.scheme == "wss"
        host = parts.hostname or ""
        port = parts.port or (443 if secure else 80)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        try:
            raw = socket.create_connection((host, port), timeout=timeout)
        except OSError as e:
            raise WebSocketError(f"cannot connect to {host}:{port}: {e}") from None
        sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host) if secure else raw
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        default_port = 443 if secure else 80
        lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}" + ("" if port == default_port else f":{port}"),
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
        ]
        lines += [f"{k}: {v}" for k, v in (headers or {}).items()]
        try:
            sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("utf-8"))
            response = b""
            while b"\r\n\r\n" not in response:
                chunk = sock.recv(4096)
                if not chunk:
                    raise WebSocketError("connection closed during handshake")
                response += chunk
                if len(response) > 65536:
                    raise WebSocketError("handshake answer too long")
        except OSError as e:
            sock.close()
            raise WebSocketError(f"handshake failed: {e}") from None
        head, _, rest = response.partition(b"\r\n\r\n")
        status_line, *header_lines = head.decode("latin-1").split("\r\n")
        try:
            status = int(status_line.split()[1])
        except (IndexError, ValueError):
            sock.close()
            raise WebSocketError(f"bad handshake answer: {status_line[:80]}") from None
        if status != 101:
            sock.close()
            detail = rest[:200].decode("utf-8", "replace").strip()
            raise WebSocketError(f"handshake refused: HTTP {status} {detail}".strip(), status)
        answer = {k.strip().lower(): v.strip() for k, _, v in (h.partition(":") for h in header_lines)}
        if answer.get("sec-websocket-accept") != accept_key(key):
            sock.close()
            raise WebSocketError("handshake: wrong Sec-WebSocket-Accept")
        ws = cls(_Prefixed(sock, rest) if rest else sock)
        return ws

    def send_text(self, text: str) -> None:
        self._send(OP_TEXT, text.encode("utf-8"))

    def send_binary(self, data: bytes) -> None:
        self._send(OP_BINARY, data)

    def _send(self, opcode: int, payload: bytes) -> None:
        if self.closed:
            raise WebSocketError("connection closed")
        try:
            with self._send_lock:
                self.sock.sendall(encode_frame(opcode, payload))
        except OSError as e:
            self.closed = True
            raise WebSocketError(f"send failed: {e}") from None

    def _readable(self, timeout: float | None) -> bool:
        if timeout is None:
            return True
        sock = self.sock
        if getattr(sock, "buffered", 0):
            return True
        pending = getattr(sock, "pending", None)
        if callable(pending) and pending() > 0:  # TLS bytes already decrypted
            return True
        try:
            ready, _, _ = select.select([sock], [], [], max(0.0, timeout))
        except (OSError, ValueError) as e:
            self.closed = True
            raise WebSocketError(f"receive failed: {e}") from None
        return bool(ready)

    def recv(self, timeout: float | None = None) -> str | bytes | None:
        """Waits up to `timeout` seconds for a message (None = forever). Once a frame has begun,
        it is read completely (up to READ_TIMEOUT_S per chunk)."""
        parts: list[bytes] = []
        message_op = None
        while True:
            if not parts and not self._readable(timeout):
                return None
            try:
                self.sock.settimeout(READ_TIMEOUT_S)
                fin, opcode, payload = self.reader.read_frame()
            except (OSError, ssl.SSLError) as e:  # socket.timeout is an OSError
                self.closed = True
                raise WebSocketError(f"receive failed: {e}") from None
            except WebSocketError:
                self.closed = True
                raise
            if opcode == OP_PING:
                self._send(OP_PONG, payload)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else 1005
                reason = payload[2:].decode("utf-8", "replace")
                try:
                    self._send(OP_CLOSE, payload[:2])
                except WebSocketError:
                    pass
                self.closed = True
                try:
                    self.sock.close()
                except OSError:
                    pass
                raise WebSocketError(f"closed by server ({code} {reason})".strip())
            if opcode in (OP_TEXT, OP_BINARY):
                message_op, parts = opcode, [payload]
            elif opcode == OP_CONT and message_op is not None:
                parts.append(payload)
            else:
                self.closed = True
                raise WebSocketError(f"unexpected opcode {opcode}")
            if sum(len(p) for p in parts) > MAX_MESSAGE:
                self.closed = True
                raise WebSocketError("message too large")
            if fin:
                data = b"".join(parts)
                return data.decode("utf-8") if message_op == OP_TEXT else data

    def close(self) -> None:
        if self.closed:
            return
        try:
            self._send(OP_CLOSE, struct.pack(">H", 1000))
        except WebSocketError:
            pass
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass


class _Prefixed:
    """A socket whose first recv() calls return bytes already read with the handshake."""

    def __init__(self, sock, prefix: bytes):
        self._sock = sock
        self._prefix = prefix

    @property
    def buffered(self) -> int:
        return len(self._prefix)

    def recv(self, n: int) -> bytes:
        if self._prefix:
            chunk, self._prefix = self._prefix[:n], self._prefix[n:]
            return chunk
        return self._sock.recv(n)

    def __getattr__(self, name):
        return getattr(self._sock, name)
