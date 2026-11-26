"""Version 67 (26.11.2026, on top of v66): v66 did not load on Don's PC because VaM had plugins of d0n.AIBody.66 set to "always
denied" (VaM log + AddonPackagesUserPrefs); the companion now warns about it (read-only). Reload Plugin keeps the plugin's
settings (ReloadState.cs, pure C#, run in a dotnet harness). Version 67 everywhere; the plugin passes the VaM-limits compile check."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__, package_prefs
from aibody_companion import setup as first_start

from .test_plugin_menu import method_body
from . import test_version35 as v35

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
HARNESS = Path(__file__).parent / "csharp_reload_harness" / "Program.cs"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_67_everywhere(self):
        self.assertEqual(__version__, "67")
        self.assertIn('PluginVersion = "67"', src("AIBody.cs"))
        self.assertIn('version = "67"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 67)
        self.assertTrue(re.search(r"d0n\.AIBody\.67:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 67 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 67, package `d0n.AIBody.67.var`, release `v67`", readme)
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.66.var", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_release_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        for part in ("**AIBody v67**", "d0n.AIBody.67.var", "always been denied plugin loading", "User Prefs",
                     "Reload Plugin keeps the Activate toggle", "T125"):
            self.assertIn(part, notes)
        self.assertNotIn("Le" + "on", notes)
        self.assertIn("## T125 ", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
        self.assertIn("(version 67, release; on top of v66)", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertIn("**Done in version 67:**", (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8"))


class CslistTests(TestCase):
    """Regression guard: every plugin source is in AIBody.cslist exactly once, every listed file exists, the MVRScript file last."""

    def test_cslist_matches_the_sources(self):
        listed = [l.strip() for l in src("AIBody.cslist").splitlines() if l.strip()]
        self.assertEqual(len(listed), len(set(listed)), "no file twice")
        for name in listed:
            self.assertTrue((SRC / name).is_file(), name)
        on_disk = sorted(p.name for p in SRC.glob("*.cs"))
        self.assertEqual(sorted(listed), on_disk)
        self.assertEqual(listed[-1], "AIBody.cs")
        self.assertIn("ReloadState.cs", listed)

    def test_no_csharp_7_constructs_in_the_plugin(self):
        """VaM compiles C# 6 (tools/check_plugin.py also builds with LangVersion 6); a cheap text guard on top."""
        bad = re.compile(r"\bout var\b|\bis not\b|\bis null\b|\bswitch\s*\{|\bdefault\s*[;,)]|\b_\s*=")
        for path in SRC.glob("*.cs"):
            # one pass over comments, verbatim / normal strings and char literals, so "//" in a string or '"' in a char
            # literal cannot confuse the next rule
            token = re.compile(r'//[^\n]*|/\*.*?\*/|@"(?:""|[^"])*"|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\])\'', re.S)
            code = token.sub(' ', path.read_text(encoding="utf-8"))
            m = bad.search(code)
            self.assertIsNone(m, f"{path.name}: {m.group(0) if m else ''}")

    def test_compile_check_uses_vams_limits(self):
        check = (ROOT / "tools" / "check_plugin.py").read_text(encoding="utf-8")
        self.assertIn("<LangVersion>6</LangVersion>", check)
        self.assertIn("<TargetFramework>net35</TargetFramework>", check)


class PackagePrefsTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "AddonPackages").mkdir()
        (self.root / "AddonPackagesUserPrefs").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def prefs(self, version, enabled, disabled):
        (self.root / "AddonPackagesUserPrefs" / f"d0n.AIBody.{version}.prefs").write_text(json.dumps(
            {"pluginsAlwaysEnabled": enabled, "pluginsAlwaysDisabled": disabled, "ignoreMissingDependencyErrors": "false"}), encoding="utf-8")

    def var(self, version):
        (self.root / "AddonPackages" / f"d0n.AIBody.{version}.var").write_bytes(b"PK")

    def test_dons_case_is_found(self):
        self.var(66)
        self.prefs(65, "true", "false")
        self.prefs(66, "false", "true")
        self.assertEqual(package_prefs.denied_installed(self.root), ["d0n.AIBody.66"])
        text = package_prefs.warning(self.root)
        self.assertIn("d0n.AIBody.66", text)
        self.assertIn("User Prefs", text)

    def test_allowed_missing_broken_or_not_installed_is_quiet(self):
        self.var(67)
        self.assertIsNone(package_prefs.warning(self.root), "no prefs file yet (VaM asks)")
        self.prefs(67, "true", "false")
        self.assertIsNone(package_prefs.warning(self.root))
        (self.root / "AddonPackagesUserPrefs" / "d0n.AIBody.67.prefs").write_text("{broken", encoding="utf-8")
        self.assertIsNone(package_prefs.warning(self.root))
        self.prefs(60, "false", "true")
        self.assertIsNone(package_prefs.warning(self.root), "old package not installed any more")
        self.assertIsNone(package_prefs.warning(self.root / "nope"))

    def test_read_only_and_wired_into_the_start(self):
        code = (ROOT / "companion" / "aibody_companion" / "package_prefs.py").read_text(encoding="utf-8")
        self.assertNotIn("write_text", code)
        self.assertNotIn("open(", code)
        cli = (ROOT / "companion" / "aibody_companion" / "cli.py").read_text(encoding="utf-8")
        self.assertIn("package_prefs.warning(cfg.vam_root)", cli)


class ReloadWiringTests(TestCase):
    def test_saved_on_destroy_read_in_init_applied_before_the_config_seeding(self):
        plugin = src("AIBody.cs")
        self.assertLess(method_body(plugin, "private void OnDestroy()").index("SaveReloadState();"),
                        method_body(plugin, "private void OnDestroy()").index("OnDisable();"))
        save = method_body(plugin, "private void SaveReloadState()")
        self.assertIn("GetJSON(true, true, true)", save)
        self.assertIn("ReloadState.Stamp(DateTime.UtcNow)", save)
        self.assertIn('root["atom"] = containingAtom.uid;', save)
        read = method_body(plugin, "private void ReadReloadState()")
        self.assertIn("FileManagerSecure.DeleteFile(ReloadStatePath);", read)
        self.assertIn("ReloadState.Fresh(", read)
        self.assertIn("ReadReloadState();", method_body(plugin, "public override void Init()"))
        settings = method_body(plugin, "private void UpdateSettings(float dt)")
        self.assertLess(settings.index("ApplyReloadState();"), settings.index('_link.LoadSettingsFile()'))
        apply = method_body(plugin, "private void ApplyReloadState()")
        self.assertIn("_sceneRestored", apply, "a scene loaded into the new plugin wins")
        self.assertIn("RestoreFromJSON(state);", apply)

    def test_token_is_never_in_the_state(self):
        link = src("AppLink.cs")
        self.assertIn("// Not registered (version 31): same as the first-run note's field; the token lives in config.json only.", link)
        self.assertNotIn("RegisterString(_xaiTokenJson", link)


@unittest.skipUnless(Path(v35.DOTNET).exists(), "dotnet SDK not installed")
class ReloadStateHarnessTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        shutil.copy(HARNESS, folder / "Program.cs")
        (folder / "Harness.csproj").write_text(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType><Nullable>disable</Nullable>
  <EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup>
  <ItemGroup><Compile Include="Program.cs" /><Compile Include="{SRC / 'ReloadState.cs'}" /></ItemGroup>
</Project>""", encoding="utf-8")
        result = subprocess.run([v35.DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder, capture_output=True,
                                text=True, timeout=240, env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
        if result.returncode != 0:
            raise AssertionError("harness build failed:\n" + result.stdout + result.stderr)
        cls.exe = folder / "out" / "Harness.dll"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cmds(self, *cmds):
        proc = subprocess.run([v35.DOTNET, str(self.exe)], input="".join(c + "\n" for c in cmds), capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.splitlines()

    def test_constants(self):
        self.assertEqual(self.run_cmds("const"), ["reload_state.json\t30"])

    def test_fresh_window(self):
        stamp = self.run_cmds("stamp\t2026-11-26T20:00:00Z")[0]
        out = self.run_cmds(*("fresh\t" + stamp + "\t" + now + "\t30" for now in
                              ("2026-11-26T20:00:00Z", "2026-11-26T20:00:29Z", "2026-11-26T20:00:31Z", "2026-11-26T19:59:59Z")))
        self.assertEqual(out, ["1", "1", "0", "0"], "0-30 s fresh; older or from the future is not")
        self.assertEqual(self.run_cmds("fresh\tgarbage\t2026-11-26T20:00:00Z\t30", "fresh\t\t2026-11-26T20:00:00Z\t30"), ["0", "0"])

    def test_applies_only_for_a_plain_reload_on_the_same_atom(self):
        out = self.run_cmds("applies\t1\tClient\tClient\t0", "applies\t1\tClient\tClient\t1", "applies\t0\tClient\tClient\t0",
                            "applies\t1\tClient\tAI\t0", "applies\t1\t\t\t0")
        self.assertEqual(out, ["1", "0", "0", "0", "0"])
