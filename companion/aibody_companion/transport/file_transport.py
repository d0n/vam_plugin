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
import os
import threading
import time
from pathlib import Path
from typing import Any

from .base import Transport

log = logging.getLogger(__name__)

# Unparseable outbox files younger than this are assumed to be still being written.
PARTIAL_WRITE_GRACE_S = 2.0


class FileTransport(Transport):
    def __init__(self, channel_dir: Path):
        self.channel_dir = Path(channel_dir)
        self.inbox = self.channel_dir / "inbox"
        self.outbox = self.channel_dir / "outbox"
        self.audio_dir = self.channel_dir / "audio"
        self._seq = itertools.count(1)
        self._lock = threading.Lock()

    def start(self) -> None:
        for d in (self.inbox, self.outbox, self.audio_dir):
            d.mkdir(parents=True, exist_ok=True)
        # Leftovers from a previous session must not be replayed (old speech, old events).
        stale = [*self.inbox.glob("*.json"), *self.inbox.glob("*.tmp"), *self.outbox.glob("*.json")]
        for path in stale:
            path.unlink(missing_ok=True)

    def stop(self) -> None:
        pass

    def send(self, command: dict[str, Any]) -> None:
        with self._lock:
            # Zero padded ns timestamp + sequence keeps ordinal sort == send order.
            name = f"{time.time_ns():020d}_{next(self._seq):06d}"
            tmp = self.inbox / f"{name}.tmp"
            tmp.write_text(json.dumps(command), encoding="utf-8")
            os.replace(tmp, self.inbox / f"{name}.json")

    def poll_events(self) -> list[dict[str, Any]]:
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
                log.warning("Dropping unreadable event file %s", path.name)
                path.unlink(missing_ok=True)
                continue
            path.unlink(missing_ok=True)
            if isinstance(data, list):
                events.extend(d for d in data if isinstance(d, dict))
            elif isinstance(data, dict):
                events.append(data)
        return events
