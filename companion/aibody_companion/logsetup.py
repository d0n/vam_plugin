"""Logging: console + rotating log file, redaction of secrets, and the per-turn trace.

Log file: <vam_root>/Saves/PluginData/AIBody/logs/companion.log (rotating, 1 MB x 5 files), next
to config.json, so it is found where everything else of AIBody lives. The plugin never reads it.

Verbose (config.json advanced.verbose_log, the plugin's "Verbose log" toggle in tab Config, or
--verbose) switches on the turn trace: one line per step of every turn with a turn id and the
time since the turn started, e.g.

  [t0003 +0.84s] stt: engine=xai ms=812 text='What time is it?'

Normal operation logs INFO only. --verbose also shows DEBUG of all modules.

Secrets never reach a handler unredacted: every formatted line goes through redact(), which
masks keys that were read (pipeline/keys.py registers them), "Bearer <token>" and anything shaped
like an API key (xai-..., sk-..., sk_...).
"""
from __future__ import annotations

import logging
import logging.handlers
import re
import time
from pathlib import Path
from typing import Any

TRACE_LOGGER = "aibody_companion.trace"
LOG_SUBDIR = "Saves/PluginData/AIBody/logs"
LOG_FILE = "companion.log"
MAX_BYTES = 1_000_000
BACKUPS = 5
FORMAT = "%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"
MASK = "***"

_SECRETS: set[str] = set()
_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{6,}"),
    re.compile(r"(?i)((?:api[_-]?key|xi-api-key|authorization)[\"']?\s*[:=]\s*[\"']?)(?!bearer\b)[A-Za-z0-9._~+/=-]{6,}"),
    re.compile(r"\b(?:xai-|sk-|sk_)[A-Za-z0-9_-]{8,}"),
]

trace_log = logging.getLogger(TRACE_LOGGER)
trace_log.setLevel(logging.WARNING)  # off until set_verbose(True)


def add_secret(secret: str | None) -> None:
    """Registers a secret (an API key) that must never appear in the log."""
    if secret and len(secret) >= 6:
        _SECRETS.add(secret)


def redact(text: str) -> str:
    for secret in sorted(_SECRETS, key=len, reverse=True):
        text = text.replace(secret, MASK)
    for pattern in _PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.groups() else "") + MASK, text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


_state: dict[str, Any] = {"verbose": False, "debug": False, "file": None, "console": None}


def setup(vam_root: str | None, verbose: bool = False, debug: bool = False,
          stream: Any = None) -> Path | None:
    """Console + rotating file (if the VaM folder exists). Returns the log file path or None."""
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_aibody", False):
            root.removeHandler(h)
            h.close()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = RedactingFormatter(FORMAT, DATEFMT)
    console = logging.StreamHandler(stream)
    console.setFormatter(formatter)
    console._aibody = True  # type: ignore[attr-defined]
    root.addHandler(console)
    _state.update(console=console, file=None, debug=debug)
    path = None
    if vam_root and Path(vam_root).is_dir():
        path = Path(vam_root) / LOG_SUBDIR / LOG_FILE
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUPS,
                                                      encoding="utf-8")
        except OSError as e:
            logging.getLogger(__name__).warning("Log file %s not writable: %s", path, e)
            path = None
        else:
            fh.setFormatter(formatter)
            fh._aibody = True  # type: ignore[attr-defined]
            root.addHandler(fh)
            _state["file"] = path
    set_verbose(verbose or debug)
    return path


def teardown() -> None:
    """Removes the handlers setup() added and turns the trace off (tests)."""
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_aibody", False):
            root.removeHandler(h)
            h.close()
    _state.update(file=None, console=None, debug=False)
    set_verbose(False)


def set_verbose(on: bool) -> bool:
    """Turn trace on/off at runtime. Returns True if it changed."""
    on = bool(on) or bool(_state["debug"])
    changed = on != _state["verbose"]
    _state["verbose"] = on
    trace_log.setLevel(logging.INFO if on else logging.WARNING)
    if changed:
        logging.getLogger(__name__).info("Verbose log %s%s", "on (turn trace)" if on else "off",
                                         f" - log file {_state['file']}" if _state["file"] else "")
    return changed


def is_verbose() -> bool:
    return bool(_state["verbose"])


def log_file() -> Path | None:
    return _state["file"]


def _fmt(value: Any, limit: int = 160) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".") if value % 1 else str(int(value))
    if isinstance(value, str):
        text = " ".join(value.split())
        if len(text) > limit:
            text = text[: limit - 1] + "…"
        return repr(text)
    return str(value)


class Turn:
    """One turn's trace: trace lines carry the turn id and the seconds since the turn started."""

    _counter = 0
    latency = None  # latency.LatencyTrace of a user turn (set by the companion)

    def __init__(self, kind: str, prefix: str = "t", **fields: Any):
        Turn._counter += 1
        self.id = f"{prefix}{Turn._counter:04d}"
        self.t0 = time.monotonic()
        self.step("start", kind=kind, **fields)

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def step(self, what: str, **fields: Any) -> None:
        if not trace_log.isEnabledFor(logging.INFO):
            return
        detail = " ".join(f"{k}={_fmt(v)}" for k, v in fields.items() if v is not None)
        trace_log.info("[%s +%.2fs] %s%s", self.id, self.elapsed(), what, f": {detail}" if detail else "")


def trace(turn_id: str, what: str, **fields: Any) -> None:
    """A trace line that belongs to a turn known only by its id (plugin events)."""
    if not trace_log.isEnabledFor(logging.INFO):
        return
    detail = " ".join(f"{k}={_fmt(v)}" for k, v in fields.items() if v is not None)
    trace_log.info("[%s] %s%s", turn_id, what, f": {detail}" if detail else "")
