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


def code(text: str) -> str:
    """C# without // comments (the menu code keeps comments that name the removed controls)."""
    return re.sub(r"//[^\n]*", "", text)


class VersionTests(TestCase):
    def test_version_66_everywhere(self):
        """Historical: version 66 sources are gone after the v67 bump; consistency is test_version67."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version67.py").is_file())
        self.assertIn("(version 66, release; on top of v65)", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))

    def test_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
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
        notes = (ROOT / "docs" / "RELEASE_NOTES_V66.md").read_text(encoding="utf-8")
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
        self.assertEqual(body.count("IdlePoolNames(IdleAllFiles)"), 5)
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


class IdleIntervalFloorTests(TestCase):
    """Version 66 (Don 20:31): the idle pose interval goes down to 5 s (30 s in v51-v65)."""

    def test_floor_is_5_everywhere(self):
        sched = src("IdlePoses.cs")
        self.assertIn("public const float LowestSeconds = 5f;", sched)
        self.assertNotIn("LowestSeconds = 30f", sched)
        self.assertIn("public const float DefaultIntervalSeconds = 30f;", sched)   # back to 30 s (165 s in v59-v65)
        self.assertIn("public const float HighestSeconds = 18000f;", sched)
        self.assertEqual(settings_file.RANGES[("body", "idle_pose_interval_s")], (5.0, 18000.0))
        self.assertEqual(settings_file.DEFAULTS["body"]["idle_pose_interval_s"], 30.0)
        schema = json.loads((ROOT / "protocol" / "schema" / "config.schema.json").read_text(encoding="utf-8"))
        node = schema["properties"]["body"]["properties"]["idle_pose_interval_s"]
        bounds = [a for a in node["anyOf"] if a.get("type") == "number"][0]
        self.assertEqual((bounds["minimum"], bounds["maximum"]), (5.0, 18000.0))
        self.assertIn("range 5 to 18000 s", src("Body.cs"))
        self.assertIn("range 5-18000 = 300 min", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))

    def test_companion_clamps_to_5_and_keeps_5(self):
        for given, want in ((5, 5.0), (4.9, 5.0), (0, 5.0), (7.5, 7.5), (165, 165.0), (18000, 18000.0), (99999, 18000.0)):
            data, _ = settings_file.validate({"body": {"idle_pose_interval_s": given}})
            self.assertEqual(data["body"]["idle_pose_interval_s"], want, given)
        data, _ = settings_file.validate({"body": {"idle_pose_min_s": 1, "idle_pose_max_s": 2}})
        self.assertEqual(data["body"]["idle_pose_interval_s"], 5.0, "an old min / max pair is clamped to the new floor")
        data, _ = settings_file.validate({"body": {"idle_pose_min_s": 6, "idle_pose_max_s": 10}})
        self.assertEqual(data["body"]["idle_pose_interval_s"], 8.0)

    def test_shortest_wait_is_longer_than_the_pose_guard_window(self):
        """5 s +/- 25 % is 3.75-6.25 s: longer than PoseGuard.MinSeconds (1.5 s) and the 1 s check; the guard can run up to
        MaxSeconds (5 s) only while the body keeps moving, and a change that starts then keeps the first capture."""
        sched, pose = src("IdlePoses.cs"), src("PoseController.cs")
        lowest = float(re.search(r"LowestSeconds = ([\d.]+)f", sched).group(1))
        jitter = float(re.search(r"Jitter = ([\d.]+)f", sched).group(1))
        settle = float(re.search(r"SettleSeconds = ([\d.]+)f", pose).group(1))
        guard_min = settle + 0.5
        guard_max = float(re.search(r"public const float MaxSeconds = ([\d.]+)f;", pose).group(1))
        self.assertEqual((lowest * (1 - jitter), lowest * (1 + jitter)), (3.75, 6.25))
        self.assertGreater(lowest * (1 - jitter), guard_min)
        self.assertGreater(lowest * (1 - jitter), settle)
        self.assertLessEqual(guard_max, lowest * (1 + jitter) - 1.0, "the guard is over before the longest wait is")
        self.assertIn("keeps the first capture", pose)
        self.assertNotIn("CooldownSeconds", code(sched), "version 66: no lockout after a manual pose")
        self.assertNotIn("_cooldown", code(sched))

    def test_idle_scheduler_waits_never_starve_or_overlap(self):
        """The quiet time restarts at every pick and with speech; the next pick is never earlier than the shortest wait."""
        sched = src("IdlePoses.cs")
        update = method_body(sched, "public string Update(float dt, bool busy, bool bodyControl, PoseVocabulary vocabulary, List<string> poolNames, List<string> allNames)")
        self.assertIn("_quiet = 0f;\n            PlanNext();\n            return PickNow(", update)
        self.assertIn("if (busy) { _quiet = 0f;", update)
        self.assertIn("if (_quiet < _next)", update)

    def test_docs_and_notes_name_the_floor_and_the_jitter(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_V66.md").read_text(encoding="utf-8")
        for part in ("Shorter idle pose interval", "down to 5 s", "3.75 to 6.25 s", "120 s"):
            self.assertIn(part, notes)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("**Idle pose interval minimum 5 s**", spec)
        self.assertIn("PoseGuard", spec)
        self.assertIn("3.75-6.25 s", (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8"))
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("8. Set **Idle pose interval (s)** to 5", proto)


class ExpressionGestureMenuRemovedTests(TestCase):
    """Version 66 (Don 20:34 / 20:36): every expression / gesture entry is gone from the plugin menu; the AI path stays."""

    def test_menu_entries_are_gone(self):
        body = src("Body.cs")
        tab = code(method_body(body, "public void BuildCharacterTab(UiPage page)"))
        body = code(body)
        for gone in ("Expression and gesture", "Show expression", "Reset expression", "Play gesture", "_expressionChoiceJson",
                     "_gestureChoiceJson", "ShowChosenExpression", "PlayChosenGesture"):
            self.assertNotIn(gone, tab, gone)
        for gone in ('new JSONStorableStringChooser("Expression"', 'new JSONStorableStringChooser("Gesture"',
                     "ShowChosenExpression", "PlayChosenGesture", "_expressionChoiceJson", "_gestureChoiceJson",
                     "private static void SetMenu(", "ExpressionHelp", "ExpressionsNote",
                     'JSONStorableAction("Reset expression"', 'text += "Expression: "'):
            self.assertNotIn(gone, body, gone)
        self.assertNotIn("expressions.json reloaded", src("AIBody.cs"))
        self.assertLess(tab.index("page.Slider(_breathDepthJson);"), tab.index('"<b>Poses</b>"'))

    def test_no_expression_or_gesture_line_in_info_selftest_and_status(self):
        body = src("Body.cs")
        info = code(method_body(body, "public string CharacterInfoText()"))
        self.assertNotRegex(info, r"(?i)expression|gesture\b")
        selftest = code(method_body(body, "public string SelfTestText()"))
        self.assertNotRegex(selftest, r"(?i)expression|gesture|timeline")
        self.assertIn('t["expression_morphs_found"]', body, "the values stay in SelfTestJson")
        for f in ("Body.cs", "AIBody.cs", "AppLink.cs", "MicConfig.cs", "CharacterWizard.cs"):
            for m in re.finditer(r'page\.(?:Button|Header|Toggle|Slider|Popup|ScrollablePopup)\(([^;]*)\)', code(src(f))):
                if '"Reload poses"' in m.group(1):
                    continue   # the Poses section is unchanged (the button reloads gestures.json, which holds poses)
                self.assertNotRegex(m.group(1), r"(?i)expression|gesture", f + ": " + m.group(0))

    def test_poses_section_is_unchanged(self):
        tab = method_body(src("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        for part in ('page.Header("<b>Poses</b>");', "page.ScrollablePopup(_poseCommandChoiceJson);", 'page.Button("Apply Pose", ApplyPoseCommandNow);',
                     'page.Button("Add Pose", StartAddPose);', 'page.Button("Reload poses"'):
            self.assertIn(part, tab, part)

    def test_ai_path_stays(self):
        router = src("CommandRouter.cs")
        self.assertIn('Protocol.Has(msg, "expression") && BodyOn && _expressions != null', router)
        self.assertIn("_expressions.SetExpression(Protocol.GetString(msg, \"expression\", \"\"),", router)
        self.assertIn('public const string CmdExpression = "expression";', src("Protocol.cs"))
        self.assertIn('public const string CmdGesture = "gesture";', src("Protocol.cs"))
        body = src("Body.cs")
        self.assertIn("_expressions.OnShowingChanged = PauseAutoExpressions;", body)
        self.assertIn('JSONStorableAction("Expression: " + expression', body)
        self.assertIn('JSONStorableAction("Gesture: " + gesture', body)
        self.assertIn('JSONStorableAction("Reload config files", ReloadConfigFiles)', body)
        self.assertIn("ReloadExpressions();", method_body(body, "public void ReloadConfigFiles()"))
        self.assertIn("ReloadGestures();", method_body(body, "public void ReloadConfigFiles()"))
        idle = src("IdleController.cs")
        for g in ("nod", "shake", "tilt"):
            self.assertIn(f'"{g}"', idle)
        self.assertIn("public string PlayGesture(", src("PoseController.cs"))
        self.assertIn("public bool SetExpression(", src("ExpressionController.cs"))
        self.assertIn("public IEnumerable<string> PresetNames", src("ExpressionController.cs"))

    def test_old_scene_and_config_load_without_errors(self):
        """The removed controls never stored a value: no scene storable (the choosers were not registered) and no config key."""
        scene = (ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8")
        for gone in ('"Expression"', '"Gesture"', "Reset expression"):
            self.assertNotIn(gone, scene)
        body = src("Body.cs")
        self.assertNotIn("RegisterStringChooser(_expressionChoiceJson", body)
        defaults = settings_file.defaults()
        for key in defaults["body"]:
            self.assertNotRegex(key, r"(?i)expression|gesture_choice|show_expression")
        old = {"body": {"expression": "happy", "gesture": "nod", "show_expression": True, "idle_poses": True}}
        data, errors = settings_file.validate(old)
        self.assertIs(data["body"]["idle_poses"], True)
        self.assertEqual(len(errors), 3, "unknown keys are reported as problems, never raised; nothing was ever written")
        # a real v65 config.json (example) loads clean, and the AI's keys stay
        data, errors = settings_file.validate(json.loads((ROOT / "examples" / "config.json").read_text(encoding="utf-8")))
        self.assertEqual(errors, [])
        self.assertIn("gestures", data["ai"]["emotion"])
        self.assertIn("keywords", data["ai"]["emotion"])
        self.assertEqual(data["connection"]["paths"]["expressions"], "Saves/PluginData/AIBody/expressions.json")
        self.assertEqual(data["connection"]["paths"]["gestures"], "Saves/PluginData/AIBody/gestures.json")

    def test_docs_and_notes(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_V66.md").read_text(encoding="utf-8")
        for part in ("Expression and gesture controls removed from the menu", "Reset expression",
                     "Nothing changes for the AI"):
            self.assertIn(part, notes)
        proto = (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("9. Tab AI Character has no section *Expression and gesture*", proto)
        self.assertIn("obsolete since version 66", proto)
        self.assertIn("**Manual expression and gesture UI removed**", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
        self.assertNotIn("`Reset expression`,", (ROOT / "README.md").read_text(encoding="utf-8"))
