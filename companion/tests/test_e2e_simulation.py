"""End-to-end simulation without VaM: the real companion (Companion + FileTransport + engines) and
a fake plugin (tests/fakes.py, a Python model of the C# code paths) exchange files in a temporary
VaM folder. Covers the config.json round trip, disconnect / reconnect and a full speak cycle with
mocked xAI engines (streaming LLM, TTS)."""
import json
import queue
import tempfile
import time
import unittest
import wave
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion.audio import EchoGate
from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline.engines import EngineSet
from aibody_companion.pipeline.http import HttpClient
from aibody_companion.transport import FileTransport
from tests.fakes import FakeClock, FakeHttp, FakePlugin, FakeResponse, text_stream

KEY = "test-key-not-real-1234567890"


class Sim:
    """Companion app + fake plugin on one fake clock."""

    def __init__(self, root: str, clock: FakeClock, http: FakeHttp | None = None, env: dict | None = None,
                 background: bool = False, mode: str = "chain", connector=None, wall=None):
        self.root = root
        self.mode = mode
        self.connector = connector
        self.wall = wall
        self.clock = clock
        self.http = http
        self.env = env or {}
        self.background = background
        self.app: Companion | None = None

    def start_app(self) -> Companion:
        cfg = Config(vam_root=self.root)
        problems = settings_file.apply_to_config(cfg)
        self.cfg = cfg
        self.cfg_problems = problems
        transport = FileTransport(cfg.channel_dir, clock=self.clock)
        transport.start()
        engines = EngineSet({**cfg.ai, "mode": self.mode}, http=HttpClient(self.http) if self.http else None,
                            env=self.env)
        self.app = Companion(cfg, transport, gate=EchoGate(clock=self.clock), clock=self.clock,
                             engines=engines, background_turns=self.background,
                             realtime_connector=self.connector, wall=self.wall)
        return self.app

    def run(self, plugin: FakePlugin, seconds: float, dt: float = 0.1, app: bool = True) -> None:
        steps = int(round(seconds / dt))
        for _ in range(steps):
            self.clock.advance(dt)
            plugin.tick(dt)
            if app and self.app:
                self.app.tick()

    def sent(self, plugin: FakePlugin, type_: str) -> list[dict]:
        return [m for m in plugin.received if m.get("type") == type_]


class ConfigRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.sim = Sim(self.tmp.name, self.clock)
        self.plugin = FakePlugin(Path(self.tmp.name), self.clock, mode="chain")

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_app_file_plugin_file_app(self):
        # 1. The app starts first and creates config.json (with the ai section).
        app = self.sim.start_app()
        self.assertEqual(self.sim.cfg_problems, [])
        path = settings_file.settings_path(self.tmp.name)
        self.assertIn("ai", json.loads(path.read_text()))

        # 2. A new scene: the plugin seeds its UI from the file, the user changes things in the tabs,
        #    the plugin writes everything back VaM-style (numbers and booleans as strings).
        self.plugin.start()
        self.plugin.seed_from_file()
        self.plugin.ui["mic"].update(mode="ptt", gain=2.5, ptt_interrupts=False)
        self.plugin.ui["engines"]["llm"] = "xai"
        self.plugin.ui["body"]["speech_volume"] = 0.6
        self.plugin.write_settings()
        raw = json.loads(path.read_text())
        self.assertEqual(raw["mic"]["gain"], "2.5", "VaM writes numbers as strings")
        self.assertEqual(raw["connection"]["active"], "true")
        self.assertEqual(raw["ai"]["xai"]["model"], "grok-4.7", "the plugin keeps the ai section")
        self.assertEqual(raw["ai"]["xai"]["max_output_tokens"], "400")

        # 3. The live link: the plugin's config event (strings) is applied by the running app.
        self.sim.run(self.plugin, 3)
        acks = self.sim.sent(self.plugin, "config_ack")
        self.assertTrue(acks, "config_ack received")
        applied = acks[-1]["applied"]
        self.assertEqual(applied["mic"]["mode"], "ptt")
        self.assertEqual(applied["mic"]["gain"], 2.5)
        self.assertFalse(applied["mic"]["ptt_interrupts"])
        self.assertEqual(applied["engines"]["llm"], "xai")
        self.assertTrue(any("nicht konfiguriert" in e for e in acks[-1]["errors"]), acks[-1]["errors"])
        self.assertFalse([e for e in acks[-1]["errors"] if "must be" in e], "no type errors from VaM strings")
        self.assertEqual(app.engine_set.active_names["llm"], "echo", "no key: fallback runs")
        beat = self.sim.sent(self.plugin, "companion_heartbeat")[-1]
        self.assertEqual(beat["engines_active"]["llm"], "echo")
        self.assertTrue(beat["engines_status"]["llm"]["xai"].startswith("nicht konfiguriert"))

        # 4. Push-to-talk arrives as "true"/"false" strings and still works.
        self.plugin.press_ptt(True)
        self.sim.run(self.plugin, 0.3)
        self.assertTrue(app.input.ptt_active)
        self.plugin.press_ptt(False)
        self.sim.run(self.plugin, 0.3)
        self.assertFalse(app.input.ptt_active)

        # 5. The app restarts and reads the plugin-written (stringified) file without problems.
        app.shutdown()
        app2 = self.sim.start_app()
        self.assertEqual([p for p in self.sim.cfg_problems if "must be" in p], [])
        self.assertEqual(self.sim.cfg.mic["mode"], "ptt")
        self.assertEqual(self.sim.cfg.mic["gain"], 2.5)
        self.assertEqual(self.sim.cfg.llm, "xai")
        self.assertEqual(self.sim.cfg.ai["xai"]["max_output_tokens"], 400)
        self.assertEqual(app2.engines["llm"], "xai")

    def test_plugin_first_then_app_adds_ai_section(self):
        self.plugin.start()
        self.plugin.seed_from_file()  # no file yet
        self.plugin.write_settings()
        path = settings_file.settings_path(self.tmp.name)
        self.assertEqual(set(json.loads(path.read_text())["ai"]), {"mode", "proactive", "realtime"},
                         "only the Engines tab's ai controls")
        self.sim.start_app()
        data = json.loads(path.read_text())
        self.assertIn("persona", data["ai"], "the app fills in the rest of its section so it can be edited")
        self.assertEqual(data["ai"]["mode"], "chain")
        self.assertEqual(data["mic"]["gain"], "1.0", "the plugin's part stays as it was")
        self.plugin.ui["mic"]["gain"] = 3.0
        self.plugin.ai_ui["proactive"]["idle_seconds"] = 120.0
        self.plugin.write_settings()
        ai = json.loads(path.read_text())["ai"]
        self.assertIn("persona", ai, "the plugin keeps the app's ai settings")
        self.assertEqual(ai["proactive"]["idle_seconds"], "120.0", "and merges its controls into them")
        self.assertIn("prompt", ai["proactive"])
        app = self.sim.start_app()
        self.assertEqual(app.proactive.idle_seconds, 120.0)


class ReconnectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.sim = Sim(self.tmp.name, self.clock)
        self.plugin = FakePlugin(Path(self.tmp.name), self.clock, mode="chain")

    def tearDown(self):
        self.tmp.cleanup()

    def test_app_crash_and_restart(self):
        app = self.sim.start_app()
        self.plugin.start()
        self.sim.run(self.plugin, 5)
        self.assertEqual(self.plugin.status, "verbunden")
        first_session = app.session_id
        app.say("A long sentence that is still playing when the app dies.")
        self.sim.run(self.plugin, 0.5)
        self.assertTrue(self.plugin.playing)

        # The app crashes: no more ticks. After 6 s the plugin shows GETRENNT, logged once.
        self.sim.run(self.plugin, 60, app=False)
        self.assertEqual(self.plugin.status, "GETRENNT")
        self.assertEqual(self.plugin.log.count("Companion app disconnected"), 1)
        self.assertLessEqual(len(list(self.plugin.outbox.glob("*.json"))), 21, "outbox pruned while away")

        # Restart: the new app clears the channel, the plugin reconnects by itself.
        self.plugin.playing = [{"id": "still-playing", "duration": 30}]
        app2 = self.sim.start_app()
        self.assertNotEqual(app2.session_id, first_session)
        self.assertFalse(list(self.plugin.outbox.glob("*.json")), "stale events cleared by the app")
        self.sim.run(self.plugin, 5)
        self.assertEqual(self.plugin.status, "verbunden")
        self.assertIn("app restarted", self.plugin.log)
        self.assertFalse(self.plugin.playing, "old speech stopped after the app restart")
        readies_after = [m for m in self.plugin.received if m.get("type") == "config_ack"]
        self.assertTrue(readies_after, "ready + config re-sent, config_ack came back")

    def test_plugin_away_and_back(self):
        app = self.sim.start_app()
        self.plugin.start()
        self.sim.run(self.plugin, 4)
        self.assertTrue(app.transport.connected)
        app.say("hello")
        self.assertFalse(app.gate.is_open)
        # The plugin disappears (scene unloaded) - only the app ticks.
        for _ in range(80):
            self.clock.advance(0.1)
            app.tick()
        self.assertFalse(app.transport.connected)
        self.assertTrue(app.gate.is_open, "mic not muted for a body that is gone")
        inbox_before = len(list(self.plugin.inbox.glob("*.json")))
        for _ in range(50):
            self.clock.advance(0.1)
            app.tick()
        self.assertEqual(len(list(self.plugin.inbox.glob("*.json"))), inbox_before, "no heartbeats pile up")
        # Back: a fresh plugin start clears the stale inbox and connects again.
        self.plugin.start()
        self.sim.run(self.plugin, 5)
        self.assertTrue(app.transport.connected)
        self.assertEqual(self.plugin.status, "verbunden")
        self.assertFalse([m for m in self.plugin.received[-20:] if m.get("type") == "speak"],
                         "no replay of the old speech")


class SpeakCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.http = FakeHttp()

    def tearDown(self):
        self.tmp.cleanup()

    def _tts(self, request):
        body = json.loads(request.data)
        n = 24000 * max(1, len(body["text"]) // 10)  # 1 s of 24 kHz audio per 10 characters
        return FakeResponse(b"\x01\x00" * n, "audio/pcm")

    def test_streamed_answer_is_spoken_sentence_by_sentence(self):
        lines: queue.Queue = queue.Queue()
        self.http.route("/responses", lambda r: FakeResponse(content_type="text/event-stream", lines=lines))
        self.http.route("/tts", self._tts)
        sim = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": KEY}, background=True)
        cfg_path = settings_file.settings_path(self.tmp.name)
        sim.start_app().shutdown()  # creates config.json
        data = json.loads(cfg_path.read_text())
        data["engines"] = {"stt": "null", "llm": "xai", "tts": "xai"}
        cfg_path.write_text(json.dumps(data))
        app = sim.start_app()
        self.assertEqual(app.engine_set.active_names, {"stt": "null", "llm": "xai", "tts": "xai"})
        plugin = FakePlugin(Path(self.tmp.name), self.clock, mode="chain")
        plugin.start()
        plugin.ui["engines"] = {"stt": "null", "llm": "xai", "tts": "xai"}
        sim.run(plugin, 3)

        app.handle_user_text("Hallo, wer bist du?")
        stream = text_stream(["<<happy nod>> Hallo! Ich bin Anna, ", "schön dich zu sehen. ",
                              "Wie geht es dir heute?"])
        chunks = stream.split(b"\n")
        first_half = chunks[:6]  # response.created + the first text delta (3 lines per event)
        for c in first_half:
            lines.put(c + b"\n")
        # The first sentence is spoken while the model is still writing.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not sim.sent(plugin, "speak"):
            sim.run(plugin, 0.1)
            time.sleep(0.01)
        speaks = sim.sent(plugin, "speak")
        self.assertEqual([s["text"] for s in speaks], ["Hallo!"], "TTS starts on the first sentence")
        for c in chunks[6:]:
            lines.put(c + b"\n")
        lines.put(None)
        self.assertTrue(app.wait_turns())
        sim.run(plugin, 1)
        speaks = sim.sent(plugin, "speak")
        self.assertEqual([s["text"] for s in speaks],
                         ["Hallo!", "Ich bin Anna, schön dich zu sehen.", "Wie geht es dir heute?"])
        expr = sim.sent(plugin, "expression")
        self.assertEqual(expr[0]["name"], "happy")
        self.assertEqual(sim.sent(plugin, "gesture")[0]["name"], "nod")
        for s in speaks:
            with wave.open(str(Path(self.tmp.name) / s["audio"]), "rb") as w:
                self.assertEqual(w.getframerate(), 24000)
                self.assertAlmostEqual(w.getnframes() / 24000, s["duration"], places=2)

        # The plugin plays them in order; the echo gate keeps the mic closed meanwhile.
        self.assertFalse(app.gate.is_open)
        sim.run(plugin, 10)
        ended = [e for e in plugin.speech_events if e[0] == "ended"]
        self.assertEqual(len(ended), 3)
        self.assertTrue(app.gate.is_open, "mic open again after the last sentence + tail")

        # The persona went out once; the second turn continues the conversation.
        first = json.loads(self.http.requests[0].data)
        self.assertTrue(first["stream"])
        self.assertIn("instructions", first)
        self.assertEqual(self.http.requests[0].get_header("Authorization"), f"Bearer {KEY}")
        self.http.route("/responses", lambda r: FakeResponse(text_stream(["Gut."], "resp-2"),
                                                             "text/event-stream"))
        app.handle_user_text("Und jetzt?")
        self.assertTrue(app.wait_turns())
        llm_calls = [json.loads(r.data) for r in self.http.requests if r.full_url.endswith("/responses")]
        self.assertEqual(llm_calls[-1]["previous_response_id"], "resp-1")
        self.assertNotIn("instructions", llm_calls[-1])

    def test_ptt_barge_in_cancels_the_answer(self):
        lines: queue.Queue = queue.Queue()
        self.http.route("/responses", lambda r: FakeResponse(content_type="text/event-stream", lines=lines))
        self.http.route("/tts", self._tts)
        sim = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": KEY}, background=True)
        sim.start_app().shutdown()
        cfg_path = settings_file.settings_path(self.tmp.name)
        data = json.loads(cfg_path.read_text())
        data["engines"] = {"stt": "null", "llm": "xai", "tts": "xai"}
        data["mic"]["mode"] = "ptt"
        cfg_path.write_text(json.dumps(data))
        app = sim.start_app()
        plugin = FakePlugin(Path(self.tmp.name), self.clock, mode="chain")
        plugin.start()
        plugin.seed_from_file()
        sim.run(plugin, 3)
        app.handle_user_text("Erzähl mir eine lange Geschichte.")
        for c in text_stream(["Es war einmal. "]).split(b"\n")[:6]:
            lines.put(c + b"\n")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not sim.sent(plugin, "speak"):
            sim.run(plugin, 0.1)
            time.sleep(0.01)
        plugin.press_ptt(True)  # the user interrupts
        sim.run(plugin, 0.3)
        lines.put(b'data: {"type": "response.output_text.delta", "delta": "Ein Drache kam. Und noch mehr. "}\n\n')
        lines.put(None)
        self.assertTrue(app.wait_turns())
        sim.run(plugin, 1)
        self.assertEqual([s["text"] for s in sim.sent(plugin, "speak")], ["Es war einmal."],
                         "nothing after the barge-in")
        self.assertTrue(sim.sent(plugin, "stop_speaking"))


if __name__ == "__main__":
    unittest.main()
