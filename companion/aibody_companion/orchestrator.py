"""Ties transport, microphone, echo gate, VAD, STT, LLM and TTS together.

Call tick() regularly (every ~20 ms) from one thread: it handles plugin events, pulls
microphone frames, finishes utterances and streams level / state feedback to the plugin.

Pipeline modes (config ai.mode, see docs/CONFIG.md):
  * qa       = simple questions and answers (default): speech to text -> language model -> text
               to speech, with xai instead of the offline test engines (null / echo / tone) when
               an xAI key is there, speech only (no expressions / gestures), no proactive nudges
  * chain    = speech to text -> language model -> text to speech (exactly the engines selected)
  * realtime = Grok Voice speech-to-speech over one WebSocket (realtime_voice.py); used by "auto"
               when an xAI key is there. While it is not connected, or after it did not answer,
               the chain runs (with xai instead of the test engines) and the status says so.
Typed text (console) always takes the chain, so the answer path can be tested without a mic.
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
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__, logsetup, protocol
from .audio import (
    EchoGate,
    InputProcessor,
    MicController,
    MicSettings,
    apply_mic_config,
    list_input_devices,
)
from .config import ENGINES_AVAILABLE, Config
from .logsetup import Turn
from .pipeline import Directive, LanguageModel, SpeechToText, TextToSpeech
from .pipeline.context import is_silent, nudge_text, time_context
from .pipeline.engines import EngineSet
from .pipeline.http import ApiError
from .pipeline.tts import test_tone_pcm, write_pcm_wav
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
XAI_ALL = {"stt": "xai", "llm": "xai", "tts": "xai"}
OFFLINE_ENGINES = {"stt": "null", "llm": "echo", "tts": "tone"}
# said instead of an answer when the language model fails in the simple Q&A mode
LLM_ERROR_SAY = {"de": "Entschuldigung, ich kann gerade nicht antworten. Das Sprachmodell meldet einen Fehler.",
                 "en": "Sorry, I cannot answer right now. The language model reported an error."}


class _CancelledError(Exception):
    pass


def _pcm_stats(pcm: bytes, rate: int) -> dict[str, float]:
    """Length and level of 16-bit mono PCM (for the turn trace)."""
    import array
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not samples:
        return {"seconds": 0.0, "rms": 0.0, "peak": 0.0}
    step = max(1, len(samples) // 20000)  # enough for a level, cheap for long utterances
    part = samples[::step]
    rms = (sum(x * x for x in part) / len(part)) ** 0.5 / 32768.0
    return {"seconds": round(len(samples) / rate, 2), "rms": round(rms, 4),
            "peak": round(max(abs(x) for x in part) / 32768.0, 3)}


def _short(text: str, limit: int = 80) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


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
        self.realtime_off = ""  # why realtime was given up until "API Reconnect" (it did not answer)
        self.turn_status = ""  # last question / answer step, shown in the plugin's status box
        self.audio_note = ""  # audio folder problems / switch, shown in the plugin's status box
        self._recent_speech: dict[str, tuple[str, Path, float]] = {}  # id -> (text, path, duration)
        self._utt_turn: dict[str, Turn] = {}  # utterance id -> its turn (trace of the plugin's answers)
        self._null_stt_warned = False
        self._stt_error = ""
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

    @property
    def speech_only(self) -> bool:
        """Simple Q&A mode: no expressions / gestures from the answers."""
        return self.mode_requested == "qa"

    def _want_realtime(self) -> tuple[bool, str]:
        mode = self.mode_requested
        has_key = bool(self.engine_set.key("xai"))
        if mode == "qa":
            if has_key:
                return False, "Einfacher Q&A: Spracherkennung xAI -> Grok -> Stimme xAI, nur Sprache"
            return False, ("Einfacher Q&A ohne xAI-Key: nur Test-Engines (Echo + Ton) - "
                           "XAI_API_KEY setzen oder Key-Datei im Tab AI")
        if mode == "chain":
            return False, "Chain gewählt (Spracherkennung -> Sprachmodell -> Sprachausgabe)"
        if self.realtime_off:
            return False, (f"Realtime aus: {self.realtime_off} - Fallback Chain"
                           f"{' mit xAI' if has_key else ''}; 'API Reconnect' versucht es neu")
        if mode == "realtime":
            return (True, "") if has_key else (False, "Realtime nicht konfiguriert (kein xAI-Key) - Chain läuft")
        if self.engine_set.requested.get("tts") == "elevenlabs":
            return False, "Auto: Chain, weil Text-to-speech = elevenlabs gewählt ist"
        if not has_key:
            return False, "Auto: Chain (kein xAI-Key für Realtime)"
        return True, ""

    def _chain_override(self) -> dict[str, str] | None:
        """With an xAI key, every mode but chain runs xai instead of the offline test engines
        (null / echo / tone) on the chain path: the simple Q&A mode, typed text and the fallback
        while realtime is not running. chain mode runs exactly the selection."""
        if not self.engine_set.key("xai") or self.mode_requested == "chain":
            return None
        requested = self.engine_set.requested
        return {k: v for k, v in XAI_ALL.items() if requested[k] == OFFLINE_ENGINES[k]} or None

    def realtime_unresponsive(self, reason: str) -> None:
        """Realtime connected but did not answer: give it up until "API Reconnect" / a mode change."""
        log.warning("Realtime antwortet nicht (%s) - ab jetzt Chain; 'API Reconnect' versucht es neu", reason)
        if self.realtime is not None and self.realtime.turn is not None:
            self.realtime.turn.step("realtime given up", reason=reason, fallback="chain")
        self.realtime_off = reason
        self.turn_status = f"Realtime antwortete nicht ({reason}) - ab jetzt Chain, bitte Frage wiederholen"
        self._update_mode()
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S

    def _update_mode(self) -> None:
        want, note = self._want_realtime()
        self.engine_set.set_override(self._chain_override())
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
        if client.last_error and client.last_error.startswith("API-Key abgelehnt"):
            self.engine_set.rejected["xai"] = f"vom Realtime-Server abgelehnt ({client.last_error})"
        if client.ready:
            self.engine_set.rejected.pop("xai", None)
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
        if self.proactive.enabled and self.speech_only:
            info["status"] = "pausiert im Einfachen Q&A-Modus"
        elif self.proactive.enabled and not self._can_nudge_engine():
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
        if self.speech_only:
            return False  # simple Q&A: the AI speaks only when asked
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
            self._trace_plugin_event(event)
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
            elif type_ == "test_tone":
                self.play_test_tone()
            elif type_ == "reconnect":
                self.reconnect_api()
            elif type_ == "error":
                log.warning("Body error (%s): %s", event.get("code"), event.get("message"))
                if event.get("code") == "audio_failed":
                    self._audio_failed(str(event.get("reply_to") or ""), str(event.get("message") or ""))
            else:
                log.debug("event: %s", event)
        return events

    def _trace_plugin_event(self, event: dict[str, Any]) -> None:
        type_ = event.get("type")
        if type_ not in ("speech_started", "speech_ended", "error", "ack"):
            return
        uid = str(event.get("utterance_id") or event.get("reply_to") or "")
        turn = self._utt_turn.get(uid)
        if turn is None:
            return
        turn.step(f"plugin: {type_}", utterance=uid, duration=event.get("duration"), reason=event.get("reason"),
                  code=event.get("code"), message=event.get("message"))

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
            mode=self.mode_info(), proactive=self.proactive_info(), keys=self.engine_set.key_info(),
            audio_out=self.audio_info(), turn=self.turn_status,
        ))

    def audio_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"folder": self.cfg.audio_rel_dir, "auto": self.cfg.audio_auto}
        if self.audio_note:
            info["note"] = self.audio_note
        return info

    def _set_turn(self, text: str) -> None:
        self.turn_status = text
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S  # the plugin shows it right away

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

    # ai keys the plugin's tabs may change live (AI, AI Character, Client Character)
    AI_LIVE_KEYS = {("mode",), ("proactive", "enabled"), ("proactive", "idle_seconds"),
                    ("realtime", "send_while_speaking"), ("realtime", "voice"), ("xai", "voice"),
                    ("xai", "key_file"), ("elevenlabs", "key_file")}

    def reconnect_api(self) -> None:
        """Plugin button "API Reconnect": re-read the keys and open the realtime connection anew."""
        log.info("API Reconnect requested by the plugin")
        self.realtime_off = ""
        self.engine_set.refresh()
        if self.realtime is not None:
            self.realtime.stop()
            self.realtime = None
        self._update_mode()
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S

    def apply_ai(self, data: Any) -> list[str]:
        """Applies the plugin's ai controls (mode, proactive on/off + idle seconds, voice
        barge-in). Other ai settings live in config.json only."""
        if data is None:
            return []
        if not isinstance(data, dict):
            return ["ai: must be an object"]
        _ = (CHOICES, RANGES)  # validation tables used by _check_value
        errors: list[str] = []
        changed: set[tuple[str, ...]] = set()
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
            before = len(errors)
            checked = _check_value(("ai", *path), default[path[-1]], value, errors)
            if path[-1] == "key_file" and len(errors) > before:
                continue  # a pasted key is refused; the old key file path stays
            if checked != target[path[-1]]:
                changed.add(path)
            target[path[-1]] = checked
        if ("mode",) in changed:
            self.realtime_off = ""  # a new mode choice gives realtime a new chance
        p = ai["proactive"]
        self.proactive.configure(bool(p["enabled"]), float(p["idle_seconds"]))
        if ("xai", "key_file") in changed or ("elevenlabs", "key_file") in changed:
            self.engine_set.refresh()
        if ("xai", "voice") in changed:
            self.engine_set.rebuild("tts")
        if ("realtime", "voice") in changed and self.realtime is not None:
            self.realtime.stop()  # the voice is part of the session: reconnect with the new one
            self.realtime = None
        self._update_mode()
        return errors

    def apply_advanced(self, data: Any) -> list[str]:
        """The plugin's "Verbose log" toggle (advanced.verbose_log): turn trace on/off live."""
        if data is None:
            return []
        if not isinstance(data, dict):
            return ["advanced: must be an object"]
        if "verbose_log" not in data:
            return []
        value = as_bool(data["verbose_log"])
        if value is None:
            return ["advanced.verbose_log: must be true/false"]
        logsetup.set_verbose(value)
        return []

    def handle_config(self, event: dict[str, Any]) -> None:
        settings, errors = apply_mic_config(self.mic_settings, event.get("mic"))
        errors = errors + self.apply_engines(event.get("engines")) + self.apply_ai(event.get("ai"))
        errors += self.apply_advanced(event.get("advanced"))
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
                                         bool(self.engine_set.ai["realtime"]["send_while_speaking"]),
                                         "voice": str(self.engine_set.ai["realtime"]["voice"])}},
                     "advanced": {"verbose_log": logsetup.is_verbose()}},
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
        """Typed text (console): the same answer path as speech, without speech to text."""
        self.on_user_activity()
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
        """Yields steps: ("heard", text), ("command", cmd), ("speak", id, text, path, duration),
        ("status", text) for the plugin's status box."""
        turn = Turn(kind, **(_pcm_stats(data, self.cfg.sample_rate) if kind == "audio" and logsetup.is_verbose()
                             else {"text": str(data)} if kind == "text" else {}))
        names = self.engine_set.active_names
        turn.step("path", mode=self.mode_requested, active=self.active_mode, chain=f"{names['stt']} -> "
                  f"{names['llm']} -> {names['tts']}", selected="/".join(self.engine_set.requested.values()),
                  speech_only=self.speech_only, note=self.mode_note)
        try:
            if kind == "audio":
                t = turn.elapsed()
                text = self._transcribe(data)
                turn.step("stt", engine=self.engine_set.active_names["stt"],
                          ms=round((turn.elapsed() - t) * 1000), text=text, error=self._stt_error or None)
                yield ("heard", text, len(data) / 2 / self.cfg.sample_rate)
                if not text:
                    turn.step("end", result="nothing understood")
                    return
            else:
                text = str(data)
                if kind == "text":
                    yield ("status", f"Frage (getippt): {_short(text)}")
            self._check(generation)
            nudge = kind == "nudge"
            prompt = text
            if not nudge:
                self.history.append({"role": "user", "content": text})
                if getattr(self.llm, "accepts_context", False):  # the echo test model would read it out
                    prompt = time_context(self.now(), self.since_last_exchange()) + "\n" + text
            said: list[str] = []
            problems: list[str] = []
            held: list[Directive] = []  # a nudge's tag waits until its first sentence is not "[silent]"
            llm_name = self.engine_set.active_names["llm"]
            turn.step("llm request", engine=llm_name,
                      model=self.engine_set.ai["xai"]["model"] if llm_name == "xai" else None,
                      streaming=hasattr(self.llm, "stream"), history=len(self.history), text=text,
                      time_context=prompt != text)
            for item in self._answer(text, prompt, nudge, problems):
                self._check(generation)
                if isinstance(item, Directive):
                    turn.step("llm tag", expression=item.expression, gesture=item.gesture,
                              action="dropped (speech only)" if self.speech_only else "sent as commands")
                    if self.speech_only:
                        continue  # simple Q&A: speech only
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
                turn.step(f"llm sentence {len(said) + 1}", text=sentence)
                utterance_id = protocol.new_id("utt")
                path = self.cfg.audio_abs_path(f"{utterance_id}.wav")
                t = turn.elapsed()
                tts_before = len(problems)
                duration = self._synthesize(sentence, path, problems)
                tts_name = self.engine_set.active_names["tts"]
                turn.step("tts", engine=tts_name if len(problems) == tts_before else f"{tts_name} failed -> fallback",
                          voice=self._voice_of(tts_name), ms=round((turn.elapsed() - t) * 1000),
                          wav=self._rel(path), seconds=round(duration, 2))
                self._check(generation)
                said.append(sentence)
                self._utt_turn[utterance_id] = turn
                yield ("speak", utterance_id, sentence, path, duration)
            if said:
                self.history.append({"role": "assistant", "content": " ".join(said)})
                self.on_exchange()
            turn.step("end", sentences=len(said), problems=" | ".join(dict.fromkeys(problems)) or None)
            if not nudge:
                if problems:
                    yield ("status", " | ".join(dict.fromkeys(problems)))
                elif said:
                    yield ("status", f"Antwort ({len(said)} Satz/Sätze, {self.engine_set.active_names['llm']} -> "
                                     f"{self.engine_set.active_names['tts']}): {_short(' '.join(said))}")
                else:
                    yield ("status", "Keine Antwort: das Sprachmodell lieferte keinen Text")
        except _CancelledError:
            turn.step("end", result="cancelled (barge-in)")
            log.info("Answer cancelled")

    def _voice_of(self, tts: str) -> str | None:
        if tts == "xai":
            return str(self.engine_set.ai["xai"]["voice"])
        if tts == "elevenlabs":
            return str(self.engine_set.ai["elevenlabs"]["voice_id"])
        return None

    def _directive_steps(self, item: Directive):
        if item.expression:
            yield ("command", self.body_command("expression", name=item.expression, intensity=1.0, blend=0.4))
        if item.gesture:
            yield ("command", self.body_command("gesture", name=item.gesture))

    def _transcribe(self, utterance: bytes) -> str:
        try:
            return self.stt.transcribe(utterance, self.cfg.sample_rate).strip()
        except Exception as e:  # noqa: BLE001 - a failed request must not end the turn silently
            if isinstance(e, ApiError):
                self.engine_set.note_api_error(e)
            self._stt_error = f"Spracherkennung-Fehler: {_short(str(e), 120)}"
            name, fallback = self.engine_set.fallback("stt")
            log.warning("Speech to text failed (%s); fallback %s", e, name)
            try:
                return fallback.transcribe(utterance, self.cfg.sample_rate).strip()
            except Exception:  # noqa: BLE001
                return ""

    def _answer(self, text: str, prompt: str | None = None, nudge: bool = False,
                problems: list[str] | None = None):
        """Directive / sentence items from the active model (it gets `prompt`, the text with the
        time context); the fallback model gets the plain text if it fails before saying anything
        (a nudge has no fallback: the echo test model would read the note aloud). In the simple
        Q&A mode a short spoken error notice replaces the fallback model."""
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
        except Exception as e:  # noqa: BLE001 - network / parse errors included
            if isinstance(e, ApiError):
                self.engine_set.note_api_error(e)
            name, fallback = self.engine_set.fallback("llm")
            log.warning("Language model failed (%s)%s", e, "" if produced else f"; fallback {name}")
            if problems is not None:
                problems.append(f"Sprachmodell-Fehler: {_short(str(e), 120)}"
                                + ("" if produced or nudge else " - Ersatzantwort"))
            if produced or nudge:
                return
        if self.speech_only:
            language = str(self.engine_set.ai.get("language") or "auto")
            yield LLM_ERROR_SAY["en" if language.startswith("en") else "de"]
            return
        yield from self._reply_items(fallback, user_text)

    def _reply_items(self, llm: Any, text: str):
        reply = llm.reply(text, self.history)
        if reply.expression or reply.gesture:
            yield Directive(reply.expression, reply.gesture)
        if reply.say:
            yield reply.say

    def _synthesize(self, text: str, path: Path, problems: list[str] | None = None) -> float:
        try:
            return self.tts.synthesize(text, path)
        except Exception as e:  # noqa: BLE001 - network errors included; the fallback tone is heard
            if isinstance(e, ApiError):
                self.engine_set.note_api_error(e)
            name, fallback = self.engine_set.fallback("tts")
            log.warning("Text to speech failed (%s); fallback %s for: %s", e, name, text)
            if problems is not None:
                problems.append(f"Sprachausgabe-Fehler: {_short(str(e), 120)} - Ersatzton ({name})")
            return fallback.synthesize(text, path)

    def _apply(self, step: tuple[Any, ...]) -> None:
        """Runs on the tick thread: sends what a turn produced."""
        kind = step[0]
        if kind == "heard":
            log.info("Heard: %r (%.1fs)", step[1], step[2])
            stt_error, self._stt_error = self._stt_error, ""
            if step[1]:
                self._set_turn(f"Gehört: {_short(step[1])}")
            elif stt_error:
                self._set_turn(f"{stt_error} - keine Antwort")
            elif self.engine_set.active_names.get("stt") == "null":
                self._set_turn("Nichts verstanden: Spracherkennung 'null' (Test) erkennt nichts - xAI-Key nötig")
            else:
                self._set_turn(f"Nichts verstanden ({step[2]:.1f} s Ton, Spracherkennung lieferte keinen Text)")
            if not step[1] and self.engine_set.active_names.get("stt") == "null" and not self._null_stt_warned:
                self._null_stt_warned = True
                log.warning("Speech-to-text 'null' understands nothing, so there is no answer. For a spoken "
                            "conversation choose Speech-to-text 'xai' or use realtime mode (xAI key).")
        elif kind == "status":
            log.info("Status: %s", step[1])
            self._set_turn(step[1])
        elif kind == "command":
            self.send(step[1])
        elif kind == "speak":
            _, utterance_id, text, path, duration = step
            self._queue_speech(utterance_id, text, path, duration)

    # -- audio folder --------------------------------------------------------------------

    def _audio_failed(self, utterance_id: str, message: str) -> None:
        """The plugin could not load / start one of our WAVs (code audio_failed). With the automatic
        audio folder the app switches once from Custom/Sounds to Saves/PluginData (or back) and
        sends the same speech again from there."""
        entry = self._recent_speech.get(utterance_id)
        if entry is None:
            return
        text, path, duration = entry
        current = self.cfg.audio_rel_dir
        failed_dir = self._rel(path.parent)
        if not self.cfg.audio_auto:
            self.audio_note = (f"VaM konnte {path.name} nicht laden ({_short(message, 100)}); "
                               f"Audio-Ordner fest eingestellt: {current} (connection.paths.audio)")
        elif failed_dir == current and self.cfg.audio_dir_index == 0:
            self.cfg.audio_dir_index = 1
            new = self.cfg.audio_rel_dir
            self.audio_note = f"VaM konnte {failed_dir} nicht laden - Audio-Ordner gewechselt auf {new}"
            log.warning("Audio: %s", self.audio_note)
        elif failed_dir == current:
            self.audio_note = (f"VaM konnte die WAVs weder aus {self.cfg.audio_default_dirs[0]} noch aus "
                               f"{current} laden ({_short(message, 100)}) - siehe TESTPROTOKOLL T9")
            log.warning("Audio: %s", self.audio_note)
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S
        if failed_dir == self.cfg.audio_rel_dir or not path.exists():
            return  # nothing better to try
        new_id = protocol.new_id("utt")
        new_path = self.cfg.audio_abs_path(f"{new_id}.wav")
        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, new_path)
        except OSError as e:
            log.warning("Audio: could not copy %s to %s: %s", path, new_path, e)
            return
        log.info("Audio: sending %s again from %s", utterance_id, self.cfg.audio_rel_dir)
        if utterance_id in self._utt_turn:
            self._utt_turn[new_id] = self._utt_turn[utterance_id]
        self._queue_speech(new_id, text, new_path, duration)

    def _rel(self, path: Path) -> str:
        """Path below the VaM folder with forward slashes (as the plugin loads it)."""
        try:
            return path.relative_to(Path(self.cfg.vam_root)).as_posix()
        except ValueError:
            return path.as_posix()

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
        self._recent_speech[utterance_id] = (text, path, duration)
        while len(self._recent_speech) > self.cfg.keep_audio_files:
            self._recent_speech.pop(next(iter(self._recent_speech)))
        while len(self._utt_turn) > 4 * self.cfg.keep_audio_files:
            self._utt_turn.pop(next(iter(self._utt_turn)))
        rel = self._rel(path)
        turn = self._utt_turn.get(utterance_id)
        if turn is not None:
            turn.step("speak sent", utterance=utterance_id, audio=rel, seconds=round(duration, 2),
                      queue="interrupt" if interrupt else "append")
        self.gate.on_speak_sent(utterance_id, duration, interrupt=interrupt)
        self.send(self.body_command(
            "speak", id_=utterance_id, audio=rel, text=text, duration=round(duration, 3),
            queue="interrupt" if interrupt else "append",
        ))
        log.info("Say (%.1fs): %s", duration, text)
        return utterance_id

    def play_test_tone(self) -> str:
        """Plugin button "Test-Ton über Companion": a chime WAV in the audio folder, sent as a normal
        speak (interrupting), so the path companion -> audio file -> VaM head audio is tested alone."""
        utterance_id = protocol.new_id("utt-test")
        path = self.cfg.audio_abs_path(f"{utterance_id}.wav")
        duration = write_pcm_wav(test_tone_pcm(), 22050, path)
        log.info("Test tone requested by the plugin: %s", self.cfg.audio_rel_path(path.name))
        turn = Turn("test_tone")
        turn.step("wav written", wav=self._rel(path), seconds=round(duration, 2))
        self._utt_turn[utterance_id] = turn
        return self._queue_speech(utterance_id, "Test-Ton", path, duration, interrupt=True)

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
