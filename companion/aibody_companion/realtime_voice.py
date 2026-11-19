"""Realtime mode: the companion's microphone goes straight to Grok Voice (xAI realtime API) and
the spoken answer comes back as audio, cut into sentence-sized WAV segments that the plugin plays
through the normal file transport (`speak` commands), so the body starts talking on the first
segment.

  mic frame -> gain / level meter -> echo gate -> (resample) -> input_audio_buffer.append
  response.output_audio.delta + transcript deltas -> SegmentAssembler -> WAV -> speak
  function "express" -> existing expression / gesture commands
  input_audio_buffer.speech_started -> barge-in: stop the body (stop_speaking), drop the rest

Echo: without headphones the mic hears the body's voice. Like the chain mode, the mic is muted
(silence is sent) while the body speaks, unless ai.realtime.send_while_speaking is on (use
headphones then); voice barge-in needs that. Push-to-talk always interrupts.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from . import body_tools, protocol
from .emotion import offered as offered_expressions
from .latency import LatencyTrace
from .logsetup import Turn
from .pipeline.context import is_silent, time_rules
from .pipeline.realtime import (
    BACKOFF_S,
    DISCONNECTED,
    PCM_RATES,
    REALTIME_RULES,
    REALTIME_SPEECH_ONLY_RULES,
    RealtimeClient,
    SegmentAssembler,
    resample_pcm16,
)
from .pipeline.sentences import StreamParser
from .pipeline.tts import write_pcm_wav

if TYPE_CHECKING:
    from .orchestrator import Companion

log = logging.getLogger(__name__)

INSTRUCTIONS_REFRESH_S = 60.0  # the time line in the instructions is refreshed this often
NUDGE_HOLD_CHARS = 12  # a nudge answer is held until this much transcript shows it is not "[silent]"
# Connected but no answer this long after the user stopped talking: the companion gives realtime up
# (until "API Reconnect" / a mode change) and answers with the chain, see Companion.realtime_unresponsive.
ANSWER_TIMEOUT_S = 12.0
RESPONSE_LOCK_MAX_S = 90.0  # the mic stays locked at most this long for ONE answer (failsafe for a lost response.done)
# server events that get a line in the turn trace (verbose log); audio / transcript deltas are summed up
TRACE_EVENTS = {"input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped",
                "conversation.item.input_audio_transcription.completed", "response.created", "response.done",
                "response.function_call_arguments.done", "input_audio_buffer.timeout_triggered", "error",
                "session.updated", DISCONNECTED}


class RealtimeVoice:
    BACKOFF = BACKOFF_S  # reconnect delays (tests use shorter ones)

    def __init__(self, companion: Companion, key: str | None, connector: Any = None):
        self.c = companion
        ai = companion.engine_set.ai
        self.settings = ai["realtime"]
        self.out_rate = int(self.settings["sample_rate"])
        mic_rate = int(companion.cfg.sample_rate)
        self.in_rate = mic_rate if mic_rate in PCM_RATES else 24000
        self.assembler = SegmentAssembler(self.out_rate, float(self.settings["first_segment_s"]),
                                          min_s=max(2.0, float(self.settings["first_segment_s"])),
                                          max_s=float(self.settings["max_segment_s"]))
        kwargs: dict[str, Any] = {"connect_timeout": float(self.settings["connect_timeout_s"]),
                                  "backoff": self.BACKOFF}
        if connector is not None:
            kwargs["connector"] = connector
        self.client = RealtimeClient(str(self.settings["url"]), str(self.settings["model"]), key,
                                     self.session_config, **kwargs)
        self.response_id: str | None = None  # answer being received
        self.cancelled: set[str] = set()  # answers dropped by a barge-in
        self.user_speaking = False
        self._parser: StreamParser | None = None
        self._nudge_pending = False  # next response.created answers a nudge
        self._nudge_response: str | None = None
        self._held: list[tuple[bytes, str]] = []  # nudge segments held until it is clearly not silent
        self._last_instructions = 0.0
        self._response_started = 0.0
        self._sent_any = False
        self._waiting_since: float | None = None  # user stopped talking, no answer yet
        self.turn: Turn | None = None  # trace of the current realtime exchange
        self._audio_bytes = 0

    # -- session ---------------------------------------------------------------------------

    def _lists(self) -> tuple[list[str], list[str]]:
        from .orchestrator import DEFAULT_EXPRESSIONS, DEFAULT_GESTURES
        info = self.c.body_info
        return (offered_expressions(info.get("expressions") or DEFAULT_EXPRESSIONS),
                list(info.get("gestures") or DEFAULT_GESTURES))

    def instructions(self) -> str:
        expressions, gestures = self._lists()
        persona = str(self.c.engine_set.ai.get("persona") or "").strip()
        rules = REALTIME_RULES.format(expressions=", ".join(expressions), gestures=", ".join(gestures) or "none")
        if self.c.offered_tools():
            rules += "\n" + body_tools.rules(self.c.body_lists())
        else:
            rules = REALTIME_SPEECH_ONLY_RULES
        return "\n\n".join(p for p in (persona, rules, time_rules(self.c.now(), self.c.since_last_exchange())) if p)

    def session_config(self) -> dict[str, Any]:
        expressions, gestures = self._lists()
        s = self.settings
        session: dict[str, Any] = {
            "instructions": self.instructions(),
            "voice": str(s["voice"]),
            "turn_detection": {"type": "server_vad"},
            "tools": self.c.offered_tools(),
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": self.in_rate}},
                "output": {"format": {"type": "audio/pcm", "rate": self.out_rate}},
            },
        }
        speed = float(s["speed"])
        if abs(speed - 1.0) > 1e-6:
            session["audio"]["output"]["speed"] = speed
        language = str(self.c.engine_set.ai.get("language") or "auto")
        if language != "auto":
            session["audio"]["input"]["transcription"] = {"language_hint": language}
        if s.get("reasoning_effort"):
            session["reasoning"] = {"effort": str(s["reasoning_effort"])}
        self._last_instructions = time.monotonic()
        return session

    def refresh_instructions(self) -> None:
        """Sends the current time (and expression lists) with fresh instructions."""
        # TODO(verify): instructions can be replaced mid-session with session.update (the docs say
        # so for replace / language_hint / keyterms; instructions are assumed to work the same).
        if self.client.send({"type": "session.update", "session": {"instructions": self.instructions(),
                                                                   "tools": self.c.offered_tools()}}):
            self._last_instructions = time.monotonic()

    # -- lifecycle -------------------------------------------------------------------------

    def start(self) -> None:
        self.client.start()

    def stop(self) -> None:
        self.client.stop()
        self._reset_response()

    @property
    def ready(self) -> bool:
        return self.client.ready

    @property
    def responding(self) -> bool:
        return self.response_id is not None

    # -- microphone ------------------------------------------------------------------------

    def echo_locked(self) -> bool:
        """True while the microphone must stay silent for the server: the echo gate is closed (a clip is
        queued / playing, plus the tail) OR an answer is still being delivered. The second part closes the
        gaps between two clips of one answer (the gate may open for a moment when the next clip is slower than
        real time), so the server's voice detection never hears the body. Failsafe: a response that never
        ends (lost response.done) locks the mic for at most RESPONSE_LOCK_MAX_S."""
        if not self.c.gate.is_open:
            return True
        return self.responding and time.monotonic() - self._response_started < RESPONSE_LOCK_MAX_S

    def feed_mic(self, frame: bytes) -> None:
        frame = self.c.input.meter(frame)
        s = self.c.mic_settings
        send = s.enabled
        if s.mode == "ptt":
            send = send and self.c.input.ptt_active and (s.ptt_interrupts or self.c.gate.is_open)
        elif self.echo_locked() and not bool(self.settings["send_while_speaking"]):
            send = False  # the body is talking: the mic would hear it (no echo cancellation)
        data = frame if send else bytes(len(frame))
        data = resample_pcm16(data, self.c.cfg.sample_rate, self.in_rate)
        self.client.append_audio(data)

    # -- server events (tick thread) -------------------------------------------------------

    def tick(self) -> None:
        for event in self.client.poll():
            try:
                self.handle(event)
            except Exception:  # noqa: BLE001 - one bad event must not stop the companion
                log.exception("Realtime event failed: %.200s", event)
        if self._waiting_since is not None and not self.responding and self.client.ready \
                and self.c._clock() - self._waiting_since > ANSWER_TIMEOUT_S:
            self._waiting_since = None
            self.c.realtime_unresponsive(f"no answer {ANSWER_TIMEOUT_S:.0f} s after speaking")
            return
        if self.client.ready and not self.responding and not self.user_speaking \
                and time.monotonic() - self._last_instructions >= INSTRUCTIONS_REFRESH_S:
            self.refresh_instructions()

    def _trace(self, type_: str, rid: str | None, event: dict[str, Any]) -> None:
        if self.turn is None or type_ == "input_audio_buffer.speech_started":
            self.turn = Turn("realtime", prefix="rt")
        err = event.get("error")
        self.turn.step(f"realtime {type_}", response=rid, transcript=event.get("transcript"),
                       name=event.get("name"), arguments=event.get("arguments"),
                       error=(err.get("message") if isinstance(err, dict) else err) or None,
                       answer_audio_s=round(self._audio_bytes / 2 / self.out_rate, 2)
                       if type_ == "response.done" else None)

    def handle(self, event: dict[str, Any]) -> None:
        type_ = event.get("type", "")
        rid = event.get("response_id") or (event.get("response") or {}).get("id")
        if type_ in TRACE_EVENTS:
            self._trace(type_, rid, event)
        if type_ == "response.created":
            self._audio_bytes = 0
        if type_ == DISCONNECTED:
            self._reset_response()
            self.user_speaking = False
            self._waiting_since = None
        elif type_ == "session.updated":
            log.debug("Realtime session configured")
        elif type_ == "input_audio_buffer.speech_started":
            self.user_speaking = True
            self.c.on_user_activity()
            self.barge_in(manual=False)
            self.refresh_instructions()  # the answer to this turn sees the current time
        elif type_ == "input_audio_buffer.speech_stopped":
            self.user_speaking = False
            self.c.on_user_activity()
            if self.turn is not None and self.turn.latency is None:
                self.turn.latency = LatencyTrace(self.c._clock(), "realtime")
            if not self.responding:
                self._waiting_since = self.c._clock()
        elif type_ == "input_audio_buffer.timeout_triggered":
            log.info("Realtime: server idle timeout (proactive check-in by the server)")
        elif type_ == "conversation.item.input_audio_transcription.completed":
            text = str(event.get("transcript") or "").strip()
            if text:
                log.info("Heard: %r", text)
                self.c.history.append({"role": "user", "content": text})
        elif type_ == "response.created":
            self._start_response(rid)
        elif type_ == "response.output_audio.delta":
            if not self._current(rid):
                return
            try:
                pcm = base64.b64decode(str(event.get("delta") or ""), validate=False)
            except (binascii.Error, ValueError):
                return
            self._audio_bytes += len(pcm)
            if self.turn is not None and self.turn.latency is not None:
                self.turn.latency.mark("first_audio", self.c._clock())
            self._emit(self.assembler.feed_audio(pcm))
        elif type_ == "response.output_audio_transcript.delta":
            if not self._current(rid):
                return
            delta = str(event.get("delta") or "")
            self._directives(delta)
            self._emit(self.assembler.feed_text(delta))
        elif type_ == "response.function_call_arguments.done":
            self._function_call(event)
        elif type_ in ("response.output_audio.done", "response.done"):
            if self._current(rid):
                self._emit(self.assembler.finish(), final=True)
            if type_ == "response.done":
                self._finish_response(rid)
        elif type_ == "error":
            err = event.get("error") or {}
            log.warning("Realtime error: %s", err.get("message") if isinstance(err, dict) else err)
        else:
            log.debug("Realtime event: %s", type_)

    def _current(self, rid: str | None) -> bool:
        if rid and rid in self.cancelled:
            return False
        if self.response_id is None:  # deltas without response.created: start implicitly
            self._start_response(rid)
        return rid is None or rid == self.response_id

    def _start_response(self, rid: str | None) -> None:
        if rid and rid in self.cancelled:
            return
        self._waiting_since = None
        self.c.emotion.begin_answer()
        self.response_id = rid or protocol.new_id("rt")
        self._response_started = time.monotonic()
        self.assembler.reset()
        self._held = []
        self._sent_any = False
        expressions, gestures = self._lists()
        self._parser = StreamParser(expressions, gestures)
        self._nudge_response = self.response_id if self._nudge_pending else None
        self._nudge_pending = False

    def _finish_response(self, rid: str | None) -> None:
        if rid and rid in self.cancelled:
            self.cancelled.discard(rid)
            return
        transcript = self.assembler.transcript.strip()
        if self._nudge_response and self._nudge_response == self.response_id and is_silent(transcript):
            log.info("Proactive talking: the AI chose to stay silent")
        elif transcript:
            self.c.history.append({"role": "assistant", "content": transcript})
            self.c.on_exchange()
        self._reset_response()

    def _reset_response(self) -> None:
        self.response_id = None
        self.assembler.reset()
        self._held = []
        self._parser = None
        self._nudge_response = None

    def _directives(self, delta: str) -> None:
        """A leading <<expression gesture>> tag in the transcript (should not happen in realtime
        mode, the persona asks for the express function) is still mapped, like in chain mode."""
        if self._parser is None:
            return
        for item in self._parser.feed(delta):
            if not isinstance(item, str):
                self.c.send_directive(item)

    def _function_call(self, event: dict[str, Any]) -> None:
        name, call_id = event.get("name"), event.get("call_id")
        try:
            args = json.loads(event.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        commands, result = self.c.tool_commands(str(name or ""), args)
        for cmd in commands:
            self.c.send(cmd)
        if self.turn is not None:
            self.turn.step("realtime tool call", name=name, arguments=json.dumps(args, ensure_ascii=False),
                           result=json.dumps(result, ensure_ascii=False))
        if call_id:
            # The result goes back without response.create: the model must not start a second
            # answer (docs: "Avoid Audio Overlap During Tool Calls").
            # TODO(verify): an unanswered function_call_output does not make the server wait.
            self.client.send({"type": "conversation.item.create",
                              "item": {"type": "function_call_output", "call_id": call_id,
                                       "output": json.dumps(result)}})

    def _emit(self, segments: list[tuple[bytes, str]], final: bool = False) -> None:
        if not segments and not final:
            return
        if self._nudge_response and self._nudge_response == self.response_id and not self._sent_any:
            # Hold a nudge answer until it is clearly not "[silent]" (then its audio is dropped).
            self._held += segments
            text = self.assembler.transcript.strip()
            if final:
                if is_silent(text):
                    self._held = []
                    return
            elif len(text) < NUDGE_HOLD_CHARS or is_silent(text):
                return
            segments, self._held = self._held, []
        for pcm, text in segments:
            if len(pcm) < 2:
                continue
            uid = protocol.new_id("utt")
            path = self.c.cfg.audio_abs_path(f"{uid}.wav")
            duration = write_pcm_wav(pcm, self.out_rate, path)
            if self.turn is not None:
                self.turn.step("realtime segment", text=text, seconds=round(duration, 2))
                self.c._utt_turn[uid] = self.turn
                if self.turn.latency is not None:
                    self.turn.latency.mark("segment", self.c._clock())
            self.c._queue_speech(uid, text or "…", path, duration)
            self._sent_any = True

    # -- actions from the companion --------------------------------------------------------

    def barge_in(self, manual: bool) -> None:
        """The user talks: stop the body and drop the rest of the current answer. With server
        VAD the server cancels its answer itself; push-to-talk (manual) also sends
        response.cancel."""
        active = self.responding
        if active and self.response_id:
            self.cancelled.add(self.response_id)
        if manual and active:
            self.client.send({"type": "response.cancel"})
        if active or not self.c.gate.is_open:
            self.c.stop_speaking()
        self._reset_response()

    def nudge(self, text: str) -> bool:
        """Proactive turn: an app note as user text, then response.create."""
        ok = self.client.send({"type": "conversation.item.create",
                               "item": {"type": "message", "role": "user",
                                        "content": [{"type": "input_text", "text": text}]}})
        if ok and self.client.send({"type": "response.create"}):
            self._nudge_pending = True
            return True
        return False
