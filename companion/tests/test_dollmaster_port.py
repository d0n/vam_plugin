"""Tab Dollmaster (Don, 22.11.2026): the old Dollmaster plugin (VAMDeluxe, MIT; Don's copy in third_party/dollmaster)
ported into AIBody - full port, nothing dropped, behaviour identical; rewritten only where the project rules need it
(one .cslist / one MVRScript / one namespace, no .Keys/.Values, file access only through FileManagerSecure). Checkbox
"Activate" at the top of the tab, off by default: off = nothing of Dollmaster runs. While active Dollmaster owns the body
of the AI character; AIBody keeps speech (and owns the head audio)."""
from __future__ import annotations

import difflib
import importlib.util
import re
import sys
import unittest
import zipfile
from pathlib import Path

from tests.test_plugin_menu import method_body

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
ORIGINAL = ROOT / "third_party" / "dollmaster" / "src"
ASSETS = ROOT / "assets" / "dollmaster"
STUBS = ROOT / "tools" / "stubs" / "DollmasterStubs.cs"


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PORT = load_tool("port_dollmaster")


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class CompletenessTests(unittest.TestCase):
    def test_every_original_file_is_ported_and_listed(self):
        originals = sorted(f.name for f in ORIGINAL.glob("*.cs"))
        self.assertEqual(len(originals), 25)
        cslist = (SRC / "AIBody.cslist").read_text(encoding="utf-8").split()
        old_cslist = (ROOT / "third_party" / "dollmaster" / "ADD_ME.cslist").read_text(encoding="utf-8").split()
        self.assertEqual(sorted(Path(x).name for x in old_cslist), originals)
        for name in originals:
            ported = PORT.ported_name(name)
            self.assertTrue((SRC / ported).is_file(), ported)
            self.assertIn(ported, cslist)
            self.assertIn("namespace AIBody", source(ported))
        self.assertNotIn("namespace DeluxePlugin", "".join(source(PORT.ported_name(n)) for n in originals))

    def test_every_difference_to_the_original_is_marked(self):
        """Apart from DmPlugin (the old MVRScript, now run by AIBodyPlugin), each ported file is the original with the
        mechanical renames; every other change carries "AIBody port" in the changed lines or right next to them."""
        unmarked = []
        for f in sorted(ORIGINAL.glob("*.cs")):
            name = PORT.ported_name(f.name)
            if name == "DmPlugin.cs":
                continue
            expected = PORT.port_text(f.read_text(encoding="utf-8-sig")).split("\n")
            actual = source(name).split("\n")
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, expected, actual, autojunk=False).get_opcodes():
                if tag == "equal":
                    continue
                window = "\n".join(actual[max(0, j1 - 3):j2 + 3])
                if "AIBody port" not in window:
                    unmarked.append(f"{name}:{j1 + 1}: {expected[i1:i2]} -> {actual[j1:j2]}")
        self.assertEqual(unmarked, [])

    def test_labels_and_storable_names_are_the_old_ones(self):
        for f in sorted(ORIGINAL.glob("*.cs")):
            old = f.read_text(encoding="utf-8-sig")
            new = source(PORT.ported_name(f.name))
            for literal in set(re.findall(r'new JSONStorable\w+\("([^"]+)"', old)):
                self.assertIn(f'"{literal}"', new, f"{f.name}: {literal}")
            for label in set(re.findall(r'\.label = "([^"]+)"', old)) | set(re.findall(r'CreateButton\("([^"]+)"', old)):
                self.assertIn(f'"{label}"', new, f"{f.name}: {label}")

    def test_old_plugin_methods_are_all_there(self):
        dm = source("DmPlugin.cs")
        old = PORT.rename((ORIGINAL / "Dollmaster.cs").read_text(encoding="utf-8-sig"))
        for sig in ("void RegisterActions()", "public void SetPersonality(string name)", "public void PlayAudio(NamedAudioClip clip)",
                    "public void TriggerExpression()", "public void ForcePlayExpression()", "public void TriggerClimax()",
                    "public static NamedAudioClip LoadAudio(string path)", "protected void HandleRename(string oldId, string newId)",
                    "public static Atom GetSomeoneElse(Atom notThisPerson)", "public void Init()", "public void Update()",
                    "public void LateUpdate()", "public void OnDestroy()", "public void PostRestore()"):
            self.assertIn(sig, dm)
        # unchanged bodies
        for sig in ("public void TriggerExpression()", "public void ForcePlayExpression()", "public void TriggerClimax()",
                    "public static NamedAudioClip LoadAudio(string path)", "protected void HandleRename(string oldId, string newId)",
                    "public static Atom GetSomeoneElse(Atom notThisPerson)"):
            self.assertEqual(method_body(dm, sig), method_body(old, sig), sig)
        # the modules in the old order
        init = method_body(dm, "public void Init()")
        order = ["RegisterActions();", "new DmUI(host, 0.001f)", "new DmConfig(this)", "new DmPersonas(this)",
                 "new DmPluginState(this)", "new DmArousal(this)", "new DmExpressions(this)", "new DmExpressionController(this)",
                 "new DmSFXController(this)", "new DmThrustController(this)", "new DmThrustAutoController(this)",
                 "new DmBreathController(this)", "new DmHeadController(this)", "new DmPoseController(this)",
                 "new DmMontageController(this, poseController)", "new DmDressController(this)", "new DmClimaxController(this)",
                 "new DmKissController(this)", "new DmTopButtons(this)", "CreateSpacer().height = 200;"]
        positions = [init.index(x) for x in order]
        self.assertEqual(positions, sorted(positions))


class ProjectRuleTests(unittest.TestCase):
    def test_no_dictionary_keys_values_and_files_only_through_file_manager_secure(self):
        for f in SRC.glob("Dm*.cs"):
            code = "\n".join(l for l in f.read_text(encoding="utf-8").split("\n") if not l.strip().startswith("//"))
            for banned in (".Keys", ".Values", "ReadFileIntoString", "GetFilesAtPath", "GetDirectoriesAtPath",
                           "currentSaveDir =", ": MVRScript", "System.IO"):
                self.assertNotIn(banned, code, f"{f.name}: {banned}")
        for name in ("DmConfig.cs", "DmExpressions.cs", "DmExpressionGroup.cs", "DmMontage.cs", "DmPersonality.cs", "DmTopButtons.cs"):
            self.assertIn("FileManagerSecure.ReadAllText(", source(name))
        self.assertIn("FileManagerSecure.GetDirectories(PERSONA_PATH)", source("DmPersonas.cs"))

    def test_stubs_name_their_evidence(self):
        lines = [l for l in STUBS.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.lstrip().startswith(("//", "#", "using", "namespace", "{", "}"))]
        missing = [l for l in lines if "// E39" not in l]
        self.assertEqual(missing, [])
        self.assertIn("DollmasterStubs.cs", (ROOT / "tools" / "check_plugin.py").read_text(encoding="utf-8"))

    def test_storable_names_do_not_clash_with_aibody(self):
        dm = set()
        for f in SRC.glob("Dm*.cs"):
            dm |= set(re.findall(r'new JSONStorable\w+\("([^"]+)"', f.read_text(encoding="utf-8")))
        own = set()
        for f in SRC.glob("*.cs"):
            if not f.name.startswith("Dm"):
                own |= set(re.findall(r'new JSONStorable\w+\("([^"]+)"', f.read_text(encoding="utf-8")))
        self.assertEqual(dm & own, set())


class ActivateTests(unittest.TestCase):
    def test_checkbox_off_by_default_and_saved_with_the_scene(self):
        plugin = source("AIBody.cs")
        self.assertIn('public const string DollmasterActivateName = "Activate";', plugin)
        self.assertIn("new JSONStorableBool(DollmasterActivateName, false,", plugin)
        self.assertIn("RegisterBool(_dmActivateJson);", plugin)
        create = method_body(plugin, "private void CreateDollmaster()")
        # the checkbox is the first control of the tab: made before Dollmaster's own controls
        self.assertLess(create.index("CreateToggle(_dmActivateJson, true)"), create.index("_dm.Init();"))
        self.assertIn("_dm.SetActive(_dmActivateJson.val);", create)

    def test_off_means_nothing_runs(self):
        dm = source("DmPlugin.cs")
        for sig in ("public void Update()", "public void LateUpdate()"):
            self.assertIn("if (!Active || !Started) return;", method_body(dm, sig))
        self.assertIn("ui.canvas.enabled = false;", method_body(dm, "public void Init()"))
        # helper atoms only while active; made again at the next activation
        for name in ("DmSFXController.cs", "DmThrustController.cs", "DmWorldUI.cs"):
            self.assertNotIn("StartCoroutine(CreateAtom(", source(name))
            self.assertIn("dm.MakeAtom(", source(name))
        self.assertIn("if (Active) host.StartCoroutine(maker());", method_body(dm, "public void MakeAtom(string key, Func<IEnumerator> maker)"))
        on = method_body(dm, "private void OnActivated()")
        for part in ('SetFloatParamValue("volumeTriggerMultiplier", 0)', "_atomMakers[i]()", "personality.Load()",
                     "config.Apply()", "sfxController.LoadClips()", "montageController.LoadMontagesFromPath("):
            self.assertIn(part, on)
        off = method_body(dm, "private void OnDeactivated()")
        for part in ("module.OnDestroy()", "personality.Unload()", '"blinkEnabled", true', "_savedVolumeTriggerMultiplier",
                     "currentLookMode = _savedLookMode"):
            self.assertIn(part, off)
        # the constructors no longer change the scene
        self.assertNotIn("            Apply();", method_body(source("DmConfig.cs"), "public DmConfig(DmPlugin dm)"))
        self.assertNotIn('dm.headAudioSource.SetFloatParamValue("volumeTriggerMultiplier", 0);',
                         "\n".join(l for l in source("DmExpressionController.cs").split("\n") if not l.strip().startswith("//")))
        self.assertIn("if (Active && personality != null) personality.Load();", method_body(dm, "public void SetPersonality(string name)"))
        for action in ("emotionTrigger", "climaxTrigger"):
            self.assertIn(f'new JSONStorableAction("{action}"', dm)
        self.assertEqual(dm.count("if (!Active) return;"), 2)

    def test_restore_hooks_are_forwarded(self):
        plugin = source("AIBody.cs")
        self.assertIn("public override void RestoreFromJSON(JSONClass jc, bool restorePhysical = true", plugin)
        self.assertIn("_dm.RestoreFromJSON(jc)", plugin)
        self.assertIn("_dm.PostRestore()", plugin)
        self.assertIn("_dm.RestoreLate(_restoredJson)", plugin)
        self.assertIn("dressController.OnRestore()", method_body(source("DmPlugin.cs"), "public void RestoreFromJSON(JSONClass jc)"))
        self.assertIn("_dm.OnDestroy()", method_body(plugin, "private void OnDestroy()"))
        self.assertIn("_dm.LateUpdate()", method_body(plugin, "private void LateUpdate()"))


class TabAndOwnershipTests(unittest.TestCase):
    def test_tab_between_client_character_and_config(self):
        plugin = source("AIBody.cs")
        self.assertIn('Tabs = { "Voice", "AI Character", "Client Character", "Dollmaster", "Config" };', plugin)
        self.assertIn("private const int DollmasterTab = 3;", plugin)
        self.assertIn("ShowDollmasterMenu(index == DollmasterTab);", method_body(plugin, "private void ShowTab(int index)"))

    def test_menu_in_the_right_column_and_only_on_its_tab(self):
        dm = source("DmPlugin.cs")
        for sig, call in (("public UIDynamicToggle CreateToggle(", "host.CreateToggle(p, true)"),
                          ("public UIDynamicSlider CreateSlider(", "host.CreateSlider(p, true)"),
                          ("public UIDynamicPopup CreatePopup(", "host.CreatePopup(p, true)"),
                          ("public UIDynamicButton CreateButton(", "host.CreateButton(label, true)"),
                          ("public UIDynamic CreateSpacer(", "host.CreateSpacer(true)")):
            body = dm[dm.index(sig):]
            self.assertIn(call, body[:body.index("}")])
        self.assertIn("SetActive(on)", method_body(dm, "private static void Show(Component c, bool on)"))

    def test_dollmaster_owns_the_body_while_active(self):
        body = source("Body.cs")
        self.assertIn("&& !DollmasterOwns; } }", body)   # BodyControl: no AI poses / gestures / expressions / idle poses
        update = method_body(body, "public void Update(float dt)")
        self.assertLess(update.index("if (DollmasterOwns)"), update.index("_expressions.Update(dt)"))
        self.assertLess(update.index("_speech.Update(dt)"), update.index("if (DollmasterOwns)"))   # speech keeps running
        self.assertIn("_body.DollmasterOwnsBody = () => _dm != null && _dm.Active;", source("AIBody.cs"))
        # AIBody's speech owns the head audio
        self.assertIn("if (HostSpeaking != null && HostSpeaking()) return;", method_body(source("DmPlugin.cs"), "public void PlayAudio(NamedAudioClip clip)"))

    def test_info_text_states_the_ownership(self):
        info = method_body(source("AIBody.cs"), "private string DollmasterInfoText()")
        for part in ("Activate", "off = nothing of it runs", "Dollmaster owns the body", "AIBody keeps speech",
                     "voice clips wait while the AI speaks"):
            self.assertIn(part, info.replace('"\n                + "', ""))


class PackageTests(unittest.TestCase):
    def test_assets_complete(self):
        files = [p for p in ASSETS.rglob("*") if p.is_file()]
        self.assertEqual(len(files), 488)
        names = {p.relative_to(ASSETS).as_posix() for p in files}
        self.assertIn("dollmaster_config.json", names)
        self.assertIn("Assets/Expressions/expression_manifest.json", names)
        self.assertEqual(len({n.split("/")[2] for n in names if n.startswith("Assets/Personas/")}), 18)
        self.assertTrue(any(n.startswith("Assets/VAMasutra/") and n.endswith(".json") for n in names))
        for rel in ("Assets/SFX/skin_1.wav", "Assets/SFX/Slide01.wav"):
            self.assertIn(rel, names)   # dollmaster_config.json sfxDefaults
        self.assertNotIn("config.json", {p.name for p in files})
        self.assertIn('"/dollmaster_config.json"', source("DmConfig.cs"))

    def test_var_ships_the_assets_next_to_the_plugin(self):
        build_var = load_tool("build_var")
        self.assertEqual(build_var.DOLLMASTER_FOLDER, "Dollmaster")
        self.assertIn('DollmasterFolder = "Dollmaster"', source("AIBody.cs"))
        version = int(__import__("json").loads((ROOT / "packaging" / "AIBody.json").read_text(encoding="utf-8"))["version"])
        var = ROOT / "dist" / f"d0n.AIBody.{version}.var"
        if not var.is_file():
            self.skipTest(f"{var.name} not built (python tools/build_var.py)")
        with zipfile.ZipFile(var) as z:
            names = set(z.namelist())
        if not any("/Dollmaster/" in n for n in names):
            self.skipTest(f"{var.name} was built before the Dollmaster tab")
        base = "Custom/Scripts/d0n/AIBody/Dollmaster/"
        for rel in ("dollmaster_config.json", "Assets/Expressions/expression_manifest.json", "Assets/SFX/skin_1.wav",
                    "Assets/Personas/Aiko/persona.json"):
            self.assertIn(base + rel, names)
        self.assertEqual(len([n for n in names if n.startswith(base)]), 488)

    def test_credits_and_license(self):
        self.assertIn("MIT License", (ROOT / "third_party" / "dollmaster" / "LICENSE").read_text(encoding="utf-8"))
        credits = (ROOT / "docs" / "CREDITS.md").read_text(encoding="utf-8")
        self.assertIn("Dollmaster", credits)
        self.assertIn("ported", credits)


if __name__ == "__main__":
    unittest.main()
