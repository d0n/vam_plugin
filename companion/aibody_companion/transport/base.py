from __future__ import annotations

import abc
from typing import Any


class Transport(abc.ABC):
    """Moves commands to the plugin and events back. Implementations must be thread safe
    for send() and poll_events() being called from different threads."""

    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...

    @abc.abstractmethod
    def send(self, command: dict[str, Any]) -> None: ...

    @abc.abstractmethod
    def poll_events(self) -> list[dict[str, Any]]:
        """Returns events received since the last call (may be empty)."""
