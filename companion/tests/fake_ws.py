"""A local fake of the xAI realtime WebSocket server (no key, no network beyond 127.0.0.1).

Speaks real RFC 6455 framing (the client's frames must be masked), records every JSON event the
client sends, answers session.update with session.updated, and lets a test push scripted server
events (audio / transcript deltas, speech_started, ...) or drop the connection.
"""
from __future__ import annotations

import base64
import json
import socket
import struct
import threading
import time

from aibody_companion.pipeline.websocket import (
    OP_BINARY,
    OP_CLOSE,
    OP_PING,
    OP_TEXT,
    FrameReader,
    _xor,
    accept_key,
    encode_frame,
)


class _Conn:
    def __init__(self, sock: socket.socket, path: str, headers: dict[str, str]):
        self.sock = sock
        self.path = path
        self.headers = headers
        self.received: list[dict] = []
        self.binary: list[bytes] = []
        self.masked_ok = True
        self.alive = True
        self.lock = threading.Lock()

    def send(self, event: dict) -> None:
        self.send_raw(OP_TEXT, json.dumps(event).encode("utf-8"))

    def send_raw(self, opcode: int, payload: bytes, fin: bool = True) -> None:
        with self.lock:
            try:
                self.sock.sendall(encode_frame(opcode, payload, mask=False, fin=fin))
            except OSError:
                self.alive = False

    def drop(self) -> None:
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()

    def types(self) -> list[str]:
        return [e.get("type", "") for e in list(self.received)]


class FakeRealtimeServer:
    def __init__(self, refuse_status: int | None = None, auto_session: bool = True):
        self.refuse_status = refuse_status
        self.auto_session = auto_session
        self.connections: list[_Conn] = []
        self.attempts = 0
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(8)
        self.port = self._srv.getsockname()[1]
        self._stop = False
        threading.Thread(target=self._accept_loop, daemon=True).start()

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/v1/realtime?model=grok-voice-latest"

    @property
    def conn(self) -> _Conn:
        return self.connections[-1]

    def stop(self) -> None:
        self._stop = True
        try:
            self._srv.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._srv.close()
        except OSError:
            pass
        for c in self.connections:
            if c.alive:
                c.drop()

    # -- server side ---------------------------------------------------------------------

    def _accept_loop(self) -> None:
        while not self._stop:
            try:
                sock, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(sock,), daemon=True).start()

    def _serve(self, sock: socket.socket) -> None:
        self.attempts += 1
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                return
            data += chunk
        head = data.split(b"\r\n\r\n", 1)[0].decode("latin-1").split("\r\n")
        path = head[0].split()[1]
        headers = {k.strip().lower(): v.strip() for k, _, v in (h.partition(":") for h in head[1:])}
        if self.refuse_status:
            body = b'{"error":"refused by fake server"}'
            sock.sendall(f"HTTP/1.1 {self.refuse_status} Refused\r\nContent-Length: {len(body)}\r\n\r\n".encode()
                         + body)
            sock.close()
            return
        accept = accept_key(headers.get("sec-websocket-key", ""))
        sock.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        conn = _Conn(sock, path, headers)
        self.connections.append(conn)
        if self.auto_session:
            conn.send({"type": "conversation.created", "conversation": {"id": f"conv-{len(self.connections)}"}})
            conn.send({"type": "session.created", "session": {"id": "sess", "voice": "eve"}})
        reader = _ServerReader(sock, conn)
        try:
            while conn.alive:
                fin, opcode, payload = reader.read_frame()
                if opcode == OP_TEXT:
                    event = json.loads(payload.decode("utf-8"))
                    conn.received.append(event)
                    if event.get("type") == "session.update" and self.auto_session:
                        conn.send({"type": "session.updated", "session": event.get("session", {})})
                elif opcode == OP_BINARY:
                    conn.binary.append(payload)
                elif opcode == OP_PING:
                    conn.send_raw(0xA, payload)
                elif opcode == OP_CLOSE:
                    conn.send_raw(OP_CLOSE, struct.pack(">H", 1000))
                    conn.drop()
        except Exception:  # noqa: BLE001 - client went away
            conn.alive = False

    # -- helpers for tests ----------------------------------------------------------------

    def wait(self, predicate, timeout: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return True
            except IndexError:
                pass
            time.sleep(0.005)
        return False

    def wait_connections(self, n: int, timeout: float = 3.0) -> bool:
        return self.wait(lambda: len(self.connections) >= n, timeout)

    def wait_type(self, type_: str, count: int = 1, timeout: float = 3.0) -> bool:
        return self.wait(lambda: self.conn.types().count(type_) >= count, timeout)

    def appended_audio(self, conn: _Conn | None = None) -> bytes:
        c = conn or self.conn
        return b"".join(base64.b64decode(e["audio"]) for e in list(c.received)
                        if e.get("type") == "input_audio_buffer.append")

    def respond(self, transcript_parts: list[str], pcm: bytes, response_id: str = "resp-1",
                chunk: int = 4800, call: dict | None = None) -> None:
        """Sends one complete assistant response: created, audio + transcript deltas, done."""
        c = self.conn
        c.send({"type": "response.created", "response": {"id": response_id, "status": "in_progress"}})
        audio_chunks = [pcm[i:i + chunk] for i in range(0, len(pcm), chunk)] or [b""]
        # transcript deltas spread evenly over the audio (roughly when they are spoken)
        at = {int(k * len(audio_chunks) / max(1, len(transcript_parts))): k for k in range(len(transcript_parts))}
        for i, audio in enumerate(audio_chunks):
            if i in at:
                c.send({"type": "response.output_audio_transcript.delta", "response_id": response_id,
                        "delta": transcript_parts[at[i]]})
            if audio:
                c.send({"type": "response.output_audio.delta", "response_id": response_id,
                        "delta": base64.b64encode(audio).decode("ascii")})
        c.send({"type": "response.output_audio.done", "response_id": response_id})
        c.send({"type": "response.output_audio_transcript.done", "response_id": response_id,
                "transcript": "".join(transcript_parts)})
        if call:
            c.send({"type": "response.function_call_arguments.done", "response_id": response_id,
                    "call_id": call.get("call_id", "call-1"), "name": call["name"],
                    "arguments": json.dumps(call.get("arguments", {}))})
        c.send({"type": "response.done", "response": {"id": response_id, "status": "completed"}})


class _ServerReader(FrameReader):
    """Reads client frames and notes whether each carries the mask bit (RFC 6455 requires it)."""

    def __init__(self, sock: socket.socket, conn: _Conn):
        super().__init__(sock)
        self._conn = conn

    def read_frame(self) -> tuple[bool, int, bytes]:
        b1, b2 = self._exact(2)
        fin, opcode = bool(b1 & 0x80), b1 & 0x0F
        masked, n = bool(b2 & 0x80), b2 & 0x7F
        if not masked:
            self._conn.masked_ok = False
        if n == 126:
            n = struct.unpack(">H", self._exact(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._exact(8))[0]
        key = self._exact(4) if masked else b""
        payload = self._exact(n) if n else b""
        return fin, opcode, (_xor(payload, key) if masked else payload)
