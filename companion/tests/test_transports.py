import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline import EchoLlm, NullStt, ToneTts, wav_duration
from aibody_companion.transport import FileTransport, HttpTransport


class FileTransportTests(unittest.TestCase):
    def test_roundtrip_like_the_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = FileTransport(Path(tmp) / "ch")
            t.start()
            t.send({"type": "ping", "id": "a"})
            t.send({"type": "ping", "id": "b"})
            # Plugin side: read inbox in ordinal order, delete.
            files = sorted(t.inbox.glob("*.json"))
            self.assertEqual([json.loads(f.read_text())["id"] for f in files], ["a", "b"])
            self.assertFalse(list(t.inbox.glob("*.tmp")))
            # Plugin side writes events into outbox.
            (t.outbox / "00000000000000000001_000001.json").write_text(json.dumps({"type": "ready"}))
            (t.outbox / "00000000000000000002_000002.json").write_text('{"type": "spee')  # partial
            events = t.poll_events()
            self.assertEqual([e["type"] for e in events], ["ready"])
            self.assertTrue((t.outbox / "00000000000000000002_000002.json").exists(), "fresh partial file kept")


class HttpTransportTests(unittest.TestCase):
    def test_poll_and_post(self):
        t = HttpTransport("Person", port=0)
        t.start()
        try:
            base = f"http://127.0.0.1:{t.port}"
            t.send({"type": "ping", "id": "1"})
            with urllib.request.urlopen(f"{base}/v1/commands?channel=Person&after=0") as r:
                data = json.loads(r.read())
            self.assertEqual(data["last"], 1)
            self.assertEqual(data["commands"][0]["id"], "1")
            with urllib.request.urlopen(f"{base}/v1/commands?channel=Person&after=1") as r:
                self.assertEqual(json.loads(r.read())["commands"], [])
            req = urllib.request.Request(f"{base}/v1/events?channel=Person", data=b'{"type":"ready"}',
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req).read()
            self.assertEqual(t.poll_events(), [{"type": "ready"}])
        finally:
            t.stop()


class CompanionTests(unittest.TestCase):
    def test_text_turn_produces_commands_and_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(vam_root=tmp, channel="Person")
            t = FileTransport(cfg.channel_dir)
            t.start()
            c = Companion(cfg, t, NullStt(), EchoLlm(), ToneTts())
            c.handle_user_text("Hallo, wie geht's?")
            cmds = [json.loads(f.read_text()) for f in sorted(t.inbox.glob("*.json"))]
            types = [x["type"] for x in cmds]
            self.assertEqual(types, ["expression", "gesture", "speak"])
            speak = cmds[-1]
            self.assertTrue(speak["audio"].startswith("Saves/PluginData/AIBody/Person/audio/"))
            wav = Path(tmp) / speak["audio"]
            self.assertTrue(wav.exists())
            self.assertGreater(wav_duration(wav), 0.4)
            self.assertFalse(c.gate.is_open, "mic must be gated right after speak")


if __name__ == "__main__":
    unittest.main()
