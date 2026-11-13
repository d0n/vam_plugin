"""Ties transport, microphone, echo gate, VAD, STT, LLM and TTS together.

Call tick() regularly (every ~20 ms) from one thread: it handles plugin events, pulls
microphone frames, finishes utterances and streams level / state feedback to the plugin.

VaM side = Session plugin (link, mic menu, engine menus) + one Person plugin per character.
The companion tracks the Persons the Session reports and adds "atom" to body commands
(config default_atom > the Session's default character > first Person; if none is known the
field is left out and the Session picks).
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__, protocol
from .audio import (
    EchoGate,
    InputProcessor,
    MicController,
    MicSettings,
    apply_mic_config,
    list_input_devices,
)
from .config import ENGINES_AVAILABLE, Config
from .pipeline import LanguageModel, SpeechToText, TextToSpeech
from .transport import Transport

log = logging.getLogger(__name__)

LEVEL_INTERVAL_S = 0.2  # mic_level rate (5 Hz)
HEARTBEAT_INTERVAL_S = 2.0  # companion_heartbeat rate


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
        self.body_info: dict[str, Any] = {}  # last ready/heartbeat from the Session plugin
        self.persons: dict[str, dict[str, Any]] = {}  # atom uid -> last known Person info
        self.session_default_atom = ""
        self.engines: dict[str, str] = {"stt": config.stt, "llm": config.llm, "tts": config.tts}
        self.session_id = uuid.uuid4().hex[:12]  # changes on every companion start
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S
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
        self._send_heartbeat()
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
            self._last_heartbeat = -HEARTBEAT_INTERVAL_S  # heartbeat right away on (re)connect
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
                    log.info("Session ready: plugin=%s channel=%s persons=%s", event.get("plugin_version"),
                             event.get("channel"), [p.get("atom") for p in event.get("persons") or []])
                    self._last_mic_state = None  # make sure the plugin gets a fresh mic_state
                self.body_info = event
                self._update_persons(event)
            elif type_ == "persons":
                self._update_persons(event)
                log.info("Characters: %s (default %s)", sorted(self.persons), self.target_atom or "-")
            elif type_ == "person_status":
                atom = event["atom"]
                self.persons.setdefault(atom, {"atom": atom}).update(
                    {k: v for k, v in event.items() if k not in protocol.ENVELOPE_FIELDS})
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

    def _update_persons(self, event: dict[str, Any]) -> None:
        persons = event.get("persons")
        if isinstance(persons, list):
            known = {}
            for p in persons:
                if isinstance(p, dict) and isinstance(p.get("atom"), str):
                    known[p["atom"]] = {**self.persons.get(p["atom"], {}), **p}
            self.persons = known
        if isinstance(event.get("default_atom"), str):
            self.session_default_atom = event["default_atom"]

    @property
    def target_atom(self) -> str | None:
        """Person atom that gets body commands (None = let the Session plugin decide)."""
        for atom in (self.cfg.default_atom, self.session_default_atom):
            if atom and (atom in self.persons or not self.persons):
                return atom
        return next(iter(self.persons), None)

    def _send_heartbeat(self) -> None:
        # Only while the Session plugin is alive: over files, unread heartbeats would pile up.
        if not self.transport.connected:
            return
        now = self._clock()
        if now - self._last_heartbeat < HEARTBEAT_INTERVAL_S:
            return
        self._last_heartbeat = now
        self.send(protocol.make_command(
            "companion_heartbeat", session=self.session_id, version=__version__,
            engines_available=ENGINES_AVAILABLE, mic_capturing=bool(self.mic and self.mic.capturing),
        ))

    def apply_engines(self, requested: Any) -> list[str]:
        """Applies the Session plugin's engine menu. Only implemented engines are accepted."""
        if requested is None:
            return []
        if not isinstance(requested, dict):
            return ["engines: must be an object"]
        errors = []
        for kind, name in requested.items():
            if kind not in ENGINES_AVAILABLE:
                errors.append(f"engines: unknown kind {kind!r}")
            elif name not in ENGINES_AVAILABLE[kind]:
                errors.append(f"engines: {kind} {name!r} is not available (have: {', '.join(ENGINES_AVAILABLE[kind])})")
            elif self.engines.get(kind) != name:
                # TODO: switch the engine instance once more than one engine per kind exists.
                self.engines[kind] = name
        return errors

    def handle_config(self, event: dict[str, Any]) -> None:
        settings, errors = apply_mic_config(self.mic_settings, event.get("mic"))
        errors = errors + self.apply_engines(event.get("engines"))
        self.mic_settings = settings
        self.input.apply(settings)
        if self.mic:
            self.mic.apply(settings)
        if errors:
            log.warning("Config problems: %s", "; ".join(errors))
        log.info("Mic settings: %s", settings.to_dict())
        state = self.mic_state()
        self._last_mic_state = state
        self.send(protocol.make_command(
            "config_ack", reply_to=event.get("id", ""),
            applied={"mic": settings.to_dict(), "engines": dict(self.engines)},
            errors=errors, mic_state=state,
        ))

    def handle_ptt(self, active: bool) -> None:
        if self.mic_settings.mode != "ptt":
            log.debug("ptt ignored: mic mode is %s", self.mic_settings.mode)
            return
        if active and self.mic_settings.ptt_interrupts and not self.gate.is_open:
            self.send(self.body_command("stop_speaking"))
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
            self.send(self.body_command("expression", name=reply.expression, intensity=1.0, blend=0.4))
        if reply.gesture:
            self.send(self.body_command("gesture", name=reply.gesture))
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
        self.send(self.body_command(
            "speak", id_=utterance_id, url=url, audio=rel, text=text, duration=round(duration, 3),
            queue="interrupt" if interrupt else "append",
        ))
        log.info("Say (%.1fs, via %s): %s", duration, "url" if url else "file path", text)
        return utterance_id

    def stop_speaking(self) -> None:
        self.send(self.body_command("stop_speaking"))

    def body_command(self, type_: str, atom: str | None = None, **fields: Any) -> dict[str, Any]:
        """Builds a body command addressed to `atom` (default: target_atom)."""
        return protocol.make_command(type_, atom=atom or self.target_atom, **fields)

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
