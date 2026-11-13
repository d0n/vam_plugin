#!/usr/bin/env python3
"""Checks the three VaM plugins (Session, Person, Person2) without VaM.

1. Sandbox scan: the sources listed in each default .cslist must not use APIs VaM 1.22's plugin
   sandbox blocks (System.IO, System.Net, Process, reflection, native interop, UnityEngine.Networking
   / UnityWebRequest), ignoring code inside `#if AIBODY_HTTP` blocks.
2. Compile check: every .cslist is compiled on its own (as VaM does) as C# 6 against the
   .NET 3.5 profile and the API stubs in tools/stubs. The default builds are compiled WITHOUT
   the UnityEngine.Networking stubs, so networking code that slipped through fails here.
   The optional AIBODY_HTTP builds are compiled too, to keep that code healthy.
3. Identity: Person2 is generated from the Person sources (tools/make_person2.py); the three
   MVRScript classes and the Person slots/params must be distinct.

The stubs encode assumptions about the real VaM API; see TODO(verify) in src/.
Usage: python tools/check_plugin.py   (needs the .NET SDK 6+ on PATH or in ~/.dotnet)
"""
from __future__ import annotations

import os
import re
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
STUBS = ROOT / "tools" / "stubs"
BUILD = STUBS / "build"

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

PERSON2_SRC = BUILD / "person2-src"

# (name, source root, cslist, define AIBODY_HTTP, extra optional sources)
TARGETS = [
    ("session", SRC, "AIBodySession.cslist", False, []),
    ("person", SRC, "AIBodyPerson.cslist", False, []),
    ("person2", PERSON2_SRC, "AIBodyPerson2.cslist", False, []),
    ("session-http", SRC, "AIBodySession.cslist", True, ["Optional/HttpTransport.cs", "Optional/AutoTransport.cs"]),
    ("person-http", SRC, "AIBodyPerson.cslist", True, []),
    ("person2-http", PERSON2_SRC, "AIBodyPerson2.cslist", True, []),
]
DEFAULT_SETS = [(SRC, "AIBodySession.cslist"), (SRC, "AIBodyPerson.cslist"), (PERSON2_SRC, "AIBodyPerson2.cslist")]


def generate_person2() -> None:
    spec = importlib.util.spec_from_file_location("make_person2", ROOT / "tools" / "make_person2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate(PERSON2_SRC)


def cslist_files(name: str, root: Path = SRC) -> list[str]:
    lines = [ln.strip() for ln in (root / name).read_text(encoding="utf-8").splitlines()]
    files = [ln for ln in lines if ln and not ln.startswith("//")]
    missing = [f for f in files if not (root / f).is_file()]
    if missing:
        raise SystemExit(f"{name} references missing files: {missing}")
    if any(f.startswith("Optional/") for f in files):
        raise SystemExit(f"{name} must not list Optional/ (HTTP) sources")
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
    for root, cslist in DEFAULT_SETS:
        for rel in cslist_files(cslist, root):
            code = strip_optional((root / rel).read_text(encoding="utf-8"))
            code = re.sub(r"//.*", "", code)  # comments may mention the APIs
            for pattern in FORBIDDEN:
                for m in re.finditer(pattern, code):
                    line = code[: m.start()].count("\n") + 1
                    problems.append(f"{cslist}: {rel}:{line}: forbidden API '{m.group(0)}'")
    return problems


def identity_check() -> list[str]:
    """The three plugins must be distinct scripts; the two Person builds distinct slots."""
    problems, classes, slots = [], {}, {}
    for root, cslist in DEFAULT_SETS:
        text = "\n".join((root / f).read_text(encoding="utf-8") for f in cslist_files(cslist, root))
        code = strip_optional(text)
        ns = re.findall(r"(?m)^namespace (\w+)", code)
        scripts = re.findall(r"public class (\w+) : MVRScript", code)
        if len(scripts) != 1 or len(set(ns)) != 1:
            problems.append(f"{cslist}: expected one MVRScript and one namespace, got {scripts} / {sorted(set(ns))}")
            continue
        full = f"{ns[0]}.{scripts[0]}"
        if full in classes.values() or scripts[0] in [c.split(".")[1] for c in classes.values()]:
            problems.append(f"{cslist}: script class {full} collides with another plugin")
        classes[cslist] = full
        slot = re.findall(r"Slot = Protocol\.(Slot\d);", code)
        if slot:
            if slot[0] in slots.values():
                problems.append(f"{cslist}: slot {slot[0]} is also used by another Person build")
            slots[cslist] = slot[0]
    print(f"[identity] {'ok' if not problems else 'FAILED'} " + ", ".join(f"{k}={v}" for k, v in classes.items())
          + " | " + ", ".join(f"{k}={v}" for k, v in slots.items()))
    return problems


def dotnet() -> str:
    exe = shutil.which("dotnet") or str(Path.home() / ".dotnet" / "dotnet")
    if not Path(exe).exists():
        raise SystemExit("dotnet SDK not found (install .NET 6+ or put it in ~/.dotnet)")
    return exe


def compile_target(name: str, root: Path, cslist: str, http: bool, extra: list[str]) -> bool:
    files = cslist_files(cslist, root) + extra
    stubs = ["UnityStubs.cs", "VaMStubs.cs"] + (["NetworkingStubs.cs"] if http else [])
    items = "\n".join(f'    <Compile Include="{STUBS / s}" />' for s in stubs)
    items += "\n" + "\n".join(f'    <Compile Include="{(SRC if f.startswith("Optional/") else root) / f}" />'
                               for f in files)
    project = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net35</TargetFramework>
    <LangVersion>6</LangVersion>
    <OutputType>Library</OutputType>
    <AssemblyName>AIBodyCheck_{name.replace('-', '_')}</AssemblyName>
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
    folder = BUILD / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Check.csproj").write_text(project, encoding="utf-8")
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
    result = subprocess.run([dotnet(), "build", "-nologo", "-v", "q", "--no-incremental", str(folder / "Check.csproj")],
                            capture_output=True, text=True, env=env)
    output = result.stdout + result.stderr
    errors = sorted({ln.strip() for ln in output.splitlines() if ": error " in ln})
    warnings = sorted({ln.strip() for ln in output.splitlines() if ": warning " in ln})
    status = "ok" if result.returncode == 0 else "FAILED"
    print(f"[compile] {name:13s} {status} ({len(files)} files, {len(errors)} errors, {len(warnings)} warnings)")
    for line in errors + warnings:
        print("   ", line.replace(str(ROOT) + os.sep, ""))
    return result.returncode == 0


def main() -> int:
    generate_person2()
    problems = sandbox_scan()
    print(f"[sandbox] {'ok' if not problems else 'FAILED'} (default builds of all three plugins)")
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
