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


def persons(**slots):
    return [{"slot": slot, "atom": atom, "plugin_version": "0.4.0"} for slot, atom in slots.items()]


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

    def test_slot_envelope_field(self):
        self.assertEqual(protocol.validate_command({"type": "speak", "audio": "a.wav", "slot": "person2"}), [])
        self.assertTrue(protocol.validate_command({"type": "speak", "audio": "a.wav", "slot": "person3"}))
        self.assertTrue(protocol.validate_command({"type": "speak", "audio": "a.wav", "atom": ""}))
        self.assertTrue(protocol.validate_command({"type": "mic_level", "rms": 0.1, "slot": "person1"}))

    def test_body_commands_always_carry_a_slot(self):
        self.c.say("hi")
        self.assertEqual(self.t.sent[-1]["slot"], "person1")
        self.assertNotIn("atom", self.t.sent[-1])

    def test_session_default_slot_is_used(self):
        self.feed(evt("ready", role="session", persons=persons(person1="Person", person2="Person#2"),
                      default_slot="person2"))
        self.assertEqual(self.c.target_slot, "person2")
        self.c.say("hi")
        speak = self.t.sent[-1]
        self.assertEqual((speak["type"], speak["slot"]), ("speak", "person2"))
        self.assertTrue(speak["audio"].startswith("Saves/PluginData/AIBody/default/audio/"))

    def test_config_slot_wins_and_never_falls_back(self):
        self.cfg.default_slot = "person2"
        self.feed(evt("heartbeat", role="session", persons=persons(person1="Person", person2="Person#2"),
                      default_slot="person1"))
        self.assertEqual(self.c.target_slot, "person2")
        # character 2 leaves the scene: commands stay addressed to person2 (Session will refuse them)
        self.feed(evt("persons", persons=persons(person1="Person"), default_slot="person1"))
        self.assertEqual(self.c.target_slot, "person2")
        self.c.say("hi")
        self.assertEqual(self.t.sent[-1]["slot"], "person2")
        self.assertEqual(sorted(self.c.persons), ["person1"])

    def test_explicit_slot_per_turn(self):
        self.c.handle_user_text("Hallo", slot="person2")
        cmds = [x for x in self.t.sent if x["type"] in protocol.BODY_COMMANDS]
        self.assertTrue(cmds)
        self.assertEqual({x["slot"] for x in cmds}, {"person2"})

    def test_conflicts_and_person_status_are_tracked(self):
        self.feed(evt("persons", persons=persons(person2="Person#2"), default_slot="person1",
                      conflicts=[{"slot": "person1", "atoms": ["Person", "Person#3"]}]))
        self.assertEqual(self.c.conflicts, {"person1": ["Person", "Person#3"]})
        self.feed(evt("person_status", slot="person2", atom="Person#2", speaking=True))
        self.assertTrue(self.c.persons["person2"]["speaking"])
        self.assertEqual(self.c.persons["person2"]["atom"], "Person#2")
        self.assertTrue(protocol.validate_event({"type": "person_status", "atom": "Person"}))

    def test_slot_taken_by_another_atom_drops_stale_status(self):
        self.feed(evt("persons", persons=persons(person1="Person")))
        self.feed(evt("person_status", slot="person1", atom="Person", speaking=True))
        self.feed(evt("persons", persons=persons(person1="Other")))
        self.assertNotIn("speaking", self.c.persons["person1"])

    def test_ptt_stops_every_character(self):
        self.feed(evt("config", mic={"mode": "ptt"}))
        self.feed(evt("persons", persons=persons(person1="Person", person2="Person#2")))
        self.c.say("hi")
        self.c.handle_ptt(True)
        stops = [x["slot"] for x in self.t.sent if x["type"] == "stop_speaking"]
        self.assertEqual(sorted(stops), ["person1", "person2"])

    def test_typed_line_slot_prefix(self):
        from aibody_companion.cli import parse_typed_line
        self.assertEqual(parse_typed_line("@person2 hallo du"), ("person2", "hallo du"))
        self.assertEqual(parse_typed_line("hallo"), (None, "hallo"))

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

    def test_routing_errors_open_the_gate(self):
        for code in sorted(protocol.ROUTING_ERRORS):
            uid = self.c.say("hi")
            self.assertFalse(self.c.gate.is_open, code)
            self.feed(evt("error", reply_to=uid, code=code, slot="person2", message="not delivered"))
            self.assertTrue(self.c.gate.is_open, code)

    def test_config_validates_slot(self):
        self.assertTrue(Config(vam_root=self.tmp.name, default_slot="Person").validate())
        self.assertEqual(Config(vam_root=self.tmp.name, default_slot="person2").validate(), [])


if __name__ == "__main__":
    unittest.main()
