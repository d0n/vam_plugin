import json
import tempfile
import time
import unittest
from pathlib import Path

from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline import EchoLlm, NullStt, ToneTts, wav_duration
from aibody_companion.transport import FileTransport


class FileTransportTests(unittest.TestCase):
    def test_roundtrip_like_the_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = FileTransport(Path(tmp) / "ch")
            t.start()
            self.assertFalse(t.connected)
            t.send({"type": "ping", "id": "a"})
            t.send({"type": "ping", "id": "b"})
            files = sorted(t.inbox.glob("*.json"))
            self.assertEqual([json.loads(f.read_text())["id"] for f in files], ["a", "b"])
            self.assertFalse(list(t.inbox.glob("*.tmp")))
            (t.outbox / "00000000000000000001_000001.json").write_text(json.dumps({"type": "ready"}))
            (t.outbox / "00000000000000000002_000002.json").write_text('{"type": "spee')  # partial
            events = t.poll_events()
            self.assertEqual([e["type"] for e in events], ["ready"])
            self.assertTrue((t.outbox / "00000000000000000002_000002.json").exists(), "fresh partial file kept")
            self.assertTrue(t.connected)

    def test_start_clears_stale_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = FileTransport(Path(tmp) / "ch")
            t.start()
            t.send({"type": "ping"})
            FileTransport(Path(tmp) / "ch").start()
            self.assertFalse(list(t.inbox.glob("*.json")))


class CompanionFileTests(unittest.TestCase):
    def test_text_turn_produces_commands_and_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(vam_root=tmp, channel="Person", ai={"mode": "chain"})
            t = FileTransport(cfg.channel_dir)
            t.start()
            c = Companion(cfg, t, NullStt(), EchoLlm(), ToneTts())
            c.handle_user_text("Hallo, wie geht's?")
            cmds = [json.loads(f.read_text()) for f in sorted(t.inbox.glob("*.json"))]
            self.assertEqual([x["type"] for x in cmds], ["expression", "gesture", "speak"])
            speak = cmds[-1]
            self.assertNotIn("url", speak)
            self.assertTrue(speak["audio"].startswith("Custom/Sounds/AIBody/Person/"))
            wav = Path(tmp) / speak["audio"]
            self.assertGreater(wav_duration(wav), 0.4)
            self.assertFalse(c.gate.is_open, "mic must be gated right after speak")


class FakePlugin:
    """Talks to the companion through the channel folder the way the C# FileTransport does:
    reads and deletes inbox/*.json, writes events as outbox/<20 digits>_<6 digits>.json."""

    def __init__(self, channel_dir: Path):
        self.inbox = channel_dir / "inbox"
        self.outbox = channel_dir / "outbox"
        self.seq = 0

    def poll(self):
        commands = []
        for f in sorted(self.inbox.glob("*.json")):
            commands.append(json.loads(f.read_text(encoding="utf-8")))
            f.unlink()
        return commands

    def send(self, *events):
        for e in events:
            self.seq += 1
            msg = dict(v=3, id=f"e{self.seq - 1}", ts=0, **e)
            name = f"{time.time_ns():020d}_{self.seq:06d}.json"
            (self.outbox / name).write_text(json.dumps(msg), encoding="utf-8")


class CompanionFilePluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(vam_root=self.tmp.name, channel="Person")
        self.t = FileTransport(self.cfg.channel_dir)
        self.t.start()
        self.devices = [{"name": "USB Mic", "index": 1, "default": True}]
        self.c = Companion(self.cfg, self.t, NullStt(), EchoLlm(), ToneTts(),
                           device_lister=lambda: (self.devices, None))
        self.plugin = FakePlugin(self.cfg.channel_dir)
        self.plugin.send({"type": "ready", "plugin_version": "test", "protocol": 3})
        self.c.tick()
        self.plugin.poll()  # drop the greeting (mic_state, heartbeat, ...)

    def tearDown(self):
        self.tmp.cleanup()

    def test_speak_points_to_a_wav_in_the_channel_folder_and_gate_follows_playback(self):
        uid = self.c.say("Hello there")
        speak = [m for m in self.plugin.poll() if m["type"] == "speak"][0]
        self.assertEqual(speak["id"], uid)
        self.assertNotIn("url", speak)
        wav = Path(self.tmp.name) / speak["audio"]
        self.assertEqual(wav.read_bytes()[:4], b"RIFF")
        self.assertFalse(self.c.gate.is_open)
        self.plugin.send({"type": "speech_started", "utterance_id": uid, "duration": 1.0})
        self.c.tick()
        self.assertTrue(self.c.gate.is_speaking)
        self.plugin.send({"type": "speech_ended", "utterance_id": uid, "reason": "completed"})
        self.c.tick()
        self.assertFalse(self.c.gate.is_open, "echo tail")
        time.sleep(self.c.gate.tail_s + 0.05)
        self.assertTrue(self.c.gate.is_open)

    def test_config_is_applied_and_acked(self):
        self.plugin.send({"type": "config", "mic": {"mode": "ptt", "vad_threshold": 0.05, "gain": 2.0,
                                                   "echo_tail_s": 1.0, "bogus": 1}})
        self.c.tick()
        self.assertEqual(self.c.mic_settings.mode, "ptt")
        self.assertEqual(self.c.input.vad.min_rms, 0.05)
        self.assertEqual(self.c.gate.tail_s, 1.0)
        ack = [m for m in self.plugin.poll() if m["type"] == "config_ack"][0]
        self.assertEqual(ack["reply_to"], "e1")
        self.assertEqual(ack["applied"]["mic"]["gain"], 2.0)
        self.assertEqual(len(ack["errors"]), 1)
        self.assertEqual(ack["mic_state"]["capturing"], False)

    def test_list_devices(self):
        self.plugin.send({"type": "list_devices"})
        self.c.tick()
        msg = [m for m in self.plugin.poll() if m["type"] == "devices"][0]
        self.assertEqual(msg["devices"][0]["name"], "USB Mic")

    def test_ptt_press_interrupts_speech(self):
        self.plugin.send({"type": "config", "mic": {"mode": "ptt", "ptt_interrupts": True}})
        self.c.tick()
        uid = self.c.say("A long answer")
        self.plugin.send({"type": "speech_started", "utterance_id": uid, "duration": 5.0},
                         {"type": "ptt", "active": True})
        self.c.tick()
        types = [m["type"] for m in self.plugin.poll()]
        self.assertIn("stop_speaking", types)
        self.assertTrue(self.c.input.ptt_active)

    def test_mic_state_sent_once_when_connected(self):
        fresh = Companion(self.cfg, self.t, NullStt(), EchoLlm(), ToneTts(),
                          device_lister=lambda: (self.devices, None))
        fresh.tick()
        states = [m for m in self.plugin.poll() if m["type"] == "mic_state"]
        self.assertEqual(len(states), 1)
        self.assertIn("error", states[0])  # no microphone in this test stack
        fresh.tick()
        self.assertEqual([m for m in self.plugin.poll() if m["type"] == "mic_state"], [])


if __name__ == "__main__":
    unittest.main()
