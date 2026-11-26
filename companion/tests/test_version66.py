"""Version 66 (26.11.2026, on top of v65): the checkbox "Idle poses from all pose files" (body.idle_poses_all_files) is the
dropdown "Idle pose pool" (body.idle_pose_pool = "aibody" | "all"); migration of old config.json files and scenes; version
everywhere and English release notes. The pure C# (IdlePoolMode in IdlePoses.cs) runs in a dotnet harness."""
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

from aibody_companion import __version__
from aibody_companion import settings_file
from aibody_companion import setup as first_start

from .test_plugin_menu import method_body
from . import test_version35 as v35

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
HARNESS = Path(__file__).parent / "csharp_idle_pool_harness" / "Program.cs"

AIBODY = "AIBody poses only"
ALL = "All pose files"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_66_everywhere(self):
        self.assertEqual(__version__, "66")
        self.assertIn('PluginVersion = "66"', src("AIBody.cs"))
        self.assertIn('version = "66"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 66)
        self.assertTrue(re.search(r"d0n\.AIBody\.66:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 66 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((ROOT / "packaging" / "meta.json").read_text())["licenseType"], "FC")
        for f in ("README.md", "docs/REQUIREMENTS.md", "docs/SCENE_GREENSCREEN.md", "docs/RELEASE_NOTES_NEXT.md"):
            self.assertNotIn("AIBody.65", (ROOT / f).read_text(encoding="utf-8"), f)

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Status: version 66, package `d0n.AIBody.66.var`, release `v66`", readme)
        self.assertIn("**Idle pose pool**", readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("(version 66, release; on top of v65)", spec)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## T122", proto)
        config = (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8")
        self.assertIn("`body.idle_pose_pool` (`\"aibody\"`, version 66", config)
        self.assertIn("`body.idle_poses_all_files` (version 54-65, removed in version 66)", config)
        self.assertIn("## Version 66", (ROOT / "docs" / "API_AUDIT.md").read_text(encoding="utf-8"))

    def test_release_notes_english_without_personal_names(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("**AIBody v66**", notes)
        for part in ("d0n.AIBody.66.var", "AI-Buddy.jpg", "AI-Buddy.json", "Idle pose pool", AIBODY, ALL,
                     "body.idle_pose_pool", "body.idle_poses_all_files", "T122"):
            self.assertIn(part, notes)
        self.assertIsNone(re.search(r"\b(" + "Le" + "on|Don)\b", notes), "no personal names in public release notes")


class CompanionConfigTests(TestCase):
    def pool(self, body):
        data, errors = settings_file.validate({"body": body})
        return data["body"], errors

    def test_default_and_example(self):
        self.assertEqual(settings_file.DEFAULTS["body"]["idle_pose_pool"], "aibody")
        self.assertNotIn("idle_poses_all_files", settings_file.DEFAULTS["body"])
        self.assertEqual(settings_file.CHOICES[("body", "idle_pose_pool")], ("aibody", "all"))
        example = json.loads((ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(example["body"]["idle_pose_pool"], "aibody")
        self.assertNotIn("idle_poses_all_files", example["body"])
        data, errors = settings_file.validate(example)
        self.assertEqual(errors, [])

    def test_new_key_is_kept(self):
        for value in ("aibody", "all"):
            body, errors = self.pool({"idle_pose_pool": value})
            self.assertEqual(body["idle_pose_pool"], value)
            self.assertEqual(errors, [])

    def test_old_true_becomes_all_old_false_becomes_aibody(self):
        body, errors = self.pool({"idle_poses_all_files": True})
        self.assertEqual(body["idle_pose_pool"], "all")
        self.assertNotIn("idle_poses_all_files", body)
        self.assertEqual(errors, [], "the old key is a legacy key: no warning")
        body, errors = self.pool({"idle_poses_all_files": False})
        self.assertEqual(body["idle_pose_pool"], "aibody")
        self.assertEqual(errors, [])
        body, _ = self.pool({"idle_poses_all_files": "true"})  # VaM's SimpleJSON may write a string
        self.assertEqual(body["idle_pose_pool"], "all")
        body, _ = self.pool({"idle_poses_all_files": "false"})
        self.assertEqual(body["idle_pose_pool"], "aibody")

    def test_missing_is_aibody(self):
        body, _ = self.pool({})
        self.assertEqual(body["idle_pose_pool"], "aibody")
        data, _ = settings_file.validate({})
        self.assertEqual(data["body"]["idle_pose_pool"], "aibody")

    def test_new_key_wins_over_the_old_one(self):
        body, _ = self.pool({"idle_pose_pool": "aibody", "idle_poses_all_files": True})
        self.assertEqual(body["idle_pose_pool"], "aibody")
        body, _ = self.pool({"idle_pose_pool": "all", "idle_poses_all_files": False})
        self.assertEqual(body["idle_pose_pool"], "all")

    def test_unknown_value_falls_back_to_the_default(self):
        for bad in ("foo", "", "0", "ALL", "All pose files", 7, None):
            body, errors = self.pool({"idle_pose_pool": bad})
            self.assertEqual(body["idle_pose_pool"], "aibody", repr(bad))
            self.assertTrue(errors, repr(bad))

    def test_migration_does_not_touch_other_keys_or_the_input(self):
        original = {"idle_poses_all_files": True, "idle_poses": False, "idle_pose_interval_s": 60}
        copy = dict(original)
        body, _ = self.pool(original)
        self.assertEqual(original, copy)
        self.assertIs(body["idle_poses"], False)
        self.assertEqual(body["idle_pose_interval_s"], 60.0)
        self.assertEqual(settings_file.migrate_idle_pool({"idle_poses": True}), {"idle_poses": True})

    def test_schema_has_the_menu_and_not_the_old_toggle(self):
        schema = json.loads((ROOT / "protocol" / "schema" / "config.schema.json").read_text(encoding="utf-8"))
        props = schema["properties"]["body"]["properties"]
        self.assertEqual(props["idle_pose_pool"]["enum"], ["aibody", "all"])
        self.assertEqual(props["idle_pose_pool"]["default"], "aibody")
        self.assertNotIn("idle_poses_all_files", props)
        gen = (ROOT / "tools" / "gen_config_schema.py").read_text(encoding="utf-8")
        self.assertIn('("body", "idle_pose_pool")', gen)
        self.assertNotIn('"idle_poses_all_files"):', gen)

    def test_file_roundtrip_old_file_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"body": {"idle_poses_all_files": True}}), encoding="utf-8")
            data, errors = settings_file.load(path)
            self.assertEqual(data["body"]["idle_pose_pool"], "all")
            self.assertEqual(errors, [])


class PluginSourceTests(TestCase):
    def test_menu_is_a_chooser_through_popup(self):
        body = src("Body.cs")
        self.assertIn("_idlePoolJson = new JSONStorableStringChooser(IdlePoolMode.MenuName, IdlePoolMode.Labels(), IdlePoolMode.DefaultLabel,", body)
        self.assertIn("SettingsDefaults.Chooser(_plugin, _idlePoolJson);", body)
        self.assertIn("page.Popup(_idlePoolJson);", body)
        self.assertNotIn("page.Toggle(_idleAllFilesJson)", body)
        self.assertNotIn("_idleAllFilesJson", body)
        self.assertNotIn("SettingsDefaults.Bool(_plugin, _idleAllFilesLegacy)", body, "the old toggle is not part of Reset to Default")

    def test_pool_still_picked_through_idle_all_files(self):
        body = src("Body.cs")
        self.assertIn("private bool IdleAllFiles { get { return _idlePoolJson != null && IdlePoolMode.IsAll(_idlePoolJson.val); } }", body)
        self.assertEqual(body.count("IdlePoolNames(IdleAllFiles)"), 4)
        self.assertIn("(allFiles || IsOwnPoseFile(kv.Value))", src("PoseController.cs"))

    def test_legacy_toggle_stays_registered_but_hidden(self):
        body = src("Body.cs")
        self.assertIn("new JSONStorableBool(IdlePoolMode.LegacyToggleName, false, (bool v) => MigrateIdlePool(v));", body)
        self.assertIn("_idleAllFilesLegacy.isStorable = false;", body)
        self.assertIn("_plugin.RegisterBool(_idleAllFilesLegacy);", body)
        self.assertLess(body.index("SettingsDefaults.Chooser(_plugin, _idlePoolJson);"), body.index("_plugin.RegisterBool(_idleAllFilesLegacy);"))
        self.assertIn('public const string LegacyToggleName = "Idle poses from all pose files";', src("IdlePoses.cs"))
        migrate = method_body(body, "private void MigrateIdlePool(bool allFiles)")
        self.assertIn("if (!allFiles || _idlePoolJson == null) return;", migrate)
        self.assertIn("_idlePoolJson.val = IdlePoolMode.AllLabel;", migrate)
        keep = method_body(body, "private void MaintainLegacyPool(float dt)")
        self.assertIn("_legacyPoolSeconds -= dt;", keep)
        self.assertLess(body.index("MaintainLegacyPool(dt);"), body.index("if (DollmasterOwns)\n            {\n                UpdateSceneState(speaking);"))

    def test_unknown_menu_value_is_repaired(self):
        changed = method_body(src("Body.cs"), "private void OnIdlePoolChanged(string value)")
        self.assertIn("_poolDirty = true;", changed)
        self.assertIn("if (_idlePoolJson != null && !IdlePoolMode.IsLabel(value)) _idlePoolJson.val = IdlePoolMode.Normalize(value);", changed)

    def test_config_write_and_read(self):
        body = src("Body.cs")
        self.assertIn('body["idle_pose_pool"] = IdlePoolMode.KeyOf(_idlePoolJson.val);', body)
        self.assertNotIn('body["idle_poses_all_files"]', body, "the old key is no longer written")
        apply = method_body(body, "public void ApplySettings(JSONClass root)")
        new = apply.index('if (Protocol.Has(body, "idle_pose_pool"))')
        old = apply.index('else if (Protocol.Has(body, "idle_poses_all_files"))')
        self.assertLess(new, old, "the new key wins")
        self.assertIn("IdlePoolMode.LabelOfKey(", apply)
        self.assertIn("IdlePoolMode.LabelOfLegacy(Protocol.GetBool(body, \"idle_poses_all_files\", false))", apply)

    def test_info_text_names_the_pool(self):
        info = method_body(src("Body.cs"), "private string IdlePosesInfo()")
        self.assertIn("IdlePoolMode.Describe(", info)
        self.assertNotIn("<b>Idle poses from all pose files</b>", src("Body.cs"))

    def test_no_idleposer_comes_back(self):
        for f in SRC.glob("*.cs"):
            self.assertNotRegex(f.read_text(encoding="utf-8"), r"IdlePoserLink|IdleMovement\b|AIBODY_IDLEPOSER", f.name)

    def test_two_entries_stay_a_popup_under_the_v65_rule(self):
        self.assertEqual(len(re.findall(r"public const string (?:Aibody|All)Label", src("IdlePoses.cs"))), 2)
        self.assertIn("public const int DropdownMin = 2;", src("UiHelper.cs"))


@unittest.skipUnless(Path(v35.DOTNET).exists(), "dotnet SDK not installed")
class IdlePoolHarnessTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        shutil.copy(HARNESS, folder / "Program.cs")
        (folder / "Harness.csproj").write_text(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType><Nullable>disable</Nullable>
  <EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup>
  <ItemGroup><Compile Include="Program.cs" /><Compile Include="{SRC / 'IdlePoses.cs'}" /><Compile Include="{SRC / 'PoseVocabulary.cs'}" /></ItemGroup>
</Project>""", encoding="utf-8")
        result = subprocess.run([v35.DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder,
                                capture_output=True, text=True, timeout=240,
                                env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
        if result.returncode != 0:
            raise AssertionError("harness build failed:\n" + result.stdout + result.stderr)
        cls.exe = folder / "out" / "Harness.dll"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cmds(self, *cmds):
        proc = subprocess.run([v35.DOTNET, str(self.exe)], input="".join(c + "\n" for c in cmds),
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.splitlines()

    def test_labels_and_constants(self):
        labels, consts = self.run_cmds("labels", "constants")
        self.assertEqual(labels.split("\t"), [AIBODY, ALL])
        self.assertEqual(consts.split("\t"), [AIBODY, "Idle pose pool", "Idle poses from all pose files"])

    def test_normalize_unknown_empty_zero_are_the_default(self):
        out = self.run_cmds(*("normalize\t" + v for v in (AIBODY, ALL, "all", "aibody", "", "0", "foo", "all pose files", "None")))
        self.assertEqual(out, [AIBODY, ALL, ALL, AIBODY, AIBODY, AIBODY, AIBODY, AIBODY, AIBODY])

    def test_key_mapping_round_trips(self):
        out = self.run_cmds("keyof\t" + AIBODY, "keyof\t" + ALL, "keyof\tfoo", "labelofkey\taibody", "labelofkey\tall",
                            "labelofkey\tfoo", "labelofkey\t", "labelofkey\t0")
        self.assertEqual(out, ["aibody", "all", "aibody", AIBODY, ALL, AIBODY, AIBODY, AIBODY])

    def test_legacy_boolean_maps(self):
        self.assertEqual(self.run_cmds("legacy\ttrue", "legacy\tfalse"), [ALL, AIBODY])

    def test_is_label_and_is_all(self):
        out = self.run_cmds("islabel\t" + AIBODY, "islabel\t" + ALL, "islabel\tall", "islabel\t", "isall\t" + ALL, "isall\t" + AIBODY, "isall\tall")
        self.assertEqual(out, ["1", "1", "0", "0", "1", "0", "0"])

    def test_info_sentence_explains_both_pools(self):
        a, b = self.run_cmds("describe\t" + AIBODY, "describe\t" + ALL)
        for text in (a, b):
            self.assertIn("Idle pose pool", text)
            self.assertIn("gestures.json poses", text)
            self.assertIn("pose commands", text)
            self.assertIn("Idle default pose", text)
        self.assertIn("Custom/Atom/Person/Pose/AIBody", a)
        self.assertIn("other packages", a)
        self.assertIn("every pose file of your library, including other packages", b)
        self.assertNotIn("Custom/Atom/Person/Pose/AIBody", b)
