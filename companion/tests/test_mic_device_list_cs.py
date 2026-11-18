"""Runs tools/cs_tests/MicDeviceListTests.cs against the plugin's src/AIBody/MicDeviceList.cs with
plain .NET (C# 6, like VaM). Skipped when no dotnet SDK is installed."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _dotnet() -> str | None:
    exe = shutil.which("dotnet") or str(Path.home() / ".dotnet" / "dotnet")
    return exe if Path(exe).exists() else None


PROJECT = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <LangVersion>6</LangVersion>
    <OutputType>Exe</OutputType>
    <Nullable>disable</Nullable>
    <ImplicitUsings>disable</ImplicitUsings>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="{lib}" />
    <Compile Include="{tests}" />
  </ItemGroup>
</Project>
"""


@unittest.skipUnless(_dotnet(), "dotnet SDK not installed")
class MicDeviceListCsTest(unittest.TestCase):
    def test_menu_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "MicTests.csproj"
            proj.write_text(PROJECT.format(lib=ROOT / "src/AIBody/MicDeviceList.cs",
                                           tests=ROOT / "tools/cs_tests/MicDeviceListTests.cs"), encoding="utf-8")
            env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
            r = subprocess.run([_dotnet(), "run", "--project", str(proj)], capture_output=True, text=True,
                               env=env, check=False, timeout=300)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(r.stdout.strip().splitlines()[-1].startswith("OK "), r.stdout)


if __name__ == "__main__":
    unittest.main()
