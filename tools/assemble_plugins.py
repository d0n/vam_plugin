#!/usr/bin/env python3
"""Assembles the VaM script folders of the two AIBody plugins from src/.

  <out>/Client/AIBodyClient.cslist        + Shared/*.cs + src/Client/*.cs
  <out>/Companion/AIBodyCompanion.cslist  + Shared/*.cs + src/Companion/*.cs

src/Shared/*.cs (Log, Protocol) is written once in the placeholder namespace AIBodyShared. Each
plugin gets its own copy with that namespace renamed (AIBodyClientShared / AIBodyCompanionShared),
so the two separately compiled plugins never define the same full type names. Plugin sources say
`using AIBodyShared;`, which is renamed the same way.

The default output is the sandbox-safe build. --http adds "#define AIBODY_HTTP" to every source
and src/Optional/*.cs (HTTP transport, UnityWebRequest) to the Client; never ship that by default.

Usage: python tools/assemble_plugins.py [--out DIR] [--http]
  default DIR: build/scripts/AIBody   (loose-file install: <VaM>/Custom/Scripts/d0n/AIBody)
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DEFAULT_OUT = ROOT / "build" / "scripts" / "AIBody"
PLACEHOLDER = "AIBodyShared"

# folder -> (cslist, namespace of the plugin, namespace for its copy of Shared)
PLUGINS = {
    "Client": ("AIBodyClient.cslist", "AIBodyClient", "AIBodyClientShared"),
    "Companion": ("AIBodyCompanion.cslist", "AIBodyCompanion", "AIBodyCompanionShared"),
}
OPTIONAL = {"Client": ["Optional/HttpTransport.cs", "Optional/AutoTransport.cs"]}
BANNER = "// Assembled by tools/assemble_plugins.py from src/{src} - edit the source, not this copy.\n"


def cslist_entries(folder: str) -> list[str]:
    cslist = PLUGINS[folder][0]
    lines = [ln.strip() for ln in (SRC / folder / cslist).read_text(encoding="utf-8").splitlines()]
    entries = [ln for ln in lines if ln]
    if any(e.startswith(("/", "..", "Optional/", "//")) for e in entries):
        raise SystemExit(f"{cslist}: entries must be plain relative paths (no comments, no Optional/)")
    return entries


def source_path(folder: str, entry: str) -> Path:
    if entry.startswith("Shared/"):
        return SRC / entry
    if entry.startswith("Optional/"):
        return SRC / entry
    return SRC / folder / entry


def transform(text: str, shared_ns: str, http: bool, src_rel: str) -> str:
    if PLACEHOLDER not in text:
        raise SystemExit(f"{src_rel}: must use the {PLACEHOLDER} namespace (namespace or using)")
    text = re.sub(rf"\b{PLACEHOLDER}\b", shared_ns, text)
    header = BANNER.format(src=src_rel)
    if http:
        header = "#define AIBODY_HTTP\n" + header  # #define must come before any code
    return header + text


def assemble(out: Path = DEFAULT_OUT, http: bool = False) -> dict[str, list[str]]:
    """Writes both plugin folders below `out` (replacing them). Returns folder -> relative files, cslist first."""
    result = {}
    for folder, (cslist, _ns, shared_ns) in PLUGINS.items():
        target_dir = out / folder
        if target_dir.exists():
            shutil.rmtree(target_dir)
        entries = cslist_entries(folder) + (OPTIONAL.get(folder, []) if http else [])
        for entry in entries:
            src = source_path(folder, entry)
            if not src.is_file():
                raise SystemExit(f"{cslist}: missing source {src.relative_to(ROOT)}")
            dest = target_dir / entry
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(transform(src.read_text(encoding="utf-8"), shared_ns, http,
                                      str(src.relative_to(SRC))), encoding="utf-8")
        # No comment lines: VaM treats every line of a .cslist as a file path.
        (target_dir / cslist).write_text("\n".join(entries) + "\n", encoding="utf-8")
        result[folder] = [cslist] + entries
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--http", action="store_true", help="optional AIBODY_HTTP build (not sandbox-safe)")
    args = parser.parse_args()
    for folder, files in assemble(args.out, args.http).items():
        print(f"{args.out / folder}: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
