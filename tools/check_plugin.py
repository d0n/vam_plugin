#!/usr/bin/env python3
"""Checks the two VaM plugins (AIBody Client and AIBody Companion) without VaM.

The plugin folders are first assembled from src/ exactly as they ship (tools/assemble_plugins.py),
then:

1. Sandbox scan: the default build must not use APIs VaM 1.22's plugin sandbox blocks
   (System.IO, System.Net, Process, reflection, native interop, UnityEngine.Networking /
   UnityWebRequest, WWW), ignoring code inside `#if AIBODY_HTTP` blocks.
2. Identity: one MVRScript per plugin with distinct class names, and no type full name (namespace
   + name) defined by both plugins, so they load side by side without clashes.
3. Compile check: each .cslist is compiled on its own (as VaM does) as C# 6 against the .NET 3.5
   profile and the API stubs in tools/stubs, WITHOUT the UnityEngine.Networking stubs in the
   default build. Both plugins are also compiled together into one assembly, which fails on any
   duplicate type name. The optional AIBODY_HTTP builds are compiled too.

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

PLUGINS = [("Client", "AIBodyClient.cslist"), ("Companion", "AIBodyCompanion.cslist")]
# (name, variant, plugin folders compiled into one assembly, define AIBODY_HTTP)
TARGETS = [
    ("client", "default", ["Client"], False),
    ("companion", "default", ["Companion"], False),
    ("client+companion", "default", ["Client", "Companion"], False),
    ("client-http", "http", ["Client"], True),
    ("companion-http", "http", ["Companion"], True),
]


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
    for folder, cslist in PLUGINS:
        root = ASSEMBLED / "default" / folder
        files = cslist_files(root, cslist)
        if any(f.startswith("Optional/") for f in files):
            problems.append(f"{cslist}: lists Optional/ (HTTP) sources")
        for rel in files:
            code = strip_optional((root / rel).read_text(encoding="utf-8"))
            code = re.sub(r"//.*", "", code)  # comments may mention the APIs
            for pattern in FORBIDDEN:
                for m in re.finditer(pattern, code):
                    line = code[: m.start()].count("\n") + 1
                    problems.append(f"{folder}/{rel}:{line}: forbidden API '{m.group(0)}'")
    return problems


TYPE_RE = re.compile(r"(?m)^\s*(?:public |internal |static |sealed |abstract |partial )*(?:class|struct|interface|enum) (\w+)")


def identity_check() -> list[str]:
    """Distinct MVRScript classes and no type full name declared by both plugins."""
    problems, scripts, types = [], {}, {}
    for folder, cslist in PLUGINS:
        root = ASSEMBLED / "default" / folder
        declared = set()
        for rel in cslist_files(root, cslist):
            code = strip_optional((root / rel).read_text(encoding="utf-8"))
            ns = re.findall(r"(?m)^namespace ([\w.]+)", code)
            if len(ns) != 1:
                problems.append(f"{folder}/{rel}: expected one namespace, got {ns}")
                continue
            declared |= {f"{ns[0]}.{t}" for t in TYPE_RE.findall(code)}
            for script in re.findall(r"public class (\w+) : MVRScript", code):
                scripts.setdefault(folder, []).append(f"{ns[0]}.{script}")
        types[folder] = declared
        if len(scripts.get(folder, [])) != 1:
            problems.append(f"{cslist}: expected exactly one MVRScript, got {scripts.get(folder)}")
    shared = types["Client"] & types["Companion"]
    if shared:
        problems.append(f"types declared by both plugins: {sorted(shared)}")
    names = [s.split(".")[-1] for v in scripts.values() for s in v]
    if len(names) != len(set(names)):
        problems.append(f"MVRScript class names collide: {names}")
    print(f"[identity] {'ok' if not problems else 'FAILED'} "
          + ", ".join(f"{k}={v[0] if v else '?'}" for k, v in scripts.items())
          + f" ({len(types['Client'])} + {len(types['Companion'])} types, {len(shared)} shared)")
    return problems


def dotnet() -> str:
    exe = shutil.which("dotnet") or str(Path.home() / ".dotnet" / "dotnet")
    if not Path(exe).exists():
        raise SystemExit("dotnet SDK not found (install .NET 6+ or put it in ~/.dotnet)")
    return exe


def compile_target(name: str, variant: str, folders: list[str], http: bool) -> bool:
    paths = []
    for folder in folders:
        root = ASSEMBLED / variant / folder
        paths += [root / f for f in cslist_files(root, dict(PLUGINS)[folder])]
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
    print(f"[sandbox] {'ok' if not problems else 'FAILED'} (default build of both plugins)")
    for p in problems:
        print("   ", p)
    identity = identity_check()
    for p in identity:
        print("   ", p)
    ok = not problems and not identity
    for target in TARGETS:
        ok &= compile_target(*target)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
