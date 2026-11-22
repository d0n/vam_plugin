"""Microphone capture from the system default input device (no device selection since the version
after 22: on Windows the default device is what the user means). Optional dependency: `sounddevice`
(python -m pip install sounddevice). Everything degrades to a clear error without it. list_input_devices()
only serves the diagnostics (`--list-devices`, tools/mic_test.py).
"""
from __future__ import annotations

import logging
import queue
from collections.abc import Callable, Iterator
from typing import Any

from .. import wakeup
from .mic_settings import MicSettings

log = logging.getLogger(__name__)


def _sounddevice():
    try:
        import sounddevice as sd  # type: ignore

        return sd
    except (ImportError, OSError):  # OSError: PortAudio library missing
        return None


def default_output_device() -> str:
    """Version 48 (Leon 22.11.2026 12:58), diagnostics only: the name of the Windows default OUTPUT device as PortAudio
    reports it. The companion plays no sound itself (its WAVs are played by VaM's head audio), and VaM plays on the
    Windows default output device that was active when VaM started; this line shows which one that is right now."""
    sd = _sounddevice()
    if sd is None:
        return "unknown (sounddevice is not installed)"
    try:
        dev = sd.query_devices(kind="output")
        name = dev.get("name") if isinstance(dev, dict) else None
        return str(name) if name else "unknown"
    except Exception as e:  # noqa: BLE001 - no output device, PortAudio errors: only a log line
        return f"unknown ({e})"


def _default_input(sd: Any) -> int:
    try:
        dev = sd.default.device
        index = dev[0] if isinstance(dev, (list, tuple)) or hasattr(dev, "__getitem__") else dev
        return int(index) if index is not None else -1
    except Exception:  # noqa: BLE001 - PortAudio / odd default values
        return -1


def _input_devices(sd: Any) -> list[dict[str, Any]]:
    """Input devices of ONE host API, one entry per name (diagnostics only).

    PortAudio lists every microphone once per Windows host API (MME, DirectSound, WASAPI, WDM-KS;
    MME cuts names to 31 characters), so only the host API of the default input device is listed
    (the one Windows itself uses), each name once."""
    devices = list(sd.query_devices())
    try:
        apis = list(sd.query_hostapis())
    except Exception:  # noqa: BLE001
        apis = []
    default_in = _default_input(sd)
    api = None
    if 0 <= default_in < len(devices):
        api = devices[default_in].get("hostapi")
    else:
        try:
            api = int(sd.default.hostapi)
        except Exception:  # noqa: BLE001
            api = None
    inputs = [(i, d) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]
    chosen = [(i, d) for i, d in inputs if api is None or d.get("hostapi") == api] or inputs
    log.info("Microphones (raw): %d PortAudio devices, %d with input channels, %d in the listed host API %s",
             len(devices), len(inputs), len(chosen),
             apis[api].get("name", api) if isinstance(api, int) and 0 <= api < len(apis) else "(all)")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, d in chosen:
        name = str(d.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        hostapi = d.get("hostapi")
        result.append({
            "name": name,
            "index": index,
            "default": index == default_in,
            "channels": d.get("max_input_channels"),
            "sample_rate": d.get("default_samplerate"),
            "hostapi": str(apis[hostapi].get("name", "")) if isinstance(hostapi, int) and 0 <= hostapi < len(apis)
            else "",
        })
    return result


def list_input_devices() -> tuple[list[dict[str, Any]], str | None]:
    """Returns ([{"name", "index", "default", "channels", "sample_rate", "hostapi"}], error)."""
    sd = _sounddevice()
    if sd is None:
        return [], "sounddevice is not installed (the Python package the microphone needs): run 'python -m pip install sounddevice', then restart this app. Typing into this console still works"
    try:
        devices = _input_devices(sd)
    except Exception as e:  # noqa: BLE001 - PortAudio raises various errors
        return [], f"could not list devices: {e}"
    if not devices:
        return [], "no input device found: connect a microphone and make sure Windows lets apps use it (Settings > Privacy > Microphone), then restart this app"
    return devices, None


class MicCapture:
    """Delivers fixed size 16-bit mono frames from the audio callback thread via a queue."""

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 30):
        self.sample_rate = sample_rate
        self.frame_samples = sample_rate * frame_ms // 1000
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=200)
        self._stream = None

    def start(self) -> None:
        sd = _sounddevice()
        if sd is None:
            raise RuntimeError("The microphone needs the Python package 'sounddevice' (not installed): run 'python -m pip install sounddevice', then restart this app")

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            if status:
                log.debug("mic status: %s", status)
            try:
                self._queue.put_nowait(bytes(indata))
                wakeup.notify()  # version 36: the VAD sees the frame now (utterance end without a poll delay)
            except queue.Full:
                log.warning("The computer cannot keep up with the microphone, so a bit of sound was skipped (harmless if rare; close heavy programs if it repeats)")

        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.frame_samples,
            channels=1,
            dtype="int16",
            device=None,  # always the sounddevice default input
            callback=callback,
        )
        self._stream.start()
        log.info("Microphone started (%d Hz, system default input)", self.sample_rate)

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
    """Starts and stops the capture stream to match MicSettings (enabled)."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        capture_factory: Callable[[int, int], Any] | None = None,
    ):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self._factory = capture_factory or (lambda rate, ms: MicCapture(rate, ms))
        self._capture: Any = None
        self.error: str | None = None

    @property
    def capturing(self) -> bool:
        return self._capture is not None

    def apply(self, settings: MicSettings, allowed: bool = True) -> None:
        want = settings.enabled and allowed
        if self._capture is not None and not want:
            self.stop()
        if want and self._capture is None:
            try:
                capture = self._factory(self.sample_rate, self.frame_ms)
                capture.start()
            except Exception as e:  # noqa: BLE001 - surface any capture error to the plugin UI
                self.error = str(e)
                log.error("Microphone could not start: %s - check that a microphone is connected, set as the system default input and allowed for apps (Windows: Settings > Privacy > Microphone)", e)
                return
            self._capture = capture
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
