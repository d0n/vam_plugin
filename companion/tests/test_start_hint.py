"""Version 22: README section "Getting started", config.json key hint (ai.xai.key_hint), Windows-style VaM path examples."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aibody_companion import cli, settings_file
from tests.test_plugin_menu import source

ROOT = Path(__file__).resolve().parents[2]


class KeyHintTests(unittest.TestCase):
    def test_default_file_has_the_hint_with_the_three_ways(self):
        hint = settings_file.defaults()["ai"]["xai"]["key_hint"]
        for part in ("API key", "XAI API Token", "Voice > Companion connection", "API Reconnect", "XAI_API_KEY", "ai.xai.key_file"):
            self.assertIn(part, hint)
        self.assertEqual(hint, settings_file.KEY_HINT_TEXT)

    def test_hint_is_accepted_without_warnings_and_not_treated_as_a_key(self):
        data, errors = settings_file.validate({"ai": {"xai": {"key_hint": settings_file.KEY_HINT_TEXT}}})
        self.assertEqual(errors, [])
        self.assertEqual(data["ai"]["xai"]["key_hint"], settings_file.KEY_HINT_TEXT)
        data, errors = settings_file.validate({"ai": {"xai": {"key_hint": "my own note"}}})
        self.assertEqual((errors, data["ai"]["xai"]["key_hint"]), ([], "my own note"))
        data, errors = settings_file.validate(json.loads(json.dumps(settings_file.defaults())))
        self.assertEqual(errors, [])

    def test_written_default_and_existing_file_get_the_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            settings_file.write_defaults_if_missing(path)
            self.assertIn("key_hint", json.loads(path.read_text())["ai"]["xai"])
            old = json.loads(path.read_text())
            del old["ai"]["xai"]["key_hint"]
            old["ai"]["xai"]["key_file"] = "keys/xai.txt"
            path.write_text(json.dumps(old))
            added = settings_file.add_missing_companion_sections(path)
            self.assertIn("ai.xai.key_hint", added)
            after = json.loads(path.read_text())["ai"]["xai"]
            self.assertEqual(after["key_file"], "keys/xai.txt", "the user's value is kept")
            data, errors = settings_file.load(path)
            self.assertEqual(errors, [])

    def test_hint_is_not_redacted_pattern_bait_and_in_the_schema(self):
        from aibody_companion import logsetup

        self.assertEqual(logsetup.redact(settings_file.KEY_HINT_TEXT), settings_file.KEY_HINT_TEXT)
        schema = json.loads((ROOT / "protocol/schema/config.schema.json").read_text(encoding="utf-8"))
        prop = schema["properties"]["ai"]["properties"]["xai"]["properties"]["key_hint"]
        self.assertEqual(prop["type"], "string")
        self.assertIn("XAI API Token", prop["description"])
        example = json.loads((ROOT / "examples/config.json").read_text(encoding="utf-8"))
        self.assertEqual(example["ai"]["xai"]["key_hint"], settings_file.KEY_HINT_TEXT)

    def test_plugin_keeps_the_hint_when_it_writes_the_file(self):
        link = source("AppLink.cs")
        self.assertNotIn("key_hint", link, "the plugin neither reads nor writes it; it keeps everything else in 'ai'")


class WindowsPathExampleTests(unittest.TestCase):
    def test_cli_help_example(self):
        self.assertIn('e.g. "D:\\VaM"', cli.build_parser().format_help())

    def test_plugin_hints_show_the_windows_style_path(self):
        # Leon, 21.11.2026: the plugin points to the Start menu entry of the installed companion, no console command
        self.assertNotIn("--vam-root", source("MicConfig.cs"))
        # version 35 (Leon): the start command is no longer in the menu; it is logged once (MicConfig.StartHint)
        self.assertNotIn('--vam-root', source("AppLink.cs"))
        self.assertNotIn("--channel", source("AppLink.cs"))
        self.assertNotIn('--vam-root \\"<VaM>\\"', source("MicConfig.cs") + source("AppLink.cs"))

    def test_example_config_is_valid_json_with_an_escaped_backslash(self):
        data = json.loads((ROOT / "companion/config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(data["vam_root"], "D:\\VaM")


class ReadmeStartTests(unittest.TestCase):
    def test_starten_section_near_the_top(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("\n## Getting started\n", text)
        self.assertLess(text.index("## Getting started"), text.index("## 1. Purpose and use"))
        section = text[text.index("## Getting started"):text.index("## 1. Purpose and use")]
        for part in ('python -m aibody_companion --vam-root "D:\\VaM"', "started by hand", "separately from VaM",
                     "cd companion", "pip install -e .", "No module named aibody_companion",
                     "pip install sounddevice", "requirements.txt", "3.10", "git pull", "XAI API Token"):
            self.assertIn(part, section)

    def test_pyproject_allows_pip_install_e(self):
        # "readme = ../README.md" points outside the project folder; setuptools refuses that and
        # "pip install -e ." failed with it (found while writing version 22)
        self.assertNotIn("../README.md", (ROOT / "companion/pyproject.toml").read_text(encoding="utf-8"))

    def test_python_requirement_matches(self):
        self.assertIn('requires-python = ">=3.10"', (ROOT / "companion/pyproject.toml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
