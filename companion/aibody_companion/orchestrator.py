"""Ties transport, echo gate, VAD, STT, LLM and TTS together."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from . import protocol
from .audio import EchoGate, EnergyVad, SegmenterConfig, UtteranceSegmenter
from .config import Config
from .pipeline import LanguageModel, SpeechToText, TextToSpeech
from .transport import Transport

log = logging.getLogger(__name__)


class Companion:
    def __init__(
        self,
        config: Config,
        transport: Transport,
        stt: SpeechToText,
        llm: LanguageModel,
        tts: TextToSpeech,
        gate: EchoGate | None = None,
    ):
        self.cfg = config
        self.transport = transport
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.gate = gate or EchoGate(tail_s=config.echo_tail_s)
        self.segmenter = UtteranceSegmenter(
            EnergyVad(ratio=config.vad_ratio, min_rms=config.vad_min_rms),
            SegmenterConfig(
                sample_rate=config.sample_rate,
                frame_ms=config.frame_ms,
                start_ms=config.start_ms,
                end_silence_ms=config.end_silence_ms,
                max_utterance_ms=config.max_utterance_ms,
            ),
        )
        self.history: list[dict[str, str]] = []
        self.body_info: dict[str, Any] = {}  # last ready/heartbeat from the plugin
        self._audio_files: list[Path] = []

    # -- events from the body ------------------------------------------------------------

    def process_events(self) -> list[dict[str, Any]]:
        events = self.transport.poll_events()
        for event in events:
            self.gate.on_event(event)
            type_ = event.get("type")
            if type_ in ("ready", "heartbeat"):
                if type_ == "ready":
                    log.info("Body ready: atom=%s plugin=%s", event.get("atom"), event.get("plugin_version"))
                self.body_info = event
            elif type_ == "error":
                log.warning("Body error (%s): %s", event.get("code"), event.get("message"))
            else:
                log.debug("event: %s", event)
        return events

    # -- input ---------------------------------------------------------------------------

    def handle_audio_frame(self, frame: bytes) -> str | None:
        """Feed one microphone frame. Returns recognized text when an utterance finished."""
        if not self.gate.is_open:
            # The body is talking: whatever the mic hears now is (mostly) our own voice.
            if self.segmenter.in_speech:
                self.segmenter.reset()
            return None
        utterance = self.segmenter.push(frame)
        if utterance is None:
            return None
        text = self.stt.transcribe(utterance, self.cfg.sample_rate).strip()
        log.info("Heard: %r (%.1fs)", text, len(utterance) / 2 / self.cfg.sample_rate)
        if text:
            self.handle_user_text(text)
        return text

    def handle_user_text(self, text: str) -> None:
        # TODO: run LLM + TTS on a worker thread so events keep flowing during long replies.
        self.history.append({"role": "user", "content": text})
        reply = self.llm.reply(text, self.history)
        self.history.append({"role": "assistant", "content": reply.say})

        if reply.expression:
            self.send(protocol.make_command("expression", name=reply.expression, intensity=1.0, blend=0.4))
        if reply.gesture:
            self.send(protocol.make_command("gesture", name=reply.gesture))
        if reply.say:
            self.say(reply.say)

    # -- output --------------------------------------------------------------------------

    def say(self, text: str) -> str:
        utterance_id = protocol.new_id("utt")
        name = f"{utterance_id}.wav"
        duration = self.tts.synthesize(text, self.cfg.audio_abs_path(name))
        self._track_audio_file(self.cfg.audio_abs_path(name))
        self.gate.on_speak_sent(utterance_id, duration)
        self.send(protocol.make_command("speak", id_=utterance_id, audio=self.cfg.audio_rel_path(name), text=text))
        log.info("Say (%.1fs): %s", duration, text)
        return utterance_id

    def send(self, command: dict[str, Any]) -> None:
        self.transport.send(command)

    def _track_audio_file(self, path: Path) -> None:
        self._audio_files.append(path)
        while len(self._audio_files) > self.cfg.keep_audio_files:
            old = self._audio_files.pop(0)
            try:
                old.unlink(missing_ok=True)
            except OSError:
                pass  # still loaded by VaM; try again later is not worth it
