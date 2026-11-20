"""OSC listener (UDP, standard library only), bound to 127.0.0.1.

Messages (OSC 1.0 types i f s T F, also h d; bundles are unpacked) to /aibody/<action>:

  /aibody/say "text" [interrupt 0|1]            /aibody/ask "text"              /aibody/event "text"
  /aibody/expression "name" [intensity] [blend] [hold]
  /aibody/gesture "name"                        /aibody/pose "name"
  /aibody/stop                                  /aibody/ptt "start|stop|toggle"  (or 1 = start, 0 = stop)

There is no token (OSC senders rarely support one): the socket accepts only datagrams from this computer, nothing else
can reach it, and a bad message is dropped with a log line. Datagrams over 4 KB are dropped.
"""
from __future__ import annotations

import logging
import socket
import struct
import threading
from typing import TYPE_CHECKING, Any

from .core import LOOPBACK, RemoteError

if TYPE_CHECKING:
    from .core import RemoteControl

log = logging.getLogger(__name__)

MAX_DATAGRAM = 4096
PREFIX = "/aibody/"


def _pad(n: int) -> int:
    return (n + 3) & ~3


def _read_string(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(b"\x00", pos)
    return data[pos:end].decode("utf-8"), _pad(end + 1)


def parse_message(data: bytes) -> tuple[str, list[Any]]:
    """One OSC message -> (address, arguments). Raises ValueError on anything malformed."""
    try:
        address, pos = _read_string(data, 0)
        if not address.startswith("/"):
            raise ValueError("not an OSC message")
        if pos >= len(data):  # old senders may omit the type tag string
            return address, []
        tags, pos = _read_string(data, pos)
        if not tags.startswith(","):
            raise ValueError("missing type tags")
        args: list[Any] = []
        for tag in tags[1:]:
            if tag == "i":
                args.append(struct.unpack_from(">i", data, pos)[0])
                pos += 4
            elif tag == "f":
                args.append(struct.unpack_from(">f", data, pos)[0])
                pos += 4
            elif tag == "h":
                args.append(struct.unpack_from(">q", data, pos)[0])
                pos += 8
            elif tag == "d":
                args.append(struct.unpack_from(">d", data, pos)[0])
                pos += 8
            elif tag == "s":
                text, pos = _read_string(data, pos)
                args.append(text)
            elif tag == "T":
                args.append(True)
            elif tag == "F":
                args.append(False)
            elif tag == "N":
                args.append(None)
            else:
                raise ValueError(f"unsupported OSC type {tag!r}")
        return address, args
    except (ValueError, struct.error, UnicodeDecodeError) as e:
        raise ValueError(str(e) or "malformed OSC message") from None


def parse_packet(data: bytes, depth: int = 0) -> list[tuple[str, list[Any]]]:
    """A message or a bundle (nested up to 4 levels) -> its messages."""
    if data.startswith(b"#bundle\x00"):
        if depth > 4:
            raise ValueError("bundle nested too deep")
        out: list[tuple[str, list[Any]]] = []
        pos = 16  # tag + time tag
        while pos + 4 <= len(data):
            size = struct.unpack_from(">i", data, pos)[0]
            pos += 4
            if size <= 0 or pos + size > len(data):
                raise ValueError("bad bundle element size")
            out.extend(parse_packet(data[pos:pos + size], depth + 1))
            pos += size
        return out
    return [parse_message(data)]


def to_action(address: str, args: list[Any]) -> tuple[str, dict[str, Any]]:
    """/aibody/<action> + arguments -> (action, params) for RemoteControl.submit. Raises RemoteError."""
    if not address.startswith(PREFIX):
        raise RemoteError(f"address must start with {PREFIX}")
    action = address[len(PREFIX):].strip("/")
    p: dict[str, Any] = {}
    if action == "say":
        p = {"text": _arg(args, 0), "interrupt": bool(args[1]) if len(args) > 1 else False}
    elif action in ("ask", "event"):
        p = {"text": _arg(args, 0)}
    elif action in ("gesture", "pose"):
        p = {"name": _arg(args, 0)}
    elif action == "expression":
        p = {"name": _arg(args, 0)}
        for i, key in ((1, "intensity"), (2, "blend"), (3, "hold")):
            if len(args) > i:
                p[key] = args[i]
    elif action == "ptt":
        first = args[0] if args else "toggle"
        p = {"action": {1: "start", 0: "stop", True: "start", False: "stop"}.get(first, first) if not isinstance(first, str) else first}
    return action, p


def _arg(args: list[Any], index: int) -> Any:
    if len(args) <= index:
        raise RemoteError("missing argument")
    return args[index]


class OscServer:
    def __init__(self, remote: RemoteControl, port: int):
        self.remote = remote
        self._wanted = port
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def port(self) -> int:
        return self._sock.getsockname()[1] if self._sock is not None else 0

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((LOOPBACK, self._wanted))  # raises OSError if the port is taken
        except OSError:
            sock.close()
            raise
        sock.settimeout(0.2)
        self._sock = sock
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="aibody-remote-osc", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def _loop(self) -> None:
        sock = self._sock
        assert sock is not None
        while not self._stop.is_set():
            try:
                data, _ = sock.recvfrom(MAX_DATAGRAM + 1)
            except socket.timeout:
                continue
            except OSError:
                return
            if len(data) > MAX_DATAGRAM:
                log.warning("Remote OSC: datagram over %d bytes dropped", MAX_DATAGRAM)
                continue
            self.handle(data)

    def handle(self, data: bytes) -> int:
        """Runs one datagram. Returns how many messages were queued."""
        queued = 0
        try:
            messages = parse_packet(data)
        except ValueError as e:
            log.warning("Remote OSC: dropped a malformed message (%s)", e)
            return 0
        for address, args in messages:
            try:
                action, params = to_action(address, args)
                self.remote.submit(action, params, source="osc")
                queued += 1
            except RemoteError as e:
                log.warning("Remote OSC %s: %s", address, e)
        return queued
