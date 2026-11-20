"""Version 26: natural gaze, blinking and the scene hooks (scene_event). The plugin side is checked on the C#
sources (like the other plugin menu tests), the companion side end to end with the fake plugin."""
from __future__ import annotations

import json
import unittest

from aibody_companion import protocol, settings_file
from aibody_companion.pipeline import context
from tests.fakes import FakeHttp, FakeResponse, text_stream
from tests.test_plugin_menu import ROOT, method_body, source
from tests.test_realtime import RealtimeSim


class SceneEventProtocolTests(unittest.TestCase):
    def test_event_is_known_and_validated(self):
        self.assertIn("scene_event", protocol.EVENTS)
        ok = {"v": 3, "type": "scene_event", "id": "e1", "ts": 1.0, "text": "the door opened"}
        self.assertEqual(protocol.validate_event(ok), [])
        for bad in ("", "   ", None, 5):
            with self.subTest(bad=bad):
                self.assertTrue(protocol.validate_event({**ok, "text": bad}))
        schema = json.loads((ROOT / "protocol/schema/event.schema.json").read_text(encoding="utf-8"))
        self.assertIn("scene_event", schema["properties"]["type"]["enum"])
        self.assertIn("text", schema["properties"])

    def test_text_is_cleaned_and_limited(self):
        self.assertEqual(context.clean_scene_event("  a\n\tdoor\x00 opened  "), "a door opened")
        self.assertEqual(len(context.clean_scene_event("x" * 1000)), context.SCENE_EVENT_MAX_CHARS)
        self.assertEqual(context.clean_scene_event(None), "")
        self.assertEqual(context.clean_scene_event("\n\x01"), "")

    def test_prompt_placeholder_is_replaced_without_str_format(self):
        note = context.scene_event_text("Event: {event}. Say {hi}.", "a {brace}", fakes_now(), None)
        self.assertIn("Event: a {brace}. Say {hi}.", note)
        self.assertIn("[App note:", note)
        default = context.scene_event_text("", "bell rang", fakes_now(), None)
        self.assertIn("bell rang", default)
        self.assertIn("[silent]", default)

    def test_config_keys(self):
        cfg = settings_file.DEFAULTS["ai"]["scene_events"]
        self.assertEqual(cfg["enabled"], True)
        self.assertIn("{event}", cfg["prompt"])
        self.assertNotIn("blink_control", settings_file.DEFAULTS["body"])   # removed with the blink control (20.11.2026)
        data, errors = settings_file.validate({"ai": {"scene_events": {"enabled": "false"}}})
        self.assertEqual(errors, [])
        self.assertEqual(data["ai"]["scene_events"]["enabled"], False)
        # the keys the plugin owns stay as they are
        self.assertIn("idle_seconds", settings_file.DEFAULTS["ai"]["proactive"])


def fakes_now():
    from tests.test_realtime import NOW
    return NOW


class SceneEventFlowTests(RealtimeSim):
    def chain(self, answers, ai=None, mode="chain"):
        http = FakeHttp()
        http.route("/responses", lambda r: FakeResponse(answers.pop(0), "text/event-stream"))
        http.route("/tts", lambda r: FakeResponse(b"\x01\x00" * 24000, "audio/pcm"))
        self.http = http
        self.start(mode=mode, http=http, ai=ai or {"proactive": {"idle_seconds": 0}})
        self.plugin.ui["engines"] = {"stt": "null", "llm": "xai", "tts": "xai"}
        self.pump(lambda: bool(self.plugin.app_alive))

    def llm(self):
        return [json.loads(r.data) for r in self.http.requests if r.full_url.endswith("/responses")]

    def test_event_makes_the_ai_react(self):
        self.chain([text_stream(["Huch, wer war das?"], "resp-1")])
        self.plugin.send("scene_event", text="The door opened")
        self.sim.run(self.plugin, 1)
        self.assertTrue(self.app.wait_turns())
        self.sim.run(self.plugin, 1)
        note = self.llm()[0]["input"][0]["content"]
        self.assertIn("[App note:", note)
        self.assertIn("The door opened", note)
        self.assertEqual(self.speaks()[-1]["text"], "Huch, wer war das?")
        self.assertEqual(self.app.history, [{"role": "assistant", "content": "Huch, wer war das?"}],
                         "the note itself is not part of the history, like a nudge")

    def test_silent_answer_is_not_spoken(self):
        self.chain([text_stream(["[silent]"], "resp-1")])
        self.plugin.send("scene_event", text="a light flickered")
        self.sim.run(self.plugin, 1)
        self.assertTrue(self.app.wait_turns())
        self.sim.run(self.plugin, 1)
        self.assertEqual(len(self.llm()), 1)
        self.assertEqual(self.speaks(), [])

    def test_disabled_and_qa_mode_ignore_events(self):
        self.chain([], ai={"proactive": {"idle_seconds": 0}, "scene_events": {"enabled": False}})
        self.plugin.send("scene_event", text="ignored")
        self.sim.run(self.plugin, 2)
        self.assertEqual(self.llm(), [])
        self.tearDown()
        self.setUp()
        self.chain([], mode="qa")
        self.plugin.send("scene_event", text="also ignored")
        self.sim.run(self.plugin, 2)
        self.assertEqual(self.llm(), [], "simple Q&A: the AI speaks only when asked")

    def test_events_that_wait_are_combined_and_old_ones_dropped(self):
        self.chain([text_stream(["Zwei Dinge!"], "resp-1")])
        self.app._busy.set()  # the AI is busy with something else
        self.plugin.send("scene_event", text="first")
        self.plugin.send("scene_event", text="second")
        self.sim.run(self.plugin, 1)
        self.assertEqual(self.llm(), [])
        self.app._busy.clear()
        self.sim.run(self.plugin, 1)
        self.assertTrue(self.app.wait_turns())
        note = self.llm()[0]["input"][0]["content"]
        self.assertIn("first; second", note)
        # an event that waited too long is dropped
        self.app._busy.set()
        self.plugin.send("scene_event", text="stale")
        self.sim.run(self.plugin, 40)
        self.app._busy.clear()
        self.sim.run(self.plugin, 2)
        self.assertEqual(len(self.llm()), 1)

    def test_long_text_is_cut(self):
        self.chain([text_stream(["Okay."], "resp-1")])
        self.plugin.send("scene_event", text="x" * 5000)
        self.sim.run(self.plugin, 1)
        self.assertTrue(self.app.wait_turns())
        note = self.llm()[0]["input"][0]["content"]
        self.assertLess(len(note), 1200)


class PluginLivelinessSourceTests(unittest.TestCase):
    """Gaze and blink control were removed after version 36 (Leon, 20.11.2026): the eyes belong to VaM.
    The scene hooks stay (without the Look / Gaze / Blink actions)."""

    def setUp(self):
        self.body = source("Body.cs")

    def test_scene_hooks(self):
        hooks = method_body(self.body, "private void CreateSceneHooks()")
        for name in ('"AI speaking"', '"User speaking"', '"Scene event"'):
            self.assertIn(name, hooks)
        for gone in ('"Look at client"', '"Look at camera"', '"Look straight ahead"', '"Look away"',
                     '"Gaze back to default"', '"Blink now"'):
            self.assertNotIn(gone, self.body)
        # not saved with the scene: a loaded scene must not replay an event or a stale speaking state
        self.assertGreaterEqual(hooks.count("isStorable = false"), 3)
        self.assertGreaterEqual(hooks.count("isRestorable = false"), 3)
        self.assertIn("RegisterString(_sceneEventJson)", hooks)
        event = method_body(self.body, "private void OnSceneEventSet(string v)")
        self.assertIn("Protocol.EvtSceneEvent", event)
        self.assertIn('_sceneEventJson.val = ""', event)
        self.assertIn("finally", event)
        self.assertIn('EvtSceneEvent = "scene_event"', source("Protocol.cs"))
        actions = method_body(self.body, "private void RegisterSceneActions()")
        self.assertIn('"Expression: "', actions)
        self.assertIn('"Gesture: "', actions)
        # closures capture a per-iteration copy (old compilers share the foreach variable)
        self.assertIn("string expression = name;", actions)
        self.assertIn("string gesture = gestures[i];", actions)

    def test_no_new_network_or_file_apis(self):
        self.assertNotRegex(self.body, r"UnityWebRequest|System\.IO|\bProcess\b")


if __name__ == "__main__":
    unittest.main()
