"""Ties transport, microphone, echo gate, VAD, STT, LLM and TTS together.

Call tick() regularly (every ~20 ms) from one thread: it handles plugin events, pulls
microphone frames, finishes utterances and streams level / state feedback to the plugin.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import protocol
from .audio import (
    EchoGate,
    InputProcessor,
    MicController,
    MicSettings,
    apply_mic_config,
    list_input_devices,
)
from .config import Config
from .pipeline import LanguageModel, SpeechToText, TextToSpeech
from .transport import Transport

log = logging.getLogger(__name__)

LEVEL_INTERVAL_S = 0.2  # mic_level rate (5 Hz)


class Companion:
    def __init__(
        self,
        config: Config,
        transport: Transport,
        stt: SpeechToText,
        llm: LanguageModel,
        tts: TextToSpeech,
        gate: EchoGate | None = None,
        mic: MicController | None = None,
        device_lister: Callable[[], tuple[list[dict[str, Any]], str | None]] = list_input_devices,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.cfg = config
        self.transport = transport
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self._clock = clock
        settings, errors = apply_mic_config(MicSettings(), config.mic)
        for e in errors:
            log.warning("config 'mic': %s", e)
        self.mic_settings = settings
        self.gate = gate or EchoGate(tail_s=settings.echo_tail_s)
        self.input = InputProcessor(settings, self.gate, config.sample_rate, config.frame_ms)
        self.mic = mic  # None = no microphone (text only)
        self._list_devices = device_lister
        self.history: list[dict[str, str]] = []
        self.body_info: dict[str, Any] = {}  # last ready/heartbeat from the plugin
        self._audio_files: list[Path] = []
        self._last_level = 0.0
        self._last_mic_state: dict[str, Any] | None = None
        self._was_connected = False
        if self.mic:
            self.mic.apply(self.mic_settings)

    # -- main loop -----------------------------------------------------------------------

    def tick(self) -> None:
        self.process_events()
        self._watch_connection()
        if self.mic:
            for frame in self.mic.frames():
                utterance = self.input.process(frame)
                if utterance:
                    self.handle_utterance(utterance)
            self._send_level()
        self._send_mic_state_if_changed()

    def _watch_connection(self) -> None:
        connected = self.transport.connected
        if connected != self._was_connected:
            log.info("Plugin %s (link: %s)", "connected" if connected else "disconnected", self.transport.link)
            self._was_connected = connected
            if not connected:
                self.gate.force_open()

    # -- events from the body ------------------------------------------------------------

    def process_events(self) -> list[dict[str, Any]]:
        events = self.transport.poll_events()
        for event in events:
            problems = protocol.validate_event(event)
            if problems:
                log.warning("Ignoring event: %s (%s)", "; ".join(problems), event)
                continue
            self.gate.on_event(event)
            type_ = event.get("type")
            if type_ in ("ready", "heartbeat"):
                if type_ == "ready":
                    log.info("Body ready: atom=%s plugin=%s link=%s", event.get("atom"), event.get("plugin_version"),
                             event.get("link"))
                    self._last_mic_state = None  # make sure the plugin gets a fresh mic_state
                self.body_info = event
            elif type_ == "config":
                self.handle_config(event)
            elif type_ == "ptt":
                self.handle_ptt(bool(event.get("active")))
            elif type_ == "list_devices":
                self.send_devices(event.get("id"))
            elif type_ == "error":
                log.warning("Body error (%s): %s", event.get("code"), event.get("message"))
            else:
                log.debug("event: %s", event)
        return events

    def handle_config(self, event: dict[str, Any]) -> None:
        settings, errors = apply_mic_config(self.mic_settings, event.get("mic"))
        self.mic_settings = settings
        self.input.apply(settings)
        if self.mic:
            self.mic.apply(settings)
        if errors:
            log.warning("Mic config problems: %s", "; ".join(errors))
        log.info("Mic settings: %s", settings.to_dict())
        state = self.mic_state()
        self._last_mic_state = state
        self.send(protocol.make_command(
            "config_ack", reply_to=event.get("id", ""), applied={"mic": settings.to_dict()},
            errors=errors, mic_state=state,
        ))

    def handle_ptt(self, active: bool) -> None:
        if self.mic_settings.mode != "ptt":
            log.debug("ptt ignored: mic mode is %s", self.mic_settings.mode)
            return
        if active and self.mic_settings.ptt_interrupts and not self.gate.is_open:
            self.send(protocol.make_command("stop_speaking"))
        utterance = self.input.set_ptt(active)
        if utterance:
            self.handle_utterance(utterance)

    def send_devices(self, reply_to: str | None = None) -> None:
        devices, error = self._list_devices()
        self.send(protocol.make_command("devices", devices=devices, error=error, reply_to=reply_to))

    def mic_state(self) -> dict[str, Any]:
        s = self.mic_settings
        error = self.mic.error if self.mic else "no microphone in this mode (text input only)"
        state = {
            "enabled": s.enabled,
            "capturing": bool(self.mic and self.mic.capturing),
            "device": s.device,
            "mode": s.mode,
            "ptt_active": self.input.ptt_active,
        }
        if error and s.enabled:
            state["error"] = error
        return state

    def _send_mic_state_if_changed(self) -> None:
        if not self.transport.connected:
            return
        state = self.mic_state()
        if state != self._last_mic_state:
            self._last_mic_state = state
            self.send(protocol.make_command("mic_state", **state))

    def _send_level(self) -> None:
        now = self._clock()
        if now - self._last_level < LEVEL_INTERVAL_S:
            return
        self._last_level = now
        level = self.input.take_level()
        if self.mic_settings.level_meter and self.mic and self.mic.capturing and self.transport.connected:
            self.send(protocol.make_command("mic_level", **level))

    # -- input ---------------------------------------------------------------------------

    def handle_audio_frame(self, frame: bytes) -> str | None:
        """Feeds one microphone frame (for tests / custom capture). Returns text if an utterance finished."""
        utterance = self.input.process(frame)
        return self.handle_utterance(utterance) if utterance else None

    def handle_utterance(self, utterance: bytes) -> str:
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

    def say(self, text: str, interrupt: bool = False) -> str:
        """Synthesizes text and queues it on the body. Returns the utterance id."""
        utterance_id = protocol.new_id("utt")
        name = f"{utterance_id}.wav"
        path = self.cfg.audio_abs_path(name)
        duration = self.tts.synthesize(text, path)
        self._track_audio_file(path)
        url = self.transport.audio_url(name)
        rel = self.cfg.audio_rel_path(name)
        if not url and not rel:
            log.error("Cannot deliver audio: no HTTP link and no vam_root for the file path")
            return utterance_id
        self.gate.on_speak_sent(utterance_id, duration, interrupt=interrupt)
        self.send(protocol.make_command(
            "speak", id_=utterance_id, url=url, audio=rel, text=text, duration=round(duration, 3),
            queue="interrupt" if interrupt else "append",
        ))
        log.info("Say (%.1fs, via %s): %s", duration, "url" if url else "file path", text)
        return utterance_id

    def stop_speaking(self) -> None:
        self.send(protocol.make_command("stop_speaking"))

    def send(self, command: dict[str, Any]) -> None:
        self.transport.send(command)

    def _track_audio_file(self, path: Path) -> None:
        self._audio_files.append(path)
        while len(self._audio_files) > self.cfg.keep_audio_files:
            old = self._audio_files.pop(0)
            try:
                old.unlink(missing_ok=True)
            except OSError:
                pass  # still loaded by VaM; not worth retrying

    def shutdown(self) -> None:
        if self.mic:
            self.mic.stop()
