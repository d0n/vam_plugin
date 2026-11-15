#!/usr/bin/env python3
"""Builds the AIBody VaM package: ONE .var with ONE plugin (one .cslist, one MVRScript).

  dist/d0n.AIBody.<N>.var
    meta.json
    Custom/Scripts/d0n/AIBody/AIBody.cslist   (+ the .cs files it lists, same folder)

meta.json is packaging/meta.json (unchanged, incl. licenseType) with the overrides from
packaging/AIBody.json, which also sets the package version <N>. The script folder is assembled by
tools/assemble_plugins.py (the legacy plugins in legacy/ are never packaged). After writing,
every file inside the .var is scanned with the strict sandbox rules (tools/sandbox_rules.py);
on any match the .var is deleted and the build fails.

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


def assemble() -> list[str]:
    spec = importlib.util.spec_from_file_location("assemble_plugins", ROOT / "tools" / "assemble_plugins.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.assemble(STAGE)


def scan_var(path: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location("sandbox_rules", ROOT / "tools" / "sandbox_rules.py")
    rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules)
    with zipfile.ZipFile(path) as z:
        items = [(f"{path.name}:{n}", z.read(n).decode("utf-8", "replace")) for n in z.namelist()]
    return rules.scan_files(items)


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

    files = assemble()
    meta["contentList"] = [f"{script_dir}/{f}" for f in files]
    out = ROOT / "dist" / f"{creator}.{meta['packageName']}.{version}.var"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, indent=2))
        for f in files:
            z.write(STAGE / f, f"{script_dir}/{f}")
    problems = scan_var(out)
    if problems:
        out.unlink()
        raise SystemExit("forbidden APIs inside the .var (deleted):\n" + "\n".join(problems))
    print(f"Wrote {out.relative_to(ROOT)} ({len(files)} files); strict scan of the .var: 0 forbidden matches")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, help="override the package version from packaging/AIBody.json")
    args = parser.parse_args()
    build(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
