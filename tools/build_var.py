#!/usr/bin/env python3
"""Builds the three VaM packages (.var) of AIBody.

  dist/d0n.AIBodySession.<N>.var   session plugin             (Main UI > Session Plugins)
  dist/d0n.AIBodyPerson.<N>.var    person plugin, character 1 (character 1's Plugins tab, slot person1)
  dist/d0n.AIBodyPerson2.<N>.var   person plugin, character 2 (character 2's Plugins tab, slot person2)

A .var is a zip with meta.json at the root. Each package's meta.json is packaging/meta.json
(unchanged, incl. licenseType) with the overrides from packaging/<Package>.json, which also set
the package version <N>. Each package contains its own .cslist plus exactly the sources it lists
(shared files are copied into each), below Custom/Scripts/<creator>/<scriptFolder>/
(AIBody for Session and Person, AIBody2 for Person2). Person2's sources are generated from the
Person sources by tools/make_person2.py. The optional HTTP sources are never packaged.

Usage: python tools/build_var.py [--only AIBodySession|AIBodyPerson|AIBodyPerson2] [--version N]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGES = ["AIBodySession", "AIBodyPerson", "AIBodyPerson2"]
PERSON2_DIR = ROOT / "build" / "person2"


def generated_root(generator: str | None) -> Path:
    if not generator:
        return SRC
    if generator != "person2":
        raise SystemExit(f"unknown generator {generator!r}")
    spec = importlib.util.spec_from_file_location("make_person2", ROOT / "tools" / "make_person2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate(PERSON2_DIR)
    return PERSON2_DIR


def cslist_files(root: Path, cslist: str) -> list[str]:
    lines = [ln.strip() for ln in (root / cslist).read_text(encoding="utf-8").splitlines()]
    files = [ln for ln in lines if ln and not ln.startswith("//")]
    missing = [f for f in files if not (root / f).is_file()]
    if missing:
        raise SystemExit(f"{cslist} references missing files: {missing}")
    if any(f.startswith("Optional/") for f in files):
        raise SystemExit(f"{cslist} must not list Optional/ (HTTP) sources in the default package")
    return files


def build(package: str, version_override: int | None = None) -> Path:
    meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / "packaging" / f"{package}.json").read_text(encoding="utf-8"))
    overrides.pop("_comment", None)
    cslist = overrides.pop("cslist")
    version = version_override or int(overrides.pop("version", 1))
    overrides.pop("version", None)
    root = generated_root(overrides.pop("generator", None))
    folder = overrides.pop("scriptFolder", "AIBody")
    for key, value in overrides.items():
        meta[key] = value.replace("<version>", str(version)) if isinstance(value, str) else value
    creator = meta["creatorName"]
    script_dir = f"Custom/Scripts/{creator}/{folder}"

    files = [cslist] + cslist_files(root, cslist)
    meta["contentList"] = [f"{script_dir}/{f}" for f in files]
    out = ROOT / "dist" / f"{creator}.{meta['packageName']}.{version}.var"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, indent=2))
        for f in files:
            z.write(root / f, f"{script_dir}/{f}")
    print(f"Wrote {out.relative_to(ROOT)} ({len(files)} files)")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=PACKAGES)
    parser.add_argument("--version", type=int, help="override the package version from packaging/<Package>.json")
    args = parser.parse_args()
    for package in [args.only] if args.only else PACKAGES:
        build(package, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
