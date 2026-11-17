"""xAI realtime speech-to-speech (Grok Voice) over one persistent WebSocket.

Documented (docs.x.ai, checked 17.11.2026):
  * wss://api.x.ai/v1/realtime?model=grok-voice-latest, header "Authorization: Bearer <key>"
    https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech
    https://docs.x.ai/developers/rest-api-reference/inference/voice
  * session.update {instructions, voice, turn_detection {type: server_vad}, tools,
    audio {input|output {format {type: "audio/pcm", rate}}}}; PCM = 16-bit little endian,
    rates 8000/16000/22050/24000/32000/44100/48000 (default 24000)
  * input_audio_buffer.append {audio: base64}; with server_vad the server detects turns and
    interrupts its own answer when the user speaks (input_audio_buffer.speech_started)
  * response.created / response.output_audio.delta {response_id, delta: base64} /
    response.output_audio_transcript.delta / .done / response.done / error
  * conversation.item.create (user input_text, function_call_output) + response.create
  * custom function tools -> response.function_call_arguments.done {name, call_id, arguments}
Never verified against the real server (no key): TODO(verify), see docs/CONFIG.md.

This module has no VaM knowledge: RealtimeClient keeps the connection (thread, reconnect with
backoff) and hands parsed server events to the companion; SegmentAssembler cuts the streamed
answer audio into sentence-sized WAV segments for the file transport.
"""
from __future__ import annotations

import base64
import json
import logging
import queue
import threading
import time
from array import array
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from .sentences import SentenceSplitter
from .websocket import WebSocket, WebSocketError

log = logging.getLogger(__name__)

PCM_RATES = (8000, 16000, 22050, 24000, 32000, 44100, 48000)
BACKOFF_S = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)
DISCONNECTED = "_disconnected"  # pseudo event put into the queue when the socket is gone


def resample_pcm16(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Linear interpolation, mono 16-bit little endian (only used when the mic rate is not one
    the API accepts)."""
    if src_rate == dst_rate or not data:
        return data
    src = array("h")
    src.frombytes(data[: len(data) - len(data) % 2])
    n_out = max(1, int(len(src) * dst_rate / src_rate))
    out = array("h", bytes(2 * n_out))
    step = src_rate / dst_rate
    last = len(src) - 1
    for i in range(n_out):
        pos = i * step
        j = int(pos)
        if j >= last:
            out[i] = src[last]
        else:
            frac = pos - j
            out[i] = int(src[j] + (src[j + 1] - src[j]) * frac)
    return out.tobytes()


def express_tool(expressions: list[str], gestures: list[str]) -> dict[str, Any]:
    """Function tool for the existing expression / gesture commands (no new body features)."""
    props: dict[str, Any] = {"expression": {"type": "string", "enum": list(expressions) or ["neutral"]}}
    if gestures:
        props["gesture"] = {"type": "string", "enum": list(gestures)}
    return {
        "type": "function",
        "name": "express",
        "description": "Silently shows a facial expression and optionally a gesture on your 3D body. "
                       "Call it at the start of an answer when your mood changes. It is never spoken.",
        "parameters": {"type": "object", "properties": props, "required": ["expression"]},
    }


REALTIME_RULES = """Your voice comes out of a 3D character standing in front of the user. Talk in short, natural
spoken sentences. To show a facial expression or a gesture, call the function "express"; never say
expression names, gestures or tags aloud. Expressions: {expressions}. Gestures: {gestures}.
Messages that start with [App context or [App note come from the app, not from the user; never read
them aloud."""


class SegmentAssembler:
    """Collects one answer's PCM and transcript; returns (pcm, text) segments to play.

    A segment is cut when the transcript has completed a sentence and enough audio is buffered
    (first_s for the first segment, so speech starts early; min_s later), or when max_s of audio
    piled up without a sentence end (cut at the quietest 20 ms in the last third). Audio and
    transcript are not aligned exactly; the text is only for the log and the plugin's display."""

    def __init__(self, sample_rate: int = 24000, first_s: float = 1.2, min_s: float = 2.0, max_s: float = 6.0):
        self.rate = sample_rate
        self.first_s, self.min_s, self.max_s = first_s, max(min_s, first_s), max(max_s, min_s)
        self.reset()

    def reset(self) -> None:
        self._pcm = bytearray()
        self._splitter = SentenceSplitter()
        self._sentences: list[str] = []
        self.transcript = ""
        self.segments_out = 0

    def _seconds(self) -> float:
        return len(self._pcm) / 2 / self.rate

    def feed_text(self, delta: str) -> list[tuple[bytes, str]]:
        self.transcript += delta
        self._sentences += self._splitter.feed(delta)
        return self._maybe_cut()

    def feed_audio(self, pcm: bytes) -> list[tuple[bytes, str]]:
        self._pcm += pcm
        return self._maybe_cut()

    def _maybe_cut(self) -> list[tuple[bytes, str]]:
        out: list[tuple[bytes, str]] = []
        need = self.first_s if self.segments_out == 0 else self.min_s
        if self._sentences and self._seconds() >= need:
            out.append(self._take(len(self._pcm), " ".join(self._sentences)))
            self._sentences = []
        while self._seconds() >= self.max_s:
            out.append(self._take(self._quiet_cut(), " ".join(self._sentences)))
            self._sentences = []
        return out

    def _quiet_cut(self) -> int:
        """Byte offset of the quietest 20 ms window in the last third of max_s of audio."""
        total = int(self.max_s * self.rate) * 2
        win = max(2, int(self.rate * 0.02)) * 2
        start = total * 2 // 3
        best, best_at = None, total
        samples = array("h")
        samples.frombytes(bytes(self._pcm[:total]))
        for off in range(start - start % 2, total - win + 1, win):
            i = off // 2
            energy = sum(abs(s) for s in samples[i:i + win // 2])
            if best is None or energy < best:
                best, best_at = energy, off + win // 2 - (win // 2) % 2
        return best_at

    def _take(self, nbytes: int, text: str) -> tuple[bytes, str]:
        nbytes -= nbytes % 2
        pcm = bytes(self._pcm[:nbytes])
        del self._pcm[:nbytes]
        self.segments_out += 1
        return pcm, text

    def finish(self) -> list[tuple[bytes, str]]:
        self._sentences += self._splitter.flush()
        text = " ".join(self._sentences)
        self._sentences = []
        if len(self._pcm) < 2:
            self._pcm = bytearray()
            return []
        return [self._take(len(self._pcm), text)]

    def drop(self) -> None:
        """Discards buffered audio (barge-in); the transcript so far stays readable."""
        self._pcm = bytearray()
        self._sentences = []


class RealtimeClient:
    """One persistent connection: a background thread connects, sends the session config, reads
    events into a queue (poll() on the tick thread) and reconnects with backoff. send() may be
    called from the tick thread at any time; it returns False while not connected."""

    def __init__(self, base_url: str, model: str, key: str | None,
                 session: Callable[[], dict[str, Any]],
                 connector: Callable[..., Any] = WebSocket.connect,
                 connect_timeout: float = 15.0,
                 backoff: tuple[float, ...] = BACKOFF_S,
                 clock: Callable[[], float] = time.monotonic):
        self.url = base_url.rstrip("/") + "?" + urlencode({"model": model})
        self.model = model
        self._key = key
        self._session = session
        self._connector = connector
        self._connect_timeout = connect_timeout
        self._backoff = backoff or (1.0,)
        self._clock = clock
        self._events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._ws: Any = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.ready = False  # session.updated received on the current connection
        self.connected = False
        self.failures = 0  # connection attempts in a row that ended without a usable session
        self.last_error = ""
        self.next_attempt_at = 0.0
        self.ever_ready = False

    # -- lifecycle -------------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="aibody-realtime", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass
        if self._thread:
            self._thread.join(timeout)
        self.ready = self.connected = False

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._connect_and_read()
            except WebSocketError as e:
                self.last_error = self._describe(e)
            except Exception as e:  # noqa: BLE001 - keep the thread alive
                self.last_error = f"Fehler: {e}"
                log.exception("Realtime connection failed")
            was_ready = self.ready
            self.ready = self.connected = False
            self._ws = None
            self._events.put({"type": DISCONNECTED, "error": self.last_error})
            if self._stop.is_set():
                return
            self.failures = 0 if was_ready else self.failures + 1
            delay = self._backoff[min(max(self.failures - 1, 0), len(self._backoff) - 1)]
            self.next_attempt_at = self._clock() + delay
            log.warning("Realtime: %s - neuer Versuch in %.0f s", self.last_error or "getrennt", delay)
            self._stop.wait(delay)

    @staticmethod
    def _describe(e: WebSocketError) -> str:
        if e.status in (401, 403):
            return f"API-Key abgelehnt (HTTP {e.status})"
        return str(e)

    def _connect_and_read(self) -> None:
        if not self._key:
            raise WebSocketError("nicht konfiguriert (kein xAI-Key)")
        ws = self._connector(self.url, {"Authorization": f"Bearer {self._key}"}, self._connect_timeout)
        self._ws = ws
        self.connected = True
        self.last_error = ""
        log.info("Realtime: verbunden mit %s", self.url)
        ws.send_text(json.dumps({"type": "session.update", "session": self._session()}))
        while not self._stop.is_set():
            msg = ws.recv(timeout=0.2)
            if msg is None:
                continue
            if isinstance(msg, bytes):
                continue  # binary transport is not requested
            try:
                event = json.loads(msg)
            except json.JSONDecodeError:
                log.debug("Realtime: not JSON: %.80s", msg)
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "session.updated" and not self.ready:
                self.ready = True
                self.ever_ready = True
                self.failures = 0
            self._events.put(event)

    # -- tick thread -----------------------------------------------------------------------

    def poll(self) -> list[dict[str, Any]]:
        events = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def send(self, event: dict[str, Any]) -> bool:
        ws = self._ws
        if ws is None or not self.connected:
            return False
        try:
            ws.send_text(json.dumps(event))
            return True
        except WebSocketError as e:
            log.warning("Realtime: send failed (%s)", e)
            return False

    def append_audio(self, pcm16: bytes) -> bool:
        if not self.ready:
            return False
        return self.send({"type": "input_audio_buffer.append", "audio": base64.b64encode(pcm16).decode("ascii")})

    def retry_in(self) -> float:
        return max(0.0, self.next_attempt_at - self._clock())
