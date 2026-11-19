#!/usr/bin/env python3
"""Checks the AIBody VaM plugin (one .cslist, one MVRScript) without VaM.

1. Strict sandbox scan (tools/sandbox_rules.py): EVERY file below src/ and every file of the
   assembled plugin folder must contain zero matches for UnityWebRequest, UnityEngine.Networking,
   WWW, System.IO, System.Net, sockets, Process, System.Diagnostics, reflection, Assembly.Load,
   DllImport/InteropServices, UnityEngine.Microphone, OpenURL and the old AIBODY_HTTP flag -
   in code, comments and strings alike. The same scan bans constructs VaM's own compiler (old
   Mono mcs) rejects although the stub compile accepts them: foreach / LINQ over Dictionary
   .Keys/.Values and the KeyCollection/ValueCollection types (CS584, version 13).
2. Single plugin: AIBody.cslist is flat (plain file names) and its files declare exactly ONE
   MVRScript (AIBody.AIBodyPlugin), one namespace, and no type twice.
3. Compile check: the .cslist is compiled as one assembly (as VaM does) as C# 6 against the
   .NET 3.5 profile and the API stubs in tools/stubs. The stubs declare only APIs with public
   evidence (docs/API_AUDIT.md), so any other VaM API fails the compile.

Usage: python tools/check_plugin.py   (needs the .NET SDK 6+ on PATH or in ~/.dotnet)
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tools" / "stubs"
BUILD = STUBS / "build"
ASSEMBLED = BUILD / "assembled"

CSLIST = "AIBody.cslist"
ENTRY = "AIBody.AIBodyPlugin"
SRC = ROOT / "src"


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assemble() -> None:
    load_tool("assemble_plugins").assemble(ASSEMBLED)


def cslist_files(folder: Path, cslist: str) -> list[str]:
    lines = [ln.strip() for ln in (folder / cslist).read_text(encoding="utf-8").splitlines()]
    files = [ln for ln in lines if ln]
    missing = [f for f in files if not (folder / f).is_file()]
    if missing:
        raise SystemExit(f"{cslist} references missing files: {missing}")
    return files


def sandbox_scan() -> tuple[list[str], int]:
    rules = load_tool("sandbox_rules")
    files = [p for p in sorted(SRC.rglob("*")) if p.is_file()]
    files += [p for p in sorted(ASSEMBLED.rglob("*")) if p.is_file()]
    items = [(str(p.relative_to(ROOT)), p.read_text(encoding="utf-8", errors="replace")) for p in files]
    return rules.scan_files(items), len(items)


TYPE_RE = re.compile(r"(?m)^\s*(?:public |internal |static |sealed |abstract |partial )*"
                     r"(?:class|struct|interface|enum) (\w+)")


def single_plugin_check() -> list[str]:
    """Flat .cslist, exactly one MVRScript (the entry class), one namespace, no duplicate types."""
    problems, scripts, types, namespaces = [], [], [], set()
    root = ASSEMBLED
    files = cslist_files(root, CSLIST)
    if any("/" in f or "\\" in f for f in files):
        problems.append(f"{CSLIST}: sub folder entries: {files}")
    for rel in files:
        code = (root / rel).read_text(encoding="utf-8")
        ns = re.findall(r"(?m)^namespace ([\w.]+)", code)
        if len(ns) != 1:
            problems.append(f"{rel}: expected one namespace, got {ns}")
            continue
        namespaces.add(ns[0])
        types += [f"{ns[0]}.{t}" for t in TYPE_RE.findall(code)]
        scripts += [f"{ns[0]}.{c}" for c in re.findall(r"class (\w+)\s*:\s*MVRScript\b", code)]
    if scripts != [ENTRY]:
        problems.append(f"expected exactly one MVRScript {ENTRY}, got {scripts}")
    if len(namespaces) != 1:
        problems.append(f"expected one namespace, got {sorted(namespaces)}")
    dupes = sorted({t for t in types if types.count(t) > 1})
    if dupes:
        problems.append(f"types declared twice: {dupes}")
    print(f"[single]  {'ok' if not problems else 'FAILED'} {len(files)} files, MVRScript={scripts}, "
          f"{len(types)} types")
    return problems


def dotnet() -> str:
    exe = shutil.which("dotnet") or str(Path.home() / ".dotnet" / "dotnet")
    if not Path(exe).exists():
        raise SystemExit("dotnet SDK not found (install .NET 6+ or put it in ~/.dotnet)")
    return exe


def compile_target() -> bool:
    name = "aibody"
    paths = [ASSEMBLED / f for f in cslist_files(ASSEMBLED, CSLIST)]
    files = paths
    stubs = ["UnityStubs.cs", "VaMStubs.cs"]
    items = "\n".join(f'    <Compile Include="{STUBS / s}" />' for s in stubs)
    items += "\n" + "\n".join(f'    <Compile Include="{p}" />' for p in paths)
    project = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net35</TargetFramework>
    <LangVersion>6</LangVersion>
    <OutputType>Library</OutputType>
    <AssemblyName>AIBodyCheck_{re.sub(r'[^A-Za-z0-9]', '_', name)}</AssemblyName>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <NoWarn>CS0618</NoWarn>
  </PropertyGroup>
  <ItemGroup>
{items}
  </ItemGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies.net35" Version="1.0.3" PrivateAssets="all" />
  </ItemGroup>
</Project>
"""
    folder = BUILD / re.sub(r'[^A-Za-z0-9-]', '_', name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Check.csproj").write_text(project, encoding="utf-8")
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
    result = subprocess.run([dotnet(), "build", "-nologo", "-v", "q", "--no-incremental", str(folder / "Check.csproj")],
                            check=False, capture_output=True, text=True, env=env)
    output = result.stdout + result.stderr
    errors = sorted({ln.strip() for ln in output.splitlines() if ": error " in ln})
    warnings = sorted({ln.strip() for ln in output.splitlines() if ": warning " in ln})
    status = "ok" if result.returncode == 0 else "FAILED"
    print(f"[compile] {name:17s} {status} ({len(files)} files, {len(errors)} errors, {len(warnings)} warnings)")
    for line in errors + warnings:
        print("   ", line.replace(str(ROOT) + os.sep, ""))
    return result.returncode == 0


GERMAN_WORDS = {"und", "oder", "nicht", "für", "wird", "ist", "eine", "einen", "einem", "mit", "der", "das", "den",
                "dem", "wenn", "werden", "wurde", "kann", "müssen", "sind", "auch", "noch", "nur", "bitte", "dass",
                "diese", "dieser", "nach", "über", "vom", "zum", "zur", "beim", "keine", "kein", "datei", "fehler",
                "starten", "gestartet", "verbunden", "getrennt", "bereit", "läuft", "gefunden", "test-ton"}
STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def language_scan() -> list[str]:
    """Everything the plugin shows or logs is English (Leon, 19.11.2026): string literals with umlauts or
    common German words are reported."""
    problems = []
    for path in sorted(SRC.rglob("*.cs")):
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line.lstrip().startswith("//"):
                continue
            for m in STRING_RE.finditer(line):
                text = m.group(1)
                words = [w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß-]+", text)]
                if re.search(r"[äöüÄÖÜß]", text) or (len(words) >= 2 and any(w in GERMAN_WORDS for w in words)) \
                        or "test-ton" in words:
                    problems.append(f"{path.relative_to(ROOT)}:{number}: German text? {text[:80]!r}")
    return problems


DOC_GERMAN_MARKERS = {"und", "oder", "nicht", "wird", "ist", "eine", "einen", "einem", "einer", "mit", "für", "wenn",
                      "werden", "wurde", "kann", "sind", "auch", "noch", "nur", "nach", "vom", "zum", "zur", "beim",
                      "keine", "kein", "dass", "sich", "bitte", "ich"}
DOC_EXEMPT = {"docs/TRANSLATION_V18.md"}  # the translation table quotes the German originals on purpose


def docs_language_scan() -> list[str]:
    """All markdown files are English (Leon, 19.11.2026): lines with umlauts or two common German words are reported."""
    problems = []
    for path in sorted(ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in DOC_EXEMPT or any(part in {"dist", "build", ".git", "node_modules"} for part in path.parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            words = re.findall(r"[a-zäöüß]+", line.lower())
            if re.search(r"[äöüÄÖÜß]", line) or sum(1 for w in words if w in DOC_GERMAN_MARKERS) >= 2:
                problems.append(f"{rel}:{number}: German text? {line.strip()[:80]!r}")
    return problems


def main() -> int:
    assemble()
    problems, count = sandbox_scan()
    print(f"[sandbox] {'ok' if not problems else 'FAILED'}: {len(problems)} forbidden matches in {count} files "
          "(src/ + assembled plugin)")
    for p in problems:
        print("   ", p)
    single = single_plugin_check()
    for p in single:
        print("   ", p)
    german = language_scan()
    print(f"[english] {'ok' if not german else 'FAILED'}: {len(german)} string literals that look German")
    for p in german:
        print("   ", p)
    docs = docs_language_scan()
    print(f"[english] docs {'ok' if not docs else 'FAILED'}: {len(docs)} markdown lines that look German")
    for p in docs:
        print("   ", p)
    ok = not problems and not single and not german and not docs
    ok &= compile_target()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
