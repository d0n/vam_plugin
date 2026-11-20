"""Loopback UDP transport (version 30): the plugin's "Network Active" option.

- Binds 127.0.0.1 ONLY (never 0.0.0.0): the app is not reachable from the network, only from this computer.
- One character, one plugin, so there is one peer. The plugin (UdpClient on an ephemeral port) says
  {"net": "hello"}; the app learns the sender's address, answers {"net": "hello_ack"} and from then on sends
  commands to that address. Every other datagram is one complete JSON message (an object, or an array),
  exactly the text a file in the inbox/outbox would hold.
- A receiver thread owns the socket for reading; poll_events() hands the parsed messages to the app's main loop.
- The link is "connected" while the plugin sent something within SOCKET_ALIVE_S (it sends a heartbeat every 2 s).
- No token travels here: the plugin sends the config event (with the token) through the file channel
  (see HybridTransport and the plugin's NetworkTransport).
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from .. import wakeup
from .base import Transport

log = logging.getLogger(__name__)

LOOPBACK = "127.0.0.1"
DEFAULT_PORT = 38437
SOCKET_ALIVE_S = 5.0
MAX_DATAGRAM_BYTES = 60000  # larger messages go through the file channel
MAX_QUEUED_EVENTS = 1000


class SocketTransport(Transport):
    name = "socket"

    def __init__(self, port: int = DEFAULT_PORT, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self.port = port  # 0 = pick a free port (tests); the real port is known after start()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=MAX_QUEUED_EVENTS)
        self._peer: tuple[str, int] | None = None
        self._last_seen = 0.0
        self.error = ""  # why the socket could not be opened (shown by the caller)

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((LOOPBACK, self.port))  # loopback only, on purpose
            sock.settimeout(0.2)
        except OSError as e:
            sock.close()
            self.error = f"port {self.port} on {LOOPBACK} could not be opened: {e}"
            log.warning("Network listener off (%s). The file exchange keeps working. Another program (or a second copy "
                        "of this app) may use the port; change connection.network_port in config.json.", self.error)
            return
        self._sock = sock
        self.port = sock.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._receive_loop, name="aibody-socket", daemon=True)
        self._thread.start()
        log.info("Network listener on %s:%d (loopback only; the plugin option 'Network Active' connects here, "
                 "the file exchange stays as the fallback)", LOOPBACK, self.port)

    def stop(self) -> None:
        self._running = False
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._peer = None

    # -- receiving (thread) ---------------------------------------------------------------------------

    def _receive_loop(self) -> None:
        while self._running:
            sock = self._sock
            if sock is None:
                return
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue  # Windows: an earlier datagram to a port nobody listens on
            except OSError:
                if not self._running:
                    return
                time.sleep(0.05)
                continue
            self._handle_datagram(data, addr)

    def _handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        if addr[0] != LOOPBACK:
            return
        try:
            message = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            log.debug("Dropped a datagram that is not JSON")
            return
        if isinstance(message, dict) and message.get("net") == "hello":
            with self._lock:
                if self._peer != addr:
                    log.info("Plugin connected over the network socket (127.0.0.1:%d)", addr[1])
                self._peer = addr
                self._last_seen = self._clock()
            self._send_to(addr, {"net": "hello_ack", "v": 3})
            return
        with self._lock:
            if addr != self._peer:
                return  # not the plugin that said hello (or the app restarted: the plugin will say hello again)
            self._last_seen = self._clock()
            items = message if isinstance(message, list) else [message]
            self._events.extend(m for m in items if isinstance(m, dict) and "net" not in m)
        wakeup.notify()  # version 36: the main loop handles the plugin's event now (push-to-talk, speech_started)

    # -- Transport ------------------------------------------------------------------------------------

    def _send_to(self, addr: tuple[str, int], message: dict[str, Any]) -> bool:
        sock = self._sock
        if sock is None:
            return False
        data = json.dumps(message).encode("utf-8")
        if len(data) > MAX_DATAGRAM_BYTES:
            return False
        try:
            sock.sendto(data, addr)
            return True
        except OSError as e:
            log.debug("Network send failed: %s", e)
            return False

    def send(self, command: dict[str, Any]) -> bool:
        """True if the message went out over the socket (False: nobody connected, or too large for one datagram)."""
        with self._lock:
            peer = self._peer
        if peer is None:
            return False
        return self._send_to(peer, command)

    def poll_events(self) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
        return events

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._peer is not None and self._clock() - self._last_seen < SOCKET_ALIVE_S
