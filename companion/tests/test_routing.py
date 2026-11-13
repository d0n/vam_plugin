"""Session/Person split: per-atom routing, person tracking, companion heartbeat, engines."""
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
    return {"v": 1, "type": type_, "id": protocol.new_id("evt"), "ts": 0.0, **fields}


def persons(*atoms, default=""):
    return [{"atom": a, "plugin_version": "0.3.0"} for a in atoms], default


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

    def test_atom_envelope_field(self):
        self.assertEqual(protocol.validate_command({"type": "speak", "audio": "a.wav", "atom": "Person#2"}), [])
        self.assertTrue(protocol.validate_command({"type": "speak", "audio": "a.wav", "atom": ""}))
        self.assertTrue(protocol.validate_command({"type": "mic_level", "rms": 0.1, "atom": "Person"}))

    def test_without_persons_atom_is_left_to_the_session(self):
        self.c.say("hi")
        self.assertNotIn("atom", self.t.sent[-1])

    def test_session_default_atom_is_used(self):
        lst, _ = persons("Person", "Person#2")
        self.feed(evt("ready", role="session", persons=lst, default_atom="Person#2"))
        self.assertEqual(self.c.target_atom, "Person#2")
        self.c.say("hi")
        speak = self.t.sent[-1]
        self.assertEqual((speak["type"], speak["atom"]), ("speak", "Person#2"))
        self.assertTrue(speak["audio"].startswith("Saves/PluginData/AIBody/default/audio/"))

    def test_config_default_atom_wins_and_falls_back_when_gone(self):
        self.cfg.default_atom = "Person#2"
        lst, _ = persons("Person", "Person#2")
        self.feed(evt("heartbeat", role="session", persons=lst, default_atom="Person"))
        self.assertEqual(self.c.target_atom, "Person#2")
        lst, _ = persons("Person")
        self.feed(evt("persons", persons=lst, default_atom="Person"))
        self.assertEqual(self.c.target_atom, "Person")
        self.assertEqual(sorted(self.c.persons), ["Person"])

    def test_person_status_is_tracked(self):
        self.feed(evt("person_status", atom="Person", speaking=True, expressions=["happy"]))
        self.assertTrue(self.c.persons["Person"]["speaking"])
        self.assertEqual(self.c.target_atom, "Person")

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

    def test_default_transport_is_file_and_needs_vam_root(self):
        self.assertEqual(Config().transport, "file")
        self.assertTrue(Config().validate())

    def test_no_person_error_opens_the_gate(self):
        uid = self.c.say("hi")
        self.assertFalse(self.c.gate.is_open)
        self.feed(evt("error", reply_to=uid, code="no_person", message="No AIBody Person plugin in the scene"))
        self.assertTrue(self.c.gate.is_open)


if __name__ == "__main__":
    unittest.main()
