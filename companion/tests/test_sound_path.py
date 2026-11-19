"""The plain question-and-answer sound path: companion -> WAV file -> speak -> plugin head audio."""
from __future__ import annotations

import json
import logging
import tempfile
import unittest
import wave
from pathlib import Path

from aibody_companion import settings_file
from tests.fakes import FakeClock, FakePlugin
from tests.test_e2e_simulation import Sim


class SoundPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.sim = Sim(self.tmp.name, self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def connect(self):
        app = self.sim.start_app()
        plugin = FakePlugin(Path(self.tmp.name), self.clock, mode="chain")
        plugin.start()
        self.sim.run(plugin, 3)
        self.assertTrue(plugin.app_alive)
        return app, plugin

    def speaks(self, plugin):
        return self.sim.sent(plugin, "speak")

    def test_test_tone_button_plays_a_companion_wav(self):
        app, plugin = self.connect()
        plugin.request_test_tone()
        self.sim.run(plugin, 0.5)
        speak = self.speaks(plugin)[-1]
        self.assertEqual(speak["text"], "Test-Ton")
        self.assertEqual(speak["queue"], "interrupt")
        self.assertTrue(speak["audio"].startswith("Custom/Sounds/AIBody/default/"), speak["audio"])
        with wave.open(str(Path(self.tmp.name) / speak["audio"]), "rb") as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 22050))
            self.assertAlmostEqual(w.getnframes() / 22050, 1.5, places=2)
        self.assertEqual(plugin.speech_events[-1], ("started", speak["id"]))

    def test_typed_question_is_spoken_with_body_control_off(self):
        app, plugin = self.connect()
        plugin.ui["body"]["body_control"] = False
        plugin.write_settings()
        app.handle_user_text("Hallo")
        self.sim.run(plugin, 0.5)
        speak = self.speaks(plugin)[-1]
        self.assertIn("Hallo", speak["text"])
        self.assertTrue((Path(self.tmp.name) / speak["audio"]).is_file())
        raw = json.loads(settings_file.settings_path(self.tmp.name).read_text())
        self.assertEqual(raw["body"]["body_control"], "false")
        app2 = self.sim.start_app()
        self.assertEqual([p for p in self.sim.cfg_problems if "body_control" in p], [], "known key")
        app2.shutdown()

    def test_audio_folder_can_be_moved_below_custom(self):
        self.sim.start_app().shutdown()
        path = settings_file.settings_path(self.tmp.name)
        data = json.loads(path.read_text())
        data["connection"]["paths"]["audio"] = "Custom/Sounds/AIBody"
        path.write_text(json.dumps(data))
        app, plugin = self.connect()
        self.assertEqual(self.sim.cfg_problems, [])
        app.say("Hallo")
        self.sim.run(plugin, 0.3)
        speak = self.speaks(plugin)[-1]
        self.assertTrue(speak["audio"].startswith("Custom/Sounds/AIBody/utt-"), speak["audio"])
        self.assertTrue((Path(self.tmp.name) / speak["audio"]).is_file())
        plugin.seed_from_file()
        plugin.write_settings()
        self.assertEqual(json.loads(path.read_text())["connection"]["paths"]["audio"], "Custom/Sounds/AIBody",
                         "the plugin keeps the setting")

    def test_bad_audio_folder_is_refused(self):
        self.sim.start_app().shutdown()
        path = settings_file.settings_path(self.tmp.name)
        data = json.loads(path.read_text())
        data["connection"]["paths"]["audio"] = "C:/Temp"
        path.write_text(json.dumps(data))
        self.sim.start_app()
        self.assertTrue(any("connection.paths.audio" in p for p in self.sim.cfg_problems), self.sim.cfg_problems)
        self.assertEqual(self.sim.cfg.audio_rel_path("x.wav"), "Custom/Sounds/AIBody/default/x.wav")

    def test_null_speech_to_text_warns_once(self):
        app, plugin = self.connect()
        with self.assertLogs("aibody_companion.orchestrator", logging.WARNING) as logs:
            app._apply(("heard", "", 1.0))
            app._apply(("heard", "", 1.0))
        self.assertEqual(sum("cannot understand speech" in m for m in logs.output), 1)


if __name__ == "__main__":
    unittest.main()
