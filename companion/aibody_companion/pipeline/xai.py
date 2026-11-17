"""xAI engines: speech to text, language model (Grok) and text to speech.

Documented endpoints (docs.x.ai, checked 17.11.2026):
  * STT  POST {base}/stt        multipart/form-data, file last; answer {"text", "language", ...}
         https://docs.x.ai/developers/model-capabilities/audio/speech-to-text
  * LLM  POST {base}/responses  {"model", "input", "instructions", "previous_response_id",
         "stream": true} -> Server-Sent Events
         https://docs.x.ai/developers/model-capabilities/text/generate-text
         https://docs.x.ai/developers/rest-api-reference/inference/responses
  * TTS  POST {base}/tts        {"text", "voice_id", "language", "output_format": {"codec",
         "sample_rate"}} -> raw audio bytes
         https://docs.x.ai/developers/model-capabilities/audio/text-to-speech
Authentication: "Authorization: Bearer <key>", key from XAI_API_KEY or ai.xai.key_file.

Not used: the realtime speech-to-speech WebSocket (wss://api.x.ai/v1/realtime) and the
streaming STT/TTS WebSockets; they would bypass this STT -> LLM -> TTS pipeline and the file
transport, and the standard library has no WebSocket client.

Everything here is tested against a fake server only (no key was available).
TODO(verify): run once against the real API (see docs/CONFIG.md, "Real API check").
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .http import ApiError, HttpClient, iter_sse
from .llm import Reply
from .sentences import Directive, StreamParser
from .tts import pcm_to_wav_bytes, write_audio

log = logging.getLogger(__name__)

ENV_KEY = "XAI_API_KEY"

STYLE_RULES = """Your words are spoken aloud by a 3D character with a voice: answer in short, natural spoken
sentences. No markdown, no lists, no emojis, no stage directions.
You may start your answer with ONE tag in double angle brackets naming your facial expression and
optionally a gesture, for example <<happy nod>>. Expressions: {expressions}. Gestures: {gestures}.
The tag is not spoken."""


class _XaiBase:
    service = "xAI"

    def __init__(self, settings: dict[str, Any], key: str | None, http: HttpClient | None = None):
        self.settings = settings
        self.key = key
        self.http = http or HttpClient()
        self.base_url = str(settings.get("base_url") or "https://api.x.ai/v1").rstrip("/")
        self.timeout = float(settings.get("timeout_s") or 60.0)

    @property
    def configured(self) -> bool:
        return bool(self.key)

    def _headers(self) -> dict[str, str]:
        if not self.key:
            raise ApiError(self.service, 0, "nicht konfiguriert (kein API-Key)")
        return {"Authorization": f"Bearer {self.key}"}


class XaiStt(_XaiBase):
    """Batch transcription of one utterance (the companion's VAD cuts the utterances)."""

    def __init__(self, settings: dict[str, Any], key: str | None, http: HttpClient | None = None,
                 language: str = "auto"):
        super().__init__(settings, key, http)
        self.language = language

    def transcribe(self, pcm16: bytes, sample_rate: int) -> str:
        fields = [("model", str(self.settings.get("stt_model") or "grok-voice-transcribe-2.0"))]
        if self.language and self.language != "auto":
            fields.append(("language", self.language))
        body = self.http.post_multipart(
            self.service, f"{self.base_url}/stt", self._headers(), fields,
            "file", "utterance.wav", "audio/wav", pcm_to_wav_bytes(pcm16, sample_rate), self.timeout,
        )
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(self.service, 200, "STT answer is not JSON") from None
        return str(data.get("text") or "").strip() if isinstance(data, dict) else ""


def _output_text(response: dict[str, Any]) -> str:
    """Text of a complete Responses API object (output[].content[].text of type output_text)."""
    parts = []
    for item in response.get("output") or []:
        if isinstance(item, dict) and item.get("type") == "message":
            for c in item.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "output_text":
                    parts.append(str(c.get("text") or ""))
    return "".join(parts)


class XaiLlm(_XaiBase):
    """Grok over the Responses API with streaming. The persona goes into `instructions` on the
    first request; later requests continue with `previous_response_id` (the docs say
    `instructions` cannot be combined with it - the stored system prompt is reused)."""

    def __init__(self, settings: dict[str, Any], key: str | None, http: HttpClient | None = None,
                 persona: str = ""):
        super().__init__(settings, key, http)
        self.persona = persona
        self.model = str(settings.get("model") or "grok-4.7")
        self.max_output_tokens = int(settings.get("max_output_tokens") or 400)
        self.previous_response_id: str | None = None

    def reset(self) -> None:
        """Starts a new conversation (next request sends the persona again)."""
        self.previous_response_id = None

    def instructions(self, expressions: list[str], gestures: list[str]) -> str:
        rules = STYLE_RULES.format(expressions=", ".join(expressions) or "neutral",
                                   gestures=", ".join(gestures) or "none")
        return (self.persona.strip() + "\n\n" + rules).strip()

    def _payload(self, user_text: str, expressions: list[str], gestures: list[str]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": "user", "content": user_text}],
            "stream": True,
            "max_output_tokens": self.max_output_tokens,
        }
        if self.previous_response_id:
            payload["previous_response_id"] = self.previous_response_id
        else:
            payload["instructions"] = self.instructions(expressions, gestures)
        return payload

    def stream_text(self, user_text: str, expressions: list[str] | None = None,
                    gestures: list[str] | None = None) -> Iterator[str]:
        """Yields text deltas. Retries once as a new conversation if the stored one is gone."""
        expressions, gestures = expressions or [], gestures or []
        try:
            yield from self._stream_once(self._payload(user_text, expressions, gestures))
        except ApiError as e:
            if self.previous_response_id and e.status in (400, 404):
                log.warning("xAI: conversation %s not usable (%s); starting a new one",
                            self.previous_response_id, e.message)
                self.previous_response_id = None
                yield from self._stream_once(self._payload(user_text, expressions, gestures))
            else:
                raise

    def _stream_once(self, payload: dict[str, Any]) -> Iterator[str]:
        headers = {**self._headers(), "Content-Type": "application/json", "Accept": "text/event-stream"}
        resp = self.http.open(self.service, "POST", f"{self.base_url}/responses", headers,
                              json.dumps(payload).encode("utf-8"), self.timeout)
        with resp:
            ctype = (resp.headers.get("Content-Type", "") if resp.headers else "").lower()
            if "application/json" in ctype:  # server answered without streaming
                data = json.loads(resp.read().decode("utf-8"))
                self.previous_response_id = data.get("id") or self.previous_response_id
                text = _output_text(data)
                if text:
                    yield text
                return
            got_text = False
            # TODO(verify): SSE event names. The docs only say "data-only server-sent events,
            # terminated by data: [DONE]"; the names below are the OpenAI-compatible Responses
            # events (response.created / response.output_text.delta / response.completed).
            for event, data in iter_sse(iter(resp.readline, b"")):
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict):
                    continue
                kind = msg.get("type") or event
                if kind in ("response.created", "response.in_progress", "response.completed"):
                    response = msg.get("response") or {}
                    if isinstance(response, dict) and response.get("id"):
                        self.previous_response_id = response["id"]
                    if kind == "response.completed" and not got_text and isinstance(response, dict):
                        text = _output_text(response)
                        if text:
                            got_text = True
                            yield text
                elif kind == "response.output_text.delta":
                    delta = msg.get("delta")
                    if isinstance(delta, str) and delta:
                        got_text = True
                        yield delta
                elif kind in ("response.failed", "error", "response.error"):
                    err = msg.get("error") or (msg.get("response") or {}).get("error") or msg
                    text = err.get("message") if isinstance(err, dict) else str(err)
                    raise ApiError(self.service, 200, f"stream error: {text}")

    def stream(self, user_text: str, history: list[dict[str, str]], expressions: list[str],
               gestures: list[str]) -> Iterator[object]:
        """Yields a Directive (if the answer starts with a tag) and then sentences."""
        parser = StreamParser(expressions, gestures)
        for delta in self.stream_text(user_text, expressions, gestures):
            yield from parser.feed(delta)
        yield from parser.finish()

    def reply(self, user_text: str, history: list[dict[str, str]]) -> Reply:
        """Non-streaming form of stream() (LanguageModel protocol)."""
        reply = Reply()
        sentences = []
        for item in self.stream(user_text, history, [], []):
            if isinstance(item, Directive):
                reply.expression, reply.gesture = item.expression, item.gesture
            else:
                sentences.append(str(item))
        reply.say = " ".join(sentences)
        return reply


class XaiTts(_XaiBase):
    """POST /v1/tts with codec pcm; the raw 16-bit PCM is wrapped into a WAV for VaM."""

    def __init__(self, settings: dict[str, Any], key: str | None, http: HttpClient | None = None,
                 language: str = "auto"):
        super().__init__(settings, key, http)
        self.language = language or "auto"
        self.sample_rate = int(settings.get("sample_rate") or 24000)

    def synthesize(self, text: str, out_path: Path) -> float:
        payload = {
            "text": text,
            "voice_id": str(self.settings.get("voice") or "eve"),
            "language": self.language,  # required by the API; "auto" detects it
            # TODO(verify): pcm output is mono s16le (docs: "PCM = 16-bit LE").
            "output_format": {"codec": "pcm", "sample_rate": self.sample_rate},
        }
        speed = float(self.settings.get("speed") or 1.0)
        if abs(speed - 1.0) > 1e-6:
            payload["speed"] = speed
        body, ctype = self.http.post_json(self.service, f"{self.base_url}/tts", self._headers(), payload,
                                           self.timeout)
        if not body:
            raise ApiError(self.service, 200, "TTS answer is empty")
        if "json" in ctype.lower():
            detail = body[:200].decode("utf-8", "replace")
            raise ApiError(self.service, 200, "TTS answered JSON instead of audio: " + detail)
        return write_audio(body, self.sample_rate, out_path)
