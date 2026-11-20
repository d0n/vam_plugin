"""Pose commands (version 32): the ONLY way a pose is applied.

A pose is applied only when the user's ENTIRE input equals a command of the vocabulary (config.json poses.commands:
command text -> pose id). The match is deterministic, in code, not in a prompt:

  1. trim and collapse white space, lower case, drop trailing '.', '!', '?' (and '...'),
  2. compare the whole text with the command text normalized the same way.

No substring, word or fuzzy match: "please sit down" and "sit down and smile" do not match. The AI never sees the
vocabulary and has no pose tool. The answer to a match is the JSON {"pose": "<id>"} in the command `pose`; the plugin
parses and checks it against ITS vocabulary again (PoseVocabulary.cs, same rules; tests/test_pose_commands.py runs
both with the same test vectors).

A command is "available" when a pose with its id exists on the character (the plugin's `poses` list: gestures.json
poses and pose preset files; names compare ignoring case, spaces, '_' and '-': pose_key). Commands without a pose are
kept, shown as unavailable, never applied.
"""
from __future__ import annotations

import json
from typing import Any

# Leon's wording (20.11.2026), exactly. Each starter command links to a pose of the same name until the user changes it.
STARTER_COMMANDS = (
    "Sit Down", "Lay Down", "Prone", "Stand Up", "Spread Your Legs", "Ankle Your Knees", "Ankle Your Elbows",
    "Turn Around", "Crawl on all fours", "Bend Over",
)
MAX_COMMANDS = 100
MAX_COMMAND_CHARS = 60
MAX_POSE_CHARS = 200

# Exactly the characters that the plugin treats as white space (char.IsWhiteSpace on .NET 3.5), so both sides agree.
_WHITESPACE = frozenset("\t\n\x0b\x0c\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009"
                        "\u200a\u2028\u2029\u202f\u205f\u3000")
_TRAILING = frozenset(".!?\u2026\u3002\uff01\uff1f")  # . ! ? ... and the full-width forms


def collapse(text: str) -> str:
    """Trims and collapses internal white space to single spaces."""
    out: list[str] = []
    word: list[str] = []
    for ch in text:
        if ch in _WHITESPACE:
            if word:
                out.append("".join(word))
                word = []
        else:
            word.append(ch)
    if word:
        out.append("".join(word))
    return " ".join(out)


def normalize_input(text: Any) -> str:
    """The form in which the user's input and a command text are compared ("" = nothing to compare)."""
    if not isinstance(text, str):
        return ""
    t = collapse(text).lower()
    while t and (t[-1] in _TRAILING or t[-1] in _WHITESPACE):
        t = t[:-1]
    return t


def pose_key(name: Any) -> str:
    """Pose ids compare ignoring case, spaces, '_', '-' and any other non-alphanumeric character."""
    return "".join(c for c in str(name).lower() if c.isalnum()) if isinstance(name, str) else ""


def starter_entries() -> list[dict[str, str]]:
    return [{"command": c, "pose": c} for c in STARTER_COMMANDS]


def validate_entries(raw: Any) -> tuple[list[dict[str, str]], list[str]]:
    """Checks a poses.commands list: returns the usable entries (cleaned) and the problems. Never raises."""
    errors: list[str] = []
    if not isinstance(raw, list):
        return [], ["poses.commands: must be a list"]
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        where = f"poses.commands[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object with 'command' and 'pose'")
            continue
        command, pose = item.get("command"), item.get("pose")
        if not isinstance(command, str) or not isinstance(pose, str):
            errors.append(f"{where}: 'command' and 'pose' must be text")
            continue
        command, pose = collapse(command), collapse(pose)
        if not command or not normalize_input(command):
            errors.append(f"{where}: empty command")
        elif len(command) > MAX_COMMAND_CHARS:
            errors.append(f"{where}: command longer than {MAX_COMMAND_CHARS} characters")
        elif not pose_key(pose) or len(pose) > MAX_POSE_CHARS:
            errors.append(f"{where}: bad pose id")
        elif normalize_input(command) in seen:
            errors.append(f"{where}: command {command!r} is already defined")
        elif len(entries) >= MAX_COMMANDS:
            errors.append(f"{where}: more than {MAX_COMMANDS} commands, ignored")
        else:
            seen.add(normalize_input(command))
            entries.append({"command": command, "pose": pose})
    return entries, errors


class PoseVocabulary:
    """The commands and what the character can do with them."""

    def __init__(self, entries: list[dict[str, str]] | None = None):
        self.entries = list(entries or [])

    def match(self, text: Any) -> dict[str, str] | None:
        """The command whose text equals the ENTIRE input (see the module docstring), else None."""
        key = normalize_input(text)
        if not key:
            return None
        for entry in self.entries:
            if normalize_input(entry["command"]) == key:
                return entry
        return None

    @staticmethod
    def resolve(entry: dict[str, str], pose_names: list[str]) -> str | None:
        """The character's pose that the command links to (its real name), or None if there is none."""
        key = pose_key(entry["pose"])
        for name in pose_names:
            if pose_key(name) == key:
                return name
        return None

    def available(self, pose_names: list[str]) -> list[dict[str, str]]:
        return [e for e in self.entries if self.resolve(e, pose_names) is not None]

    def unavailable(self, pose_names: list[str]) -> list[dict[str, str]]:
        return [e for e in self.entries if self.resolve(e, pose_names) is None]

    @staticmethod
    def reply_json(entry: dict[str, str]) -> str:
        """The answer to a matched command, as sent to the plugin: {"pose":"<id>"}."""
        return json.dumps({"pose": entry["pose"]}, ensure_ascii=False, separators=(",", ":"))


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate key")
    return dict(pairs)


def parse_pose_json(text: Any) -> tuple[str | None, str]:
    """The strict reader for the answer: exactly one key "pose" with a non-empty text. Returns (pose id, error)."""
    if not isinstance(text, str) or len(text) > 400:
        return None, "pose reply is not text or too long"
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicates)
    except (ValueError, RecursionError):
        return None, "pose reply is not valid JSON"
    if not isinstance(data, dict) or list(data) != ["pose"]:
        return None, 'pose reply must be exactly {"pose": "<id>"}'
    pose = data["pose"]
    if not isinstance(pose, str) or not pose_key(pose) or len(pose) > MAX_POSE_CHARS:
        return None, "pose reply has no usable pose id"
    return pose, ""
