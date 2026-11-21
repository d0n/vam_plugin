"""Fixes after Leon's v38 test (call 21.11.2026 16:06), on main without a new version yet:

1. Companion console noise: the start hint and the test-tone wait line go to the VaM log once per VaM session; while
   the app is not connected at most ONE test-tone request waits; a double-click starter companion/start_companion.bat.
2. Character wizard: the stored answers rebuild the section when they change from outside the buttons
   (scene restore after Init, Reload Config JSON, config.json seed).
3. Persona menu: the app writes the starter personas Anna and Marc once into an empty personas folder (before, they
   existed only in the repository, so the menu had only "(none)"); an empty persona_name means "(none)".
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest import TestCase

from aibody_companion import personas

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def method_body(text: str, signature: str) -> str:
    start = text.index(signature)
    depth, i = 0, text.index("{", start)
    begin = i
    while True:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[begin:i + 1]
        i += 1


class ConsoleNoiseTests(TestCase):
    def test_start_hint_once_per_session_and_names_the_starter(self):
        mic = source("MicConfig.cs")
        self.assertIn("private static bool _startHintLogged;", mic)
        self.assertIn("start 'AIBody Companion' from the Windows Start menu", mic)
        self.assertNotIn("python -m", mic)
        self.assertEqual(mic.count("Log.Info("), 1)

    def test_one_pending_test_tone_and_one_log_line(self):
        link = source("AppLink.cs")
        self.assertIn("private static bool _testToneWaitLogged;", link)
        body = method_body(link, "public void RequestTestTone()")
        pending = body.index("if (_testTonePending)")
        self.assertLess(pending, body.index("_testTonePending = true;"))
        self.assertIn("already waiting for the companion app", body)
        self.assertEqual(body.count("Log.Info("), 1)
        self.assertIn("if (!_testToneWaitLogged)", body)
        self.assertNotIn("SuperController.LogError", body)
        self.assertNotIn("Log.Error", body)

    def test_windows_starter(self):
        bat = (ROOT / "companion" / "start_companion.bat").read_bytes()
        self.assertIn(b"\r\n", bat)
        self.assertNotIn(b"\n", bat.replace(b"\r\n", b""), "CRLF line endings only")
        text = bat.decode("ascii")
        self.assertIn('-m aibody_companion --vam-root "%VAMROOT%"', text)
        self.assertIn("vam_root.txt", text)
        self.assertIn("AddonPackages", text)
        self.assertIn("pause", text)
        self.assertIn("companion/vam_root.txt", (ROOT / ".gitignore").read_text())
        self.assertIn("*.bat text eol=crlf", (ROOT / ".gitattributes").read_text())
        self.assertIn("start_companion.bat", (ROOT / "README.md").read_text(encoding="utf-8"))


class WizardRefreshTests(TestCase):
    def test_answers_rebuild_the_section(self):
        cs = source("CharacterWizard.cs")
        self.assertIn("new JSONStorableBool(AskedName, false, (bool v) => RequestTabRebuild())", cs)
        self.assertIn("new JSONStorableBool(WantedName, false, (bool v) => RequestTabRebuild())", cs)
        self.assertNotIn("(bool v) => { }", cs)
        body = source("Body.cs")
        self.assertIn("Characters.RequestRebuild = () => { RebuildTab = true; };", body)
        self.assertLess(body.index("Characters.RequestRebuild ="), body.index("Characters.CreateStorables();"))
        self.assertIn("if (_tab == 1) ShowTab(_tab);", source("AIBody.cs"))

    def test_gate_answer_is_per_scene_not_from_config_json(self):
        """Root cause of "no question at all": the global config.json seeded the gate answer into every new scene."""
        cs = source("CharacterWizard.cs")
        apply = method_body(cs, "public void ApplySettings(JSONClass root)")
        self.assertNotIn('"setup_answered"', apply)
        self.assertNotIn('"setup_wanted"', apply)
        self.assertNotIn("_askedJson.val", apply)
        self.assertNotIn("_wantedJson.val", apply)
        self.assertIn('ApplyRecordedGender(_aiGenderJson', apply)
        write = method_body(cs, "public void WriteSettings(JSONClass root)")
        self.assertIn('characters["setup_answered"]', write)

    def test_question_stands_above_its_buttons(self):
        build = method_body(source("CharacterWizard.cs"), "public void Build(UiPage page)")
        gate = method_body(build, "if (stage == 0)")
        self.assertLess(gate.index("page.Header(GateQuestion);"), gate.index('page.Button("Yes", OnYes)'))

    def test_stage_logic(self):
        cs = source("CharacterWizard.cs")
        stage = method_body(cs, "public static int Stage(bool answered, bool wanted)")
        # mirror of the C# rule: not answered -> gate, answered + wanted -> steps, answered + skipped -> reopen button
        def py_stage(answered: bool, wanted: bool) -> int:
            return 0 if not answered else (2 if wanted else 1)
        self.assertIn("if (!answered) return 0;", stage)
        self.assertIn("return wanted ? 2 : 1;", stage)
        self.assertEqual([py_stage(a, w) for a in (False, True) for w in (False, True)], [0, 0, 1, 2])
        build = method_body(cs, "public void Build(UiPage page)")
        self.assertIn("int stage = Stage(", build)


class PersonaTests(TestCase):
    def test_starters_match_the_examples(self):
        for name, data in personas.STARTER_PERSONAS.items():
            example = json.loads((ROOT / "examples" / "personas" / name / "persona.json").read_text(encoding="utf-8"))
            self.assertEqual(data, example)
            persona, problems = personas.parse_persona(name, data)
            self.assertIsNotNone(persona)
            self.assertEqual(problems, [])

    def test_seed_once_into_an_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Saves" / "PluginData" / "AIBody" / "personas"
            self.assertEqual(personas.seed_starter_personas(root), ["Anna", "Marc"])
            store = personas.PersonaStore(root)
            self.assertEqual(store.names(), ["Anna", "Marc"])
            persona, problems = store.load("Anna")
            self.assertIsNotNone(persona)
            self.assertEqual(problems, [])
            # deleted starters do not come back
            (root / "Marc" / "persona.json").unlink()
            (root / "Marc").rmdir()
            self.assertEqual(personas.seed_starter_personas(root), [])
            self.assertEqual(store.names(), ["Anna"])

    def test_existing_personas_are_never_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Mine").mkdir()
            (root / "Mine" / "persona.json").write_text('{"name": "Mine", "prompt": "x"}', encoding="utf-8")
            self.assertEqual(personas.seed_starter_personas(root), [])
            self.assertEqual(personas.PersonaStore(root).names(), ["Mine"])

    def test_cli_seeds_on_start(self):
        cli = (ROOT / "companion" / "aibody_companion" / "cli.py").read_text(encoding="utf-8")
        self.assertIn("personas_module.seed_starter_personas(", cli)

    def test_plugin_empty_persona_is_none(self):
        link = source("AppLink.cs")
        self.assertIn("if (string.IsNullOrEmpty(name)) name = PersonaNone;", method_body(link, "private void SetPersona(string name)"))
        refresh = method_body(link, "private void RefreshPersonaChoices()")
        self.assertIn("if (string.IsNullOrEmpty(_personaJson.val)) _personaJson.val = PersonaNone;", refresh)
        self.assertIn("_personaJson.popupOpenCallback = RefreshPersonaChoices;", link)
        self.assertIn("the list comes from the app", link)
