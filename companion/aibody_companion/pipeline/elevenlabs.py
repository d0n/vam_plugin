"""ElevenLabs text to speech (REST), a swappable TextToSpeech adapter.

Documented endpoint (elevenlabs.io/docs, checked 17.11.2026):
  POST {base}/text-to-speech/{voice_id}?output_format=pcm_24000
  header xi-api-key: <key>; body {"text", "model_id"[, "language_code"]}; answer = audio bytes
  https://elevenlabs.io/docs/api-reference/text-to-speech/convert
output_format pcm_* is raw 16-bit PCM, wrapped into a WAV here (VaM plays WAV; pcm_44100 and
pcm_48000 need a Pro subscription according to the docs). Key: ELEVENLABS_API_KEY or
ai.elevenlabs.key_file. Without a key the engine is "nicht konfiguriert" and the app uses the
fallback TTS.

Tested against a fake server only. TODO(verify): run once with the real key.
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Any

from .http import ApiError, HttpClient
from .tts import write_audio

ENV_KEY = "ELEVENLABS_API_KEY"


class ElevenLabsTts:
    service = "ElevenLabs"

    def __init__(self, settings: dict[str, Any], key: str | None, http: HttpClient | None = None,
                 language: str = "auto"):
        self.settings = settings
        self.key = key
        self.http = http or HttpClient()
        self.language = language
        self.base_url = str(settings.get("base_url") or "https://api.elevenlabs.io/v1").rstrip("/")
        self.timeout = float(settings.get("timeout_s") or 60.0)
        self.output_format = str(settings.get("output_format") or "pcm_24000")
        self.sample_rate = int(self.output_format.split("_")[1])

    @property
    def configured(self) -> bool:
        return bool(self.key)

    def synthesize(self, text: str, out_path: Path) -> float:
        if not self.key:
            raise ApiError(self.service, 0, "nicht konfiguriert (kein API-Key)")
        voice_id = urllib.parse.quote(str(self.settings.get("voice_id") or ""), safe="")
        if not voice_id:
            raise ApiError(self.service, 0, "ai.elevenlabs.voice_id is empty")
        model_id = str(self.settings.get("model_id") or "eleven_multilingual_v2")
        payload: dict[str, Any] = {"text": text, "model_id": model_id}
        # The docs: language_code is not supported by the multilingual_v2 models.
        if self.language and self.language != "auto" and "multilingual_v2" not in model_id:
            payload["language_code"] = self.language
        url = f"{self.base_url}/text-to-speech/{voice_id}?output_format={self.output_format}"
        body, ctype = self.http.post_json(self.service, url, {"xi-api-key": self.key, "Accept": "audio/*"},
                                           payload, self.timeout)
        if not body:
            raise ApiError(self.service, 200, "TTS answer is empty")
        if "json" in ctype.lower():
            detail = body[:200].decode("utf-8", "replace")
            raise ApiError(self.service, 200, "TTS answered JSON instead of audio: " + detail)
        return write_audio(body, self.sample_rate, out_path)
