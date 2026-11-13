"""Auto transport: HTTP primary, shared folder fallback (mirrors the plugin's "Auto" mode).

Events are collected from both. Commands go over HTTP while the plugin is connected there,
otherwise through the folder. Before the plugin has been heard on either link, commands
go over HTTP (they wait there until the plugin connects; stale ones expire).
"""
from __future__ import annotations

from typing import Any

from .base import Transport
from .file_transport import FileTransport
from .http_transport import HttpTransport


class AutoTransport(Transport):
    name = "auto"

    def __init__(self, http: HttpTransport, file: FileTransport | None):
        self.http = http
        self.file = file

    def start(self) -> None:
        self.http.start()
        if self.file:
            self.file.start()

    def stop(self) -> None:
        self.http.stop()
        if self.file:
            self.file.stop()

    @property
    def link(self) -> str | None:
        if self.http.connected:
            return "http"
        if self.file and self.file.connected:
            return "file"
        return None

    @property
    def connected(self) -> bool:
        return self.link is not None

    def send(self, command: dict[str, Any]) -> None:
        if self.link == "file" and self.file:
            self.file.send(command)
        else:
            self.http.send(command)

    def poll_events(self) -> list[dict[str, Any]]:
        events = self.http.poll_events()
        if self.file:
            events.extend(self.file.poll_events())
        return events

    def audio_url(self, file_name: str) -> str | None:
        return self.http.audio_url(file_name) if self.link != "file" else None
