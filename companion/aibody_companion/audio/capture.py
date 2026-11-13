"""Microphone capture and device management. Optional dependency: `sounddevice`
(pip install sounddevice). Everything degrades to a clear error without it.
"""
from __future__ import annotations

import logging
import queue
from collections.abc import Callable, Iterator
from typing import Any

from .mic_settings import MicSettings

log = logging.getLogger(__name__)


def _sounddevice():
    try:
        import sounddevice as sd  # type: ignore

        return sd
    except (ImportError, OSError):  # OSError: PortAudio library missing
        return None


def list_input_devices() -> tuple[list[dict[str, Any]], str | None]:
    """Returns ([{"name", "index", "default", "channels", "sample_rate"}], error)."""
    sd = _sounddevice()
    if sd is None:
        return [], "sounddevice is not installed (pip install sounddevice)"
    try:
        devices = sd.query_devices()
        default_in = sd.default.device[0] if sd.default.device else -1
    except Exception as e:  # noqa: BLE001 - PortAudio raises various errors
        return [], f"could not list devices: {e}"
    result = []
    for index, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            result.append({
                "name": d["name"],
                "index": index,
                "default": index == default_in,
                "channels": d["max_input_channels"],
                "sample_rate": d.get("default_samplerate"),
            })
    return result, None


class MicCapture:
    """Delivers fixed size 16-bit mono frames from the audio callback thread via a queue."""

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 30, device: int | str | None = None):
        self.sample_rate = sample_rate
        self.frame_samples = sample_rate * frame_ms // 1000
        self.device = device
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=200)
        self._stream = None

    def start(self) -> None:
        sd = _sounddevice()
        if sd is None:
            raise RuntimeError("Microphone capture needs 'sounddevice': pip install sounddevice")

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
        log.info("Microphone started (%d Hz, device=%s)", self.sample_rate, self.device or "default")

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def frames(self, timeout: float = 0.0) -> Iterator[bytes]:
        """Yields frames that are available now; returns when the queue is empty."""
        while True:
            try:
                yield self._queue.get(timeout=timeout) if timeout else self._queue.get_nowait()
            except queue.Empty:
                return


class MicController:
    """Starts, stops and re-opens the capture stream to match MicSettings (enabled, device)."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        capture_factory: Callable[[int, int, str | None], Any] | None = None,
    ):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self._factory = capture_factory or (lambda rate, ms, dev: MicCapture(rate, ms, dev))
        self._capture: Any = None
        self._device: str | None = None
        self.error: str | None = None

    @property
    def capturing(self) -> bool:
        return self._capture is not None

    def apply(self, settings: MicSettings, allowed: bool = True) -> None:
        want = settings.enabled and allowed
        device = settings.device or None
        if self._capture is not None and (not want or device != self._device):
            self.stop()
        if want and self._capture is None:
            try:
                capture = self._factory(self.sample_rate, self.frame_ms, device)
                capture.start()
            except Exception as e:  # noqa: BLE001 - surface any device error to the plugin UI
                self.error = str(e)
                log.error("Microphone could not start: %s", e)
                return
            self._capture = capture
            self._device = device
            self.error = None
        if not want:
            self.error = None

    def frames(self) -> Iterator[bytes]:
        if self._capture is None:
            return iter(())
        return self._capture.frames()

    def stop(self) -> None:
        if self._capture is not None:
            try:
                self._capture.stop()
            finally:
                self._capture = None
