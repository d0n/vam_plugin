#!/usr/bin/env python3
"""Builds the AIBody VaM package: ONE .var with both plugins.

  dist/d0n.AIBody.<N>.var
    meta.json
    Custom/Scripts/d0n/AIBody/Client/AIBodyClient.cslist        (+ Shared/, sources)
    Custom/Scripts/d0n/AIBody/Companion/AIBodyCompanion.cslist  (+ Shared/, sources)

meta.json is packaging/meta.json (unchanged, incl. licenseType) with the overrides from
packaging/AIBody.json, which also sets the package version <N>. The script folders are assembled
by tools/assemble_plugins.py (sandbox-safe default build; the optional HTTP sources and the
legacy Session/Person plugins in legacy/ are never packaged).

Usage: python tools/build_var.py [--version N]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "build" / "var" / "AIBody"
SCRIPT_FOLDER = "AIBody"


def assemble() -> dict[str, list[str]]:
    spec = importlib.util.spec_from_file_location("assemble_plugins", ROOT / "tools" / "assemble_plugins.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.assemble(STAGE, http=False)


def build(version_override: int | None = None) -> Path:
    meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / "packaging" / "AIBody.json").read_text(encoding="utf-8"))
    overrides.pop("_comment", None)
    version = version_override or int(overrides.pop("version", 1))
    overrides.pop("version", None)
    for key, value in overrides.items():
        meta[key] = value.replace("<version>", str(version)) if isinstance(value, str) else value
    creator = meta["creatorName"]
    script_dir = f"Custom/Scripts/{creator}/{SCRIPT_FOLDER}"

    files = [f"{folder}/{rel}" for folder, rels in assemble().items() for rel in rels]
    for f in files:
        if f.split("/")[1] == "Optional":
            raise SystemExit(f"refusing to package optional HTTP source {f}")
    meta["contentList"] = [f"{script_dir}/{f}" for f in files]
    out = ROOT / "dist" / f"{creator}.{meta['packageName']}.{version}.var"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, indent=2))
        for f in files:
            z.write(STAGE / f, f"{script_dir}/{f}")
    print(f"Wrote {out.relative_to(ROOT)} ({len(files)} files)")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, help="override the package version from packaging/AIBody.json")
    args = parser.parse_args()
    build(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
