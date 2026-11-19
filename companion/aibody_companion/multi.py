"""Several figures, one companion app (version 28).

Every figure is its own AIBody plugin on its own channel. The app serves all channels in one
process: each figure gets its own Companion (own history, persona, memory, engines, link to its
plugin). They share one microphone and one room:

  * the microphone frames go only to the figure that is "active" (the one the user talks to),
    so there is one voice detector at work and one answer per sentence
  * who is active: the user says a figure's name near the start or at the end of the sentence
    ("Anna, ..." / "..., Marc"), else the figure that spoke last, else the one that heard last
  * every figure's gate also stays closed while a peer speaks (no figure hears another one as the user)
  * the proactive timers of all figures restart when any figure or the user talks, and a figure
    only starts a nudge while no peer is busy (the figures do not talk over each other)

A single channel never builds a Fleet; this module changes nothing for it.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any

log = logging.getLogger("aibody_companion.multi")

NAME_MIN_CHARS = 3  # shorter names are not matched ("Al" would hit too many sentences)
ADDRESS_HEAD_WORDS = 5  # a name among the first words addresses ("Hey Anna, ...")
ADDRESS_TAIL_WORDS = 3  # ... or among the last ones ("..., Marc?")
MAX_FIGURES = 8
_WORD = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)


def parse_channels(value: Any) -> list[str]:
    """"anna, marc;eve" -> ["anna", "marc", "eve"] (same character rule as the plugin's channel field,
    no duplicates, at most MAX_FIGURES)."""
    out: list[str] = []
    for part in re.split(r"[,;\s]+", str(value or "")):
        name = re.sub(r"[^A-Za-z0-9_-]", "_", part.strip())
        if name and name not in out:
            out.append(name)
    return out[:MAX_FIGURES]


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def find_address(text: str, names: dict[str, Iterable[str]]) -> str | None:
    """The key of the figure the sentence is addressed to, or None. A name counts at the start (first
    ADDRESS_HEAD_WORDS words) or at the end (last ADDRESS_TAIL_WORDS words); the earliest mention wins."""
    words = _words(text)
    if not words:
        return None
    head = set(range(min(ADDRESS_HEAD_WORDS, len(words))))
    tail = set(range(max(0, len(words) - ADDRESS_TAIL_WORDS), len(words)))
    best: tuple[int, str] | None = None
    for key, labels in names.items():
        for label in labels:
            parts = _words(label)
            if not parts or len(" ".join(parts)) < NAME_MIN_CHARS:
                continue
            for i in range(len(words) - len(parts) + 1):
                if words[i:i + len(parts)] == parts and (i in head or i in tail):
                    if best is None or i < best[0]:
                        best = (i, key)
                    break
    return best[1] if best else None


class MicTap:
    """What one figure's Companion sees as its microphone: the frames the fleet hands to it."""

    def __init__(self, fleet: Fleet):
        self._fleet = fleet
        self._frames: list[bytes] = []

    def apply(self, settings: Any, allowed: bool = True) -> None:
        self._fleet.apply_mic(settings, allowed)

    def frames(self) -> Iterable[bytes]:
        frames, self._frames = self._frames, []
        return frames

    def push(self, frames: Iterable[bytes]) -> None:
        self._frames.extend(frames)

    @property
    def capturing(self) -> bool:
        return bool(self._fleet.mic and self._fleet.mic.capturing)

    @property
    def error(self) -> str | None:
        return self._fleet.mic.error if self._fleet.mic else None

    def stop(self) -> None:  # the fleet owns the real microphone
        pass


class Fleet:
    """The figures of one app. Looks like a Companion to the command line loop (tick, handle_user_text,
    shutdown, mic)."""

    def __init__(self, mic: Any = None):
        self.mic = mic  # the one real MicController (or None = text only)
        self.members: list[Any] = []
        self.active: Any = None

    # -- build ---------------------------------------------------------------------------

    def new_tap(self) -> MicTap:
        return MicTap(self)

    def add(self, companion: Any) -> None:
        self.members.append(companion)
        if self.active is None:
            self.active = companion

    def link(self) -> None:
        """Call once all members are added: peers, shared gates, back reference."""
        for m in self.members:
            m.fleet = self
            m.peers = [o for o in self.members if o is not m]
            if hasattr(m.gate, "peers"):
                m.gate.peers = [o.gate for o in m.peers]

    @property
    def engine_set(self) -> Any:
        return self.members[0].engine_set

    @property
    def channels(self) -> list[str]:
        return [m.cfg.channel for m in self.members]

    # -- microphone ----------------------------------------------------------------------

    def apply_mic(self, settings: Any, allowed: bool = True) -> None:
        """The microphone is one device: the last settings any figure's plugin sent win."""
        if self.mic:
            self.mic.apply(settings, allowed)

    def _pump(self) -> None:
        frames = list(self.mic.frames()) if self.mic else []
        if not frames:
            return
        tap = self.active.mic if self.active is not None else None
        if tap is not None:
            tap.push(frames)  # the other figures hear nothing: dropped

    # -- who is addressed ----------------------------------------------------------------

    def names_of(self, member: Any) -> list[str]:
        out: list[str] = []
        persona = getattr(member.engine_set, "persona", None)
        if persona is not None:
            out += [persona.display_name, persona.name]
        out.append(member.cfg.channel.replace("-", " ").replace("_", " "))
        return [n for n in out if n]

    def _candidates(self) -> list[Any]:
        live = [m for m in self.members if m.transport.connected]
        return live or list(self.members)

    def route(self, source: Any, text: str) -> Any:
        """The figure that answers `text` (spoken to `source` or typed). Sets it active."""
        candidates = self._candidates()
        key = find_address(text, {str(i): self.names_of(m) for i, m in enumerate(self.members)
                                  if m in candidates})
        target = self.members[int(key)] if key is not None else (
            self.active if self.active in candidates else candidates[0])
        self.set_active(target, why="addressed" if key is not None else "")
        return target

    def set_active(self, member: Any, why: str = "") -> None:
        if member is self.active:
            return
        log.info("Now talking to %s (%s)", member.cfg.channel, why or "last speaker")
        self.active = member
        for m in self.members:
            m._last_heartbeat = -1e9  # the plugins show who listens right away

    def note_speaker(self, member: Any) -> None:
        """A figure speaks (answer or on its own): the user's next words are for it."""
        self.set_active(member)

    def activity(self, source: Any, user: bool) -> None:
        """Keeps the peers' proactive timers in step with what happens in the room."""
        for m in source.peers:
            if user:
                m.proactive.user_activity()
            else:
                m.proactive.ai_activity()

    def peers_busy(self, member: Any) -> bool:
        return any(p._busy.is_set() or not p._jobs.empty() or not p._results.empty()
                   or not p.gate.own_open for p in member.peers)

    # -- the loop the command line drives ---------------------------------------------------

    def tick(self) -> None:
        self._pump()
        for m in self.members:
            m.tick()

    def handle_user_text(self, text: str) -> None:
        self.route(None, text).handle_user_text(text)

    def shutdown(self) -> None:
        for m in self.members:
            m.shutdown()
        if self.mic:
            self.mic.stop()

    def start(self) -> None:
        for m in self.members:
            m.transport.start()

    def stop(self) -> None:
        for m in self.members:
            m.transport.stop()
