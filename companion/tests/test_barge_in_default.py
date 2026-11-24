"""Voice barge-in on by default, chain and realtime mode, echo protection always on (Don, 22.11.2026 call).

The menu toggle "Voice barge-in (headphones)" now writes ai.barge_in.enabled (default true) instead of the old
ai.realtime.send_while_speaking (which streamed the raw mic to the server while the body spoke, so with speakers she
interrupted herself). While the body speaks the mic stays closed for the AI; the loudness rule (audio/barge.py: louder
than the learned echo of her own voice for min_ms) stops her: stop_speaking, the running answer is cancelled (realtime:
response.cancel + conversation.item.truncate) and the user's words are processed."""
from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion.audio.echo_gate import EchoGate
from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline.engines import EngineSet
from tests.test_local_audio import EchoLlm, FakeTransport, HeardStt, ToneTts, tone, wobbly
from tests.test_realtime import RealtimeSim
from tests.test_realtime import tone as pcm_tone
from tests.fakes import FakeClock

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class DefaultsTests(unittest.TestCase):
    def test_on_by_default(self):
        ai = settings_file.defaults()["ai"]
        self.assertTrue(ai["barge_in"]["enabled"])
        self.assertNotIn("send_while_speaking", ai["realtime"])

    def test_old_send_while_speaking_is_ignored_without_a_warning(self):
        data = settings_file.defaults()
        data["ai"]["realtime"]["send_while_speaking"] = True
        merged, errors = settings_file.validate(data)
        self.assertEqual(errors, [])
        self.assertNotIn("send_while_speaking", merged["ai"]["realtime"])
        self.assertIn(("ai", "realtime", "send_while_speaking"), settings_file.LEGACY_KEYS)

    def test_no_raw_mic_while_speaking_anywhere(self):
        for name in ("realtime_voice.py", "orchestrator.py"):
            text = (ROOT / "companion" / "aibody_companion" / name).read_text(encoding="utf-8")
            self.assertNotIn("send_while_speaking", text, name)


class ChainModeTests(unittest.TestCase):
    def make(self, ai=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        cfg = Config(vam_root=self.tmp.name, mic={"mode": "vad"})
        cfg.audio_dir.mkdir(parents=True, exist_ok=True)
        self.transport = FakeTransport()
        engines = EngineSet(ai if ai is not None else settings_file.defaults()["ai"], env={})
        return Companion(cfg, self.transport, HeardStt(), EchoLlm(), ToneTts(), gate=EchoGate(clock=self.clock),
                         clock=self.clock, engines=engines)

    def speak(self, app):
        app.gate.on_speak_sent("u1", 10.0)
        app.gate.on_event({"type": "speech_started", "utterance_id": "u1", "duration": 10})

    def test_default_config_has_the_rule(self):
        app = self.make()
        self.assertIsNotNone(app.input.barge)

    def test_her_own_echo_never_interrupts(self):
        app = self.make()
        self.speak(app)
        for i in range(200):  # 6 s of her voice coming back through the speakers, with natural ups and downs
            app.handle_audio_frame(tone(wobbly(0.05, i)))
        self.assertNotIn("stop_speaking", [c["type"] for c in self.transport.sent])

    def test_a_short_loud_word_of_hers_does_not_interrupt(self):
        app = self.make()
        self.speak(app)
        levels = [0.04] * 40 + [0.15] * 10 + [0.04] * 40   # 300 ms emphasis in her sentence
        for level in levels:
            app.handle_audio_frame(tone(level))
        self.assertNotIn("stop_speaking", [c["type"] for c in self.transport.sent])

    def test_the_user_talks_over_her(self):
        app = self.make()
        self.speak(app)
        for i in range(40):
            app.handle_audio_frame(tone(wobbly(0.04, i)))
        for i in range(60):
            app.handle_audio_frame(tone(wobbly(0.2, i)))
        self.assertIn("stop_speaking", [c["type"] for c in self.transport.sent])
        self.assertTrue(app.gate.is_open)

    def test_menu_toggle_switches_it_live(self):
        app = self.make()
        app.apply_ai({"barge_in": {"enabled": False}})
        self.assertIsNone(app.input.barge)
        app.apply_ai({"barge_in": {"enabled": True}})
        self.assertIsNotNone(app.input.barge)


class RealtimeTruncateTests(RealtimeSim):
    def test_voice_barge_in_cancels_and_truncates(self):
        self.start()
        self.connect()
        c = self.server.conn
        c.send({"type": "response.created", "response": {"id": "r1"}})
        c.send({"type": "response.output_audio_transcript.delta", "response_id": "r1", "item_id": "item-a",
                "delta": "Das ist eine lange Geschichte. "})
        c.send({"type": "response.output_audio.delta", "response_id": "r1", "item_id": "item-a",
                "delta": base64.b64encode(pcm_tone(3.0)).decode()})
        self.assertTrue(self.pump(lambda: len(self.speaks()) == 1))
        self.app.voice_barge_in([b"\x00\x00" * 480])
        self.assertTrue(self.server.wait_type("response.cancel"))
        self.assertTrue(self.server.wait_type("conversation.item.truncate"))
        ev = [e for e in self.server.conn.received if e.get("type") == "conversation.item.truncate"][-1]
        self.assertEqual(ev["item_id"], "item-a")
        self.assertEqual(ev["content_index"], 0)
        self.assertLess(ev["audio_end_ms"], 3000)
        self.assertTrue(self.pump(lambda: bool(self.sim.sent(self.plugin, "stop_speaking"))))


class PluginTests(unittest.TestCase):
    def test_toggle_on_by_default_writes_barge_in(self):
        app = source("AppLink.cs")
        self.assertIn('new JSONStorableBool("Voice barge-in (headphones)", true,', app)
        self.assertIn('barge["enabled"].AsBool = _bargeInJson.val;', app)
        self.assertIn('MergeSection(target, ui, "barge_in", "enabled");', app)
        self.assertNotIn('["send_while_speaking"]', app)

    def test_help_text(self):
        mic = source("MicConfig.cs")
        for part in ("echo protection, always on", "<b>Voice barge-in (headphones)</b> (on by default",
                     "all AI modes", "config.json ai.barge_in"):
            self.assertIn(part, mic)
