"""What the AI is told about time, and how a "stay silent" answer is recognised.

The AI has no clock of its own: it only knows the date and time this app writes into each user
turn and each proactive nudge (the companion's local clock and time zone), plus how long ago the
last exchange was.
"""
from __future__ import annotations

import re
from datetime import datetime

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")

SILENT_TOKEN = "[silent]"
DEFAULT_NUDGE_PROMPT = (
    "The user has been quiet for a while. You may say something short and spontaneous that fits the "
    "moment and your character (a remark, a thought, a question), or you may stay silent. If you "
    f"prefer to stay silent, answer with exactly {SILENT_TOKEN} and nothing else."
)
SCENE_EVENT_MAX_CHARS = 200
DEFAULT_SCENE_EVENT_PROMPT = (
    "Something just happened in the scene: {event}. You may react briefly and in character if it fits, "
    "or you may stay silent. If you prefer to stay silent, answer with exactly "
    f"{SILENT_TOKEN} and nothing else."
)
_SILENT_WORDS = {"", "silent", "silence", "schweigen", "schweigt", "still", "stille"}


def format_since(seconds: float | None) -> str:
    if seconds is None:
        return "none yet (start of the conversation)"
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{int(seconds)} seconds ago"
    minutes = seconds / 60
    if minutes < 90:
        return f"{int(round(minutes))} minutes ago"
    hours = minutes / 60
    if hours < 36:
        return f"about {hours:.0f} hours ago"
    return f"about {hours / 24:.0f} days ago"


def format_now(now: datetime) -> str:
    """'Tuesday, 17 November 2026, 18:55 (UTC+01:00)' - the time zone of the companion's computer."""
    offset = now.strftime("%z")
    zone = f"UTC{offset[:3]}:{offset[3:]}" if offset else "local time"
    return f"{WEEKDAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]} {now.year}, {now:%H:%M} ({zone})"


def time_context(now: datetime, since_last_s: float | None) -> str:
    return (f"[App context, not said by the user: it is now {format_now(now)}. Last exchange: "
            f"{format_since(since_last_s)}. You have no clock of your own; this is the current time.]")


def time_rules(now: datetime, since_last_s: float | None) -> str:
    """The time line for the realtime session's instructions (refreshed by the app)."""
    return (f"Current local date and time (updated by the app; you have no clock of your own): "
            f"{format_now(now)}. Last exchange with the user: {format_since(since_last_s)}.")


def nudge_text(prompt: str, now: datetime, since_last_s: float | None) -> str:
    return f"{time_context(now, since_last_s)}\n[App note: {prompt.strip() or DEFAULT_NUDGE_PROMPT}]"


def clean_scene_event(text: object) -> str:
    """One line of at most SCENE_EVENT_MAX_CHARS characters, without control characters ('' if nothing is left)."""
    if not isinstance(text, str):
        return ""
    one_line = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    return " ".join(one_line.split())[:SCENE_EVENT_MAX_CHARS]


def scene_event_text(prompt: str, event: str, now: datetime, since_last_s: float | None) -> str:
    """The note the AI gets for a scene event: the prompt with {event} replaced (no str.format: scene texts may hold braces)."""
    note = (prompt.strip() or DEFAULT_SCENE_EVENT_PROMPT).replace("{event}", event)
    return f"{time_context(now, since_last_s)}\n[App note: {note}]"


def is_silent(text: str) -> bool:
    """True for an empty answer or the stay-silent token (also spoken variants like 'Silent.')."""
    t = text.strip().lower()
    if t.startswith(SILENT_TOKEN):
        return True
    return re.sub(r"[\W_]+", "", t) in _SILENT_WORDS
