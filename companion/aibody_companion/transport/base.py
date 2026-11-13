from __future__ import annotations

import abc
from typing import Any


class Transport(abc.ABC):
    """Moves commands to the plugin and events back. send() and poll_events() may be
    called from different threads."""

    name = "base"

    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...

    @abc.abstractmethod
    def send(self, command: dict[str, Any]) -> None: ...

    @abc.abstractmethod
    def poll_events(self) -> list[dict[str, Any]]:
        """Returns events received since the last call (may be empty)."""

    @property
    def connected(self) -> bool:
        """True if the plugin was heard from recently."""
        return False

    @property
    def link(self) -> str | None:
        """Which link currently reaches the plugin: "http", "file" or None."""
        return self.name if self.connected else None

    def audio_url(self, file_name: str) -> str | None:
        """URL path the plugin can download an audio file from, or None if not served."""
        return None
