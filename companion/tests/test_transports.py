import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline import EchoLlm, NullStt, ToneTts, wav_duration
from aibody_companion.transport import AutoTransport, FileTransport, HttpTransport


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def get_json(url, timeout=5):
    return json.loads(get(url, timeout)[1])


def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


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


class HttpTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audio = Path(self.tmp.name) / "audio"
        self.audio.mkdir()
        self.t = HttpTransport("Person", port=0, audio_dir=self.audio)
        self.t.start()
        self.base = f"http://127.0.0.1:{self.t.port}"

    def tearDown(self):
        self.t.stop()
        self.tmp.cleanup()

    def test_hello_returns_session(self):
        hello = get_json(f"{self.base}/v1/hello?channel=Person&plugin=0.2.0")
        self.assertEqual(hello["session"], self.t.session)
        self.assertEqual(hello["protocol"], 1)
        self.assertEqual(self.t.plugin_version, "0.2.0")
        self.assertTrue(self.t.connected)

    def test_wrong_channel_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            get(f"{self.base}/v1/hello?channel=Other")
        self.assertEqual(ctx.exception.code, 409)

    def test_poll_and_post(self):
        self.t.send({"type": "ping", "id": "1"})
        data = get_json(f"{self.base}/v1/commands?channel=Person&after=0")
        self.assertEqual(data["last"], 1)
        self.assertEqual(data["session"], self.t.session)
        self.assertEqual(data["commands"][0]["id"], "1")
        self.assertEqual(get_json(f"{self.base}/v1/commands?channel=Person&after=1")["commands"], [])
        post_json(f"{self.base}/v1/events?channel=Person", [{"type": "ready"}, {"type": "heartbeat"}])
        self.assertEqual([e["type"] for e in self.t.poll_events()], ["ready", "heartbeat"])

    def test_long_poll_returns_when_command_arrives(self):
        threading.Timer(0.3, lambda: self.t.send({"type": "ping", "id": "late"})).start()
        start = time.monotonic()
        data = get_json(f"{self.base}/v1/commands?channel=Person&after=0&wait=5", timeout=10)
        elapsed = time.monotonic() - start
        self.assertEqual(data["commands"][0]["id"], "late")
        self.assertLess(elapsed, 2.0)
        self.assertGreaterEqual(elapsed, 0.25)

    def test_long_poll_times_out_empty(self):
        start = time.monotonic()
        data = get_json(f"{self.base}/v1/commands?channel=Person&after=0&wait=0.4")
        self.assertEqual(data["commands"], [])
        self.assertGreaterEqual(time.monotonic() - start, 0.35)

    def test_plugin_ahead_of_new_session_resyncs(self):
        self.t.send({"type": "ping", "id": "1"})
        data = get_json(f"{self.base}/v1/commands?channel=Person&after=99")
        self.assertEqual([c["id"] for c in data["commands"]], ["1"])

    def test_audio_served(self):
        (self.audio / "utt-1.wav").write_bytes(b"RIFFdata")
        self.assertEqual(self.t.audio_url("utt-1.wav"), "/v1/audio/utt-1.wav")
        status, body = get(f"{self.base}/v1/audio/utt-1.wav")
        self.assertEqual((status, body), (200, b"RIFFdata"))

    def test_audio_rejects_traversal_and_missing(self):
        (Path(self.tmp.name) / "secret.wav").write_bytes(b"x")
        for name in ("..%2Fsecret.wav", "missing.wav", "notes.txt"):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                get(f"{self.base}/v1/audio/{name}")
            self.assertEqual(ctx.exception.code, 404, name)


class AutoTransportTests(unittest.TestCase):
    def test_link_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            http = HttpTransport("Person", port=0, audio_dir=Path(tmp))
            file = FileTransport(Path(tmp) / "ch")
            auto = AutoTransport(http, file)
            auto.start()
            try:
                self.assertIsNone(auto.link)
                auto.send({"type": "ping", "id": "early"})  # nobody connected yet: buffered on HTTP
                self.assertFalse(list(file.inbox.glob("*.json")))
                (file.outbox / "00000000000000000001_000001.json").write_text('{"type": "heartbeat"}')
                self.assertEqual(len(auto.poll_events()), 1)
                self.assertEqual(auto.link, "file")
                self.assertIsNone(auto.audio_url("a.wav"))
                auto.send({"type": "ping", "id": "via-file"})
                self.assertEqual(len(list(file.inbox.glob("*.json"))), 1)
                get(f"http://127.0.0.1:{http.port}/v1/hello?channel=Person")
                self.assertEqual(auto.link, "http")
                self.assertEqual(auto.audio_url("a.wav"), "/v1/audio/a.wav")
            finally:
                auto.stop()


class CompanionFileTests(unittest.TestCase):
    def test_text_turn_produces_commands_and_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(vam_root=tmp, channel="Person")
            t = FileTransport(cfg.channel_dir)
            t.start()
            c = Companion(cfg, t, NullStt(), EchoLlm(), ToneTts())
            c.handle_user_text("Hallo, wie geht's?")
            cmds = [json.loads(f.read_text()) for f in sorted(t.inbox.glob("*.json"))]
            self.assertEqual([x["type"] for x in cmds], ["expression", "gesture", "speak"])
            speak = cmds[-1]
            self.assertNotIn("url", speak)
            self.assertTrue(speak["audio"].startswith("Saves/PluginData/AIBody/Person/audio/"))
            wav = Path(tmp) / speak["audio"]
            self.assertGreater(wav_duration(wav), 0.4)
            self.assertFalse(c.gate.is_open, "mic must be gated right after speak")


class FakePlugin:
    """Talks to the companion's HTTP server the way the C# HttpTransport does."""

    def __init__(self, base):
        self.base = base
        self.after = 0
        self.session = None

    def hello(self):
        self.session = get_json(f"{self.base}/v1/hello?channel=Person&plugin=test")["session"]

    def poll(self, wait=0.0):
        data = get_json(f"{self.base}/v1/commands?channel=Person&after={self.after}&wait={wait}")
        self.after = data["last"]
        return data["commands"]

    def send(self, *events):
        batch = [dict(v=1, id=f"e{i}", ts=0, **e) for i, e in enumerate(events)]
        post_json(f"{self.base}/v1/events?channel=Person", batch)


class CompanionHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(channel="Person", audio_cache_dir=str(Path(self.tmp.name) / "cache"))
        self.cfg.audio_dir.mkdir(parents=True)
        self.http = HttpTransport("Person", port=0, audio_dir=self.cfg.audio_dir)
        self.http.start()
        self.devices = [{"name": "USB Mic", "index": 1, "default": True}]
        self.c = Companion(self.cfg, self.http, NullStt(), EchoLlm(), ToneTts(),
                           device_lister=lambda: (self.devices, None))
        self.plugin = FakePlugin(f"http://127.0.0.1:{self.http.port}")
        self.plugin.hello()

    def tearDown(self):
        self.http.stop()
        self.tmp.cleanup()

    def test_speak_delivers_downloadable_audio_and_gate_follows_playback(self):
        uid = self.c.say("Hello there")
        speak = [m for m in self.plugin.poll() if m["type"] == "speak"][0]
        self.assertEqual(speak["id"], uid)
        self.assertNotIn("audio", speak, "no vam_root: only the URL is offered")
        status, wav = get(self.plugin.base + speak["url"])
        self.assertEqual(status, 200)
        self.assertEqual(wav[:4], b"RIFF")
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
        self.assertEqual(ack["reply_to"], "e0")
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

    def test_mic_state_sent_when_connected(self):
        self.c.tick()
        states = [m for m in self.plugin.poll() if m["type"] == "mic_state"]
        self.assertEqual(len(states), 1)
        self.assertIn("error", states[0])  # no microphone in this test stack
        self.c.tick()
        self.assertEqual([m for m in self.plugin.poll() if m["type"] == "mic_state"], [])


if __name__ == "__main__":
    unittest.main()
