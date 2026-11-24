"""Pose commands (version 32): the ONLY way a pose is applied.

A pose is applied only when the user's ENTIRE input equals a command of the vocabulary (config.json poses.commands:
command text -> pose id). The match is deterministic, in code, not in a prompt:

  1. trim and collapse white space, lower case, drop trailing '.', '!', '?', '...' and (version 35) ',', ';', ':',
  2. compare the whole text with the command text normalized the same way.

No substring, word or fuzzy match in `match`: "please sit down" and "sit down and smile" do not match there (it is the
twin of the plugin's PoseVocabulary.Match, used for exact names). Version 58 (Leon 16:07) relaxes the gate for what the
user SAYS or TYPES: `find` (below) also finds a command inside a longer sentence ("please sit down now"). The AI never sees the
vocabulary and has no pose tool. The answer to a match is the JSON {"pose": "<id>"} in the command `pose`; the plugin
parses and checks it against ITS vocabulary again (PoseVocabulary.cs, same rules; tests/test_pose_commands.py runs
both with the same test vectors).

Version 58, `find`: the input and the commands are cut into words (letters and digits; apostrophes are dropped, so
"don't" is "dont"; everything else separates words, case ignored). A command matches when its words appear in the
input as a whole run of words ("sit down" in "please sit down now", never "sitting down" or "sit downstairs"). Built-in
commands also have a few German phrases (STARTER_ALIASES: "kannst du dich hinsetzen" -> Sit Down). An occurrence right
after a negation ("don't sit down", "never stand up", "nicht hinsetzen") or followed by "nicht" ("setz dich nicht hin")
does not count. Several commands: the one with the most words wins (then the most characters, then the later one in
the sentence). `rest_words` says how many other words the sentence has besides the command and filler words: from
REST_FOR_AI on, the sentence also goes to the AI as usual (the pose is applied first).

Version 58: a built-in command (a starter command still linked to the pose of its own name, `is_builtin`) without that
pose on the character is not "unavailable" any more: the plugin applies a substitute pose (PoseController.SubstituteFor).

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
# Version 58 (Leon 16:07, "kannst du dich hinsetzen"): German phrases for the built-in commands (voice input; matched
# like the command itself, whole words). Not for "Ankle Your Knees" / "Ankle Your Elbows" (no clear German phrase).
STARTER_ALIASES = {
    "Sit Down": ("hinsetzen", "setz dich", "setzt dich", "setzen sie sich"),
    "Lay Down": ("hinlegen", "leg dich", "legst dich"),
    "Prone": ("auf den bauch", "bauchlage"),
    "Stand Up": ("aufstehen", "steh auf", "stehst auf"),
    "Spread Your Legs": ("beine spreizen", "spreiz die beine", "spreiz deine beine", "beine breit"),
    "Turn Around": ("umdrehen", "dreh dich um", "drehst dich um"),
    "Crawl on all fours": ("auf alle viere", "auf allen vieren", "krabbeln", "krabbel"),
    "Bend Over": ("bück dich", "bueck dich", "bücken", "vorbeugen", "beug dich vor", "beug dich nach vorne"),
}
# Words that negate a command right before it (up to NEGATION_WINDOW words), and "nicht" right after it.
NEGATIONS = frozenset(("not", "dont", "doesnt", "didnt", "never", "no", "cant", "cannot", "wont", "shouldnt", "mustnt",
                       "stop", "nicht", "nie", "niemals", "kein", "keine", "nö", "nein"))
NEGATION_WINDOW = 3
# Words that do not count as "more to say" next to a command ("please sit down now" is just the command).
FILLERS = frozenset((
    "please", "pls", "now", "right", "away", "just", "and", "then", "ok", "okay", "hey", "hi", "so", "well", "can", "could",
    "would", "will", "you", "u", "for", "me", "go", "ahead", "quickly", "slowly", "again", "a", "the", "honey", "babe",
    "baby", "darling", "dear", "sweetie", "yes", "yeah", "come", "on", "lets", "let", "us",
    "bitte", "jetzt", "mal", "doch", "schnell", "langsam", "nochmal", "wieder", "und", "dann", "kannst", "könntest",
    "koenntest", "würdest", "wuerdest", "du", "dich", "mir", "mich", "sofort", "gleich", "schatz", "liebling", "ja", "na",
    "komm", "los", "einfach", "bitteschön",
))
REST_FOR_AI = 3   # other words from which the sentence also goes to the AI

MAX_COMMANDS = 100
MAX_COMMAND_CHARS = 60
MAX_POSE_CHARS = 200

# Exactly the characters that the plugin treats as white space (char.IsWhiteSpace on .NET 3.5), so both sides agree.
_WHITESPACE = frozenset("\t\n\x0b\x0c\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009"
                        "\u200a\u2028\u2029\u202f\u205f\u3000")
# . ! ? ... and the full-width forms; version 35 also , ; : (speech-to-text sometimes ends with them: "Sit down,")
_TRAILING = frozenset(".!?\u2026\u3002\uff01\uff1f,;:\uff0c\uff1b\uff1a\u3001")


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


def is_pose_path(pose: Any) -> bool:
    """A pose file path (contains '/' and ends with .vap or .json); same rule as PoseVocabulary.IsPosePath."""
    text = str(pose or "")
    return "/" in text and text.lower().endswith((".vap", ".json"))


def words(text: Any) -> list[str]:
    """Version 58: the words of a text for `find` (letters and digits, lower case; apostrophes dropped)."""
    if not isinstance(text, str):
        return []
    t = text.lower()
    for ch in "'\u2019\u2018`\u00b4":
        t = t.replace(ch, "")
    return "".join(c if c.isalnum() else " " for c in t).split()


def is_builtin(entry: dict[str, str]) -> bool:
    """Version 58: a starter command still linked to the pose of its own name (same rule as PoseVocabulary.IsBuiltIn)."""
    key = pose_key(entry.get("command", ""))
    return (any(pose_key(c) == key for c in STARTER_COMMANDS) and pose_key(entry.get("pose", "")) == key
            and not is_pose_path(entry.get("pose", "")))


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

    def phrases(self, entry: dict[str, str]) -> list[list[str]]:
        """The word runs that call this command: its own text, plus the German phrases of a built-in command."""
        result = [words(entry["command"])]
        for starter, aliases in STARTER_ALIASES.items():
            if pose_key(starter) == pose_key(entry["command"]):
                result.extend(words(a) for a in aliases)
        return [r for r in result if r]

    def find(self, text: Any) -> tuple[dict[str, str] | None, int]:
        """Version 58: the command said or typed, also inside a longer sentence (see the module docstring), and how many
        other non-filler words the sentence has. (None, 0) = no command. An exact `match` always wins."""
        exact = self.match(text)
        if exact is not None:
            return exact, 0
        tokens = words(text)
        if not tokens:
            return None, 0
        best: tuple[tuple[int, int, int], dict[str, str], int, int] | None = None
        for entry in self.entries:
            for phrase in self.phrases(entry):
                n = len(phrase)
                for i in range(len(tokens) - n + 1):
                    if tokens[i:i + n] != phrase:
                        continue
                    before = tokens[max(0, i - NEGATION_WINDOW):i]
                    after = tokens[i + n:i + n + 2]
                    if any(w in NEGATIONS for w in before) or "nicht" in after:
                        continue
                    rank = (n, len(" ".join(phrase)), i)
                    if best is None or rank > best[0]:
                        best = (rank, entry, i, n)
        if best is None:
            return None, 0
        _, entry, i, n = best
        rest = [w for w in tokens[:i] + tokens[i + n:] if w not in FILLERS]
        return entry, len(rest)

    @staticmethod
    def resolve(entry: dict[str, str], pose_names: list[str]) -> str | None:
        """The character's pose that the command links to (its real name), or None if there is none. A pose file path
        (Add Pose since version 42, chosen in VaM's file browser) is its own pose."""
        if is_pose_path(entry["pose"]):
            return entry["pose"]
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
