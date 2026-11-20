"""File transport: exchanges JSON files in Saves/PluginData/AIBody/<channel>/.

Works without VaM's "Allow Plugins Network Access". The companion writes commands
atomically (tmp file + rename) into inbox/, the plugin writes events into outbox/.
The plugin cannot rename files, so a fresh outbox file that does not parse yet is
retried on the next poll instead of being dropped.
"""
from __future__ import annotations

import itertools
import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..atomicfile import atomic_write_text
from .base import Transport

log = logging.getLogger(__name__)

# Unparseable outbox files younger than this are assumed to be still being written.
PARTIAL_WRITE_GRACE_S = 2.0


# Commands the plugin did not pick up within this time are deleted unread (the plugin is not
# running): no replay of old speech when it comes back.
COMMAND_TTL_S = 10.0


# The plugin counts as connected over files while it sent something within this window
# (it sends a heartbeat every 2 s).
FILE_ALIVE_S = 5.0


class FileTransport(Transport):
    name = "file"

    def __init__(self, channel_dir: Path, clock: Callable[[], float] = time.monotonic):
        self._clock = clock  # monotonic seconds; injectable for tests
        self.channel_dir = Path(channel_dir)
        self.inbox = self.channel_dir / "inbox"
        self.outbox = self.channel_dir / "outbox"
        self.audio_dir = self.channel_dir / "audio"
        self._seq = itertools.count(1)
        self._lock = threading.Lock()
        self._last_seen = 0.0
        self._last_prune = 0.0

    def start(self) -> None:
        for d in (self.inbox, self.outbox, self.audio_dir):
            d.mkdir(parents=True, exist_ok=True)
        # Leftovers from a previous session must not be replayed (old speech, old events).
        stale = [*self.inbox.glob("*.json"), *self.inbox.glob("*.tmp"), *self.inbox.glob("*.part"),
                 *self.outbox.glob("*.json")]
        for path in stale:
            path.unlink(missing_ok=True)

    def stop(self) -> None:
        pass

    def send(self, command: dict[str, Any]) -> None:
        with self._lock:
            # Zero padded ns timestamp + sequence keeps ordinal sort == send order.
            name = f"{time.time_ns():020d}_{next(self._seq):06d}"
            # The command appears under its final name only when complete (temp name, fsync, replace).
            atomic_write_text(self.inbox / f"{name}.json", json.dumps(command), durable=False)

    def drop_stale_commands(self, now: float | None = None) -> int:
        """Deletes our own inbox files older than COMMAND_TTL_S. Returns how many."""
        now = time.time() if now is None else now
        dropped = 0
        for path in self.inbox.glob("*.json"):
            try:
                if now - path.stat().st_mtime > COMMAND_TTL_S:
                    path.unlink(missing_ok=True)
                    dropped += 1
            except FileNotFoundError:
                continue  # the plugin took it meanwhile
        if dropped:
            log.info("Dropped %d old message file(s) for the plugin that it never picked up. Is VaM running with the AIBody "
                     "plugin on a Person atom, is 'Active' on (tab Voice), and is --vam-root the VaM folder you start VaM from?", dropped)
        return dropped

    def poll_events(self) -> list[dict[str, Any]]:
        if self._clock() - self._last_prune >= 1.0:
            self._last_prune = self._clock()
            self.drop_stale_commands()
        events: list[dict[str, Any]] = []
        try:
            files = sorted(self.outbox.glob("*.json"))
        except FileNotFoundError:
            return events
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
                data = json.loads(text)
            except (OSError, json.JSONDecodeError):
                try:
                    age = time.time() - path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age < PARTIAL_WRITE_GRACE_S:
                    break  # keep order: wait for this file before reading later ones
                log.warning("Dropped an unreadable message file from the plugin (%s): it is not valid JSON. If this repeats, "
                            "check that the plugin and this app are the same AIBody version", path.name)
                path.unlink(missing_ok=True)
                continue
            path.unlink(missing_ok=True)
            self._last_seen = self._clock()
            if isinstance(data, list):
                events.extend(d for d in data if isinstance(d, dict))
            elif isinstance(data, dict):
                events.append(data)
        return events

    @property
    def connected(self) -> bool:
        return self._last_seen > 0 and self._clock() - self._last_seen < FILE_ALIVE_S
