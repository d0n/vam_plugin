#!/usr/bin/env python3
"""Assembles the VaM script folder of the AIBody plugin from src/AIBody.

  <out>/AIBody.cslist + the .cs files it lists (one flat folder, no sub folders)

The default build is a plain copy of src/AIBody (that folder is installable as is). --http
prepends "#define AIBODY_HTTP" to every source and adds src/Optional/*.cs (HTTP transport,
UnityWebRequest) to the folder and the .cslist; never ship that by default.

Usage: python tools/assemble_plugins.py [--out DIR] [--http]
  default DIR: build/scripts/AIBody   (loose-file install: <VaM>/Custom/Scripts/d0n/AIBody)
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "AIBody"
OPTIONAL_DIR = ROOT / "src" / "Optional"
DEFAULT_OUT = ROOT / "build" / "scripts" / "AIBody"
CSLIST = "AIBody.cslist"
OPTIONAL = ["HttpTransport.cs", "AutoTransport.cs"]


def cslist_entries() -> list[str]:
    lines = [ln.strip() for ln in (SRC / CSLIST).read_text(encoding="utf-8").splitlines()]
    entries = [ln for ln in lines if ln]
    bad = [e for e in entries if "/" in e or "\\" in e or not e.endswith(".cs")]
    if bad:
        # Flat on purpose: sub folder paths inside a .var are unverified, and VaM treats every
        # line (comments included) as a file path.
        raise SystemExit(f"{CSLIST}: entries must be plain .cs file names in the same folder, got {bad}")
    return entries


def assemble(out: Path = DEFAULT_OUT, http: bool = False) -> list[str]:
    """Writes the plugin folder `out` (replacing it). Returns the relative files, cslist first."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    entries = cslist_entries()
    sources = [SRC / e for e in entries] + ([OPTIONAL_DIR / o for o in OPTIONAL] if http else [])
    names = [p.name for p in sources]
    for src in sources:
        if not src.is_file():
            raise SystemExit(f"missing source {src.relative_to(ROOT)}")
        text = src.read_text(encoding="utf-8")
        if http:
            text = "#define AIBODY_HTTP\n" + text  # #define must come before any code
        (out / src.name).write_text(text, encoding="utf-8")
    (out / CSLIST).write_text("\n".join(names) + "\n", encoding="utf-8")
    return [CSLIST] + names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--http", action="store_true", help="optional AIBODY_HTTP build (not sandbox-safe)")
    args = parser.parse_args()
    print(f"{args.out}: {len(assemble(args.out, args.http))} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
