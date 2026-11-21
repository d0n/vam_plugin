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

import json
import logging
import queue
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__, body_tools, logsetup, pose_commands, protocol, wakeup
from .atomicfile import atomic_copy
from .audio import (
    BargeInRule,
    EchoGate,
    InputProcessor,
    MicController,
    MicSettings,
    apply_mic_config,
    silero_model_path,
)
from .config import ENGINES_AVAILABLE, PLUGIN_DATA_SUBDIR, Config
from .emotion import EmotionDirector, offered as offered_expressions
from .latency import LatencyStats, LatencyTrace, describe
from .logsetup import Turn
from .pipeline import Directive, LanguageModel, SentenceSplitter, SpeechToText, TextToSpeech
from .pipeline import tts as tts_module
from .pipeline.context import clean_scene_event, is_silent, nudge_text, scene_event_text, time_context
from .pipeline.engines import EngineSet
from .pipeline import http as http_module
from .pipeline.http import ApiError, HttpClient
from .pipeline.realtime import KEY_REJECTED as REALTIME_KEY_REJECTED
from .pipeline.tts import test_tone_pcm, write_pcm_wav
from .pipeline.xai import ToolCall
from . import characters as characters_module
from . import personas as personas_module
from .proactive import ProactiveTimer
from .realtime_voice import RealtimeVoice
from .settings_file import CHOICES, DEFAULTS, RANGES, _check_value
from .transport import Transport
from .vamjson import as_bool, as_number

log = logging.getLogger(__name__)

LEVEL_INTERVAL_S = 0.2  # mic_level rate (5 Hz)
SCENE_EVENT_MAX_PENDING = 5  # scene events waiting for the AI to be free (older ones drop out)
SCENE_EVENT_MAX_AGE_S = 30.0  # a scene event older than this is not worth reacting to any more
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



def describe_selftest(t: dict[str, Any]) -> tuple[str, bool]:
    """One line from the plugin's "selftest" (Body.SelfTestJson) and whether something is missing."""
    if t.get("error"):
        return f"ERROR {t['error']}", True
    problems = False
    parts = []
    storage = str(t.get("pose_storage", ""))
    parts.append("pose storage yes" if storage == "ok" else f"pose storage NO ({storage})")
    problems |= storage != "ok"
    parts.append(f"poses {as_number(t.get('poses')) or 0:.0f} (files {as_number(t.get('pose_files')) or 0:.0f})")
    breath = as_bool(t.get("breath_morph_found"))
    parts.append(f"breath morph '{t.get('breath_morph', '')}' {'found' if breath else 'NOT found'}")
    problems |= not breath
    found, total = as_number(t.get("expression_morphs_found")) or 0, as_number(t.get("expression_morphs_total")) or 0
    missing = [str(m) for m in (t.get("expression_morphs_missing") or [])]
    if total:
        gone = f" (missing: {', '.join(missing)})" if missing else ""
        parts.append(f"expression morphs {found:.0f}/{total:.0f}{gone}")
        problems |= bool(missing)
    timeline_gestures = as_number(t.get("timeline_gestures")) or 0
    if timeline_gestures:
        has = as_bool(t.get("timeline"))
        parts.append(f"Timeline {'yes' if has else 'NO'} for {timeline_gestures:.0f} gesture(s)")
        problems |= not has
    return "; ".join(parts), problems

class PoseDecision:
    """Result of the pose gate for one input: the matched command, whether it can run, and the steps to apply."""

    def __init__(self, entry: dict[str, str], ok: bool, steps: list[tuple[Any, ...]]):
        self.entry, self.ok, self.steps = entry, ok, steps


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
        self.engine_set.characters = characters_module.normalize(getattr(config, "characters", None))
        for kind in ("stt", "llm", "tts"):
            self.engine_set.select(kind, getattr(config, kind))
        for kind, instance in (("stt", stt), ("llm", llm), ("tts", tts)):
            if instance is not None:  # explicit engines (tests, custom setups)
                self.engine_set.instances[kind] = instance
        self._clock = clock
        self.remote: Any = None  # remote.RemoteControl (version 31, off by default); its queue is run from tick()
        settings, errors = apply_mic_config(MicSettings(), config.mic)
        for e in errors:
            log.warning("config 'mic': %s", e)
        self.mic_settings = settings
        self.gate = gate or EchoGate(tail_s=settings.echo_tail_s)
        self.input = InputProcessor(settings, self.gate, config.sample_rate, config.frame_ms,
                                    silero_model=silero_model_path(config.vam_root))
        self._configure_barge()
        self.mic = mic  # None = no microphone (text only)
        self.latency = LatencyStats()  # end of speech -> first sound, last value + rolling average
        self.history: list[dict[str, str]] = []
        self.body_info: dict[str, Any] = {}  # last ready/heartbeat from the AIBody plugin
        self._last_selftest: dict[str, Any] | None = None  # plugin self test last logged
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
        self._user_was_talking = False  # rising edge of the VAD: warm_connections()
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
        self._scene_events: deque[tuple[float, str]] = deque(maxlen=SCENE_EVENT_MAX_PENDING)  # (time, text) not yet answered
        proactive = self.engine_set.ai["proactive"]
        self.proactive = ProactiveTimer(bool(proactive["enabled"]), float(proactive["idle_seconds"]), clock)
        self.emotion = EmotionDirector(self.engine_set.ai["emotion"], clock)  # fallback expression, fade, listening
        # personas and memory (personas.py): files below Saves/PluginData/AIBody/personas
        self.personas = personas_module.PersonaStore(Path(config.vam_root or ".") / PLUGIN_DATA_SUBDIR / personas_module.PERSONAS_SUBDIR)
        self.persona_note = ""  # why the chosen persona is not in use
        self.memory_note = ""  # last memory problem (shown in the plugin)
        self._mem_cursor = 0  # history[_mem_cursor:] = the conversation not yet summarized
        self._memory_lock = threading.Lock()  # one summary at a time
        self._persona_names: tuple[float, list[str]] = (-1e9, [])
        self._load_persona()
        if (self.engine_set.persona or self.engine_set.memory_facts) and llm is None:
            self.engine_set.rebuild("llm")  # built before the persona was known
        if self.engine_set.persona and tts is None:
            self.engine_set.rebuild("tts")  # the persona's voice / language
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
        if self.remote is not None:
            self.remote.process(self)
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
        self._maybe_scene_event()
        self._maybe_emotion()
        self._maybe_memory()
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
                return False, "Question and Answer: xAI speech recognition -> Grok -> xAI voice, speech only"
            if any(v != OFFLINE_ENGINES[k] for k, v in self.engine_set.requested.items()):
                return False, "Question and Answer with the engines selected in the menu (no xAI API key)"
            return False, ("Question and Answer without an xAI API key: test engines only (echo + tone) - "
                           "enter an API key from console.x.ai (not a Grok subscription token) in the plugin field "
                           "'XAI API Token', or set XAI_API_KEY / a key file in config.json ai.xai.key_file")
        if mode == "chain":
            return False, "Chain selected (speech recognition -> language model -> text-to-speech)"
        if self.realtime_off:
            return False, (f"Realtime off: {self.realtime_off} - falling back to the chain"
                           f"{' with xAI' if has_key else ''}; 'API Reconnect' tries again")
        if mode == "realtime":
            return (True, "") if has_key else (False, "Realtime not configured (no xAI API key) - chain running")
        if self.engine_set.requested.get("tts") == "elevenlabs":
            return False, "Auto: chain, because Text-to-speech = elevenlabs is selected"
        if not has_key:
            return False, "Auto: chain (no xAI API key for realtime)"
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
        log.warning("Realtime voice is not answering (%s). Using the normal chain (speech recognition + language "
                    "model + voice) from now on; 'API Reconnect' (tab Voice) tries realtime again.", reason)
        if self.realtime is not None and self.realtime.turn is not None:
            self.realtime.turn.step("realtime given up", reason=reason, fallback="chain")
        self.realtime_off = reason
        self.turn_status = (f"Realtime did not respond ({reason}). Using the normal chain (speech recognition + language model "
                            "+ voice) from now on - please ask again. 'API Reconnect' (tab Voice) tries realtime again")
        self._update_mode()
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S

    def _update_mode(self) -> None:
        want, note = self._want_realtime()
        self.engine_set.set_override(self._chain_override())
        key = self.engine_set.key("xai")
        if self.realtime is not None and (not want or key != self._realtime_key):
            self.realtime.stop()
            self.realtime = None
            log.info("Realtime stopped (%s)", note or "key changed")
        if want and self.realtime is None:
            self.realtime = RealtimeVoice(self, key, connector=self._realtime_connector)
            self._realtime_key = key
            self.realtime.start()
        if not want:
            self.mode_note = note
            return
        client = self.realtime.client
        settings = self.realtime.settings
        if client.last_error and client.last_error.startswith(REALTIME_KEY_REJECTED):
            self.engine_set.rejected["xai"] = f"rejected by the realtime server ({client.last_error})"
        if client.ready:
            self.engine_set.rejected.pop("xai", None)
            self.mode_note = f"Realtime connected ({client.model}, voice {settings['voice']})"
        elif client.failures == 0 and not client.last_error:
            self.mode_note = "Realtime connecting ... (the normal chain answers meanwhile)"
        else:
            self.mode_note = (f"Realtime not connected: {client.last_error or 'disconnected'} - "
                              f"falling back to the chain (speech recognition + language model + voice), "
                              f"retrying in {client.retry_in():.0f} s")
            if client.last_error and client.last_error.startswith(REALTIME_KEY_REJECTED):
                self.mode_note += ". Check the key in the field 'XAI API Token' (tab Voice)"

    def mode_info(self) -> dict[str, Any]:
        return {"requested": self.mode_requested, "active": self.active_mode, "status": self.mode_note}

    def proactive_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"enabled": self.proactive.enabled, "idle_seconds": self.proactive.idle_seconds}
        if self.proactive.enabled and not self.proactive.active:
            pass  # speech delay timer 0 s: off; the plugin shows "Proactive talking: off (speech delay timer 0 s)"
        elif self.proactive.active and self.speech_only:
            info["status"] = "paused in Question and Answer mode"
        elif self.proactive.active and not self._can_nudge_engine():
            info["status"] = "waiting: needs realtime or language model xai"
        return info

    # -- time / activity -------------------------------------------------------------------

    def clock_now(self) -> float:
        """The app's monotonic clock in seconds (a fake clock in tests)."""
        return self._clock()

    def now(self) -> datetime:
        return self._wall()

    def since_last_exchange(self) -> float | None:
        return None if self._last_exchange is None else self._clock() - self._last_exchange

    def on_user_activity(self) -> None:
        self.proactive.user_activity()

    def on_exchange(self) -> None:
        self._last_exchange = self._clock()

    def _log_selftest(self, selftest: Any) -> None:
        """Logs the plugin's in-game self test (pose storage, morphs, ...) once per change, so the
        companion console / companion.log shows what only VaM can check."""
        if not isinstance(selftest, dict) or selftest == self._last_selftest:
            return
        self._last_selftest = dict(selftest)
        text, problems = describe_selftest(selftest)
        (log.warning if problems else log.info)("Plugin self-test: %s", text)

    # -- body tools (function calls) -------------------------------------------------------

    def body_lists(self) -> body_tools.BodyLists:
        return body_tools.BodyLists.from_body_info(self.body_info, DEFAULT_EXPRESSIONS, DEFAULT_GESTURES)

    def tools_allowed(self) -> tuple[bool, str]:
        """Body tools only outside the simple Q&A mode and while Body control is on."""
        if self.speech_only:
            return False, "simple Q&A mode: speech only, no body control"
        if as_bool(self.body_info.get("body_control", True)) is False:
            return False, "body control is off in the plugin"
        return True, ""

    def offered_tools(self) -> list[dict[str, Any]]:
        allowed, _ = self.tools_allowed()
        return body_tools.tools(self.body_lists()) if allowed else []

    def tool_commands(self, name: str, arguments: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """A function call from the model -> (plugin commands, result for the model)."""
        allowed, why = self.tools_allowed()
        commands, result = body_tools.resolve(name, arguments, self.body_lists(), allowed, why)
        if any(t == "expression" for t, _ in commands):
            self.emotion.note_ai_expression()
        return [self.body_command(t, **f) for t, f in commands], result

    def send_directive(self, item: Directive) -> None:
        if item.expression:
            self.emotion.note_ai_expression()
            self.send(self.body_command("expression", name=item.expression, intensity=1.0, blend=0.4))
        if item.gesture:
            self.send(self.body_command("gesture", name=item.gesture))

    # -- personas and memory ----------------------------------------------------------------

    PERSONA_LIST_REFRESH_S = 5.0

    @property
    def persona_in_use(self) -> str:
        p = self.engine_set.persona
        return p.name if p else ""

    def persona_names(self) -> list[str]:
        now = self._clock()
        if now - self._persona_names[0] >= self.PERSONA_LIST_REFRESH_S:
            self._persona_names = (now, self.personas.names())
        return list(self._persona_names[1])

    def _load_persona(self) -> None:
        """Loads the persona named in ai.persona_name (and its memory) into the engine settings."""
        name = str(self.engine_set.ai.get("persona_name") or "").strip()
        persona, problems = (None, []) if not name else self.personas.load(name)
        for problem in problems:
            log.warning("Persona: %s", problem)
        self.persona_note = "; ".join(problems) if name and persona is None else ""
        if persona is not None:
            log.info("Persona: %s (voice %s, language %s)", persona.label, persona.voice or "from the menu",
                     persona.language or self.engine_set.ai.get("language"))
        self.engine_set.persona = persona
        self._load_memory()

    def switch_persona(self) -> None:
        """The plugin's Persona menu changed: save what was learned, then start over as the new persona."""
        self.finish_memory_session("the persona changes")
        self._load_persona()
        self.history.clear()
        self._mem_cursor = 0
        for kind in ("llm", "tts"):
            self.engine_set.rebuild(kind)  # new instructions (a new conversation), voice and language
        if self.realtime is not None:
            self.realtime.stop()  # instructions, voice and language are part of the session
            self.realtime = None
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S

    def _memory_cfg(self) -> dict[str, Any]:
        return self.engine_set.ai["memory"]

    def memory_enabled(self) -> bool:
        p = self.engine_set.persona
        return bool(self._memory_cfg()["enabled"]) and (p is None or p.memory)

    def _memory_key(self) -> str:
        return self.persona_in_use or personas_module.DEFAULT_MEMORY_KEY

    def _load_memory(self) -> None:
        facts: list[str] = []
        if self.memory_enabled():
            facts = personas_module.load_facts(self.personas.memory_path(self._memory_key()),
                                               int(self._memory_cfg()["max_facts"]))
            if facts:
                log.info("Memory: %d notes about the user loaded (%s)", len(facts),
                         self.personas.memory_path(self._memory_key()))
        self.engine_set.memory_facts = facts

    def memory_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"enabled": self.memory_enabled(), "facts": len(self.engine_set.memory_facts)}
        if self.memory_note:
            info["note"] = self.memory_note
        return info

    def _session_exchanges(self) -> int:
        return sum(1 for item in self.history[self._mem_cursor:] if item.get("role") == "user")

    def _maybe_memory(self) -> None:
        """A conversation counts as over after session_idle_minutes of silence: summarize it."""
        if not self.memory_enabled() or self._last_exchange is None:
            return
        cfg = self._memory_cfg()
        if self._session_exchanges() < int(cfg["min_exchanges"]) or not self._can_speak_now():
            return
        if self._clock() - self._last_exchange >= float(cfg["session_idle_minutes"]) * 60:
            self.finish_memory_session("silence")

    def finish_memory_session(self, reason: str, wait: bool = False) -> None:
        """Summarizes the conversation since the last summary into the memory file (on a thread; with
        wait=True, when the app stops, right here)."""
        if not self.memory_enabled() or self._session_exchanges() < int(self._memory_cfg()["min_exchanges"]):
            return
        snippet = list(self.history[self._mem_cursor:])
        self._mem_cursor = len(self.history)
        key, max_facts = self._memory_key(), int(self._memory_cfg()["max_facts"])
        log.info("Memory: updating the notes about the user (%s)", reason)
        if self.background_turns and not wait:
            threading.Thread(target=self._memory_job, args=(key, snippet, max_facts, 60.0), daemon=True,
                             name="aibody-memory").start()
        else:
            self._memory_job(key, snippet, max_facts, 15.0 if wait else 60.0)

    def _memory_job(self, key: str, snippet: list[dict[str, str]], max_facts: int, timeout: float) -> None:
        with self._memory_lock:
            path = self.personas.memory_path(key)
            old = personas_module.load_facts(path, max_facts)
            llm = self.engine_set.memory_llm()
            if llm is None:
                self.memory_note = "no xAI key: memory not updated"
                log.info("Memory: %s", self.memory_note)
                return
            try:
                instructions, text = personas_module.summary_request(old, snippet, max_facts)
                answer = llm.complete(instructions, text, timeout=timeout)
            except Exception as e:  # noqa: BLE001 - network / API errors: the old notes stay
                if isinstance(e, ApiError):
                    self.engine_set.note_api_error(e)
                self.memory_note = f"memory not updated: {_short(str(e), 100)}"
                log.warning("Memory: %s", self.memory_note)
                return
            facts = personas_module.parse_facts(answer, max_facts)
            if facts is None or (not facts and old):
                # no list, or an empty one that would wipe the notes: keep them (forgetting = the Forget memory button)
                self.memory_note = "memory not updated: the answer was not a usable list"
                log.warning("Memory: %s", self.memory_note)
                return
            try:
                personas_module.save_facts(path, facts)
            except OSError as e:
                self.memory_note = f"memory not saved: {e}"
                log.warning("Memory: %s", self.memory_note)
                return
            self.memory_note = ""
            if key == self._memory_key() and self.memory_enabled():
                self.engine_set.memory_facts = facts  # the notes in the next instructions (realtime refreshes them)
            log.info("Memory: %d notes about the user saved (%s)", len(facts), path)

    def forget_memory(self) -> None:
        """Button "Forget memory": deletes the memory file of the persona in use and starts a fresh conversation."""
        with self._memory_lock:
            deleted = personas_module.forget(self.personas.memory_path(self._memory_key()))
        self.engine_set.memory_facts = []
        self.memory_note = ""
        self.history.clear()
        self._mem_cursor = 0
        self.engine_set.rebuild("llm")  # the old conversation still holds the notes in its instructions
        if self.realtime is not None:
            self.realtime.stop()
            self.realtime = None
        log.info("Memory: forgotten (%s)", "file deleted" if deleted else "there was none")
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S

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
        log.info("Proactive talking: %.0f s of silence passed (speech delay timer) - the AI may say something on its own",
                 self.proactive.idle_seconds)
        self._dispatch_nudge(text)

    def _dispatch_nudge(self, text: str) -> None:
        if self.active_mode == "realtime":
            self.realtime.nudge(text)
        elif self.background_turns:
            self._submit("nudge", text)
        else:
            for step in self._turn("nudge", text, self._generation):
                self._apply(step)

    # -- scene events (a VaM trigger set the plugin's "Scene event" text) ------------------------

    def _scene_events_cfg(self) -> dict[str, Any]:
        cfg = self.engine_set.ai.get("scene_events")
        return cfg if isinstance(cfg, dict) else {}

    def handle_scene_event(self, event: dict[str, Any]) -> None:
        text = clean_scene_event(event.get("text"))
        if not text:
            return
        if not as_bool(self._scene_events_cfg().get("enabled", True)):
            log.info("Scene event ignored (ai.scene_events.enabled is false): %s", text)
            return
        if not self._can_nudge_engine():
            log.info("Scene event ignored (the AI answers only when asked in simple Q&A mode, or no engine takes notes): %s", text)
            return
        log.info("Scene event: %s", text)
        self._scene_events.append((self._clock(), text))

    def _maybe_scene_event(self) -> None:
        now = self._clock()
        while self._scene_events and now - self._scene_events[0][0] > SCENE_EVENT_MAX_AGE_S:
            dropped = self._scene_events.popleft()
            log.info("Scene event dropped (the AI was busy for %.0f s): %s", SCENE_EVENT_MAX_AGE_S, dropped[1])
        if not self._scene_events or not self._can_speak_now() or not self._can_nudge_engine():
            return
        # All events that waited are told in one note, oldest first.
        texts = [t for _, t in self._scene_events]
        self._scene_events.clear()
        prompt = str(self._scene_events_cfg().get("prompt") or "")
        text = scene_event_text(prompt, "; ".join(texts), self.now(), self.since_last_exchange())
        self.proactive.ai_activity()
        self._dispatch_nudge(text)

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
            if isinstance(event, dict) and event.get("type") in protocol.RETIRED_EVENTS:
                log.debug("event %r is retired (no microphone selection) - ignored", event.get("type"))
                continue
            protocol.register_event_secrets(event)
            problems = protocol.validate_event(event)
            if problems:
                log.warning("Ignoring event: %s (%s)", "; ".join(problems), protocol.loggable(event))
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
                self._log_selftest(event.get("selftest"))
            elif type_ == "config":
                self.handle_config(event)
            elif type_ == "scene_event":
                self.handle_scene_event(event)
            elif type_ == "ptt":
                self.handle_ptt(bool(as_bool(event.get("active"))))
            elif type_ == "test_tone":
                self.play_test_tone()
            elif type_ == "memory_forget":
                self.forget_memory()
            elif type_ == "reconnect":
                self.reconnect_api()
            elif type_ == "error":
                log.warning("The plugin reported a problem (%s): %s - see the VaM log (lines starting with AIBody) for details",
                            event.get("code"), event.get("message"))
                if event.get("code") == "audio_failed":
                    self._audio_failed(str(event.get("reply_to") or ""), str(event.get("message") or ""))
            else:
                log.debug("event: %s", protocol.loggable(event))
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
        if type_ == "speech_started" and getattr(turn, "latency", None):
            result = turn.latency.finish(self._clock())
            if result:
                self.latency.add(result)
                log.info("Latency %s to first sound: %s", turn.id, describe(result))
                turn.step("latency", total_s=result["total_s"],
                          parts=" ".join(f"{k}={v}" for k, v in result["parts"].items()))
                self._last_heartbeat = -HEARTBEAT_INTERVAL_S  # show it right away

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
            audio_out=self.audio_info(), turn=self.turn_status, latency=self.latency.info(),
            personas=self.persona_names(), persona=self.persona_in_use, persona_note=self.persona_note,
            memory=self.memory_info(),
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
                    ("xai", "key_file"), ("elevenlabs", "key_file"), ("persona_name",), ("memory", "enabled")}

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

    def apply_keys(self, data: Any) -> list[str]:
        """The plugin's "XAI API Token" field (config event keys.xai, plain text, no format check).
        A changed key reconnects realtime like "API Reconnect". Errors never contain the token."""
        if data is None:
            return []
        if not isinstance(data, dict):
            return ["keys: must be an object"]
        value = data.get("xai")
        if value is None:
            return []
        if not isinstance(value, str):
            return ["keys.xai: must be a string"]
        if not self.engine_set.set_ui_key("xai", value):
            return []
        log.info("XAI API Token from the plugin field %s", "set" if value.strip() else "cleared")
        self.realtime_off = ""  # a new key gives realtime a new chance
        self._update_mode()  # stops realtime on a changed key and reconnects with the new one
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S  # the plugin shows the key status right away
        return []

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
        if ("persona_name",) in changed:
            self.switch_persona()
        elif ("memory", "enabled") in changed:
            self._load_memory()
            self.engine_set.rebuild("llm")  # the notes are part of the instructions
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

    def apply_characters(self, data: Any) -> list[str]:
        """The plugin's character wizard answers (config event / config.json 'characters')."""
        if data is None:
            return []
        if not isinstance(data, dict):
            return ["characters: must be an object"]
        new = characters_module.normalize(data)
        if new == self.engine_set.characters:
            return []
        self.engine_set.characters = new
        self.engine_set.rebuild("llm")  # the genders are part of the instructions
        return []

    def handle_config(self, event: dict[str, Any]) -> None:
        settings, errors = apply_mic_config(self.mic_settings, event.get("mic"))
        errors += self.apply_keys(event.get("keys"))  # first: the engines below already use the new key
        errors = errors + self.apply_engines(event.get("engines")) + self.apply_ai(event.get("ai"))
        errors += self.apply_advanced(event.get("advanced"))
        errors += self.apply_characters(event.get("characters"))
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
        if active:
            self.warm_connections()  # version 36: TLS handshakes while the user talks, not after
        if active and self.mic_settings.ptt_interrupts and (not self.gate.is_open or self._busy.is_set()):
            self.cancel_turns()  # the user talks: the answer being prepared is dropped ...
            self.send(self.body_command("stop_speaking"))  # ... and the body stops
        utterance = self.input.set_ptt(active)
        if utterance:
            self.handle_utterance(utterance)

    def mic_state(self) -> dict[str, Any]:
        s = self.mic_settings
        error = self.mic.error if self.mic else "The microphone is not used: the app runs in text-only mode (--no-mic)"
        state = {
            "enabled": s.enabled,
            "capturing": bool(self.mic and self.mic.capturing),
            "mode": s.mode,
            "ptt_active": self.input.ptt_active,
            "vad": self.input.vad_info.text,  # the voice detector that really runs
        }
        if self.input.vad_info.note:
            state["vad_note"] = self.input.vad_info.note  # why the chosen detector is not used
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
        talking = self.input.segmenter.in_speech
        if talking and not self._user_was_talking:
            self.warm_connections()  # version 36: the user started talking: open the API connections now
        self._user_was_talking = talking
        if self.input.barge_frames:
            return self.voice_barge_in(self.input.take_barge() or [])
        return self.handle_utterance(utterance) if utterance else None

    def warm_connections(self) -> None:
        """Version 36 (latency): opens kept-alive connections to the cloud engines' hosts in the background (one per
        engine on a host, at most 2), so STT, the language model and TTS of the coming turn skip the TCP / TLS
        handshake. Only for engines on the real network (not the offline test engines or injected test clients)."""
        hosts: dict[str, int] = {}
        for engine in (self.stt, self.llm, self.tts):
            url = getattr(engine, "base_url", None)
            client = getattr(engine, "http", None)
            if isinstance(url, str) and isinstance(client, HttpClient) and client.pooled and url.startswith("https://"):
                hosts[url] = hosts.get(url, 0) + 1
        for url, count in hosts.items():
            http_module.warm(url, min(count, 2))

    def _configure_barge(self) -> None:
        """ai.barge_in (config.json only): the loudness rule for talking over the body without headphones."""
        cfg = self.engine_set.ai.get("barge_in") or {}
        if not cfg.get("enabled"):
            self.input.barge = None
            return
        self.input.barge = BargeInRule(float(cfg["ratio"]), int(cfg["min_ms"]), self.cfg.frame_ms, float(cfg["floor"]))
        log.info("Voice barge-in by loudness rule: on (user %.1f times louder than the echo for %d ms) - only "
                 "voice activation mode; see docs/LOCAL_ENGINES.md", float(cfg["ratio"]), int(cfg["min_ms"]))

    def voice_barge_in(self, frames: list[bytes]) -> str | None:
        """The loudness rule fired: the user talks over the body. The body stops, the
        gate opens, the frames of the user's stretch are processed as the start of the utterance."""
        log.info("Voice barge-in: the user talks over the body - stopping it")
        self.cancel_turns()
        self.send(self.body_command("stop_speaking"))
        self.gate.force_open()
        if self.realtime is not None and self.active_mode == "realtime":
            self.realtime.barge_in(manual=True)
        self.on_user_activity()
        if self.active_mode == "realtime":
            self.realtime.send_frames(frames)
            return None
        text = None
        for frame in frames:
            utterance = self.input.process(frame, gained=True)
            if utterance:
                text = self.handle_utterance(utterance)
        return text

    def handle_utterance(self, utterance: bytes) -> str:
        """Transcribes and answers an utterance. Returns the text (inline) or "" (queued)."""
        self.on_user_activity()
        t0 = self._clock()  # VAD end / push-to-talk release: the utterance is complete
        if self.background_turns:
            self._submit("audio", utterance, t0)
            return ""
        text = ""
        for step in self._turn("audio", utterance, self._generation, t0):
            if step[0] == "heard":
                text = step[1]
            self._apply(step)
        return text

    def handle_user_text(self, text: str) -> None:
        """Typed text (console): the same answer path as speech, without speech to text."""
        self.on_user_activity()
        t0 = self._clock()  # Enter
        if self.background_turns:
            self._submit("text", text, t0)
            return
        for step in self._turn("text", text, self._generation, t0):
            self._apply(step)

    # -- pose commands (version 32) -----------------------------------------------------------

    def pose_vocabulary(self) -> pose_commands.PoseVocabulary:
        """The commands: the plugin's list (status field pose_commands, live), else config.json poses.commands."""
        raw = self.body_info.get("pose_commands")
        if isinstance(raw, list):
            entries, _ = pose_commands.validate_entries(raw)
        else:
            entries, _ = pose_commands.validate_entries((self.cfg.poses or {}).get("commands", []))
            if not entries:
                entries = pose_commands.starter_entries()   # version 35: never an empty vocabulary from the file
        return pose_commands.PoseVocabulary(entries)

    def pose_names(self) -> list[str]:
        return [str(p) for p in self.body_info.get("poses") or [] if str(p)]

    def pose_gate_active(self) -> bool:
        """Pose commands work in every mode (they are no AI tool), but not while Body control is off in the plugin."""
        return as_bool(self.body_info.get("body_control", True)) is not False

    def pose_decision(self, text: str) -> PoseDecision | None:
        """None = the input is no pose command (it goes on to the AI as usual). Otherwise what to do: the pose command
        when the pose exists on the character, or just a status line (unavailable). Never a spoken reply: a body command
        is an action, not a conversation; it needs no network or language model and nothing talks over the pose."""
        vocabulary = self.pose_vocabulary()
        entry = vocabulary.match(text)
        if entry is None:
            return None
        names = self.pose_names()
        actual = vocabulary.resolve(entry, names)
        if actual is None:
            message = (f"Pose command '{entry['command']}' is unavailable: the character has no pose '{entry['pose']}' "
                       "(add a pose file or link the command to another pose with 'Add Pose')")
            log.warning(message)
            return PoseDecision(entry, False, [("status", message)])
        command = self.body_command("pose", json=vocabulary.reply_json(entry), command=entry["command"])
        log.info("Pose command '%s' -> %s", entry["command"], command["json"])
        return PoseDecision(entry, True, [("command", command), ("status", f"Pose command: {entry['command']} ({actual})")])

    def pose_command(self, text: str) -> tuple[bool, str]:
        """Runs a pose command given as text (remote control, realtime transcript): the same gate as typed or spoken input."""
        if not self.pose_gate_active():
            return False, "body control is off in the plugin"
        decision = self.pose_decision(text)
        if decision is None:
            return False, f"{text!r} is not a pose command"
        for step in decision.steps:
            self._apply(step)
        return decision.ok, "" if decision.ok else str(decision.steps[0][1])

    def say_text(self, text: str, interrupt: bool = False) -> None:
        """Speaks exactly this text (remote control): text to speech -> VaM, no language model. Runs like a turn
        (worker thread), so a slow speech engine never blocks the link."""
        text = text.strip()
        if not text:
            return
        self.on_user_activity()
        if self.background_turns:
            self._submit("say", (text, interrupt))
            return
        for step in self._turn("say", (text, interrupt), self._generation):
            self._apply(step)

    # -- turns: STT -> LLM -> TTS ----------------------------------------------------------

    def _submit(self, kind: str, data: Any, t0: float | None = None) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, name="aibody-turns", daemon=True)
            self._worker.start()
        self._jobs.put((kind, data, self._generation, t0))

    def _work(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                return
            kind, data, generation, t0 = job
            if generation != self._generation:
                continue  # cancelled before it started
            self._busy.set()
            try:
                for step in self._turn(kind, data, generation, t0):
                    self._results.put((generation, *step))
                    wakeup.notify()  # version 36: the main loop sends it now, not after its next poll sleep
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

    def _turn(self, kind: str, data: Any, generation: int, t0: float | None = None):
        """Yields steps: ("heard", text), ("command", cmd), ("speak", id, text, path, duration),
        ("status", text) for the plugin's status box."""
        if kind == "say":
            yield from self._say_steps(*data)
            return
        turn = Turn(kind, **(_pcm_stats(data, self.cfg.sample_rate) if kind == "audio" and logsetup.is_verbose()
                             else {"text": str(data)} if kind == "text" else {}))
        if t0 is not None:
            turn.latency = LatencyTrace(t0, "chain")
        self.emotion.begin_answer()
        names = self.engine_set.active_names
        turn.step("path", mode=self.mode_requested, active=self.active_mode, chain=f"{names['stt']} -> "
                  f"{names['llm']} -> {names['tts']}", selected="/".join(self.engine_set.requested.values()),
                  speech_only=self.speech_only, note=self.mode_note)
        try:
            if kind == "audio":
                t = turn.elapsed()
                text = self._transcribe(data)
                # always on the console (INFO), before the answer starts, so the log shows what the
                # app reacted to; the turn trace below only appears with the verbose log
                log.info("Heard (STT %s): %r", self.engine_set.active_names["stt"], text)
                if turn.latency:
                    turn.latency.mark("stt", self._clock())
                turn.step("stt", engine=self.engine_set.active_names["stt"],
                          ms=round((turn.elapsed() - t) * 1000), text=text, error=self._stt_error or None)
                yield ("heard", text, len(data) / 2 / self.cfg.sample_rate)
                if not text:
                    turn.step("end", result="nothing understood")
                    return
            else:
                text = str(data)
                if kind == "text":
                    yield ("status", f"Question (typed): {_short(text)}")
            self._check(generation)
            if kind in ("audio", "text") and self.pose_gate_active():
                decision = self.pose_decision(text)  # the HARD GATE: the whole input must equal a pose command
                if decision is not None:
                    turn.step("end", result="pose command", command=decision.entry["command"], applied=decision.ok)
                    yield from decision.steps
                    return
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
                if isinstance(item, ToolCall):
                    commands, result = self.tool_commands(item.name, item.arguments)
                    item.reply(result)
                    turn.step("llm tool call", name=item.name, arguments=item.arguments,
                              result=json.dumps(result, ensure_ascii=False))
                    for cmd in commands:
                        yield ("command", cmd)
                    continue
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
                        log.info("Proactive talking: the AI chose to stay silent")
                        return
                    for d in held:
                        yield from self._directive_steps(d)
                if turn.latency and not said:
                    first = getattr(self.llm, "first_delta_at", None)
                    turn.latency.mark("llm_first_token", first if first is not None else self._clock())
                    turn.latency.mark("first_sentence", self._clock())
                turn.step(f"llm sentence {len(said) + 1}", text=sentence)
                utterance_id = protocol.new_id("utt")
                path = self.cfg.audio_abs_path(f"{utterance_id}.wav")
                t = turn.elapsed()
                tts_before = len(problems)
                duration = self._synthesize(sentence, path, problems)
                if turn.latency and not said:
                    done, write_s = self._clock(), tts_module.LAST_WRITE_S["s"]
                    turn.latency.mark("tts", done - write_s)
                    turn.latency.mark("write", done)
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
                    yield ("status", f"Answer ({len(said)} sentence(s), {self.engine_set.active_names['llm']} -> "
                                     f"{self.engine_set.active_names['tts']}): {_short(' '.join(said))}")
                else:
                    yield ("status", "No answer: the language model returned no text")
        except _CancelledError:
            turn.step("end", result="cancelled (barge-in)")
            log.info("Answer cancelled")

    def _say_steps(self, text: str, interrupt: bool):
        """Remote control "say": the sentences of the text are synthesized one after the other and spoken as given."""
        splitter = SentenceSplitter()
        sentences = [x.strip() for x in splitter.feed(text) + splitter.flush() if x.strip()] or [text]
        problems: list[str] = []
        spoken = 0
        for sentence in sentences:
            utterance_id = protocol.new_id("utt")
            path = self.cfg.audio_abs_path(f"{utterance_id}.wav")
            duration = self._synthesize(sentence, path, problems)
            yield ("speak", utterance_id, sentence, path, duration, interrupt and spoken == 0)
            spoken += 1
        if problems:
            yield ("status", " | ".join(dict.fromkeys(problems)))
        else:
            yield ("status", f"Said (remote, {spoken} sentence(s)): {_short(text)}")

    def _voice_of(self, tts: str) -> str | None:
        if tts == "xai":
            return str(self.engine_set.xai_settings()["voice"])
        if tts == "elevenlabs":
            return str(self.engine_set.elevenlabs_settings()["voice_id"])
        return None

    def _directive_steps(self, item: Directive):
        if item.expression:
            self.emotion.note_ai_expression()
            yield ("command", self.body_command("expression", name=item.expression, intensity=1.0, blend=0.4))
        if item.gesture:
            yield ("command", self.body_command("gesture", name=item.gesture))

    def _transcribe(self, utterance: bytes) -> str:
        try:
            return self.stt.transcribe(utterance, self.cfg.sample_rate).strip()
        except Exception as e:  # noqa: BLE001 - a failed request must not end the turn silently
            if isinstance(e, ApiError):
                self.engine_set.note_api_error(e)
            self._stt_error = (f"Speech recognition error: {_short(str(e), 120)} - using the test engine instead; "
                               "check your xAI key (tab Voice) and internet connection")
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
        if hasattr(llm, "first_delta_at"):
            llm.clock = self._clock
        user_text = text
        text = prompt or text
        expressions = offered_expressions(self.body_info.get("expressions") or DEFAULT_EXPRESSIONS)
        gestures = list(self.body_info.get("gestures") or DEFAULT_GESTURES)
        produced = False
        try:
            if hasattr(llm, "stream"):
                kwargs = {}
                if getattr(llm, "supports_tools", False):
                    kwargs["tools"] = self.offered_tools()
                    kwargs["tool_rules"] = body_tools.rules(self.body_lists()) if kwargs["tools"] else ""
                for item in llm.stream(text, self.history, expressions, gestures, **kwargs):
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
                problems.append(f"Language model error: {_short(str(e), 120)}"
                                + ("" if produced or nudge else " - fallback answer"))
            if produced or nudge:
                return
        if self.speech_only:
            language = self.engine_set.language()
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
                problems.append(f"Text-to-speech error: {_short(str(e), 120)} - you hear a fallback tone ({name}) instead; "
                                "check your xAI / ElevenLabs key and internet connection")
            return fallback.synthesize(text, path)

    def _apply(self, step: tuple[Any, ...]) -> None:
        """Runs on the tick thread: sends what a turn produced."""
        kind = step[0]
        if kind == "heard":
            log.info("Heard: %r (%.1fs)", step[1], step[2])
            stt_error, self._stt_error = self._stt_error, ""
            if step[1]:
                self._set_turn(f"Heard: {_short(step[1])}")
            elif stt_error:
                self._set_turn(f"{stt_error} - no answer")
            elif self.engine_set.active_names.get("stt") == "null":
                self._set_turn("Nothing understood: speech recognition 'null' is a test engine that cannot understand speech. "
                               "Add an xAI API key (tab Voice, field 'XAI API Token') or type into the companion console")
            else:
                self._set_turn(f"Nothing understood: heard {step[2]:.1f} s of audio but speech recognition found no words. Try speaking louder or closer to the microphone")
            if not step[1] and self.engine_set.active_names.get("stt") == "null" and not self._null_stt_warned:
                self._null_stt_warned = True
                log.warning("Speech-to-text 'null' is a test engine that cannot understand speech, so you get no answer. "
                            "For a spoken conversation add an xAI API key and choose Speech-to-text 'xai' "
                            "(tab Voice > AI Character), or use realtime mode.")
        elif kind == "status":
            log.info("Status: %s", step[1])
            self._set_turn(step[1])
        elif kind == "command":
            self.send(step[1])
        elif kind == "speak":
            _, utterance_id, text, path, duration, *rest = step
            self._queue_speech(utterance_id, text, path, duration, bool(rest and rest[0]))

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
            self.audio_note = (f"VaM could not load the speech file {path.name} ({_short(message, 100)}). The audio folder is "
                               f"fixed to {current} (config.json connection.paths.audio): check that VaM can read it, "
                               "or remove that setting so the app can choose a folder by itself")
        elif failed_dir == current and self.cfg.audio_dir_index == 0:
            self.cfg.audio_dir_index = 1
            new = self.cfg.audio_rel_dir
            self.audio_note = (f"VaM could not load speech files from {failed_dir}, so the app now writes them to {new} "
                               "and sends the speech again. Nothing to do unless this also fails")
            log.warning("Audio: %s", self.audio_note)
        elif failed_dir == current:
            self.audio_note = (f"VaM could not play the speech files from either {self.cfg.audio_default_dirs[0]} or "
                               f"{current} ({_short(message, 100)}). What to do: 1) press 'Play test tone' (tab Voice) - "
                               "if that is silent too, the problem is in VaM or the character's head audio; "
                               "2) check that the app's --vam-root is the VaM folder you start VaM from; "
                               "3) see <VaM>/Saves/PluginData/AIBody/logs/companion.log")
            log.warning("Audio: %s", self.audio_note)
        self._last_heartbeat = -HEARTBEAT_INTERVAL_S
        if failed_dir == self.cfg.audio_rel_dir or not path.exists():
            return  # nothing better to try
        new_id = protocol.new_id("utt")
        new_path = self.cfg.audio_abs_path(f"{new_id}.wav")
        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_copy(path, new_path, durable=False)  # complete under its final name before the speak command follows
        except OSError as e:
            log.warning("Audio: could not copy the speech file %s to %s: %s - check that the folder is writable and the disk is not full", path, new_path, e)
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
            if getattr(turn, "latency", None):
                turn.latency.mark("speak_sent", self._clock())
            turn.step("speak sent", utterance=utterance_id, audio=rel, seconds=round(duration, 2),
                      queue="interrupt" if interrupt else "append")
        self.gate.on_speak_sent(utterance_id, duration, interrupt=interrupt)
        self._emotion_for_speech(text)
        self.emotion.note_speech()
        self.send(self.body_command(
            "speak", id_=utterance_id, audio=rel, text=text, duration=round(duration, 3),
            queue="interrupt" if interrupt else "append",
        ))
        log.info("Say (%.1fs): %s", duration, text)
        return utterance_id

    def _emotion_for_speech(self, text: str) -> None:
        """Fallback expression (words -> face) right before a sentence the AI gave no expression for."""
        if not self.tools_allowed()[0]:
            return  # simple Q&A / body control off: speech only
        step = self.emotion.for_speech(text, self.body_info.get("expressions") or DEFAULT_EXPRESSIONS)
        if step:
            name, intensity, blend = step
            log.info("Expression from the words (the AI chose none): %s", name)
            self.send(self.body_command("expression", name=name, intensity=intensity, blend=blend))

    def _maybe_emotion(self) -> None:
        """Listening brows while the user talks; back to neutral after a while without speech."""
        if not self.transport.connected or not self.tools_allowed()[0]:
            return
        user = self.input.ptt_active or self.input.segmenter.in_speech or bool(
            self.realtime is not None and self.realtime.user_speaking)
        step = self.emotion.user_speech(user, self.body_info.get("expressions") or [])
        if step:
            name, intensity, blend = step
            self.send(self.body_command("expression", name=name, intensity=intensity, blend=blend))
            return
        # the plugin's numbers and booleans may arrive as VaM strings ("false", "0"): vamjson helpers
        busy = (as_bool(self.body_info.get("speaking")) is True or (as_number(self.body_info.get("speech_queue")) or 0) > 0
                or self._busy.is_set() or not self._jobs.empty() or not self._results.empty() or user
                or (self.realtime is not None and self.realtime.responding))
        if self.emotion.fade_due(busy):
            if any(str(n).lower() == "neutral" for n in self.body_info.get("expressions") or DEFAULT_EXPRESSIONS):
                self.send(self.body_command("expression", name="neutral", intensity=1.0,
                                            blend=self.emotion.fade_seconds))
            else:
                self.send(self.body_command("reset_morphs", blend=self.emotion.fade_seconds))
                self.emotion.note_sent("neutral")

    def play_test_tone(self) -> str:
        """Plugin button "Test tone via companion": a chime WAV in the audio folder, sent as a normal
        speak (interrupting), so the path companion -> audio file -> VaM head audio is tested alone."""
        utterance_id = protocol.new_id("utt-test")
        path = self.cfg.audio_abs_path(f"{utterance_id}.wav")
        duration = write_pcm_wav(test_tone_pcm(), 22050, path)
        log.info("Test tone requested by the plugin: %s", self.cfg.audio_rel_path(path.name))
        turn = Turn("test_tone")
        turn.step("wav written", wav=self._rel(path), seconds=round(duration, 2))
        self._utt_turn[utterance_id] = turn
        self._set_turn(f"Test tone sent: {self.cfg.audio_rel_path(path.name)}")  # version 35: the plugin shows the answer
        return self._queue_speech(utterance_id, "Test tone", path, duration, interrupt=True)

    def stop_speaking(self) -> None:
        self.send(self.body_command("stop_speaking"))

    def body_command(self, type_: str, **fields: Any) -> dict[str, Any]:
        """Builds a body command (speak, expression, ...) for the plugin's body."""
        return protocol.make_command(type_, **fields)

    def send(self, command: dict[str, Any]) -> None:
        if command.get("type") == "expression":
            self.emotion.note_sent(str(command.get("name") or ""))
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
        self.finish_memory_session("the app stops", wait=True)
        self._jobs.put(None)
        if self.mic:
            self.mic.stop()
