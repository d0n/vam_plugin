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
        self.assertIn("Pose-Speicher ja", text)
        self.assertIn("Posen 3 (Dateien 2)", text)
        self.assertIn("Atem-Morph 'Breath1' gefunden", text)
        self.assertIn("Ausdrucks-Morphs 9/9", text)
        self.assertNotIn("Timeline", text)

    def test_problems_are_named(self):
        bad = {**OK, "pose_storage": "kein Storable 'PosePresets'", "breath_morph_found": "false",
               "expression_morphs_found": "7", "expression_morphs_missing": ["Smile Open", "Brow Up"],
               "timeline_gestures": 1, "timeline": False}
        text, problems = describe_selftest(bad)
        self.assertTrue(problems)
        self.assertIn("Pose-Speicher NEIN (kein Storable 'PosePresets')", text)
        self.assertIn("NICHT gefunden", text)
        self.assertIn("Ausdrucks-Morphs 7/9 (fehlen: Smile Open, Brow Up)", text)
        self.assertIn("Timeline NEIN für 1 Geste(n)", text)

    def test_error(self):
        self.assertEqual(describe_selftest({"error": "NullReferenceException"}),
                         ("FEHLER NullReferenceException", True))


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
            lines = [r.getMessage() for r in logs.records if r.getMessage().startswith("Plugin-Selbsttest:")]
            self.assertEqual(len(lines), 2, lines)
            self.assertIn("gefunden", lines[0])
            self.assertIn("NICHT gefunden", lines[1])
            warn = [r for r in logs.records if "NICHT gefunden" in r.getMessage()]
            self.assertEqual(warn[0].levelno, logging.WARNING)


if __name__ == "__main__":
    unittest.main()
