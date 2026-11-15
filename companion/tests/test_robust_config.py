import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline import EchoLlm, NullStt, ToneTts
from aibody_companion.transport import FileTransport
from aibody_companion.transport.file_transport import COMMAND_TTL_S

ROOT = Path(__file__).resolve().parents[2]


def plugin_event(outbox: Path, seq: int, **event):
    msg = dict(v=3, id=f"e{seq}", ts=0, **event)
    (outbox / f"{time.time_ns():020d}_{seq:06d}.json").write_text(json.dumps(msg), encoding="utf-8")


class RobustLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(vam_root=self.tmp.name, channel="default")

    def tearDown(self):
        self.tmp.cleanup()

    def test_commands_the_plugin_never_picked_up_expire(self):
        t = FileTransport(self.cfg.channel_dir)
        t.start()
        t.send({"type": "speak", "audio": "a.wav"})
        t.send({"type": "speak", "audio": "b.wav"})
        old, fresh = sorted(t.inbox.glob("*.json"))
        past = time.time() - COMMAND_TTL_S - 5
        os.utime(old, (past, past))
        self.assertEqual(t.drop_stale_commands(), 1)
        self.assertEqual(list(t.inbox.glob("*.json")), [fresh])

    def test_app_restart_clears_the_channel_and_gets_a_new_session(self):
        first = FileTransport(self.cfg.channel_dir)
        first.start()
        a = Companion(self.cfg, first, NullStt(), EchoLlm(), ToneTts())
        a.say("left over from the crashed app")
        plugin_event(first.outbox, 1, type="heartbeat")
        # app crashes here: inbox (speak) and outbox (heartbeat) keep their files
        self.assertTrue(list(first.inbox.glob("*.json")))
        self.assertTrue(list(first.outbox.glob("*.json")))

        second = FileTransport(self.cfg.channel_dir)
        second.start()
        self.assertFalse(list(second.inbox.glob("*.json")), "no replay of old speech")
        self.assertFalse(list(second.outbox.glob("*.json")), "no stale events")
        b = Companion(self.cfg, second, NullStt(), EchoLlm(), ToneTts())
        self.assertNotEqual(a.session_id, b.session_id)
        b.tick()
        self.assertFalse(list(second.inbox.glob("*.json")), "silent until the plugin is heard")
        plugin_event(second.outbox, 2, type="heartbeat")
        b.tick()
        sent = [json.loads(f.read_text()) for f in sorted(second.inbox.glob("*.json"))]
        beats = [m for m in sent if m["type"] == "companion_heartbeat"]
        self.assertEqual(beats[0]["session"], b.session_id)

    def test_plugin_gone_opens_gate_and_stops_heartbeats(self):
        t = FileTransport(self.cfg.channel_dir)
        t.start()
        c = Companion(self.cfg, t, NullStt(), EchoLlm(), ToneTts())
        plugin_event(t.outbox, 1, type="ready")
        c.tick()
        c.say("hello")
        self.assertFalse(c.gate.is_open)
        for f in t.inbox.glob("*.json"):
            f.unlink()
        t._last_seen = time.monotonic() - 60  # plugin silent for a minute
        c.tick()
        self.assertTrue(c.gate.is_open, "mic must not stay muted for a body that is gone")
        c._last_heartbeat = -100.0
        c.tick()
        self.assertFalse(list(t.inbox.glob("*.json")), "no heartbeats pile up while the plugin is away")


class SharedConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = settings_file.settings_path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_global_path(self):
        self.assertEqual(self.path, Path(self.tmp.name) / "Saves/PluginData/AIBody/config.json")

    def test_missing_file_is_created_with_defaults(self):
        cfg = Config(vam_root=self.tmp.name)
        self.assertEqual(settings_file.apply_to_config(cfg), [])
        data = json.loads(self.path.read_text())
        self.assertEqual(set(data) - {"version", "written_by"}, set(settings_file.CATEGORIES))
        self.assertEqual(settings_file.validate(data)[1], [])
        self.assertEqual(cfg.channel, "default")

    def test_plugin_values_are_used(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({
            "version": 1, "written_by": "AIBody plugin 0.6.3",
            "connection": {"channel": "Anna 1", "active": True},
            "engines": {"stt": "null", "llm": "gpt-9", "tts": "tone"},
            "mic": {"mode": "ptt", "gain": 2.0, "ptt_interrupts": False},
            "body": {"speech_volume": 0.5},
            "advanced": {"file_poll_interval_s": 0.2, "verbose_log": True},
        }))
        cfg = Config(vam_root=self.tmp.name)
        errors = settings_file.apply_to_config(cfg)
        self.assertEqual(cfg.channel, "Anna_1", "sanitized like the plugin's channel field")
        self.assertEqual(cfg.mic["mode"], "ptt")
        self.assertEqual(cfg.mic["gain"], 2.0)
        self.assertFalse(cfg.mic["ptt_interrupts"])
        self.assertEqual(cfg.llm, "echo", "unavailable engine is not taken over")
        self.assertTrue(any("gpt-9" in e for e in errors))

    def test_cli_channel_wins(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"connection": {"channel": "other"}}))
        cfg = Config(vam_root=self.tmp.name, channel="mine")
        errors = settings_file.apply_to_config(cfg, channel_from_cli=True)
        self.assertEqual(cfg.channel, "mine")
        self.assertTrue(errors)

    def test_validation_clamps_and_rejects(self):
        data, errors = settings_file.validate({
            "connection": {"paths": {"expressions": "C:/evil.json", "gestures": "Custom/x/g.json"}},
            "body": {"speech_volume": 7, "breathing": "yes"},
            "mic": {"mode": "loud"},
            "extra": {},
        })
        self.assertEqual(data["body"]["speech_volume"], 1.0)
        self.assertTrue(data["body"]["breathing"])
        self.assertEqual(data["connection"]["paths"]["gestures"], "Custom/x/g.json")
        self.assertEqual(data["connection"]["paths"]["expressions"], "Saves/PluginData/AIBody/expressions.json")
        self.assertEqual(data["mic"]["mode"], "vad")
        self.assertEqual(len(errors), 4)

    def test_broken_file_keeps_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"connection": ')
        cfg = Config(vam_root=self.tmp.name, channel="default")
        errors = settings_file.apply_to_config(cfg)
        self.assertTrue(errors)
        self.assertEqual(cfg.llm, "echo")

    def test_example_config_is_valid(self):
        data = json.loads((ROOT / "examples" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(settings_file.validate(data)[1], [])
        self.assertEqual(set(data) - {"version", "written_by"}, set(settings_file.CATEGORIES))

    def test_csharp_writes_the_same_categories(self):
        sources = "".join((ROOT / "src" / "AIBody" / n).read_text(encoding="utf-8")
                          for n in ("AppLink.cs", "Body.cs", "AIBody.cs"))
        for cat in settings_file.CATEGORIES:
            self.assertIn(f'root["{cat}"]', sources, cat)
        for cat in ("body", "advanced"):
            for key in settings_file.DEFAULTS[cat]:
                self.assertIn(f'"{key}"', sources, key)


if __name__ == "__main__":
    unittest.main()
