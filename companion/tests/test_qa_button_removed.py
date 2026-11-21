"""Leon, call 21.11.2026 15:59 (version 39): the button "Question and Answer" is removed from the plugin menu.

Answering questions is simply what the character does while "Proactive talking" is off; the button's side effect
(switching Body control off) disappears with it, Body control itself is untouched. The button never had a storable,
so scenes saved with older versions hold nothing for it and still load; AI mode 'qa' stays a valid mode.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import settings_file

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def all_cs() -> str:
    return "".join(p.read_text(encoding="utf-8") for p in sorted(SRC.glob("*.cs")))


class QaButtonRemovedTests(TestCase):
    def test_button_and_handlers_are_gone(self):
        cs = all_cs()
        for name in ("QaButtonLabel", "EnableSimpleQa", "SetSimpleQa", "_simpleQa", "Question\\n& Answer",
                     "SetBodyControl("):
            self.assertNotIn(name, cs)
        self.assertNotRegex(cs, r'Button\("Question')

    def test_voice_tab_ai_section_starts_with_the_ai_controls(self):
        plugin = source("AIBody.cs")
        start = plugin.index('_page.Header("<b>AI</b>");')
        nxt = plugin[start:].split("\n")[1]
        self.assertIn("BuildAiSection(_page)", nxt)

    def test_proactive_toggle_and_ai_mode_stay(self):
        link = source("AppLink.cs")
        self.assertIn('new JSONStorableBool("Proactive talking", true,', link)
        self.assertIn('new JSONStorableStringChooser("AI mode", new List<string> { ModeQa, "auto", "realtime", "chain" },', link)
        ai = link[link.index("public void BuildAiSection(UiPage page)"):]
        self.assertIn("page.Toggle(_proactiveJson);", ai)
        self.assertEqual(settings_file.DEFAULTS["ai"]["mode"], "qa")
        data, errors = settings_file.validate({"ai": {"mode": "qa"}})
        self.assertEqual(data["ai"]["mode"], "qa")
        self.assertFalse([e for e in errors if "mode" in str(e)])

    def test_left_info_explains_it_in_prose_with_bold_labels(self):
        link = source("AppLink.cs")
        self.assertIn("There is no separate Question and Answer button: ", link)
        self.assertIn("with <b>Proactive talking</b> off the character only speaks when you ask it something, "
                      "and <b>Body control</b> stays as you set it.", link)

    def test_no_storable_ever_held_the_button(self):
        """Older scenes keep loading: there is no storable named after the button, in the code or the shipped scene."""
        cs = all_cs()
        self.assertFalse(re.findall(r'new JSONStorable\w+\("(Question[^"]*|Simple Q&A[^"]*)"', cs))
        scene = json.loads((ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8"))
        text = json.dumps(scene)
        self.assertNotIn("Question and Answer", text)
        self.assertNotIn("Simple Q&A", text)

    def test_docs_updated(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn('**Question and Answer** (button, two lines', readme)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertNotIn("only the button Question and Answer switches it off on purpose", spec)
        self.assertIn("## T47", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
