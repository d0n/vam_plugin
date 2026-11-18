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


def _default_input(sd: Any) -> int:
    try:
        dev = sd.default.device
        index = dev[0] if isinstance(dev, (list, tuple)) or hasattr(dev, "__getitem__") else dev
        return int(index) if index is not None else -1
    except Exception:  # noqa: BLE001 - PortAudio / odd default values
        return -1


def _input_devices(sd: Any) -> list[dict[str, Any]]:
    """Input devices of ONE host API, one entry per name.

    PortAudio lists every microphone once per Windows host API (MME, DirectSound, WASAPI, WDM-KS;
    MME cuts names to 31 characters). The plugin menu shows names, and sounddevice refuses a
    name that matches several devices ("Multiple input devices found"), so only the host API of
    the default input device is listed (the one Windows itself uses), each name once."""
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
        return [], "sounddevice is not installed (pip install sounddevice)"
    try:
        devices = _input_devices(sd)
    except Exception as e:  # noqa: BLE001 - PortAudio raises various errors
        return [], f"could not list devices: {e}"
    if not devices:
        return [], "no input device found (is a microphone connected and allowed in the Windows privacy settings?)"
    return devices, None


def resolve_input_device(sd: Any, device: int | str | None) -> int | str | None:
    """A device name from the plugin menu -> its index in the listed host API (exact name first),
    so a name that exists under several host APIs still opens. Unknown names are passed on
    (sounddevice then matches a part of the name or reports the error)."""
    if device is None or isinstance(device, int) or device == "":
        return device or None
    try:
        for d in _input_devices(sd):
            if d["name"] == device:
                return int(d["index"])
        for d in _input_devices(sd):
            if d["name"].lower() == str(device).lower():
                return int(d["index"])
    except Exception:  # noqa: BLE001 - fall back to the name
        pass
    return device


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

        device = resolve_input_device(sd, self.device)
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.frame_samples,
            channels=1,
            dtype="int16",
            device=device,
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
