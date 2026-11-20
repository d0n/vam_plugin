"""Atomic file writes: a reader (the VaM plugin) either sees no file or the complete file.

The plugin starts to load a WAV when the `speak` command arrives, so the WAV has to be complete
and visible under its final name BEFORE the command file is written, and the command file must
become visible only when complete. The recipe for both:

    1. write everything to a temporary name in the SAME folder (so the rename stays on one volume),
    2. flush and fsync, so the bytes are on disk,
    3. close,
    4. os.replace() to the final name (atomic on Windows and POSIX).

Nothing else is needed as a signal: the existence of the final file / the command file IS the
signal. No sleeping, no guessing of wait times.

Version 36 (latency): step 2's fsync only protects against a power loss, not against another program (VaM) seeing
half a file - the rename alone guarantees that, because both programs read the same OS file cache. Speech WAVs and
command files are therefore written with durable=False (no fsync: it costs milliseconds on Windows, more on a hard
disk, on every sentence); config.json, personas, memory and scenes keep durable=True.
"""
from __future__ import annotations

import contextlib
import itertools
import os
import shutil
from pathlib import Path

_counter = itertools.count(1)


def _temp_path(final: Path) -> Path:
    # Unique per process and call; never ends in .wav / .json, so neither the plugin's .json
    # scan of the inbox nor VaM's audio loading ever picks it up.
    return final.with_name(f".{final.name}.{os.getpid()}.{next(_counter)}.part")


def atomic_write_bytes(final: Path, data: bytes, durable: bool = True) -> None:
    final = Path(final)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path(final)
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            if durable:
                os.fsync(f.fileno())
        os.replace(tmp, final)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def atomic_write_text(final: Path, text: str, encoding: str = "utf-8", durable: bool = True) -> None:
    atomic_write_bytes(final, text.encode(encoding), durable)


def atomic_copy(source: Path, final: Path, durable: bool = True) -> None:
    """Copies a complete file to `final` the same way (temp name, fsync, replace)."""
    final = Path(final)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path(final)
    try:
        with open(source, "rb") as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            if durable:
                os.fsync(dst.fileno())
        os.replace(tmp, final)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
