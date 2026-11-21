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
# Version 36 (latency): the FIRST piece of an answer may end at a clause mark (", " "; " ": " " - ") once it has
# this many characters, so text to speech starts before the model has finished the whole first sentence (and the
# first, shorter piece is synthesized faster). Later pieces stay whole sentences (natural prosody).
FIRST_CLAUSE_MIN = 28
_CLAUSE = re.compile(r"[,;:]\s|\s[-–—]\s")


@dataclass
class InlineToolCall:
    """A function call the model wrote INTO its text ("<tool_call>{"name": ..., "parameters": {...}}</tool_call>",
    seen in Leon's companion.log of 21.11.2026: it was spoken aloud). The caller runs it like a real tool call;
    it is never spoken."""
    name: str
    arguments: str


_TOOL_OPEN = "<tool_call>"
_TOOL_CLOSE = "</tool_call>"
TOOL_TEXT_MAX = 4000  # an opening tag without its end after this many characters is dropped as text


def parse_inline_tool_call(body: str) -> InlineToolCall | None:
    """{"name": "express", "parameters"|"arguments": {...}} -> InlineToolCall; None if it is not such JSON."""
    import json
    try:
        data = json.loads(body.strip())
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("name"), str):
        return None
    args = data.get("parameters", data.get("arguments", {}))
    if isinstance(args, str):
        return InlineToolCall(data["name"], args)
    return InlineToolCall(data["name"], json.dumps(args if isinstance(args, dict) else {}, ensure_ascii=False))


class ToolTextFilter:
    """Takes <tool_call>...</tool_call> blocks out of streamed text (also when split over many deltas); returns the
    speakable text and the calls found. A possible start of a tag at the end of a delta is held back."""

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, delta: str) -> tuple[str, list[InlineToolCall]]:
        self._buf += delta
        out: list[str] = []
        calls: list[InlineToolCall] = []
        while True:
            start = self._buf.find(_TOOL_OPEN)
            if start < 0:
                keep = 0
                for n in range(min(len(_TOOL_OPEN) - 1, len(self._buf)), 0, -1):
                    if _TOOL_OPEN.startswith(self._buf[-n:]):
                        keep = n
                        break
                out.append(self._buf[:len(self._buf) - keep])
                self._buf = self._buf[len(self._buf) - keep:]
                break
            out.append(self._buf[:start])
            end = self._buf.find(_TOOL_CLOSE, start)
            if end < 0:
                if len(self._buf) - start > TOOL_TEXT_MAX:
                    self._buf = self._buf[start + len(_TOOL_OPEN):]  # never closed: drop the tag, keep the words
                    continue
                self._buf = self._buf[start:]
                break
            call = parse_inline_tool_call(self._buf[start + len(_TOOL_OPEN):end])
            if call is not None:
                calls.append(call)
            self._buf = self._buf[end + len(_TOOL_CLOSE):]
        return "".join(out), calls

    def flush(self) -> str:
        rest = self._buf
        self._buf = ""
        start = rest.find(_TOOL_OPEN)
        return rest[:start] if start >= 0 else rest


@dataclass
class Directive:
    expression: str | None = None
    gesture: str | None = None


def _clean(text: str) -> str:
    text = _TAG.sub(" ", text).replace("*", "")
    return re.sub(r"\s+", " ", text).strip()


class SentenceSplitter:
    def __init__(self, early_first_clause: bool = True) -> None:
        self._buf = ""
        self._early = early_first_clause
        self._emitted = 0

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
        if self._early and not out and self._emitted == 0:
            for m in _CLAUSE.finditer(self._buf):
                if m.start() < FIRST_CLAUSE_MIN:
                    continue
                piece = _clean(self._buf[:m.start() + 1])
                if len(piece) >= FIRST_CLAUSE_MIN and "<<" not in self._buf[:m.start()]:
                    out.append(piece)
                    self._buf = self._buf[m.end():]
                break
        while len(self._buf) > MAX_CHARS:
            cut = max(self._buf.rfind(", ", 0, MAX_CHARS), self._buf.rfind(" ", 0, MAX_CHARS))
            if cut <= 0:
                cut = MAX_CHARS
            piece = _clean(self._buf[:cut + 1])
            if piece:
                out.append(piece)
            self._buf = self._buf[cut + 1:]
        self._emitted += len(out)
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
        self._tools = ToolTextFilter()

    def _parse_tag(self, body: str) -> Directive | None:
        d = Directive()
        for token in re.split(r"[\s,|/]+", body.strip().lower()):
            if token in self._expressions and d.expression is None:
                d.expression = self._expressions[token]
            elif token in self._gestures and d.gesture is None:
                d.gesture = self._gestures[token]
        return d if (d.expression or d.gesture) else None

    def feed(self, delta: str) -> list[object]:
        text, calls = self._tools.feed(delta)
        items: list[object] = list(calls)
        items.extend(self._feed_text(text))
        return items

    def _feed_text(self, delta: str) -> list[object]:
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
        rest = self._tools.flush()
        if rest:
            items.extend(self._feed_text(rest))
        if not self._head_done:
            items.extend(self._feed_text(""))
            if not self._head_done:  # stream ended inside an unfinished tag
                self._head_done = True
                items.extend(self._splitter.feed(self._head.replace("<<", "")))
        items.extend(self._splitter.flush())
        return items
