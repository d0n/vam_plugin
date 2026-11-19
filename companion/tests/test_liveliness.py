"""Version 26: natural gaze, blinking and the scene hooks (scene_event). The plugin side is checked on the C#
sources (like the other plugin menu tests), the companion side end to end with the fake plugin."""
from __future__ import annotations

import json
import re
import unittest
from datetime import timedelta

from aibody_companion import protocol, settings_file
from aibody_companion.pipeline import context
from tests import fakes
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
        self.assertEqual(settings_file.DEFAULTS["body"]["blink_control"], False)
        data, errors = settings_file.validate({"ai": {"scene_events": {"enabled": "false"}}, "body": {"blink_control": "true"}})
        self.assertEqual(errors, [])
        self.assertEqual((data["ai"]["scene_events"]["enabled"], data["body"]["blink_control"]), (False, True))
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
    def setUp(self):
        self.gaze = source("GazeController.cs")
        self.blink = source("BlinkController.cs")
        self.body = source("Body.cs")

    def test_blink_controller_is_part_of_the_one_cslist(self):
        lines = (ROOT / "src/AIBody/AIBody.cslist").read_text(encoding="utf-8").split()
        self.assertIn("BlinkController.cs", lines)
        self.assertEqual(sum(1 for f in (ROOT / "src/AIBody").glob("*.cslist")), 1)

    def test_natural_gaze(self):
        self.assertIn('KeyNatural = "natural"', self.gaze)
        natural = method_body(self.gaze, "private bool NaturalPoint(float dt, out Vector3 point, out string described)")
        for needle in ("FindClient()", "CameraPoint(", "StartAway(", "_natUserWas", "Vector3.Cross(", "OnShift"):
            self.assertIn(needle, natural)
        # thinking = the user stopped, the AI has not started
        self.assertRegex(natural, r"_natUserWas && !_userSpeaking && !_aiSpeaking")
        # natural replaces "follows speaker" instead of fighting it
        self.assertIn("_defaultKey != KeyNatural", method_body(self.gaze, "public void Update(float dt, bool aiSpeaking, bool userSpeaking)"))
        # the same undo as every other gaze: Take saves, Release restores (still used by natural)
        self.assertIn("TargetPoint(key, dt, out point, out described)", self.gaze)
        self.assertIn("KeyNatural", self.body)
        self.assertIn("Natural (looks around)", self.body)

    def test_life_gaze_is_detected_like_glance(self):
        other = method_body(self.gaze, "private string FindOtherEyePlugin()")
        self.assertIn('EndsWith("Glance")', other)
        self.assertIn('IndexOf("MacGruber") >= 0 && ids[i].EndsWith("Gaze")', other)
        blink_other = method_body(self.blink, "private string FindOtherBlinkPlugin()")
        self.assertIn('IndexOf("MacGruber") >= 0 && ids[i].EndsWith("Eyes")', blink_other)
        self.assertIn('EndsWith("Glance")', blink_other)

    def test_blink_uses_only_the_evidenced_calls_and_always_restores(self):
        for needle in ('GetStorableByID("EyelidControl")', 'GetBoolJSONParam("blinkEnabled")', '"Eyes Closed"',
                       "Mathf.SmoothStep", "_autoBlink.val = false", "morphValue"):
            self.assertIn(needle, self.blink)
        release = method_body(self.blink, "public void Release()")
        self.assertIn("_autoBlink.val = _autoWas", release)
        self.assertIn("_morph.morphValue = _baseValue", release)
        update = method_body(self.blink, "public void Update(float dt, bool speaking)")
        self.assertIn("_autoBlink.val", update[update.index("else if (_autoBlink.val)"):], "someone switched auto blink on: give up")
        self.assertIn("_yielded = true", update)
        # off by default: VaM blinks as before
        self.assertIn('new JSONStorableBool("Blink control", false', self.body)
        self.assertIn("RestoreNow", method_body(self.body, "public void Restore()"))
        self.assertIn("_blinkBroken = true", self.body, "a blink error stops only the blinking")

    def test_blink_menu_and_settings(self):
        tab = method_body(self.body, "public void BuildCharacterTab(UiPage page)")
        self.assertIn("page.Toggle(_blinkJson)", tab)
        self.assertIn('"blink_control"', method_body(self.body, "public void WriteSettings(JSONClass root)"))
        self.assertIn('"blink_control"', method_body(self.body, "public void ApplySettings(JSONClass root)"))
        info = method_body(self.body, "public string GazeInfoText()")
        for text in ("Blink control: AIBody switches VaM's automatic blinking off", "Blinking now: "):
            self.assertIn(text, info)

    def test_scene_hooks(self):
        hooks = method_body(self.body, "private void CreateSceneHooks()")
        for name in ('"AI speaking"', '"User speaking"', '"Scene event"', '"Look at client"', '"Look at camera"',
                     '"Look straight ahead"', '"Look away"', '"Gaze back to default"', '"Blink now"'):
            self.assertIn(name, hooks)
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
        for text in (self.blink, self.gaze, self.body):
            self.assertNotRegex(text, r"UnityWebRequest|System\.IO|\bProcess\b")


class VersionTests(unittest.TestCase):
    def test_new_menu_texts_are_plain_english_without_markup_noise(self):
        info = method_body(source("Body.cs"), "public string GazeInfoText()")
        self.assertNotRegex(info, r"TODO|FIXME")
        self.assertTrue(re.search(r"Natural \(looks around\)", info))


if __name__ == "__main__":
    unittest.main()
