#!/usr/bin/env python3
"""Builds a VaM package (.var) from src/ and packaging/meta.json.

A .var is a zip with meta.json at the root. Scripts go to Custom/Scripts/<creator>/<package>/.
Usage: python tools/build_var.py [--version N]  ->  dist/d0n.AIBody.<N>.var
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=1, help="package version number (integer)")
    args = parser.parse_args()

    meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
    creator, package = meta["creatorName"], meta["packageName"]
    script_dir = f"Custom/Scripts/{creator}/{package}"

    sources = sorted((ROOT / "src").glob("*.cs")) + [ROOT / "src" / "AIBody.cslist"]
    listed = [line.strip() for line in (ROOT / "src" / "AIBody.cslist").read_text().splitlines() if line.strip()]
    missing = [name for name in listed if not (ROOT / "src" / name).exists()]
    if missing:
        raise SystemExit(f"AIBody.cslist references missing files: {missing}")
    unlisted = [p.name for p in sources if p.suffix == ".cs" and p.name not in listed]
    if unlisted:
        raise SystemExit(f"src/*.cs files not in AIBody.cslist: {unlisted}")

    meta["contentList"] = [f"{script_dir}/{p.name}" for p in sources]
    out = ROOT / "dist" / f"{creator}.{package}.{args.version}.var"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, indent=2))
        for p in sources:
            z.write(p, f"{script_dir}/{p.name}")
    print(f"Wrote {out.relative_to(ROOT)} ({len(sources)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
