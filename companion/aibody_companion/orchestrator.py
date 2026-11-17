"""Ties transport, microphone, echo gate, VAD, STT, LLM and TTS together.

Call tick() regularly (every ~20 ms) from one thread: it handles plugin events, pulls
microphone frames, finishes utterances and streams level / state feedback to the plugin.

Two pipeline modes (config ai.mode, see docs/CONFIG.md):
  * chain    = speech to text -> language model -> text to speech (the engines below)
  * realtime = Grok Voice speech-to-speech over one WebSocket (realtime_voice.py); used by "auto"
               when an xAI key is there. If it cannot connect, chain runs until it can.
Proactive timer (proactive.py): after a silence the AI is nudged and may say something. Every
user turn and nudge carries the local date / time (pipeline/context.py): the AI has no clock.

One answer ("turn") = speech to text -> language model -> text to speech. With
background_turns=True (the app) a worker thread runs the turns, so heartbeats and events keep
flowing during slow network engines; tick() sends what the worker produced. A streaming model
(xAI) is spoken sentence by sentence: the first sentence is queued on the body while the model
still writes the rest. Without background turns (tests) a turn runs inline.

VaM side = ONE plugin (AIBody.cslist) on the AI character's Person atom: its app link talks to
this app (files in Saves/PluginData/AIBody/<channel>/) and hands body commands in-process to its
body. The body's state comes with ready / heartbeat / pong.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime
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
from .pipeline import Directive, LanguageModel, SpeechToText, TextToSpeech
from .pipeline.context import is_silent, nudge_text, time_context
from .pipeline.engines import EngineSet
from .pipeline.http import ApiError
from .proactive import ProactiveTimer
from .realtime_voice import RealtimeVoice
from .settings_file import CHOICES, DEFAULTS, RANGES, _check_value
from .transport import Transport
from .vamjson import as_bool

log = logging.getLogger(__name__)

LEVEL_INTERVAL_S = 0.2  # mic_level rate (5 Hz)
HEARTBEAT_INTERVAL_S = 2.0  # companion_heartbeat rate
KEY_REFRESH_S = 10.0  # how often key files are re-read (a key added later is picked up)
DEFAULT_EXPRESSIONS = ["neutral", "happy", "sad", "angry", "surprised", "thinking"]
DEFAULT_GESTURES = ["nod", "shake", "tilt"]


class _CancelledError(Exception):
    pass


class Companion:
    def __init__(
        self,
        config: Config,
        transport: Transport,
        stt: SpeechToText | None = None,
        llm: LanguageModel | None = None,
        tts: TextToSpeech | None = None,
        gate: EchoGate | None = None,
        mic: MicController | None = None,
        device_lister: Callable[[], tuple[list[dict[str, Any]], str | None]] = list_input_devices,
        clock: Callable[[], float] = time.monotonic,
        engines: EngineSet | None = None,
        background_turns: bool = False,
        realtime_connector: Callable[..., Any] | None = None,
        wall: Callable[[], datetime] | None = None,
    ):
        self.cfg = config
        self.transport = transport
        # Without an EngineSet only the offline engines exist (no keys are read).
        self.engine_set = engines or EngineSet(config.ai, env={})
        for kind in ("stt", "llm", "tts"):
            self.engine_set.select(kind, getattr(config, kind))
        for kind, instance in (("stt", stt), ("llm", llm), ("tts", tts)):
            if instance is not None:  # explicit engines (tests, custom setups)
                self.engine_set.instances[kind] = instance
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
        self.body_info: dict[str, Any] = {}  # last ready/heartbeat from the AIBody plugin
        self.session_id = uuid.uuid4().hex[:12]  # changes on every companion start
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S
        self._audio_files: list[Path] = []
        self._last_level = 0.0
        self._last_mic_state: dict[str, Any] | None = None
        self._was_connected = False
        self._last_key_check = clock()
        # turns: jobs for the worker, results back to tick()
        self.background_turns = background_turns
        self._jobs: queue.Queue[tuple[str, Any] | None] = queue.Queue()
        self._results: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._generation = 0  # bumped by cancel_turns(); older turns stop and their output is dropped
        self._busy = threading.Event()
        self._worker: threading.Thread | None = None
        if self.mic:
            self.mic.apply(self.mic_settings)
        # modes, proactive timer, time context
        self._wall = wall or (lambda: datetime.now().astimezone())
        self._realtime_connector = realtime_connector
        self.realtime: RealtimeVoice | None = None
        self._realtime_key: str | None = None
        self.mode_note = ""
        self._last_exchange: float | None = None
        proactive = self.engine_set.ai["proactive"]
        self.proactive = ProactiveTimer(bool(proactive["enabled"]), float(proactive["idle_seconds"]), clock)
        self._update_mode()

    # -- engines -------------------------------------------------------------------------

    @property
    def stt(self) -> SpeechToText:
        return self.engine_set.instances["stt"]

    @property
    def llm(self) -> LanguageModel:
        return self.engine_set.instances["llm"]

    @property
    def tts(self) -> TextToSpeech:
        return self.engine_set.instances["tts"]

    @property
    def engines(self) -> dict[str, str]:
        """The engines selected in the plugin / config.json (the active ones may be fallbacks)."""
        return dict(self.engine_set.requested)

    # -- main loop -----------------------------------------------------------------------

    def tick(self) -> None:
        self.process_events()
        self._watch_connection()
        self._update_mode()
        if self.realtime:
            self.realtime.tick()
        self._send_heartbeat()
        if self.mic:
            for frame in self.mic.frames():
                self.handle_audio_frame(frame)
            self._send_level()
        self._send_mic_state_if_changed()
        self._drain_results()
        self._maybe_nudge()
        now = self._clock()
        if now - self._last_key_check >= KEY_REFRESH_S:
            self._last_key_check = now
            if self.engine_set.refresh():
                self._last_heartbeat = -HEARTBEAT_INTERVAL_S  # tell the plugin right away

    # -- modes -----------------------------------------------------------------------------

    @property
    def mode_requested(self) -> str:
        return str(self.engine_set.ai.get("mode") or "auto")

    @property
    def active_mode(self) -> str:
        return "realtime" if self.realtime is not None and self.realtime.ready else "chain"

    def _want_realtime(self) -> tuple[bool, str]:
        mode = self.mode_requested
        has_key = bool(self.engine_set.key("xai"))
        if mode == "chain":
            return False, "Chain gewählt (Spracherkennung -> Sprachmodell -> Sprachausgabe)"
        if mode == "realtime":
            return (True, "") if has_key else (False, "Realtime nicht konfiguriert (kein xAI-Key) - Chain läuft")
        if self.engine_set.requested.get("tts") == "elevenlabs":
            return False, "Auto: Chain, weil Text-to-speech = elevenlabs gewählt ist"
        if not has_key:
            return False, "Auto: Chain (kein xAI-Key für Realtime)"
        return True, ""

    def _update_mode(self) -> None:
        want, note = self._want_realtime()
        key = self.engine_set.key("xai")
        if self.realtime is not None and (not want or key != self._realtime_key):
            self.realtime.stop()
            self.realtime = None
            log.info("Realtime beendet (%s)", note or "Key geändert")
        if want and self.realtime is None:
            self.realtime = RealtimeVoice(self, key, connector=self._realtime_connector)
            self._realtime_key = key
            self.realtime.start()
        if not want:
            self.mode_note = note
            return
        client = self.realtime.client
        settings = self.realtime.settings
        if client.ready:
            self.mode_note = f"Realtime verbunden ({client.model}, Stimme {settings['voice']})"
        elif client.failures == 0 and not client.last_error:
            self.mode_note = "Realtime verbindet ... (solange läuft Chain)"
        else:
            self.mode_note = (f"Realtime nicht verbunden: {client.last_error or 'getrennt'} - Fallback Chain, "
                              f"neuer Versuch in {client.retry_in():.0f} s")

    def mode_info(self) -> dict[str, Any]:
        return {"requested": self.mode_requested, "active": self.active_mode, "status": self.mode_note}

    def proactive_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"enabled": self.proactive.enabled, "idle_seconds": self.proactive.idle_seconds}
        if self.proactive.enabled and not self._can_nudge_engine():
            info["status"] = "wartet: braucht Realtime oder Sprachmodell xai"
        return info

    # -- time / activity -------------------------------------------------------------------

    def now(self) -> datetime:
        return self._wall()

    def since_last_exchange(self) -> float | None:
        return None if self._last_exchange is None else self._clock() - self._last_exchange

    def on_user_activity(self) -> None:
        self.proactive.user_activity()

    def on_exchange(self) -> None:
        self._last_exchange = self._clock()

    def send_directive(self, item: Directive) -> None:
        if item.expression:
            self.send(self.body_command("expression", name=item.expression, intensity=1.0, blend=0.4))
        if item.gesture:
            self.send(self.body_command("gesture", name=item.gesture))

    # -- proactive -------------------------------------------------------------------------

    def _can_nudge_engine(self) -> bool:
        return self.active_mode == "realtime" or bool(getattr(self.llm, "accepts_context", False))

    def _can_speak_now(self) -> bool:
        if not self.transport.connected or not self.gate.is_open:
            return False
        if self._busy.is_set() or not self._jobs.empty() or not self._results.empty():
            return False
        if self.input.ptt_active or self.input.segmenter.in_speech:
            return False
        if self.active_mode == "realtime" and (self.realtime.responding or self.realtime.user_speaking):
            return False
        return True

    def _maybe_nudge(self) -> None:
        if not self.proactive.due(self._can_speak_now()) or not self._can_nudge_engine():
            return
        prompt = str(self.engine_set.ai["proactive"].get("prompt") or "")
        text = nudge_text(prompt, self.now(), self.since_last_exchange())
        self.proactive.fired()
        log.info("Proactive: %.0f s Stille - die KI darf etwas sagen", self.proactive.idle_seconds)
        if self.active_mode == "realtime":
            self.realtime.nudge(text)
        elif self.background_turns:
            self._submit("nudge", text)
        else:
            for step in self._turn("nudge", text, self._generation):
                self._apply(step)

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
            if type_ in ("speech_started", "speech_ended"):
                self.proactive.ai_activity()
            if type_ in ("ready", "heartbeat"):
                if type_ == "ready":
                    log.info("AIBody plugin ready on %r: plugin=%s channel=%s", event.get("atom"),
                             event.get("plugin_version"), event.get("channel"))
                    self._last_mic_state = None  # make sure the plugin gets a fresh mic_state
                self.body_info = event
            elif type_ == "config":
                self.handle_config(event)
            elif type_ == "ptt":
                self.handle_ptt(bool(as_bool(event.get("active"))))
            elif type_ == "list_devices":
                self.send_devices(event.get("id"))
            elif type_ == "error":
                log.warning("Body error (%s): %s", event.get("code"), event.get("message"))
            else:
                log.debug("event: %s", event)
        return events

    def _send_heartbeat(self) -> None:
        # Only while the AIBody plugin is alive: over files, unread heartbeats would pile up.
        if not self.transport.connected:
            return
        now = self._clock()
        if now - self._last_heartbeat < HEARTBEAT_INTERVAL_S:
            return
        self._last_heartbeat = now
        self.send(protocol.make_command(
            "companion_heartbeat", session=self.session_id, version=__version__,
            engines_available=ENGINES_AVAILABLE, engines_status=self.engine_set.status(),
            engines_active=dict(self.engine_set.active_names),
            mic_capturing=bool(self.mic and self.mic.capturing),
            mode=self.mode_info(), proactive=self.proactive_info(),
        ))

    def apply_engines(self, requested: Any) -> list[str]:
        """Applies the AIBody plugin's engine menu (switches engines live). Returns problems, incl.
        "not configured - fallback ..." notes."""
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
            else:
                errors += self.engine_set.select(kind, name)
        return errors

    # ai keys the plugin's Engines tab may change live
    AI_LIVE_KEYS = {("mode",), ("proactive", "enabled"), ("proactive", "idle_seconds"),
                    ("realtime", "send_while_speaking")}

    def apply_ai(self, data: Any) -> list[str]:
        """Applies the plugin's ai controls (mode, proactive on/off + idle seconds, voice
        barge-in). Other ai settings live in config.json only."""
        if data is None:
            return []
        if not isinstance(data, dict):
            return ["ai: must be an object"]
        _ = (CHOICES, RANGES)  # validation tables used by _check_value
        errors: list[str] = []
        ai = self.engine_set.ai
        for path in sorted(self.AI_LIVE_KEYS):
            value: Any = data
            for part in path:
                value = value.get(part) if isinstance(value, dict) else None
            if value is None:
                continue
            default: Any = DEFAULTS["ai"]
            target = ai
            for part in path[:-1]:
                default, target = default[part], target[part]
            target[path[-1]] = _check_value(("ai", *path), default[path[-1]], value, errors)
        p = ai["proactive"]
        self.proactive.configure(bool(p["enabled"]), float(p["idle_seconds"]))
        self._update_mode()
        return errors

    def handle_config(self, event: dict[str, Any]) -> None:
        settings, errors = apply_mic_config(self.mic_settings, event.get("mic"))
        errors = errors + self.apply_engines(event.get("engines")) + self.apply_ai(event.get("ai"))
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
            applied={"mic": settings.to_dict(), "engines": dict(self.engines),
                     "ai": {"mode": self.mode_requested,
                            "proactive": {"enabled": self.proactive.enabled,
                                          "idle_seconds": self.proactive.idle_seconds},
                            "realtime": {"send_while_speaking":
                                         bool(self.engine_set.ai["realtime"]["send_while_speaking"])}}},
            errors=errors, mic_state=state,
        ))

    def handle_ptt(self, active: bool) -> None:
        if self.mic_settings.mode != "ptt":
            log.debug("ptt ignored: mic mode is %s", self.mic_settings.mode)
            return
        if active:
            self.on_user_activity()
        if self.active_mode == "realtime":
            if active and self.mic_settings.ptt_interrupts:
                self.realtime.barge_in(manual=True)
            self.input.set_ptt(active)  # frames stream to the server while held; no local utterance
            return
        if active and self.mic_settings.ptt_interrupts and (not self.gate.is_open or self._busy.is_set()):
            self.cancel_turns()  # the user talks: the answer being prepared is dropped ...
            self.send(self.body_command("stop_speaking"))  # ... and the body stops
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
        """Feeds one microphone frame: to the realtime server in realtime mode, else to the local
        VAD. Returns text if an utterance finished (chain mode, inline turns)."""
        if self.active_mode == "realtime":
            self.realtime.feed_mic(frame)
            return None
        utterance = self.input.process(frame)
        return self.handle_utterance(utterance) if utterance else None

    def handle_utterance(self, utterance: bytes) -> str:
        """Transcribes and answers an utterance. Returns the text (inline) or "" (queued)."""
        self.on_user_activity()
        if self.background_turns:
            self._submit("audio", utterance)
            return ""
        text = ""
        for step in self._turn("audio", utterance, self._generation):
            if step[0] == "heard":
                text = step[1]
            self._apply(step)
        return text

    def handle_user_text(self, text: str) -> None:
        if self.background_turns:
            self._submit("text", text)
            return
        for step in self._turn("text", text, self._generation):
            self._apply(step)

    # -- turns: STT -> LLM -> TTS ----------------------------------------------------------

    def _submit(self, kind: str, data: Any) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, name="aibody-turns", daemon=True)
            self._worker.start()
        self._jobs.put((kind, data, self._generation))

    def _work(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                return
            kind, data, generation = job
            if generation != self._generation:
                continue  # cancelled before it started
            self._busy.set()
            try:
                for step in self._turn(kind, data, generation):
                    self._results.put((generation, *step))
            except Exception:  # noqa: BLE001 - a broken turn must not kill the worker
                log.exception("Turn failed")
            finally:
                self._busy.clear()

    def _drain_results(self) -> None:
        while True:
            try:
                generation, *step = self._results.get_nowait()
            except queue.Empty:
                return
            if generation == self._generation:
                self._apply(tuple(step))

    def cancel_turns(self) -> None:
        """Drops the answer being prepared and everything queued (push-to-talk barge-in)."""
        self._generation += 1
        while True:
            try:
                self._jobs.get_nowait()
            except queue.Empty:
                break

    def wait_turns(self, timeout: float = 5.0) -> bool:
        """Test helper: waits until the worker is idle, then applies its results."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._jobs.empty() and not self._busy.is_set():
                self._drain_results()
                if self._jobs.empty() and not self._busy.is_set():
                    return True
            time.sleep(0.01)
        return False

    def _check(self, generation: int) -> None:
        if generation != self._generation:
            raise _CancelledError()

    def _turn(self, kind: str, data: Any, generation: int):
        """Yields steps: ("heard", text), ("command", cmd), ("speak", id, text, path, duration)."""
        try:
            if kind == "audio":
                text = self._transcribe(data)
                yield ("heard", text, len(data) / 2 / self.cfg.sample_rate)
                if not text:
                    return
            else:
                text = str(data)
            self._check(generation)
            nudge = kind == "nudge"
            prompt = text
            if not nudge:
                self.history.append({"role": "user", "content": text})
                if getattr(self.llm, "accepts_context", False):  # the echo test model would read it out
                    prompt = time_context(self.now(), self.since_last_exchange()) + "\n" + text
            said: list[str] = []
            held: list[Directive] = []  # a nudge's tag waits until its first sentence is not "[silent]"
            for item in self._answer(text, prompt, nudge):
                self._check(generation)
                if isinstance(item, Directive):
                    if nudge and not said:
                        held.append(item)
                        continue
                    yield from self._directive_steps(item)
                    continue
                sentence = str(item).strip()
                if not sentence:
                    continue
                if nudge and not said:
                    if is_silent(sentence):
                        log.info("Proactive: the AI chose to stay silent")
                        return
                    for d in held:
                        yield from self._directive_steps(d)
                utterance_id = protocol.new_id("utt")
                path = self.cfg.audio_abs_path(f"{utterance_id}.wav")
                duration = self._synthesize(sentence, path)
                self._check(generation)
                said.append(sentence)
                yield ("speak", utterance_id, sentence, path, duration)
            if said:
                self.history.append({"role": "assistant", "content": " ".join(said)})
                self.on_exchange()
        except _CancelledError:
            log.info("Answer cancelled")

    def _directive_steps(self, item: Directive):
        if item.expression:
            yield ("command", self.body_command("expression", name=item.expression, intensity=1.0, blend=0.4))
        if item.gesture:
            yield ("command", self.body_command("gesture", name=item.gesture))

    def _transcribe(self, utterance: bytes) -> str:
        try:
            return self.stt.transcribe(utterance, self.cfg.sample_rate).strip()
        except ApiError as e:
            name, fallback = self.engine_set.fallback("stt")
            log.warning("Speech to text failed (%s); fallback %s", e, name)
            try:
                return fallback.transcribe(utterance, self.cfg.sample_rate).strip()
            except ApiError:
                return ""

    def _answer(self, text: str, prompt: str | None = None, nudge: bool = False):
        """Directive / sentence items from the active model (it gets `prompt`, the text with the
        time context); the fallback model gets the plain text if it fails before saying anything
        (a nudge has no fallback: the echo test model would read the note aloud)."""
        llm = self.llm
        user_text = text
        text = prompt or text
        expressions = list(self.body_info.get("expressions") or DEFAULT_EXPRESSIONS)
        gestures = list(self.body_info.get("gestures") or DEFAULT_GESTURES)
        produced = False
        try:
            if hasattr(llm, "stream"):
                for item in llm.stream(text, self.history, expressions, gestures):
                    produced = True
                    yield item
            else:
                yield from self._reply_items(llm, text)
            return
        except ApiError as e:
            name, fallback = self.engine_set.fallback("llm")
            log.warning("Language model failed (%s)%s", e, "" if produced else f"; fallback {name}")
            if produced or nudge:
                return
        yield from self._reply_items(fallback, user_text)

    def _reply_items(self, llm: Any, text: str):
        reply = llm.reply(text, self.history)
        if reply.expression or reply.gesture:
            yield Directive(reply.expression, reply.gesture)
        if reply.say:
            yield reply.say

    def _synthesize(self, text: str, path: Path) -> float:
        try:
            return self.tts.synthesize(text, path)
        except (ApiError, ValueError, OSError) as e:
            name, fallback = self.engine_set.fallback("tts")
            log.warning("Text to speech failed (%s); fallback %s for: %s", e, name, text)
            return fallback.synthesize(text, path)

    def _apply(self, step: tuple[Any, ...]) -> None:
        """Runs on the tick thread: sends what a turn produced."""
        kind = step[0]
        if kind == "heard":
            log.info("Heard: %r (%.1fs)", step[1], step[2])
        elif kind == "command":
            self.send(step[1])
        elif kind == "speak":
            _, utterance_id, text, path, duration = step
            self._queue_speech(utterance_id, text, path, duration)

    # -- output --------------------------------------------------------------------------

    def say(self, text: str, interrupt: bool = False) -> str:
        """Synthesizes text and queues it on the body. Returns the utterance id."""
        utterance_id = protocol.new_id("utt")
        path = self.cfg.audio_abs_path(f"{utterance_id}.wav")
        duration = self._synthesize(text, path)
        return self._queue_speech(utterance_id, text, path, duration, interrupt)

    def _queue_speech(self, utterance_id: str, text: str, path: Path, duration: float,
                      interrupt: bool = False) -> str:
        self._track_audio_file(path)
        rel = self.cfg.audio_rel_path(path.name)
        self.gate.on_speak_sent(utterance_id, duration, interrupt=interrupt)
        self.send(self.body_command(
            "speak", id_=utterance_id, audio=rel, text=text, duration=round(duration, 3),
            queue="interrupt" if interrupt else "append",
        ))
        log.info("Say (%.1fs): %s", duration, text)
        return utterance_id

    def stop_speaking(self) -> None:
        self.send(self.body_command("stop_speaking"))

    def body_command(self, type_: str, **fields: Any) -> dict[str, Any]:
        """Builds a body command (speak, expression, ...) for the plugin's body."""
        return protocol.make_command(type_, **fields)

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
        if self.realtime:
            self.realtime.stop()
        self.cancel_turns()
        self._jobs.put(None)
        if self.mic:
            self.mic.stop()
