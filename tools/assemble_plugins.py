#!/usr/bin/env python3
"""Assembles the VaM script folder of the AIBody plugin from src/AIBody.

  <out>/AIBody.cslist + the .cs files it lists (one flat folder, no sub folders)

This is a plain copy of src/AIBody (that folder is installable as is). There is exactly one
build: no optional transports, no compile flags.

Usage: python tools/assemble_plugins.py [--out DIR]
  default DIR: build/scripts/AIBody   (loose-file install: <VaM>/Custom/Scripts/d0n/AIBody)
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "AIBody"
DEFAULT_OUT = ROOT / "build" / "scripts" / "AIBody"
CSLIST = "AIBody.cslist"


def cslist_entries() -> list[str]:
    lines = [ln.strip() for ln in (SRC / CSLIST).read_text(encoding="utf-8").splitlines()]
    entries = [ln for ln in lines if ln]
    bad = [e for e in entries if "/" in e or "\\" in e or not e.endswith(".cs")]
    if bad:
        # Flat on purpose: sub folder paths inside a .var are unverified, and VaM treats every
        # line (comments included) as a file path.
        raise SystemExit(f"{CSLIST}: entries must be plain .cs file names in the same folder, got {bad}")
    return entries


def assemble(out: Path = DEFAULT_OUT) -> list[str]:
    """Writes the plugin folder `out` (replacing it). Returns the relative files, cslist first."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    entries = cslist_entries()
    for name in entries:
        src = SRC / name
        if not src.is_file():
            raise SystemExit(f"missing source {src.relative_to(ROOT)}")
        shutil.copyfile(src, out / name)
    (out / CSLIST).write_text("\n".join(entries) + "\n", encoding="utf-8")
    return [CSLIST] + entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(f"{args.out}: {len(assemble(args.out))} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
