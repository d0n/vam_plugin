"""Turns a streamed LLM answer into speakable sentences, so TTS can start on the first one.

The model may begin its answer with a tag like <<happy nod>> (expression, optional gesture);
StreamParser strips it and reports it as a Directive. Expressions and gestures are existing
protocol commands; nothing else is derived from the text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Words before a period that do not end a sentence (lower case, without the period).
ABBREVIATIONS = {
    "z.b", "b", "bzw", "usw", "ca", "dr", "nr", "str", "etc", "vgl", "evtl", "ggf", "inkl", "u.a", "d.h",
    "mr", "mrs", "ms", "prof", "st", "e.g", "i.e", "vs", "jr", "sr", "no",
}
_END = re.compile(r"([.!?…]+)([\"'»«”“)\]]*)(\s+)")
_TAG = re.compile(r"<<([^<>]{0,80})>>")
MAX_CHARS = 240  # longer runs without a sentence end are cut at a comma or space


@dataclass
class Directive:
    expression: str | None = None
    gesture: str | None = None


def _clean(text: str) -> str:
    text = _TAG.sub(" ", text).replace("*", "")
    return re.sub(r"\s+", " ", text).strip()


class SentenceSplitter:
    def __init__(self) -> None:
        self._buf = ""

    def feed(self, delta: str) -> list[str]:
        self._buf += delta
        out: list[str] = []
        start = 0
        for m in _END.finditer(self._buf):
            candidate = self._buf[start:m.end(2)]
            words = candidate[: m.start(1) - start].split()
            last = words[-1].lower().rstrip(".") if words else ""
            if m.group(1) == "." and (last in ABBREVIATIONS or (len(last) == 1 and last.isalpha())):
                continue
            sentence = _clean(candidate)
            if sentence:
                out.append(sentence)
            start = m.end()
        self._buf = self._buf[start:]
        while len(self._buf) > MAX_CHARS:
            cut = max(self._buf.rfind(", ", 0, MAX_CHARS), self._buf.rfind(" ", 0, MAX_CHARS))
            if cut <= 0:
                cut = MAX_CHARS
            piece = _clean(self._buf[:cut + 1])
            if piece:
                out.append(piece)
            self._buf = self._buf[cut + 1:]
        return out

    def flush(self) -> list[str]:
        rest = _clean(self._buf)
        self._buf = ""
        return [rest] if rest else []


class StreamParser:
    """feed() text deltas, get Directive / sentence items; finish() at the end of the stream."""

    def __init__(self, expressions: list[str], gestures: list[str]):
        self._expressions = {e.lower(): e for e in expressions}
        self._gestures = {g.lower(): g for g in gestures}
        self._head = ""
        self._head_done = False
        self._splitter = SentenceSplitter()

    def _parse_tag(self, body: str) -> Directive | None:
        d = Directive()
        for token in re.split(r"[\s,|/]+", body.strip().lower()):
            if token in self._expressions and d.expression is None:
                d.expression = self._expressions[token]
            elif token in self._gestures and d.gesture is None:
                d.gesture = self._gestures[token]
        return d if (d.expression or d.gesture) else None

    def feed(self, delta: str) -> list[object]:
        if self._head_done:
            return list(self._splitter.feed(delta))
        self._head += delta
        stripped = self._head.lstrip()
        if not stripped:
            return []
        items: list[object] = []
        if stripped.startswith("<<"):
            end = stripped.find(">>")
            if end < 0 and len(stripped) < 90:
                return []  # tag not complete yet
            if end >= 0:
                directive = self._parse_tag(stripped[2:end])
                if directive:
                    items.append(directive)
                stripped = stripped[end + 2:]
            else:
                stripped = stripped.replace("<<", "")  # not a tag after all
        elif "<<".startswith(stripped):
            return []  # a single "<" so far
        self._head_done = True
        items.extend(self._splitter.feed(stripped))
        return items

    def finish(self) -> list[object]:
        items: list[object] = []
        if not self._head_done:
            items.extend(self.feed(""))
            if not self._head_done:  # stream ended inside an unfinished tag
                self._head_done = True
                items.extend(self._splitter.feed(self._head.replace("<<", "")))
        items.extend(self._splitter.flush())
        return items
