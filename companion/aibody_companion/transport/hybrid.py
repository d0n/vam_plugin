"""The file channel plus the loopback socket (version 30). Both are always polled. Commands go over the socket
while the plugin is connected through it, else through the files; messages the socket cannot carry (one datagram
is at most MAX_DATAGRAM_BYTES) go through the files too."""
from __future__ import annotations

from typing import Any

from .base import Transport
from .file_transport import FileTransport
from .socket_transport import SocketTransport


class HybridTransport(Transport):
    name = "network+file"

    def __init__(self, file: FileTransport, sock: SocketTransport):
        self.file = file
        self.socket = sock

    def start(self) -> None:
        self.file.start()
        self.socket.start()  # a socket that cannot start only logs a warning: the file channel carries on

    def stop(self) -> None:
        self.socket.stop()
        self.file.stop()

    def send(self, command: dict[str, Any]) -> None:
        if self.socket.connected and self.socket.send(command):
            return
        self.file.send(command)

    def poll_events(self) -> list[dict[str, Any]]:
        return self.file.poll_events() + self.socket.poll_events()

    @property
    def connected(self) -> bool:
        return self.socket.connected or self.file.connected

    @property
    def link(self) -> str | None:
        if self.socket.connected:
            return "socket"
        return "file" if self.file.connected else None

    @property
    def channel_dir(self):
        return self.file.channel_dir
