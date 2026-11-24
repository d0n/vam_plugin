"""Version 55 (Don, 23.11.2026): mute / unmute the AI by voice, without any character name.

MUTE   ("shut up", "halt's Maul", ...): the body stops talking at once, the queued speech is dropped, and from then on
       everything heard is ignored (no AI request, no answer, no pose or gesture from speech).
UNMUTE ("sprich mit mir", "speak again", "go ahead talking"): listening and answering resume. Only looked for while muted.

Matching is local (before any AI call) and tolerant: case, punctuation and apostrophes do not matter, a phrase may be
spoken inside a longer utterance (another person may talk on the same headset), and the words may be written together
by the speech recognition ("shutup", "haltsmaul"). The utterance with the command is never sent to the AI.
"""
from __future__ import annotations

import re
import unicodedata

# The phrases as spoken; normalize() turns them into the form they are matched in.
MUTE_PHRASES = (
    "shut up",
    "halt's Maul", "halts Maul", "halt das Maul", "halt dein Maul",
    "halt die Klappe", "halt deine Klappe",
    "sei still", "seid still", "sei stil",
)
UNMUTE_PHRASES = (
    "sprich mit mir", "sprich wieder mit mir",
    "speak again",
    "go ahead talking", "go ahead and talk", "go ahead, keep talking",
)

_APOSTROPHES = "'\u2019\u2018`\u00b4\u02bc"
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def normalize(text: str) -> list[str]:
    """Lower-case words without punctuation; apostrophes are dropped ("halt's" -> "halts")."""
    text = unicodedata.normalize("NFC", str(text or "")).lower()
    for a in _APOSTROPHES:
        text = text.replace(a, "")
    return [w for w in _NON_WORD.sub(" ", text).replace("_", " ").split() if w]


def _keys(phrases: tuple[str, ...]) -> list[str]:
    return sorted({"".join(normalize(p)) for p in phrases}, key=len, reverse=True)


_MUTE_KEYS = _keys(MUTE_PHRASES)
_UNMUTE_KEYS = _keys(UNMUTE_PHRASES)


def _last_match(words: list[str], keys: list[str]) -> int:
    """End position (in words) of the last phrase found as consecutive whole words, else -1."""
    best = -1
    for i in range(len(words)):
        joined = ""
        for j in range(i, min(len(words), i + 6)):
            joined += words[j]
            if joined in keys:
                best = max(best, j)
            if len(joined) > len(keys[0]):
                break
    return best


def detect(text: str, muted: bool) -> str | None:
    """'mute', 'unmute' or None for what was heard. Unmute phrases count only while muted; when both kinds are in one
    utterance, the later one wins."""
    words = normalize(text)
    if not words:
        return None
    mute_at = _last_match(words, _MUTE_KEYS)
    unmute_at = _last_match(words, _UNMUTE_KEYS) if muted else -1
    if mute_at < 0 and unmute_at < 0:
        return None
    return "unmute" if unmute_at > mute_at else "mute"
