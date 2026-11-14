#!/usr/bin/env python3
"""Checks the AIBody VaM plugin (one .cslist, one MVRScript) without VaM.

The plugin folder is first assembled from src/AIBody exactly as it ships
(tools/assemble_plugins.py), then:

1. Sandbox scan: the default build must not use APIs VaM 1.22's plugin sandbox blocks
   (System.IO, System.Net, Process, reflection, native interop, UnityEngine.Networking /
   UnityWebRequest, WWW), ignoring code inside `#if AIBODY_HTTP` blocks.
2. Single plugin: AIBody.cslist is flat (plain file names) and its files declare exactly ONE
   MVRScript (AIBody.AIBodyPlugin), one namespace, and no type twice.
3. Compile check: the .cslist is compiled as one assembly (as VaM does) as C# 6 against the
   .NET 3.5 profile and the API stubs in tools/stubs, WITHOUT the UnityEngine.Networking stubs in
   the default build. The optional AIBODY_HTTP build is compiled too.

The stubs encode assumptions about the real VaM API; see TODO(verify) in src/.
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

FORBIDDEN = [
    r"\bSystem\.IO\b",
    r"\bSystem\.Net\b",
    r"\bSystem\.Diagnostics\.Process\b",
    r"\bProcess\.Start\b",
    r"\bSystem\.Reflection\b",
    r"\bSystem\.Runtime\.InteropServices\b",
    r"\bDllImport\b",
    r"\bUnityEngine\.Networking\b",
    r"\bUnityWebRequest\w*\b",
    r"\bWWW\b",
]

CSLIST = "AIBody.cslist"
ENTRY = "AIBody.AIBodyPlugin"
# (name, variant, define AIBODY_HTTP)
TARGETS = [("aibody", "default", False), ("aibody-http", "http", True)]


def assemble() -> None:
    spec = importlib.util.spec_from_file_location("assemble_plugins", ROOT / "tools" / "assemble_plugins.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.assemble(ASSEMBLED / "default", http=False)
    module.assemble(ASSEMBLED / "http", http=True)


def cslist_files(folder: Path, cslist: str) -> list[str]:
    lines = [ln.strip() for ln in (folder / cslist).read_text(encoding="utf-8").splitlines()]
    files = [ln for ln in lines if ln]
    missing = [f for f in files if not (folder / f).is_file()]
    if missing:
        raise SystemExit(f"{cslist} references missing files: {missing}")
    return files


def strip_optional(text: str) -> str:
    """Removes `#if AIBODY_HTTP ... #else/#endif` regions (keeps `#if !AIBODY_HTTP` regions)."""
    out, depth_skip, stack = [], 0, []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#if"):
            skip = s == "#if AIBODY_HTTP"
            stack.append(skip)
            depth_skip += skip
            continue
        if s.startswith("#else") and stack:
            was = stack[-1]
            depth_skip += (not was) - was
            stack[-1] = not was
            continue
        if s.startswith("#endif") and stack:
            depth_skip -= stack.pop()
            continue
        if depth_skip == 0:
            out.append(line)
    return "\n".join(out)


def sandbox_scan() -> list[str]:
    problems = []
    root = ASSEMBLED / "default"
    for rel in cslist_files(root, CSLIST):
        if rel in ("HttpTransport.cs", "AutoTransport.cs"):
            problems.append(f"{CSLIST}: lists optional HTTP source {rel}")
        code = strip_optional((root / rel).read_text(encoding="utf-8"))
        code = re.sub(r"//.*", "", code)  # comments may mention the APIs
        for pattern in FORBIDDEN:
            for m in re.finditer(pattern, code):
                line = code[: m.start()].count("\n") + 1
                problems.append(f"{rel}:{line}: forbidden API '{m.group(0)}'")
    return problems


TYPE_RE = re.compile(r"(?m)^\s*(?:public |internal |static |sealed |abstract |partial )*"
                     r"(?:class|struct|interface|enum) (\w+)")


def single_plugin_check() -> list[str]:
    """Flat .cslist, exactly one MVRScript (the entry class), one namespace, no duplicate types."""
    problems, scripts, types, namespaces = [], [], [], set()
    root = ASSEMBLED / "default"
    files = cslist_files(root, CSLIST)
    if any("/" in f or "\\" in f for f in files):
        problems.append(f"{CSLIST}: sub folder entries: {files}")
    for rel in files:
        code = strip_optional((root / rel).read_text(encoding="utf-8"))
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


def compile_target(name: str, variant: str, http: bool) -> bool:
    root = ASSEMBLED / variant
    paths = [root / f for f in cslist_files(root, CSLIST)]
    files = paths
    stubs = ["UnityStubs.cs", "VaMStubs.cs"] + (["NetworkingStubs.cs"] if http else [])
    items = "\n".join(f'    <Compile Include="{STUBS / s}" />' for s in stubs)
    items += "\n" + "\n".join(f'    <Compile Include="{p}" />' for p in paths)
    project = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net35</TargetFramework>
    <LangVersion>6</LangVersion>
    <OutputType>Library</OutputType>
    <AssemblyName>AIBodyCheck_{re.sub(r'[^A-Za-z0-9]', '_', name)}</AssemblyName>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <DefineConstants>{'AIBODY_HTTP' if http else ''}</DefineConstants>
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


def main() -> int:
    assemble()
    problems = sandbox_scan()
    print(f"[sandbox] {'ok' if not problems else 'FAILED'} (default build)")
    for p in problems:
        print("   ", p)
    single = single_plugin_check()
    for p in single:
        print("   ", p)
    ok = not problems and not single
    for target in TARGETS:
        ok &= compile_target(*target)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
