"""Version 27: emotions for the face without the AI's help (fallback from the words, fade to neutral, listening)."""
from __future__ import annotations

import json
import unittest

from aibody_companion import body_tools, emotion, settings_file
from tests.fakes import FakeHttp, FakeResponse, text_stream
from tests.test_plugin_menu import ROOT, method_body, source
from tests.test_realtime import RealtimeSim

HAVE = ["neutral", "happy", "sad", "thinking", "listening"]


class ClassifyTests(unittest.TestCase):
    def test_words_to_emotions(self):
        cases = {
            "Das freut mich sehr, haha!": "happy",
            "That is wonderful news.": "happy",
            "Leider kann ich das nicht.": "sad",
            "Unfortunately it is closed.": "sad",
            "Ich bin so wütend darüber.": "angry",
            "Huch, wer war das?": "surprised",
            "Wirklich?! Das ist ja was.": "surprised",
            "Hmm, vielleicht morgen.": "thinking",
            "Let me think about that...": "thinking",
            "The weather is cloudy today.": None,
            "": None,
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(emotion.classify(text), want)

    def test_words_are_not_matched_inside_other_words(self):
        self.assertIsNone(emotion.classify("Der Superlativ und das Hammerwerk"))  # super / hm inside longer words
        self.assertIsNone(emotion.classify("Funktion Fundament"))  # fun inside longer words

    def test_only_expressions_the_plugin_has(self):
        self.assertEqual(emotion.infer_expression("Wie schön, haha!", HAVE), "happy")
        self.assertIsNone(emotion.infer_expression("Ich bin wütend", HAVE), "no angry preset: no change")
        self.assertEqual(emotion.infer_expression("Super", ["Smile", "neutral"]), "Smile", "alias, plugin's spelling")
        self.assertIsNone(emotion.pick_expression("listening", HAVE))

    def test_internal_expressions_are_not_offered_to_the_ai(self):
        self.assertEqual(emotion.offered(HAVE), ["neutral", "happy", "sad", "thinking"])
        lists = body_tools.BodyLists.from_body_info({"expressions": HAVE}, ["neutral"], [])
        self.assertNotIn("listening", lists.expressions)
        schema = body_tools.tools(lists)[0]["parameters"]["properties"]["expression"]["enum"]
        self.assertNotIn("listening", schema)


class DirectorTests(unittest.TestCase):
    def setUp(self):
        self.now = [100.0]
        self.d = emotion.EmotionDirector({}, lambda: self.now[0])

    def test_fallback_once_per_change_and_ai_wins(self):
        self.d.begin_answer()
        self.assertEqual(self.d.for_speech("Das freut mich!", HAVE), ("happy", 0.85, 0.5))
        self.d.note_sent("happy")
        self.assertIsNone(self.d.for_speech("Das freut mich noch mehr!", HAVE), "same face: nothing to send")
        self.assertIsNone(self.d.for_speech("Es ist Dienstag.", HAVE), "no emotion in the words: no change")
        self.assertEqual(self.d.for_speech("Leider nicht.", HAVE)[0], "sad")
        self.d.begin_answer()
        self.d.note_ai_expression()
        self.assertIsNone(self.d.for_speech("Leider nicht.", HAVE), "the AI chose a face in this answer")
        self.d.begin_answer()
        self.assertEqual(self.d.for_speech("Leider nicht.", HAVE)[0], "sad", "a new answer starts without the AI's choice")

    def test_fallback_can_be_switched_off(self):
        self.d.configure({"fallback": False})
        self.d.begin_answer()
        self.assertIsNone(self.d.for_speech("Das freut mich!", HAVE))

    def test_fade_waits_for_silence_and_happens_once(self):
        self.d.note_sent("happy")
        self.assertFalse(self.d.fade_due(False))
        self.now[0] += 5.9
        self.assertFalse(self.d.fade_due(False))
        self.now[0] += 0.2
        self.assertTrue(self.d.fade_due(False))
        self.d.note_sent("neutral")
        self.now[0] += 60
        self.assertFalse(self.d.fade_due(False), "neutral already: nothing to fade")

    def test_busy_keeps_the_face_and_restarts_the_wait(self):
        self.d.note_sent("sad")
        self.now[0] += 30
        self.assertFalse(self.d.fade_due(True), "still speaking / listening")
        self.now[0] += 5
        self.assertFalse(self.d.fade_due(False))
        self.now[0] += 2
        self.assertTrue(self.d.fade_due(False))

    def test_fade_can_be_switched_off(self):
        self.d.configure({"fade": False})
        self.d.note_sent("happy")
        self.now[0] += 600
        self.assertFalse(self.d.fade_due(False))

    def test_listening_on_the_rising_edge_only_and_only_if_available(self):
        self.assertEqual(self.d.user_speech(True, HAVE), ("listening", 1.0, 0.7))
        self.d.note_sent("listening")
        self.assertIsNone(self.d.user_speech(True, HAVE), "still talking")
        self.assertIsNone(self.d.user_speech(False, HAVE))
        self.d.note_sent("neutral")
        self.assertIsNone(self.d.user_speech(True, ["neutral", "happy"]), "an older plugin has no such preset")
        self.d.user_speech(False, HAVE)
        self.d.note_sent("happy")
        self.assertIsNone(self.d.user_speech(True, HAVE), "does not replace a face that is shown")

    def test_listening_brows_go_down_when_the_answer_has_no_emotion(self):
        self.d.note_sent("listening")
        self.d.begin_answer()
        self.assertEqual(self.d.for_speech("Es ist Dienstag.", HAVE), ("neutral", 1.0, 0.7))


class ConfigTests(unittest.TestCase):
    def test_keys_and_ranges(self):
        cfg = settings_file.DEFAULTS["ai"]["emotion"]
        self.assertEqual(cfg, {"fallback": True, "fade": True, "fade_after_s": 6.0, "fade_seconds": 2.5, "listening": True})
        data, errors = settings_file.validate({"ai": {"emotion": {"fade_after_s": "500", "fallback": "false"}}})
        self.assertEqual(errors, [])
        self.assertEqual(data["ai"]["emotion"]["fade_after_s"], 120.0)
        self.assertIs(data["ai"]["emotion"]["fallback"], False)

    def test_plugin_has_the_listening_preset(self):
        expr = source("ExpressionController.cs")
        self.assertIn('_presets["listening"] = Preset("Brow Inner Up"', expr)
        # only morphs the other presets use (evidenced names, no new morph name)
        self.assertIn('"Mouth Smile Simple"', method_body(expr, "private void LoadDefaults()"))


class EmotionFlowTests(RealtimeSim):
    def chain(self, answers, mode="chain"):
        http = FakeHttp()
        http.route("/responses", lambda r: FakeResponse(answers.pop(0), "text/event-stream"))
        http.route("/tts", lambda r: FakeResponse(b"\x01\x00" * 24000, "audio/pcm"))
        self.http = http
        self.start(mode=mode, http=http, ai={"proactive": {"idle_seconds": 0}})
        self.plugin.ui["engines"] = {"stt": "null", "llm": "xai", "tts": "xai"}
        self.pump(lambda: bool(self.plugin.app_alive))

    def ask(self, text="Hallo"):
        self.app.handle_user_text(text)
        self.sim.run(self.plugin, 0.5)
        self.assertTrue(self.app.wait_turns())
        self.sim.run(self.plugin, 0.5)

    def expressions(self):
        return [(m["name"], m.get("intensity"), m.get("blend")) for m in self.sim.sent(self.plugin, "expression")]

    def test_the_face_follows_the_words_before_the_speech(self):
        self.chain([text_stream(["Haha, das freut mich sehr! ", "Leider muss ich bald gehen."], "r1")])
        self.ask()
        names = [e[0] for e in self.expressions()]
        self.assertEqual(names, ["happy", "sad"])
        order = [m["type"] for m in self.plugin.received if m["type"] in ("expression", "speak")]
        self.assertEqual(order, ["expression", "speak", "expression", "speak"], "the face first, then the voice")

    def test_the_ais_own_expression_wins(self):
        self.chain([text_stream(["<<sad>> Haha, das freut mich sehr!"], "r1")])
        self.ask()
        self.assertEqual([e[0] for e in self.expressions()], ["sad"], "tag from the AI only, no fallback")

    def test_no_emotion_in_the_words_no_expression(self):
        self.chain([text_stream(["Heute ist Donnerstag."], "r1")])
        self.ask()
        self.assertEqual(self.expressions(), [])

    def test_simple_qa_mode_is_speech_only(self):
        self.chain([text_stream(["Haha, das freut mich sehr!"], "r1")], mode="qa")
        self.ask()
        self.assertEqual(self.expressions(), [])

    def test_fade_to_neutral_after_the_speech(self):
        self.chain([text_stream(["Haha, das freut mich sehr!"], "r1")])
        self.ask()
        self.assertEqual([e[0] for e in self.expressions()], ["happy"])
        self.sim.run(self.plugin, 4)   # speech plays (1 s) and the wait (6 s) starts at its end
        self.assertEqual([e[0] for e in self.expressions()], ["happy"], "not yet")
        self.sim.run(self.plugin, 6)
        got = self.expressions()
        self.assertEqual([e[0] for e in got], ["happy", "neutral"])
        self.assertEqual(got[1][2], 2.5, "blended over fade_seconds")
        self.sim.run(self.plugin, 30)
        self.assertEqual(len(self.expressions()), 2, "once")

    def test_listening_brows_while_the_user_talks(self):
        self.chain([text_stream(["Okay."], "r1")])
        self.app.input.ptt_active = True
        self.sim.run(self.plugin, 0.5)
        self.assertEqual([e[0] for e in self.expressions()], ["listening"])
        self.sim.run(self.plugin, 20)
        self.assertEqual([e[0] for e in self.expressions()], ["listening"], "kept while the user talks")
        self.app.input.ptt_active = False
        self.sim.run(self.plugin, 8)
        self.assertEqual([e[0] for e in self.expressions()], ["listening", "neutral"])

    def test_an_older_plugin_without_the_preset_gets_no_listening(self):
        self.chain([text_stream(["Okay."], "r1")])
        self.plugin.expressions = ["neutral", "happy"]
        self.sim.run(self.plugin, 3)
        self.app.input.ptt_active = True
        self.sim.run(self.plugin, 1)
        self.assertEqual(self.expressions(), [])


if __name__ == "__main__":
    unittest.main()
