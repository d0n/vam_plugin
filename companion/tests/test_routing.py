"""Single AIBody plugin (protocol v3): body commands, body state, companion_heartbeat, engines."""
import tempfile
import unittest
from typing import Any

from aibody_companion import protocol
from aibody_companion.audio import EchoGate
from aibody_companion.config import Config
from aibody_companion.orchestrator import HEARTBEAT_INTERVAL_S, Companion
from aibody_companion.pipeline import EchoLlm, NullStt, ToneTts
from aibody_companion.transport import Transport


class FakeTransport(Transport):
    name = "fake"

    def __init__(self):
        self.sent: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.is_connected = True

    def start(self):
        pass

    def stop(self):
        pass

    def send(self, command):
        self.sent.append(command)

    def poll_events(self):
        events, self.events = self.events, []
        return events

    @property
    def connected(self):
        return self.is_connected

    def types(self):
        return [c["type"] for c in self.sent]


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def evt(type_, **fields):
    return {"v": 3, "type": type_, "id": protocol.new_id("evt"), "ts": 0.0, **fields}


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.t = FakeTransport()
        self.cfg = Config(vam_root=self.tmp.name)
        self.c = Companion(self.cfg, self.t, NullStt(), EchoLlm(), ToneTts(), EchoGate(clock=self.clock),
                           device_lister=lambda: ([], None), clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def feed(self, *events):
        self.t.events.extend(events)
        self.c.process_events()

    def test_no_atom_or_slot_in_v3(self):
        self.assertEqual(protocol.validate_command({"type": "speak", "audio": "a.wav"}), [])
        self.assertTrue(protocol.validate_command({"type": "speak", "audio": "a.wav", "atom": "Person"}))
        self.assertTrue(protocol.validate_command({"type": "speak", "audio": "a.wav", "slot": "person1"}))

    def test_protocol_version_3(self):
        self.assertEqual(protocol.make_command("ping")["v"], 3)
        self.assertTrue(protocol.validate_command({"v": 2, "type": "ping"}))

    def test_speak_goes_to_the_one_body(self):
        self.feed(evt("ready", atom="AI", plugin_version="0.6.0", channel="default", speaking=False))
        self.c.handle_user_text("Hallo")
        cmds = [x for x in self.t.sent if x["type"] in protocol.BODY_COMMANDS]
        self.assertIn("speak", [x["type"] for x in cmds])
        self.assertTrue(all("atom" not in x for x in cmds))
        speak = [x for x in cmds if x["type"] == "speak"][-1]
        self.assertTrue(speak["audio"].startswith("Saves/PluginData/AIBody/default/audio/"))

    def test_body_state_comes_with_heartbeat(self):
        self.feed(evt("heartbeat", atom="AI", speaking=True, expressions=["happy"]))
        self.assertTrue(self.c.body_info["speaking"])
        self.assertEqual(self.c.body_info["atom"], "AI")
        for gone in ("companions", "companion_status", "persons", "person_status"):
            self.assertTrue(protocol.validate_event({"type": gone}), gone)

    def test_ptt_stops_the_body(self):
        self.feed(evt("config", mic={"mode": "ptt"}))
        self.c.say("hi")
        self.c.handle_ptt(True)
        stops = [x for x in self.t.sent if x["type"] == "stop_speaking"]
        self.assertEqual(len(stops), 1)
        self.assertNotIn("atom", stops[0])

    def test_heartbeat_only_while_connected_with_new_session_id(self):
        self.t.is_connected = False
        self.c.tick()
        self.assertNotIn("companion_heartbeat", self.t.types())
        self.t.is_connected = True
        self.c.tick()
        beats = [x for x in self.t.sent if x["type"] == "companion_heartbeat"]
        self.assertEqual(len(beats), 1)
        self.assertEqual(beats[0]["session"], self.c.session_id)
        self.assertEqual(beats[0]["engines_available"]["tts"], ["tone"])
        self.c.tick()
        self.assertEqual(self.t.types().count("companion_heartbeat"), 1)
        self.clock.t += HEARTBEAT_INTERVAL_S
        self.c.tick()
        self.assertEqual(self.t.types().count("companion_heartbeat"), 2)
        other = Companion(self.cfg, FakeTransport(), NullStt(), EchoLlm(), ToneTts())
        self.assertNotEqual(other.session_id, self.c.session_id)

    def test_engines_in_config_are_validated_and_acked(self):
        self.feed(evt("config", mic={}, engines={"stt": "null", "llm": "gpt-9", "tts": "tone"}))
        ack = self.t.sent[-1]
        self.assertEqual(ack["type"], "config_ack")
        self.assertEqual(ack["applied"]["engines"], {"stt": "null", "llm": "echo", "tts": "tone"})
        self.assertTrue(any("gpt-9" in e for e in ack["errors"]))

    def test_config_validate_rejects_unknown_engine(self):
        self.assertTrue(Config(vam_root=self.tmp.name, tts="nope").validate())
        self.assertEqual(Config(vam_root=self.tmp.name).validate(), [])

    def test_vam_root_is_required(self):
        self.assertTrue(Config().validate())
        self.assertFalse(hasattr(Config(), "transport"), "file transport is the only link")

    def test_failed_speak_opens_the_gate(self):
        for code in ("audio_failed", "command_failed"):
            uid = self.c.say("hi")
            self.assertFalse(self.c.gate.is_open, code)
            self.feed(evt("error", reply_to=uid, code=code, message="not played"))
            self.assertTrue(self.c.gate.is_open, code)


if __name__ == "__main__":
    unittest.main()
