"""Ollama language model (local, version 29): a model running on your own computer, no key, no cloud.

Documented endpoint (Ollama API, github.com/ollama/ollama/blob/main/docs/api.md):
  POST {base}/api/chat  {"model", "messages": [{"role", "content"}], "stream": true, "options": {...},
                         "keep_alive"}  ->  one JSON object per line (NDJSON):
  {"message": {"role": "assistant", "content": "..."}, "done": false} ... {"done": true, ...}
  an error is {"error": "model 'x' not found"} (HTTP 404).
Ollama keeps no conversation: this class keeps the messages itself (the persona and the style rules
as the system message, the last `max_messages` turns). The answer carries the same leading
<<expression gesture>> tag as the xAI chain (no tool calls: a local model's function calling is too uneven).
Everything here is tested against a fake server only.
TODO(verify): run once against a real Ollama (docs/TESTPROTOKOLL.md T18).
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from .http import ApiError, HttpClient
from .llm import Reply
from .sentences import Directive, StreamParser
from .xai import STYLE_RULES

log = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:11434"


class OllamaLlm:
    service = "Ollama"
    accepts_context = True    # the companion may prefix user turns with the time context
    supports_tools = False    # expressions and gestures come from the <<tag>>, not from function calls

    def __init__(self, settings: dict[str, Any], http: HttpClient | None = None, persona: str = ""):
        self.settings = settings
        self.http = http or HttpClient()
        self.persona = persona
        self.base_url = str(settings.get("base_url") or DEFAULT_URL).rstrip("/")
        self.model = str(settings.get("model") or "llama3.2")
        self.timeout = float(settings.get("timeout_s") or 120.0)
        self.max_messages = max(2, int(settings.get("max_messages") or 40))
        self.messages: list[dict[str, str]] = []
        self.clock: Any = None
        self.first_delta_at: float | None = None

    def reset(self) -> None:
        self.messages = []

    def instructions(self, expressions: list[str], gestures: list[str]) -> str:
        rules = STYLE_RULES.format(expressions=", ".join(expressions) or "neutral", gestures=", ".join(gestures) or "none")
        return (self.persona.strip() + "\n\n" + rules).strip()

    def _options(self) -> dict[str, Any]:
        options: dict[str, Any] = {"num_predict": int(self.settings.get("max_output_tokens") or 400)}
        if self.settings.get("temperature") is not None:
            options["temperature"] = float(self.settings["temperature"])
        return options

    def _payload(self, messages: list[dict[str, str]], stream: bool, options: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": stream, "options": options}
        keep = str(self.settings.get("keep_alive") or "").strip()
        if keep:
            payload["keep_alive"] = keep  # how long the model stays loaded (default of Ollama: 5m)
        return payload

    def _fail(self, error: ApiError) -> ApiError:
        """A clearer message for the two usual problems."""
        if error.status == 0:
            return ApiError(self.service, 0, f"no connection to Ollama at {self.base_url} - is it running "
                                              f"(start the Ollama app or run: ollama serve)? ({error.message})")
        if error.status == 404 and "not found" in error.message.lower():
            return ApiError(self.service, 404, f"model {self.model!r} is not installed - run: ollama pull {self.model}")
        return error

    def stream_text(self, user_text: str, expressions: list[str] | None = None,
                    gestures: list[str] | None = None) -> Iterator[str]:
        system = {"role": "system", "content": self.instructions(expressions or [], gestures or [])}
        turn = {"role": "user", "content": user_text}
        payload = self._payload([system, *self.messages, turn], True, self._options())
        self.first_delta_at = None
        answer: list[str] = []
        try:
            resp = self.http.open(self.service, "POST", f"{self.base_url}/api/chat",
                                  {"Content-Type": "application/json"}, json.dumps(payload).encode("utf-8"), self.timeout)
        except ApiError as e:
            raise self._fail(e) from None
        with resp:
            for raw in iter(resp.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("error"):
                    raise self._fail(ApiError(self.service, 404 if "not found" in str(msg["error"]).lower() else 200,
                                              str(msg["error"])[:300]))
                piece = (msg.get("message") or {}).get("content") if isinstance(msg.get("message"), dict) else None
                if isinstance(piece, str) and piece:
                    if self.first_delta_at is None and self.clock is not None:
                        self.first_delta_at = self.clock()
                    answer.append(piece)
                    yield piece
                if msg.get("done"):
                    break
        text = "".join(answer).strip()
        if text:  # only a real answer enters the conversation
            self.messages += [turn, {"role": "assistant", "content": text}]
            del self.messages[:-self.max_messages]

    def stream(self, user_text: str, history: list[dict[str, str]], expressions: list[str],
               gestures: list[str]) -> Iterator[object]:
        """Yields a Directive (if the answer starts with a tag) and sentences."""
        parser = StreamParser(expressions, gestures)
        for delta in self.stream_text(user_text, expressions, gestures):
            yield from parser.feed(delta)
        yield from parser.finish()

    def reply(self, user_text: str, history: list[dict[str, str]]) -> Reply:
        reply = Reply()
        sentences = []
        for item in self.stream(user_text, history, [], []):
            if isinstance(item, Directive):
                reply.expression, reply.gesture = item.expression, item.gesture
            else:
                sentences.append(str(item))
        reply.say = " ".join(sentences)
        return reply

    def complete(self, instructions: str, text: str, max_tokens: int = 2000, timeout: float | None = None) -> str:
        """One plain request without a conversation (memory summaries): stays on this computer."""
        messages = [{"role": "system", "content": instructions}, {"role": "user", "content": text}]
        payload = self._payload(messages, False, {"num_predict": max_tokens, "temperature": 0.2})
        try:
            body, _ = self.http.post_json(self.service, f"{self.base_url}/api/chat", {}, payload,
                                          timeout or self.timeout)
        except ApiError as e:
            raise self._fail(e) from None
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(self.service, 200, "answer is not JSON") from None
        message = data.get("message") if isinstance(data, dict) else None
        return str(message.get("content") or "") if isinstance(message, dict) else ""
