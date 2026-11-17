"""Tab "AI" / "AI Character" / "Voice Mode" controls: key file paths, key status, voice, API Reconnect."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion.pipeline.http import ApiError
from tests.fakes import FakeClock, FakePlugin
from tests.test_e2e_simulation import Sim

KEY = "xai-" + "0" * 40  # fake key, written to a temp file only


class AiTabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = FakeClock()
        self.sim = Sim(self.tmp.name, self.clock)
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(self.root, self.clock, mode="chain")
        self.plugin.start()
        self.sim.run(self.plugin, 3)

    def tearDown(self):
        self.app.shutdown()
        self.tmp.cleanup()

    def beat(self):
        return self.sim.sent(self.plugin, "companion_heartbeat")[-1]

    def push(self):
        self.plugin.send_config()
        self.sim.run(self.plugin, 2.5)

    def test_key_status_missing_then_configured_from_a_key_file_path(self):
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "missing")
        self.assertEqual(self.beat()["keys"]["elevenlabs"]["state"], "missing")
        key_file = self.root / "xai.txt"
        key_file.write_text(KEY)
        self.plugin.key_files["xai"] = str(key_file)
        self.push()
        keys = self.beat()["keys"]
        self.assertEqual(keys["xai"]["state"], "configured")
        self.assertIn("xai.txt", keys["xai"]["detail"])
        self.assertNotIn(KEY, json.dumps(self.beat()), "never the key itself")
        self.plugin.write_settings()
        raw = json.loads(settings_file.settings_path(self.tmp.name).read_text())
        self.assertEqual(raw["ai"]["xai"]["key_file"], str(key_file))
        self.assertEqual(raw["ai"]["xai"]["model"], "grok-4.7", "the rest of ai.xai is kept")
        self.assertNotIn(KEY, json.dumps(raw))

    def test_a_pasted_key_is_refused_and_the_old_path_stays(self):
        key_file = self.root / "xai.txt"
        key_file.write_text(KEY)
        self.plugin.key_files["xai"] = str(key_file)
        self.push()
        self.plugin.key_files["xai"] = KEY  # the plugin refuses this itself; the app must too
        self.push()
        ack = self.sim.sent(self.plugin, "config_ack")[-1]
        self.assertTrue(any("looks like an API key" in e for e in ack["errors"]), ack["errors"])
        self.assertEqual(self.app.engine_set.ai["xai"]["key_file"], str(key_file))
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "configured")

    def test_empty_field_does_not_wipe_a_path_from_config_json(self):
        path = settings_file.settings_path(self.tmp.name)
        data = json.loads(path.read_text())
        data["ai"]["elevenlabs"]["key_file"] = "keys/eleven.txt"
        path.write_text(json.dumps(data))
        self.plugin.adopt_key_files()  # AIBody.cs: on every start, empty fields take the file's paths
        self.assertEqual(self.plugin.key_files["elevenlabs"], "keys/eleven.txt")
        self.plugin.key_files["elevenlabs"] = ""
        self.plugin.write_settings()
        self.assertEqual(json.loads(path.read_text())["ai"]["elevenlabs"]["key_file"], "keys/eleven.txt")

    def test_rejected_key(self):
        key_file = self.root / "xai.txt"
        key_file.write_text(KEY)
        self.plugin.key_files["xai"] = str(key_file)
        self.push()
        self.app.engine_set.note_api_error(ApiError("xAI", 401, "invalid key"))
        self.sim.run(self.plugin, 2.5)
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "rejected")
        key_file.write_text(KEY.replace("0", "1"))  # a new key gets a new chance
        self.plugin.request_reconnect()
        self.sim.run(self.plugin, 2.5)
        self.assertEqual(self.beat()["keys"]["xai"]["state"], "configured")

    def test_voice_goes_to_realtime_and_tts(self):
        self.plugin.voice = "ara"
        self.push()
        self.assertEqual(self.app.engine_set.ai["realtime"]["voice"], "ara")
        self.assertEqual(self.app.engine_set.ai["xai"]["voice"], "ara")
        self.assertEqual(self.sim.sent(self.plugin, "config_ack")[-1]["applied"]["ai"]["realtime"]["voice"], "ara")


if __name__ == "__main__":
    unittest.main()
