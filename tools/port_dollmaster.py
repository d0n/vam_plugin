#!/usr/bin/env python3
"""The mechanical part of the Dollmaster port (22.11.2026, Leon: full port, nothing dropped).

third_party/dollmaster/src/<Name>.cs  ->  src/AIBody/Dm<Name>.cs (Dollmaster.cs -> DmPlugin.cs):
  * namespace DeluxePlugin.Dollmaster -> AIBody (one namespace per plugin, tools/check_plugin.py)
  * every Dollmaster type gets the prefix Dm (Dollmaster's PoseController / ExpressionController / UI / Config would
    clash with AIBody's own types); renamed only outside string literals and comments, so labels and storable names
    stay exactly the old ones (saved scenes keep their values)
  * a header naming the source.
Everything else in src/AIBody/Dm*.cs is hand-made and marked "AIBody port:" (checked by
companion/tests/test_dollmaster_port.py). This script never overwrites src/: it writes the mechanical result to
build/dollmaster_port/ (python tools/port_dollmaster.py), handy for a diff against src/AIBody.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "third_party" / "dollmaster" / "src"
OUT = ROOT / "build" / "dollmaster_port"
TYPES = ["DollmasterPlugin", "UI", "Config", "BaseModule", "WorldUI", "Arousal", "ThrustController",
         "ThrustAutoController", "PluginState", "Personality", "Personas", "ExpressionGroup", "Expressions",
         "ExpressionController", "BreathController", "HeadController", "PoseController", "Montage", "MontageController",
         "TopButtons", "DressController", "ClimaxController", "KissController", "SFXController", "PathExt"]
MAP = {t: ("DmPlugin" if t == "DollmasterPlugin" else "Dm" + t) for t in TYPES}
TOKEN = re.compile(r'//[^\n]*|/\*.*?\*/|@"(?:[^"]|"")*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|.', re.S)
HEADER = ("// Dollmaster (VAMDeluxe, 2019; Leon's copy of Dollmaster, upstream github.com/vamdeluxe/DeluxePlugin, MIT) ported into\n"
          "// AIBody (22.11.2026, Leon): same code, types prefixed Dm, namespace AIBody; changes only where the project rules need them\n"
          "// (marked \"AIBody port:\").\n")


def ported_name(original: str) -> str:
    stem = Path(original).stem
    return ("DmPlugin" if stem == "Dollmaster" else MAP.get(stem, "Dm" + stem)) + ".cs"


def rename(code: str) -> str:
    out: list[str] = []
    prev = ""
    for m in TOKEN.finditer(code):
        t = m.group(0)
        if t in MAP and prev != ".":
            t = MAP[t]
        if not t.isspace():
            prev = t
        out.append(t)
    return "".join(out)


def port_text(code: str) -> str:
    code = code.lstrip("\ufeff").replace("\r\n", "\n")
    code = re.sub(r"namespace DeluxePlugin(\.Dollmaster)?\b", "namespace AIBody", code)
    return HEADER + rename(code)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in sorted(ORIGINAL.glob("*.cs")):
        (OUT / ported_name(f.name)).write_text(port_text(f.read_text(encoding="utf-8-sig")), encoding="utf-8")
    print(f"{OUT}: {len(list(ORIGINAL.glob('*.cs')))} files (mechanical port only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
