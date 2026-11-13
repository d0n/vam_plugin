"""Microphone capture. Optional dependency: `sounddevice` (pip install sounddevice).

Yields fixed size 16-bit mono frames into a queue from the audio callback thread.
"""
from __future__ import annotations

import logging
import queue
from collections.abc import Iterator

log = logging.getLogger(__name__)


class MicCapture:
    def __init__(self, sample_rate: int = 16000, frame_ms: int = 30, device: int | str | None = None):
        self.sample_rate = sample_rate
        self.frame_samples = sample_rate * frame_ms // 1000
        self.device = device
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=200)
        self._stream = None

    def start(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
        except ImportError as e:  # pragma: no cover - depends on local install
            raise RuntimeError("Microphone capture needs 'sounddevice': pip install sounddevice") from e

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            if status:
                log.debug("mic status: %s", status)
            try:
                self._queue.put_nowait(bytes(indata))
            except queue.Full:
                log.warning("mic queue full, dropping a frame (processing too slow)")

        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.frame_samples,
            channels=1,
            dtype="int16",
            device=self.device,
            callback=callback,
        )
        self._stream.start()
        log.info("Microphone started (%d Hz, device=%s)", self.sample_rate, self.device)

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def frames(self, timeout: float = 0.1) -> Iterator[bytes]:
        """Yields frames that are available now; returns when the queue is empty."""
        while True:
            try:
                yield self._queue.get(timeout=timeout)
            except queue.Empty:
                return

    def drain(self) -> None:
        """Discards buffered frames (e.g. audio captured while the gate was closed)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
