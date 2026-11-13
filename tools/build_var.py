#!/usr/bin/env python3
"""Builds the two VaM packages (.var) of AIBody.

  dist/d0n.AIBodySession.<N>.var   session plugin  (Main UI > Session Plugins)
  dist/d0n.AIBodyPerson.<N>.var    person plugin   (Person atom > Plugins tab)

A .var is a zip with meta.json at the root. Each package's meta.json is packaging/meta.json
(unchanged, incl. licenseType) with the overrides from packaging/<Package>.json. Each package
contains its own .cslist plus exactly the sources it lists (shared files are copied into both),
below Custom/Scripts/<creator>/AIBody/. The optional HTTP sources are never packaged.

Usage: python tools/build_var.py [--version N] [--only AIBodySession|AIBodyPerson]
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGES = ["AIBodySession", "AIBodyPerson"]
SCRIPT_FOLDER = "AIBody"


def cslist_files(cslist: str) -> list[str]:
    lines = [ln.strip() for ln in (SRC / cslist).read_text(encoding="utf-8").splitlines()]
    files = [ln for ln in lines if ln and not ln.startswith("//")]
    missing = [f for f in files if not (SRC / f).is_file()]
    if missing:
        raise SystemExit(f"{cslist} references missing files: {missing}")
    if any(f.startswith("Optional/") for f in files):
        raise SystemExit(f"{cslist} must not list Optional/ (HTTP) sources in the default package")
    return files


def build(package: str, version: int) -> Path:
    meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / "packaging" / f"{package}.json").read_text(encoding="utf-8"))
    cslist = overrides.pop("cslist")
    overrides.pop("_comment", None)
    for key, value in overrides.items():
        meta[key] = value.replace("<version>", str(version)) if isinstance(value, str) else value
    creator = meta["creatorName"]
    script_dir = f"Custom/Scripts/{creator}/{SCRIPT_FOLDER}"

    files = [cslist] + cslist_files(cslist)
    meta["contentList"] = [f"{script_dir}/{f}" for f in files]
    out = ROOT / "dist" / f"{creator}.{meta['packageName']}.{version}.var"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, indent=2))
        for f in files:
            z.write(SRC / f, f"{script_dir}/{f}")
    print(f"Wrote {out.relative_to(ROOT)} ({len(files)} files)")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=1, help="package version number (integer)")
    parser.add_argument("--only", choices=PACKAGES)
    args = parser.parse_args()
    for package in [args.only] if args.only else PACKAGES:
        build(package, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
