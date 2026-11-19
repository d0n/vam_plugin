"""Silero voice detector through onnxruntime, without torch (version 29).

Optional (like webrtcvad): needs `python -m pip install onnxruntime` and the model file silero_vad.onnx (MIT license,
github.com/snakers4/silero-vad, folder src/silero_vad/data), which is NOT part of this package: put it into
<VaM>/Saves/PluginData/AIBody/models/silero_vad.onnx (or set the environment variable AIBODY_SILERO_MODEL to its path).
Model version 5: inputs input [1, 64 + 512] float32 (64 samples of context + a chunk of 512 samples = 32 ms at
16 kHz), state [2, 1, 128] float32, sr int64; outputs the speech probability and the new state.
Our frames are 30 ms, so samples are collected until a full chunk is there; the last probability counts.
"""
from __future__ import annotations

import array
import logging
from typing import Any

from .vad import EnergyVad, frame_rms

log = logging.getLogger(__name__)

CHUNK = 512
CONTEXT = 64
# vad_strictness 0..3 -> speech probability needed (0.5 is the model authors' default)
THRESHOLDS = (0.3, 0.4, 0.5, 0.65)
MODEL_FILE = "silero_vad.onnx"
ENV_MODEL = "AIBODY_SILERO_MODEL"
INSTALL = "python -m pip install onnxruntime"
DOWNLOAD = ("download silero_vad.onnx (MIT license) from https://github.com/snakers4/silero-vad/tree/master/src/silero_vad/data "
            "and put it into {folder}")


def silero_model_path(vam_root: str, env: Any = None) -> str:
    """Where silero_vad.onnx is looked for: AIBODY_SILERO_MODEL, else <VaM>/Saves/PluginData/AIBody/models/."""
    import os
    environ = os.environ if env is None else env
    given = str(environ.get(ENV_MODEL) or "").strip()
    if given:
        return given
    return os.path.join(vam_root, "Saves", "PluginData", "AIBody", "models", MODEL_FILE)


class SileroVad:
    def __init__(self, session: Any, np: Any, sample_rate: int, strictness: int, min_rms: float, hangover_frames: int = 3):
        self._session = session
        self._np = np
        self.sample_rate = sample_rate
        self.threshold = THRESHOLDS[min(max(int(strictness), 0), 3)]
        self.min_rms = min_rms
        self.hangover_frames = hangover_frames
        self._fallback = EnergyVad(min_rms=min_rms)
        self._warned = False
        self._hang = 0
        self.probability = 0.0
        self._reset_state()

    @property
    def name(self) -> str:
        return "silero"

    def _reset_state(self) -> None:
        np = self._np
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, CONTEXT), dtype=np.float32)
        self._pending: list[float] = []

    def is_speech(self, frame: bytes) -> bool:
        return self.decide(frame, frame_rms(frame))

    def is_speech_rms(self, rms: float) -> bool:  # no frame: the energy rule alone
        return self._fallback.is_speech_rms(rms)

    def hold(self) -> None:
        """The gate closed (the body talks): the audio stream is interrupted, forget what came before."""
        self._hang = 0
        self.probability = 0.0
        self._reset_state()
        self._fallback.hold()

    def decide(self, frame: bytes, rms: float) -> bool:
        try:
            self._feed(frame)
        except Exception as e:  # noqa: BLE001 - a broken model must not stop the microphone
            if not self._warned:
                self._warned = True
                log.warning("Silero failed (%s); the energy rule decides from now on", e)
            return self._fallback.decide(frame, rms)
        if self.probability >= self.threshold and rms >= self.min_rms:
            self._hang = self.hangover_frames
            return True
        if self._hang > 0:
            self._hang -= 1
            return True
        return False

    def _feed(self, frame: bytes) -> None:
        np = self._np
        samples = array.array("h")
        samples.frombytes(frame[: len(frame) - (len(frame) % 2)])
        self._pending.extend(s / 32768.0 for s in samples)
        while len(self._pending) >= CHUNK:
            chunk = np.asarray(self._pending[:CHUNK], dtype=np.float32).reshape(1, CHUNK)
            del self._pending[:CHUNK]
            x = np.concatenate([self._context, chunk], axis=1)
            out, self._state = self._session.run(None, {"input": x, "state": self._state,
                                                        "sr": np.array(self.sample_rate, dtype=np.int64)})
            self._context = x[:, -CONTEXT:]
            self.probability = float(out.reshape(-1)[0])


def load_silero(model_path: str, sample_rate: int, strictness: int, min_rms: float,
                importer: Any) -> tuple[SileroVad | None, str]:
    """(detector, "") or (None, why not). `importer(name)` imports onnxruntime / numpy."""
    if sample_rate not in (8000, 16000):
        return None, f"silero needs 8 or 16 kHz audio, this app uses {sample_rate} Hz"
    try:
        ort = importer("onnxruntime")
        np = importer("numpy")
    except ImportError:
        return None, f"onnxruntime is not installed ({INSTALL})"
    except Exception as e:  # noqa: BLE001 - a broken native library must not stop the app
        return None, f"onnxruntime could not be loaded ({type(e).__name__})"
    try:
        options = ort.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 1
        session = ort.InferenceSession(model_path, sess_options=options, providers=["CPUExecutionProvider"])
        names = {i.name for i in session.get_inputs()}
        if names != {"input", "state", "sr"}:
            return None, f"{model_path} is not a silero_vad.onnx of version 5 (inputs: {', '.join(sorted(names))})"
        vad = SileroVad(session, np, sample_rate, strictness, min_rms)
        vad._feed(b"\x00\x00" * CHUNK)  # one test run: shapes and types are checked here, not in the middle of a talk
        vad.hold()
        return vad, ""
    except Exception as e:  # noqa: BLE001
        return None, f"the silero model could not be started ({type(e).__name__}: {str(e)[:120]})"
