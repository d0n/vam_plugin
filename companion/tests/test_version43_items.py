"""Version 43 (Don, 21.11.2026 20:04-20:05): louder test tone (test_test_tone_level.py), update notice of the
installed companion (GitHub releases), the uninstaller deletes our own d0n.AIBody.<n>.var only, and speech_ended
says "completed" when a clip played to its end (his v42 log: every clip ended "interrupted" exactly after its length)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

from aibody_companion import update_check, winapp

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def release(tag: str, **extra) -> bytes:
    return json.dumps({"tag_name": tag, "html_url": "https://evil.example/x", "draft": False, "prerelease": False,
                       **extra}).encode()


class UpdateCheckTests(TestCase):
    def test_newer_release_is_offered_with_our_own_link(self):
        latest = update_check.newer_release("42", get=lambda url, t: release("v43"))
        self.assertEqual(latest, (43, "https://github.com/d0n/vam_plugin/releases/tag/v43"))
        text = update_check.notice("42", latest)
        self.assertIn("version 43", text)
        self.assertIn("https://github.com/d0n/vam_plugin/releases/tag/v43", text)
        self.assertNotIn("evil", text)

    def test_same_or_older_drafts_and_odd_tags_are_quiet(self):
        for body in (release("v43"), release("v42"), release("v44", draft=True), release("v44", prerelease=True),
                     release("latest"), b"not json", b"[]"):
            self.assertIsNone(update_check.newer_release("43", get=lambda url, t, b=body: b), body)

    def test_offline_and_errors_are_silent(self):
        def boom(url, t):
            raise OSError("no network")
        self.assertIsNone(update_check.newer_release("42", get=boom))
        self.assertIsNone(update_check.newer_release("dev", get=lambda url, t: release("v99")))

    def test_url_timeout_and_switch(self):
        seen = []
        update_check.newer_release("42", get=lambda url, t: seen.append((url, t)) or release("v1"))
        self.assertEqual(seen, [("https://api.github.com/repos/d0n/vam_plugin/releases/latest", 5.0)])
        self.assertTrue(update_check.enabled({}))
        self.assertFalse(update_check.enabled({"update_check": False}))

    def test_launcher_asks_on_the_main_thread_after_the_running_note(self):
        src = (ROOT / "companion" / "aibody_companion" / "winapp.py").read_text(encoding="utf-8")
        main = src[src.index("def main("):]
        self.assertLess(main.index("update = start_update_check(settings)"), main.index("show_note(\n        RUNNING_NOTE)"))
        self.assertLess(main.index("RUNNING_NOTE)"), main.index("offer_update(update(3.0))"))
        self.assertLess(main.index("if args.selftest:"), main.index("start_update_check"), "never in the CI self-test")
        off = winapp.start_update_check({"update_check": False})
        self.assertIsNone(off(0.1))


class UninstallTests(TestCase):
    def test_uninstaller_deletes_only_our_var_files(self):
        iss = (ROOT / "packaging" / "companion" / "AIBodyCompanion.iss").read_text(encoding="utf-8")
        self.assertIn("procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);", iss)
        self.assertIn("if CurUninstallStep <> usUninstall then exit;", iss)   # before [UninstallDelete] removes launcher.json
        self.assertIn("FindFirst(Folder + '\\d0n.AIBody.*.var', Rec)", iss)
        body = iss[iss.index("function IsOwnVar"):iss.index("procedure DeleteOwnVars")]
        self.assertIn("(Middle[I] < '0') or (Middle[I] > '9')", body)
        self.assertIn("'Inno Setup CodeFile: VamDir'", iss)
        wf = (ROOT / ".github" / "workflows" / "companion-windows.yml").read_text(encoding="utf-8")
        self.assertIn('"d0n.AIBodySession.3.var","d0n.AIBody.x.var","other.AIBody.1.var","Sub\\d0n.AIBody.40.var"', wf)
        self.assertIn("uninstall deleted d0n.AIBody.$v.var only", wf)   # version 44: the install already removed 41/42


class SpeechEndedTests(TestCase):
    def test_natural_end_is_completed(self):
        sp = (SRC / "SpeechPlayer.cs").read_text(encoding="utf-8")
        self.assertIn('Finish(PlayedToTheEnd(u) ? "completed" : "interrupted")', sp)
        self.assertIn("u.PlayTime - u.StartedAt >= u.Length - EndTolerance", sp)
        self.assertIn("u.Length = clip.length;", sp)
        self.assertIn('if (interrupt) StopAll("interrupted");', sp)   # a real barge-in still says interrupted
