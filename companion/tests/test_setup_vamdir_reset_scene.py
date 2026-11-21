"""After version 40 (Leon, 21.11.2026 17:01/17:02; on main, not released yet):
1. the installer asks for the VaM folder (wizard page, auto-detected, VaM.exe required, /VAMDIR= when silent) and writes
   it to the launcher's launcher.json, which the launcher reads first;
2. tab Config > Reset: 'Reset to Default' with a confirm step resets every saved plugin setting, including the
   per-scene character wizard answers, and never the XAI API Token or the key file paths;
3. the AI-Buddy scene carries AIBody on the male BryanGosling, not on the female Person.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest import TestCase

from aibody_companion import setup as first_start
from aibody_companion import winapp

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def method_body(text: str, signature: str) -> str:
    start = text.index(signature)
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise AssertionError(signature)


class InstallerVamFolderTests(TestCase):
    def setUp(self):
        self.iss = (ROOT / "packaging" / "companion" / "AIBodyCompanion.iss").read_text(encoding="utf-8")

    def test_wizard_page_prefilled_and_validated(self):
        for part in ("CreateInputDirPage(", "'Your VaM folder'", "VamPage.Values[0] := Found;", "DetectVamDir()",
                     "function NextButtonClick", "FileExists(AddBackslash(Trim(Dir)) + 'VaM.exe')",
                     "GetPreviousData('VamDir'", "SetPreviousData(PreviousDataKey, 'VamDir'", "LauncherVamDir()"):
            self.assertIn(part, self.iss)
        nxt = self.iss[self.iss.index("function NextButtonClick"):self.iss.index("function ChosenVamDir")]
        self.assertIn("not IsVamDir(VamPage.Values[0])", nxt)
        self.assertIn("Result := False", nxt)

    def test_silent_vamdir_parameter(self):
        self.assertIn("{param:VAMDIR|}", self.iss)
        init = self.iss[self.iss.index("function InitializeSetup"):self.iss.index("procedure InitializeWizard")]
        self.assertIn("not IsVamDir(VamDirParam)", init)
        self.assertIn("Result := False", init)

    def test_choice_written_where_the_launcher_reads_it(self):
        self.assertIn("LauncherFolder = '{localappdata}\\AIBody Companion';", self.iss)
        self.assertIn(f"LauncherFile = '{winapp.SETTINGS_FILE}';", self.iss)
        self.assertIn("'  \"vam_root\": \"' + JsonEscape(Dir) + '\",'", self.iss)
        self.assertIn("SaveStringsToUTF8File(", self.iss)
        self.assertIn("if CurStep <> ssPostInstall then exit;", self.iss)
        # the launcher's own data folder is what the installer writes into
        self.assertEqual(winapp.data_dir({"LOCALAPPDATA": "C:/L"}), Path("C:/L") / "AIBody Companion")

    def test_launcher_reads_the_installer_file_with_bom_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            vam = Path(tmp) / "Games" / "My VaM"
            vam.mkdir(parents=True)
            (vam / "VaM.exe").write_bytes(b"")
            folder = Path(tmp) / "AIBody Companion"
            folder.mkdir()
            escaped = str(vam).replace("\\", "\\\\")
            text = '{\r\n  "vam_root": "' + escaped + '",\r\n  "vam_root_set_by": "setup"\r\n}\r\n'
            (folder / winapp.SETTINGS_FILE).write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
            settings = winapp.load_settings(folder)
            self.assertEqual(settings["vam_root"], str(vam))
            other = Path(tmp) / "elsewhere" / "VaM"
            other.mkdir(parents=True)
            (other / "VaM.exe").write_bytes(b"")
            root, how = winapp.detect_vam_root(Path(tmp) / "Programs", settings["vam_root"], [other])
            self.assertEqual((root, how), (vam, "remembered"))

    def test_picker_is_only_the_fallback(self):
        src = (ROOT / "companion" / "aibody_companion" / "winapp.py").read_text(encoding="utf-8")
        main = src[src.index("def main("):]
        self.assertLess(main.index("detect_vam_root("), main.index("ask_vam_folder()"))
        self.assertIn("if root is None:\n        root = ask_vam_folder()", main)
        self.assertIn("--check-vam-root", src)

    def test_ci_installs_silently_with_vamdir_and_checks_launcher_json(self):
        wf = (ROOT / ".github" / "workflows" / "companion-windows.yml").read_text(encoding="utf-8")
        for part in ('"/VAMDIR=', "--check-vam-root", "launcher.json", "vam_root", "VaM.exe"):
            self.assertIn(part, wf)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        start = readme[readme.index("## Getting started"):readme.index("### For developers")]
        self.assertIn("Your VaM folder", start)
        tp = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T52", tp)
        self.assertIn("/VAMDIR=", (ROOT / "docs" / "TECHNICAL.md").read_text(encoding="utf-8"))


class ResetToDefaultTests(TestCase):
    def setUp(self):
        self.plugin = source("AIBody.cs")
        self.helper = source("UiHelper.cs")
        self.all = "".join(source(f) for f in ("AIBody.cs", "AppLink.cs", "Body.cs", "MicConfig.cs", "CharacterWizard.cs"))

    def test_config_tab_has_reset_header_and_button_with_confirm(self):
        show = method_body(self.plugin, "private void ShowTab(int index)")
        config = show[show.index("default: // Config"):]
        self.assertLess(config.index('_page.Header("<b>Background</b>");'), config.index('_page.Header("<b>Reset</b>");'))
        self.assertIn("BuildResetSection();", config)
        section = method_body(self.plugin, "private void BuildResetSection()")
        self.assertIn("_page.Button(ResetButtonLabel", section)
        self.assertIn("_page.Button(ResetConfirmLabel, ConfirmReset);", section)
        self.assertIn("_page.Button(ResetCancelLabel", section)
        self.assertNotIn("Note(", section)   # right column: header and controls only
        self.assertNotIn("Header(", section)
        self.assertLess(section.index("if (!_resetPending)"), section.index("ResetConfirmLabel"))
        self.assertIn('ResetButtonLabel = "Reset to Default"', self.plugin)
        # the button itself only asks; the reset runs from the confirm button
        first = section[:section.index("return;")]
        self.assertNotIn("ResetAll", first)
        self.assertIn("Defaults.ResetAll(this)", method_body(self.plugin, "private void ConfirmReset()"))
        self.assertIn("if (index != _tab) _resetPending = false;", self.plugin)

    def test_left_info_prose_with_exact_labels(self):
        info = method_body(self.plugin, "private string ResetInfo()")
        for label in ("ResetButtonLabel", "ResetConfirmLabel", "ResetCancelLabel", "BackgroundToggleName",
                      "CharacterWizard.GateQuestion"):
            self.assertIn('<b>" + ' + label + ' + "</b>', info)
        for label in ("XAI API Token", "xAI key file", "ElevenLabs key file"):
            self.assertIn(f"<b>{label}</b>", info)
        self.assertIn("never deletes your", info)
        self.assertIn("+ ResetInfo()", self.plugin)

    def test_every_saved_setting_is_tracked_except_keys_and_hooks(self):
        registered = re.findall(r"Register(?:Bool|Float|String|StringChooser|Color)\((\w+)\)", self.all)
        self.assertEqual(sorted(registered), sorted(["_settingsInitJson", "_xaiKeyFileJson", "_elevenKeyFileJson",
                                                     "_aiSpeakingJson", "_userSpeakingJson", "_sceneEventJson",
                                                     "_backgroundColorJson"]))
        self.assertIn("Defaults.TrackColor(BackgroundColorName, _backgroundColorJson.val);", self.plugin)
        wizard = source("CharacterWizard.cs")
        for name in ("_askedJson", "_wantedJson"):
            self.assertIn(f"SettingsDefaults.Bool(_plugin, {name});", wizard)
        self.assertIn("SettingsDefaults.Bool(this, _backgroundJson);", self.plugin)
        self.assertNotIn("_xaiTokenJson)", re.sub(r"//.*", "", "\n".join(
            l for l in self.all.splitlines() if "SettingsDefaults." in l)))

    def test_reset_helper_is_sandbox_safe(self):
        cls = self.helper[self.helper.index("public class SettingsDefaults"):]
        self.assertNotIn("foreach", cls)
        self.assertNotIn("Dictionary", cls)
        self.assertNotIn("Reflection", cls)
        self.assertNotIn("this[", cls)
        self.assertIn("plugin.SetColorParamValue(_colorNames[i], _colorDefaults[i]);", cls)
        self.assertIn("public readonly SettingsDefaults Defaults = new SettingsDefaults();", self.plugin)

    def test_companion_config_is_kept_and_documented(self):
        confirm = method_body(self.plugin, "private void ConfirmReset()")
        self.assertIn("_link.MarkConfigDirty()", confirm)
        self.assertNotIn("api_key", confirm)
        self.assertNotIn("WriteAllText", confirm)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("**Reset to Default**", spec)
        self.assertIn("never deleted", spec)
        self.assertIn("## T53", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))


class SceneHolderTests(TestCase):
    def test_aibody_on_bryan_gosling_only(self):
        data = json.loads(first_start.TEMPLATE.read_text(encoding="utf-8"))
        holders, settings = [], []
        for atom in data["atoms"]:
            for st in atom["storables"]:
                if st["id"] == "PluginManager" and st["plugins"]:
                    holders.append((atom["id"], st["plugins"]))
                if st["id"] == first_start.AIBODY_STORABLE:
                    settings.append((atom["id"], st))
        self.assertEqual([h for h, _ in holders], ["BryanGosling"])
        self.assertEqual([a for a, _ in settings], ["BryanGosling"])
        self.assertEqual(settings[0][1]["Set background color"], "true")
        self.assertEqual(settings[0][1]["Background color"], {"h": "0.3333333", "s": "1", "v": "1"})
        female = next(a for a in data["atoms"] if a["id"] == "Person")
        self.assertEqual(next(s for s in female["storables"] if s["id"] == "PluginManager")["plugins"], {})

    def test_build_var_checks_the_holder_and_keeps_self(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_var", ROOT / "tools" / "build_var.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        self.assertEqual(build.AIBODY_ATOM, "BryanGosling")
        text = build.example_scene("d0n", "AIBody", 99, "Custom/Scripts/d0n/AIBody")
        data = json.loads(text)
        bryan = next(a for a in data["atoms"] if a["id"] == "BryanGosling")
        pm = next(s for s in bryan["storables"] if s["id"] == "PluginManager")
        self.assertEqual(pm["plugins"], {"plugin#0": "SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist"})
        moved = json.loads(first_start.TEMPLATE.read_text(encoding="utf-8"))
        for atom in moved["atoms"]:
            if atom["id"] == "BryanGosling":
                atom["storables"] = [s for s in atom["storables"] if s["id"] != first_start.AIBODY_STORABLE]
        with self.assertRaises(SystemExit):
            build.check_aibody_atom(moved)

    def test_setup_scene_writes_aibody_on_bryan(self):
        data = first_start.scene_data(False)
        st = [(a["id"], s) for a in data["atoms"] for s in a["storables"] if s["id"] == first_start.AIBODY_STORABLE]
        self.assertEqual([a for a, _ in st], ["BryanGosling"])
        self.assertEqual(st[0][1][first_start.TOGGLE_NAME], "false")

    def test_docs(self):
        g = (ROOT / "docs" / "SCENE_GREENSCREEN.md").read_text(encoding="utf-8")
        self.assertIn("AIBody is only on the male `BryanGosling`", g)
        self.assertIn("do not add AIBody to `Person`", g)
        self.assertIn("## T54", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
        self.assertIn("AIBody on the male BryanGosling", source("AIBody.cs"))
