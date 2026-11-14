"""Client/Companion plugins: per-atom routing, Companion tracking, companion_heartbeat, engines."""
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
    return {"v": 2, "type": type_, "id": protocol.new_id("evt"), "ts": 0.0, **fields}


def companions(*atoms):
    return [{"atom": atom, "plugin_version": "0.5.0"} for atom in atoms]


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
        self.assertTrue(protocol.validate_command({"type": "speak", "audio": "a.wav", "slot": "person1"}))
        self.assertTrue(protocol.validate_command({"type": "mic_level", "rms": 0.1, "atom": "Person"}))

    def test_protocol_version_2(self):
        self.assertEqual(protocol.make_command("ping")["v"], 2)
        self.assertTrue(protocol.validate_command({"v": 1, "type": "ping"}))

    def test_without_target_the_client_decides(self):
        self.feed(evt("ready", role="client", client="Me", companions=companions("AI", "AI2"), selected_atom="AI2"))
        self.c.say("hi")
        speak = self.t.sent[-1]
        self.assertEqual(speak["type"], "speak")
        self.assertNotIn("atom", speak)  # never guessed from the Companions present
        self.assertTrue(speak["audio"].startswith("Saves/PluginData/AIBody/default/audio/"))
        self.assertEqual(self.c.client_selected_atom, "AI2")

    def test_config_target_atom_is_always_sent(self):
        self.cfg.target_atom = "AI"
        self.feed(evt("companions", companions=companions("Other"), selected_atom=""))
        self.c.say("hi")
        self.assertEqual(self.t.sent[-1]["atom"], "AI")  # even if gone: the Client refuses, no fallback

    def test_explicit_atom_per_turn(self):
        self.c.handle_user_text("Hallo", atom="AI2")
        cmds = [x for x in self.t.sent if x["type"] in protocol.BODY_COMMANDS]
        self.assertTrue(cmds)
        self.assertEqual({x["atom"] for x in cmds}, {"AI2"})

    def test_companions_and_status_are_tracked(self):
        self.feed(evt("companions", companions=companions("AI"), selected_atom=""))
        self.feed(evt("companion_status", atom="AI", speaking=True, client="Me"))
        self.assertTrue(self.c.companions["AI"]["speaking"])
        self.feed(evt("companions", companions=companions(), selected_atom=""))
        self.assertEqual(self.c.companions, {})
        self.assertTrue(protocol.validate_event({"type": "companion_status"}))
        self.assertTrue(protocol.validate_event({"type": "companions"}))

    def test_ptt_stops_every_companion(self):
        self.feed(evt("config", mic={"mode": "ptt"}))
        self.feed(evt("companions", companions=companions("AI", "AI2")))
        self.c.say("hi")
        self.c.handle_ptt(True)
        stops = [x.get("atom") for x in self.t.sent if x["type"] == "stop_speaking"]
        self.assertEqual(sorted(stops), ["AI", "AI2"])

    def test_typed_line_atom_prefix(self):
        from aibody_companion.cli import parse_typed_line
        self.assertEqual(parse_typed_line("@Person#2 hallo du"), ("Person#2", "hallo du"))
        self.assertEqual(parse_typed_line("hallo"), (None, "hallo"))
        self.assertEqual(parse_typed_line("@ hallo"), (None, "@ hallo"))

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
            self.feed(evt("error", reply_to=uid, code=code, atom="AI", message="not delivered"))
            self.assertTrue(self.c.gate.is_open, code)



if __name__ == "__main__":
    unittest.main()
