"""The plugin's in-game self test (Body.SelfTestJson) reaches the companion log once per change."""
import logging
import tempfile
import unittest
from pathlib import Path

from aibody_companion.orchestrator import describe_selftest
from tests.fakes import FakeClock, FakePlugin
from tests.test_e2e_simulation import Sim

OK = {"pose_storage": "ok", "pose_files": 2, "poses": 3, "breath_morph": "Breath1", "breath_morph_found": True,
      "expression_morphs_found": 9, "expression_morphs_total": 9, "expression_morphs_missing": [],
      "timeline_gestures": 0, "timeline": False}


class DescribeTests(unittest.TestCase):
    def test_all_ok(self):
        text, problems = describe_selftest(OK)
        self.assertFalse(problems)
        self.assertIn("pose storage yes", text)
        self.assertIn("poses 3 (files 2)", text)
        self.assertIn("breath morph 'Breath1' found", text)
        self.assertIn("expression morphs 9/9", text)
        self.assertNotIn("Timeline", text)

    def test_problems_are_named(self):
        bad = {**OK, "pose_storage": "no storable 'PosePresets'", "breath_morph_found": "false",
               "expression_morphs_found": "7", "expression_morphs_missing": ["Smile Open", "Brow Up"],
               "timeline_gestures": 1, "timeline": False}
        text, problems = describe_selftest(bad)
        self.assertTrue(problems)
        self.assertIn("pose storage NO (no storable 'PosePresets')", text)
        self.assertIn("NOT found", text)
        self.assertIn("expression morphs 7/9 (missing: Smile Open, Brow Up)", text)
        self.assertIn("Timeline NO for 1 gesture(s)", text)

    def test_error(self):
        self.assertEqual(describe_selftest({"error": "NullReferenceException"}),
                         ("ERROR NullReferenceException", True))


class LogOncePerChangeTests(unittest.TestCase):
    def test_logged_once_then_again_on_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            sim = Sim(tmp, clock)
            plugin = FakePlugin(Path(tmp), clock, mode="chain")
            sim.start_app()
            with self.assertLogs("aibody_companion", level=logging.INFO) as logs:
                plugin.start()
                sim.run(plugin, 10)   # ready + several heartbeats
                plugin.selftest["breath_morph_found"] = False
                sim.run(plugin, 5)
            lines = [r.getMessage() for r in logs.records if r.getMessage().startswith("Plugin self-test:")]
            self.assertEqual(len(lines), 2, lines)
            self.assertIn("found", lines[0])
            self.assertIn("NOT found", lines[1])
            warn = [r for r in logs.records if "NOT found" in r.getMessage()]
            self.assertEqual(warn[0].levelno, logging.WARNING)


if __name__ == "__main__":
    unittest.main()
