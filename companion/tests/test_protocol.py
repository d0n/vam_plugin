import json
import unittest
from pathlib import Path

from aibody_companion import protocol

ROOT = Path(__file__).resolve().parents[2]


class ProtocolTests(unittest.TestCase):
    def test_make_command_valid(self):
        cmd = protocol.make_command("expression", name="happy", intensity=0.5)
        self.assertEqual(cmd["type"], "expression")
        self.assertEqual(cmd["v"], 1)
        self.assertTrue(cmd["id"])

    def test_missing_field_rejected(self):
        with self.assertRaises(ValueError):
            protocol.make_command("speak")

    def test_unknown_field_rejected(self):
        self.assertTrue(protocol.validate_command({"type": "ping", "bogus": 1}))

    def test_trigger_needs_action_or_param(self):
        self.assertTrue(protocol.validate_command({"type": "trigger", "storable": "x"}))
        self.assertFalse(protocol.validate_command({"type": "trigger", "storable": "x", "action": "Play"}))

    def test_set_morphs_values_numeric(self):
        self.assertTrue(protocol.validate_command({"type": "set_morphs", "morphs": {"a": "x"}}))
        self.assertFalse(protocol.validate_command({"type": "set_morphs", "morphs": {"a": 0.5}}))

    def test_example_commands_are_valid(self):
        files = sorted((ROOT / "examples" / "commands").glob("*.json"))
        self.assertTrue(files, "no example commands found")
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            for item in items:
                self.assertEqual(protocol.validate_command(item), [], f"{f.name}: {item}")

    def test_schema_lists_same_commands(self):
        schema = json.loads((ROOT / "protocol" / "schema" / "command.schema.json").read_text(encoding="utf-8"))
        names = set(schema["properties"]["type"]["enum"])
        self.assertEqual(names, set(protocol.COMMANDS))

    def test_csharp_lists_same_commands(self):
        source = (ROOT / "src" / "Protocol.cs").read_text(encoding="utf-8")
        for name in protocol.COMMANDS:
            self.assertIn(f'= "{name}";', source, name)

    def test_event_schema_lists_same_events(self):
        schema = json.loads((ROOT / "protocol" / "schema" / "event.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["properties"]["type"]["enum"]), protocol.EVENTS)

    def test_csharp_lists_same_events(self):
        source = (ROOT / "src" / "Protocol.cs").read_text(encoding="utf-8")
        for name in protocol.EVENTS:
            self.assertIn(f'= "{name}";', source, name)

    def test_speak_needs_url_or_audio(self):
        self.assertTrue(protocol.validate_command({"type": "speak", "text": "hi"}))
        self.assertFalse(protocol.validate_command({"type": "speak", "url": "/v1/audio/a.wav"}))
        self.assertFalse(protocol.validate_command({"type": "speak", "audio": "Saves/x.wav"}))

    def test_speak_queue_mode(self):
        self.assertTrue(protocol.validate_command({"type": "speak", "url": "/a.wav", "queue": "later"}))
        self.assertFalse(protocol.validate_command({"type": "speak", "url": "/a.wav", "queue": "interrupt"}))

    def test_mic_feedback_commands(self):
        self.assertTrue(protocol.validate_command({"type": "devices", "devices": "x"}))
        self.assertTrue(protocol.validate_command({"type": "mic_state", "enabled": True}))
        self.assertFalse(protocol.validate_command({"type": "mic_level", "rms": 0.1, "speech": False}))

    def test_validate_event(self):
        self.assertEqual(protocol.validate_event({"type": "config", "mic": {}}), [])
        self.assertTrue(protocol.validate_event({"type": "config"}))
        self.assertTrue(protocol.validate_event({"type": "ptt", "active": "yes"}))
        self.assertTrue(protocol.validate_event({"type": "nope"}))

    def test_example_events_are_valid(self):
        from aibody_companion.audio import MicSettings, apply_mic_config

        files = sorted((ROOT / "examples" / "events").glob("*.json"))
        self.assertTrue(files)
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            for item in data if isinstance(data, list) else [data]:
                self.assertEqual(protocol.validate_event(item), [], f.name)
                if item["type"] == "config":
                    self.assertEqual(apply_mic_config(MicSettings(), item["mic"])[1], [])


if __name__ == "__main__":
    unittest.main()
