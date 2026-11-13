"""Language model: turns what the user said into what the body says and does.

The model is asked to answer with JSON like
  {"say": "Hello!", "expression": "happy", "gesture": "nod"}
parse_reply() also accepts plain text, so any chat model works from day one.

TODO: implement a real LanguageModel (local llama.cpp / Ollama server, or a cloud API).
Read API keys from environment variables; never commit them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

SYSTEM_PROMPT = """You are an embodied character in a 3D scene. Answer briefly, as spoken language.
Reply with a JSON object: {"say": "<what you say>", "expression": "<one of: %(expressions)s>",
"gesture": "<optional, one of: %(gestures)s>"}. Omit fields you do not need."""


@dataclass
class Reply:
    say: str = ""
    expression: str | None = None
    gesture: str | None = None
    extra: dict = field(default_factory=dict)


class LanguageModel(Protocol):
    def reply(self, user_text: str, history: list[dict[str, str]]) -> Reply: ...


def parse_reply(raw: str) -> Reply:
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return Reply(say=raw)
        if isinstance(data, dict):
            known = {"say", "expression", "gesture"}
            return Reply(
                say=str(data.get("say", "")),
                expression=data.get("expression") or None,
                gesture=data.get("gesture") or None,
                extra={k: v for k, v in data.items() if k not in known},
            )
    return Reply(say=raw)


class EchoLlm:
    """Mock model: repeats the input and picks an expression from simple keywords."""

    def reply(self, user_text: str, history: list[dict[str, str]]) -> Reply:
        lower = user_text.lower()
        expression = "neutral"
        gesture = None
        if any(w in lower for w in ("hello", "hi", "hallo", "danke", "thanks")):
            expression, gesture = "happy", "nod"
        elif any(w in lower for w in ("no", "nein", "sad", "traurig")):
            expression, gesture = "sad", "shake"
        elif "?" in user_text:
            expression, gesture = "thinking", "tilt"
        return Reply(say=f"You said: {user_text}", expression=expression, gesture=gesture)
