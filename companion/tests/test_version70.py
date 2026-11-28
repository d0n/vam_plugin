"""Version 70 (28.11.2026, on top of v69): the in-game VaM log is silent unless Verbose is on; all Log.Info / Warn /
Error / Debug go through one helper; Dollmaster SuperController.Log* and Debug.Log* use that helper; a source test
forbids direct log calls outside Log.cs. Verbose voice-path diagnostics (output device, TTS/clip received, play
result, ai.driver). No voice-pipeline fix: SpeechPlayer is unchanged since v59. No enum."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

from .test_version68 import code, compiled_files

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"

LOG_CALL = re.compile(
    r"\b(?:SuperController\.Log(?:Message|Error|ErrorOnce)?|Debug\.Log(?:Warning|Error)?)\s*\("
)


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class VersionTests(TestCase):
    def test_version_70_everywhere(self):
        self.assertEqual(__version__, "70")
        self.assertIn('PluginVersion = "70"', src("AIBody.cs"))
        self.assertIn('version = "70"', (ROOT / "companion" / "pyproject.toml").read_text())
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 70)
        self.assertTrue(re.search(r"d0n\.AIBody\.70:", first_start.TEMPLATE.read_text()))
        self.assertIn("AIBody companion app 70 (example)", (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertIn("Status: version 70, package `d0n.AIBody.70.var`, release `v70`", (ROOT / "README.md").read_text(encoding="utf-8"))
        notes = (ROOT / "docs" / "RELEASE_NOTES_NEXT.md").read_text(encoding="utf-8")
        for s in ("Release notes of version 70", "In-game VaM log only when Verbose is on",
                  "no voice-pipeline fix", "unchanged since v59", "T128"):
            self.assertIn(s, notes)
        self.assertIn("## T128", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))

    def test_still_no_enum(self):
        for f in compiled_files():
            self.assertIsNone(re.search(r"\benum\s+[A-Za-z_]", code(f.read_text(encoding="utf-8"))), f.name)


class VerboseLogGateTests(TestCase):
    def test_info_warn_error_return_when_verbose_is_off(self):
        log = src("Log.cs")
        self.assertGreaterEqual(log.count("if (!Verbose) return;"), 5)  # Info, Debug, Warn, Error, Error(Exception)
        for sig in ("public static void Info(string message)",
                    "public static void Warn(string message)",
                    "public static void Error(string message)",
                    "public static void Error(string message, Exception e)",
                    "public static void Debug(string message)"):
            pos = log.index(sig)
            block = log[pos:pos + 280]
            self.assertIn("if (!Verbose) return;", block, sig)
        self.assertIn("SuperController.LogMessage", log)
        self.assertIn("SuperController.LogError", log)

    def test_no_direct_ingame_log_calls_outside_the_helper(self):
        files = compiled_files()
        self.assertGreater(len(files), 40)
        helper = SRC / "Log.cs"
        self.assertTrue(helper.exists())
        offenders = []
        for f in files:
            if f.resolve() == helper.resolve():
                continue
            text = code(f.read_text(encoding="utf-8"))
            m = LOG_CALL.search(text)
            if m:
                offenders.append(f"{f.name}: {m.group(0)}")
        self.assertEqual(offenders, [], "direct in-game log calls must go through Log.cs")
        # The helper itself is the only place that may call SuperController / Debug.Log
        self.assertIsNotNone(LOG_CALL.search(code(helper.read_text(encoding="utf-8"))))

    def test_scan_ignores_comments_and_strings(self):
        self.assertIsNone(LOG_CALL.search(code('// SuperController.LogError("x");\nvar s = "Debug.Log(1)";')))
        self.assertIsNotNone(LOG_CALL.search(code('class X { void Y() { SuperController.LogError("x"); } }')))
        self.assertIsNotNone(LOG_CALL.search(code('class X { void Y() { Debug.LogWarning(e); } }')))


class VoicePathTests(TestCase):
    def test_speech_player_logs_clip_received(self):
        sp = src("SpeechPlayer.cs")
        self.assertIn('Log.Debug("[audio] " + id + ": received clip "', sp)
        self.assertIn("Speech volume", sp[sp.index("received clip"):sp.index("received clip") + 280])
        self.assertGreaterEqual(sp.count('Log.Debug("[audio]'), 5)
        self.assertNotIn('Log.Info("[audio]', sp)

    def test_companion_emits_verbose_voice_path(self):
        orch = (ROOT / "companion" / "aibody_companion" / "orchestrator.py").read_text(encoding="utf-8")
        self.assertIn("from .audio.capture import default_output_device", orch)
        self.assertGreaterEqual(orch.count('turn.step("voice path"'), 2)
        self.assertIn("this app does not synthesize TTS for this turn", orch)
        self.assertIn("tts_wav=rel", orch)
        self.assertIn("device=default_output_device() if logsetup.is_verbose() else None", orch)
        self.assertIn("played=(type_ == \"speech_started\") or None", orch)
        self.assertIn("Verbose log must be on", orch)
