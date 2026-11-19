"""Emotions for the AI's face when the AI itself sends none (version 27).

Three small jobs, all in the app, all using the plugin's existing "expression" command:

  * Fallback: the AI may call `express` / start with a tag, but often does not. For every spoken sentence
    that came without an AI-chosen expression in the same answer, an expression is derived from the words
    (keyword rules, German and English) and sent right before the speech. Only expressions the plugin
    lists are used; nothing matches = no change. The AI always wins: once it chose an expression in an
    answer, the fallback stays out of that answer.
  * Fade: some seconds after the last speech (or the last expression) the face blends back to "neutral".
  * Listening: while the user talks, a very small "listening" expression (inner brows up) is shown, if the
    plugin has that preset (it is not offered to the AI).

Settings: config.json ai.emotion {fallback, fade, fade_after_s, fade_seconds, listening}.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

NEUTRAL = "neutral"
LISTENING = "listening"
INTERNAL_EXPRESSIONS = (LISTENING,)  # shown by the app only, never offered to the AI

# emotion -> (word beginnings, whole words / phrases). Lower case; "ä/ö/ü/ß" as written.
RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "happy": (
        ("freu", "froh", "fröhlich", "glücklich", "wunderbar", "herrlich", "fantastisch", "großartig", "genial",
         "klasse", "prima", "lach", "lustig", "spaß", "wonderful", "delight", "fantastic", "awesome", "glad",
         "happy", "funny", "laugh", "cheer", "excit", "begeister"),
        ("haha", "hehe", "lol", "yay", "super", "toll", "great", "love", "fun", "nice to meet you",
         "freut mich", "gerne", "gern geschehen", "my pleasure", "wie schön"),
    ),
    "sad": (
        ("traurig", "bedaure", "vermiss", "einsam", "weine", "betrübt", "unglücklich", "heartbreak", "lonely",
         "regret", "sorrow", "gestorben", "verlust"),
        ("leider", "schade", "sorry", "unfortunately", "sad", "tut mir leid", "miss you", "pity", "passed away"),
    ),
    "angry": (
        ("wütend", "ärger", "sauer", "genervt", "unverschämt", "furious", "annoy", "outrag", "hassen", "hasse"),
        ("nervt", "verdammt", "frechheit", "angry", "damn", "hate", "hass", "ugh"),
    ),
    "surprised": (
        ("überrasch", "unglaublich", "unbelievable", "astonish"),
        ("wow", "whoa", "oh my", "no way", "huch", "nanu", "ups", "krass", "echt jetzt", "wirklich?", "really?",
         "ehrlich?", "oh!"),
    ),
    "thinking": (
        ("überleg", "frage mich", "wonder", "nachdenk"),
        ("hmm", "hm", "mal sehen", "let me think", "let's see", "maybe", "perhaps", "vielleicht", "not sure",
         "ich weiß nicht", "gute frage", "good question", "interessante frage", "tja"),
    ),
}
PRIORITY = ("surprised", "angry", "sad", "happy", "thinking")  # tie-break
# the preset names an emotion may be shown with (first one the plugin has wins)
CANDIDATES = {"happy": ("happy", "smile"), "sad": ("sad",), "angry": ("angry",),
              "surprised": ("surprised",), "thinking": ("thinking",)}

_COMPILED: dict[str, re.Pattern[str]] = {}


def _compile() -> None:
    for emotion, (starts, words) in RULES.items():
        parts = [r"(?<!\w)" + re.escape(s) + r"\w*" for s in starts]
        parts += [r"(?<!\w)" + re.escape(w) + r"(?!\w)" if w[-1].isalnum() else r"(?<!\w)" + re.escape(w)
                  for w in words]
        _COMPILED[emotion] = re.compile("|".join(parts), re.IGNORECASE)


_compile()


def classify(text: str) -> str | None:
    """The emotion a sentence expresses ("happy", "sad", "angry", "surprised", "thinking") or None."""
    t = " ".join(str(text).lower().split())
    if not t:
        return None
    scores = {e: len(rx.findall(t)) for e, rx in _COMPILED.items()}
    if "?!" in t or "!?" in t:
        scores["surprised"] += 1
    if t.endswith("...") or t.endswith("…"):
        scores["thinking"] += 1
    best = max(scores.values())
    if best <= 0:
        return None
    return next(e for e in PRIORITY if scores[e] == best)


def pick_expression(emotion: str | None, available: Iterable[str]) -> str | None:
    """The name of the plugin's preset for an emotion, or None if it has none."""
    if not emotion:
        return None
    have = {str(a).lower(): str(a) for a in available}
    for name in CANDIDATES.get(emotion, ()):
        if name in have:
            return have[name]
    return None


def infer_expression(text: str, available: Iterable[str]) -> str | None:
    return pick_expression(classify(text), available)


def offered(names: Iterable[str]) -> list[str]:
    """The expression names the AI may use (without the app's internal ones)."""
    return [str(n) for n in names if str(n).lower() not in INTERNAL_EXPRESSIONS]


class EmotionDirector:
    """State of the face as the app sees it, and the decisions: fallback, fade, listening.
    The app calls note_sent() for every expression command it sends and asks for the rest."""

    FALLBACK_INTENSITY = 0.85  # a little below an expression the AI chose itself (1.0)
    FALLBACK_BLEND_S = 0.5
    LISTENING_BLEND_S = 0.7

    def __init__(self, cfg: dict[str, Any], clock: Callable[[], float]):
        self._clock = clock
        self.fallback = True
        self.fade = True
        self.listening = True
        self.fade_after_s = 6.0
        self.fade_seconds = 2.5
        self.current = NEUTRAL  # last expression the app sent (what the face shows, as far as the app knows)
        self._answer = 0
        self._ai_answer = -1  # the answer in which the AI chose an expression
        self._activity = clock()
        self._user_speaking = False
        self.configure(cfg)

    def configure(self, cfg: dict[str, Any]) -> None:
        self.fallback = bool(cfg.get("fallback", True))
        self.fade = bool(cfg.get("fade", True))
        self.listening = bool(cfg.get("listening", True))
        self.fade_after_s = float(cfg.get("fade_after_s", 6.0))
        self.fade_seconds = float(cfg.get("fade_seconds", 2.5))

    @property
    def active(self) -> bool:
        return self.current.lower() != NEUTRAL

    def begin_answer(self) -> None:
        self._answer += 1

    def note_ai_expression(self) -> None:
        self._ai_answer = self._answer

    def note_sent(self, name: str) -> None:
        self.current = str(name or NEUTRAL)
        self._activity = self._clock()

    def note_speech(self) -> None:
        self._activity = self._clock()

    # -- decisions -------------------------------------------------------------------------

    def for_speech(self, text: str, available: Iterable[str]) -> tuple[str, float, float] | None:
        """(expression, intensity, blend seconds) to send before a spoken sentence, or None."""
        names = offered(available)
        if self._ai_answer == self._answer:
            return None  # the AI chose its expression in this answer
        if self.fallback:
            name = infer_expression(text, names)
            if name and name != self.current:
                return name, self.FALLBACK_INTENSITY, self.FALLBACK_BLEND_S
            if name:
                return None
        if self.current.lower() == LISTENING and any(n.lower() == NEUTRAL for n in names):
            return NEUTRAL, 1.0, self.LISTENING_BLEND_S  # no emotion found: the listening brows go down
        return None

    def user_speech(self, speaking: bool, available: Iterable[str]) -> tuple[str, float, float] | None:
        """Called every tick with "the user is talking": the small listening expression on a rising edge."""
        started = speaking and not self._user_speaking
        self._user_speaking = speaking
        if speaking:
            self._activity = self._clock()
        if (started and self.listening and not self.active
                and any(str(a).lower() == LISTENING for a in available)):
            return LISTENING, 1.0, self.LISTENING_BLEND_S
        return None

    def fade_due(self, busy: bool) -> bool:
        """True once: the face has shown something for fade_after_s without any activity."""
        now = self._clock()
        if busy:
            self._activity = now
            return False
        if not (self.fade and self.active):
            return False
        return now - self._activity >= self.fade_after_s
