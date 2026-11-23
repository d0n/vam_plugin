"""Version 55 (Leon, 23.11.2026, explicit go): mute / unmute the AI by voice (name-independent) and by the menu toggle
"Mute AI (stop talking and listening)" in the tab Config; the companion holds the state, the toggle follows it."""
from __future__ import annotations

import base64
import math
import struct
import unittest
from pathlib import Path

from aibody_companion import protocol, voice_mute

from . import test_pose_commands as pc
from .test_plugin_menu import method_body
from .test_realtime import RealtimeSim, tone

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def frame(loud: bool) -> bytes:
    n = 16000 * 30 // 1000
    return struct.pack(f"<{n}h", *(int(6000 * math.sin(i / 3)) if loud else 0 for i in range(n)))


class PhraseTests(unittest.TestCase):
    MUTE = ["shut up", "Shut up!", "SHUT UP.", "shut-up", "Shutup", "halt's Maul", "Halt\u2019s Maul!", "halts maul",
            "Haltsmaul", "halt das Maul", "halt die Klappe", "Halt deine Klappe!", "sei still", "Sei still, bitte.",
            "seid still"]
    UNMUTE = ["sprich mit mir", "Sprich mit mir!", "sprich wieder mit mir", "speak again", "Speak again.",
              "go ahead talking", "Go ahead, talking!", "go ahead and talk"]
    NOT = ["", "   ", "?!", "hello there", "shut the door", "shut upstairs", "ich halte still", "halt", "maul",
           "sei", "speak", "go ahead", "the clap", "stillness", "sprich", "upshut"]

    def test_every_mute_phrase(self):
        for text in self.MUTE:
            self.assertEqual(voice_mute.detect(text, False), "mute", text)
            self.assertEqual(voice_mute.detect(text, True), "mute", text)

    def test_every_unmute_phrase_counts_only_while_muted(self):
        for text in self.UNMUTE:
            self.assertEqual(voice_mute.detect(text, True), "unmute", text)
            self.assertIsNone(voice_mute.detect(text, False), f"{text}: a normal sentence while not muted")

    def test_inside_a_longer_utterance(self):
        self.assertEqual(voice_mute.detect("Hey Tom, look at this - shut up now, okay?", False), "mute")
        self.assertEqual(voice_mute.detect("Ja ja, halt die Klappe und hör zu", False), "mute")
        self.assertEqual(voice_mute.detect("okay okay, sprich mit mir, bitte", True), "unmute")
        self.assertEqual(voice_mute.detect("well then, go ahead talking again", True), "unmute")

    def test_the_later_command_wins(self):
        self.assertEqual(voice_mute.detect("shut up ... no, speak again", True), "unmute")
        self.assertEqual(voice_mute.detect("speak again - no, shut up", True), "mute")

    def test_no_false_positives(self):
        for text in self.NOT:
            self.assertIsNone(voice_mute.detect(text, False), text)
            self.assertIsNone(voice_mute.detect(text, True), text)

    def test_name_independent(self):
        self.assertNotIn("carina", (ROOT / "companion" / "aibody_companion" / "voice_mute.py").read_text().lower())
        self.assertEqual(voice_mute.detect("Carina, shut up", False), "mute")
        self.assertEqual(voice_mute.detect("Marc, speak again", True), "unmute")


class ChainMuteTests(unittest.TestCase):
    """The chain path (typed and spoken) with the fake xAI: no model request, no speech, no pose while muted."""
    setUp = pc.Chain.setUp
    tearDown = pc.Chain.tearDown
    start = pc.Chain.start
    requests = pc.Chain.requests
    ask = pc.Chain.ask
    poses_sent = pc.Chain.poses_sent

    def speaks(self):
        return self.sim.sent(self.plugin, "speak")

    def test_mute_suppresses_everything_and_unmute_recovers(self):
        self.start()
        self.ask("hello there")
        self.assertEqual(len(self.requests()), 1)
        spoken = len(self.speaks())
        self.assertGreater(spoken, 0)
        stops = len(self.sim.sent(self.plugin, "stop_speaking"))
        self.ask("Ach, halt's Maul!")
        self.assertTrue(self.app.muted)
        self.assertEqual(self.app.mute_by, "voice: mute")
        self.assertGreater(len(self.sim.sent(self.plugin, "stop_speaking")), stops, "stop_speaking at once")
        self.assertTrue(self.plugin.muted, "the menu toggle follows the companion")
        for text in ("what time is it?", "Sit Down", "shut up"):
            self.ask(text)
        self.assertEqual(len(self.requests()), 1, "no AI request while muted (and not for the command)")
        self.assertEqual(len(self.speaks()), spoken, "no speech while muted")
        self.assertEqual(self.poses_sent(), [], "no pose from speech while muted")
        self.ask("okay, go ahead talking")
        self.assertFalse(self.app.muted)
        self.assertFalse(self.plugin.muted)
        self.assertEqual(len(self.requests()), 1, "the unmute command itself is not sent to the AI")
        self.assertEqual(len(self.speaks()), spoken, "silent on unmute")
        self.ask("hello again")
        self.assertEqual(len(self.requests()), 2)
        self.assertGreater(len(self.speaks()), spoken)
        self.ask("Sit Down")
        self.assertEqual(len(self.poses_sent()), 1, "pose commands work again")

    def test_spoken_mute_and_unmute(self):
        self.start()
        for said in ("Shut up!", "how are you", "sprich mit mir", "how are you"):
            self.said[0] = said
            for loud in [True] * 40 + [False] * 30:
                self.app.handle_audio_frame(frame(loud))
            self.sim.run(self.plugin, 4)
            if said == "Shut up!":
                self.assertTrue(self.app.muted)
                self.assertEqual(self.requests(), [])
            if said == "sprich mit mir":
                self.assertFalse(self.app.muted)
                self.assertEqual(self.requests(), [])
        self.assertEqual(len(self.requests()), 1, "only the last question after unmuting is answered")

    def test_menu_toggle_both_ways_and_reset(self):
        self.start()
        self.plugin.set_mute(True)
        self.sim.run(self.plugin, 1)
        self.assertTrue(self.app.muted)
        self.assertEqual(self.app.mute_by, "menu")
        self.ask("hello there")
        self.assertEqual(self.requests(), [])
        self.ask("speak again")  # the voice switches the menu toggle off
        self.assertFalse(self.app.muted)
        self.sim.run(self.plugin, 1)
        self.assertFalse(self.plugin.muted)
        self.ask("sei still")
        self.sim.run(self.plugin, 1)
        self.assertTrue(self.plugin.muted)
        self.plugin.set_mute(False)  # toggle off == unmute (Reset to Default does the same: ResetMute)
        self.sim.run(self.plugin, 1)
        self.assertFalse(self.app.muted)
        self.ask("hello there")
        self.assertEqual(len(self.requests()), 1)

    def test_no_proactive_talking_and_no_scene_events_while_muted(self):
        self.start()
        self.app.set_muted(True, "menu")
        self.app.handle_scene_event({"text": "The door opens"})
        self.assertEqual(len(self.app._scene_events), 0)
        self.app.proactive.due = lambda *a: True  # type: ignore[method-assign]
        self.app._maybe_nudge()
        self.sim.run(self.plugin, 2)
        self.assertEqual(self.requests(), [])

    def test_unmuted_on_every_start_and_in_the_heartbeat(self):
        self.start()
        self.assertFalse(self.app.muted)
        hb = self.sim.sent(self.plugin, "companion_heartbeat")[-1]
        self.assertIs(hb["muted"], False)
        self.app.set_muted(True, "menu")
        self.sim.run(self.plugin, 1)
        hb = self.sim.sent(self.plugin, "companion_heartbeat")[-1]
        self.assertIs(hb["muted"], True)
        self.assertEqual(hb["mute_by"], "menu")
        self.assertEqual(protocol.validate_command(hb), [])
        self.assertEqual(protocol.validate_event({"type": "mute", "muted": "maybe"}), ["mute: 'muted' must be true/false"])
        self.assertEqual(protocol.validate_event({"type": "mute", "muted": "true"}), [])


class RealtimeMuteTests(RealtimeSim):
    def transcript(self, text, item="u1"):
        self.server.conn.send({"type": "input_audio_buffer.speech_stopped", "item_id": item})
        self.server.conn.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": item,
                               "transcript": text})

    def answer(self, rid):
        c = self.server.conn
        c.send({"type": "response.created", "response": {"id": rid}})
        c.send({"type": "response.output_audio_transcript.delta", "response_id": rid, "delta": "Sure thing. "})
        c.send({"type": "response.output_audio.delta", "response_id": rid, "delta": base64.b64encode(tone(1.0)).decode()})
        c.send({"type": "response.done", "response": {"id": rid}})

    def test_realtime_mute_cancels_answers_until_unmuted(self):
        self.start()
        self.connect()
        self.transcript("Shut up!")
        self.assertTrue(self.pump(lambda: self.app.muted))
        self.assertTrue(self.pump(lambda: bool(self.sim.sent(self.plugin, "stop_speaking"))))
        self.answer("r1")
        self.assertTrue(self.pump(lambda: "response.cancel" in self.server.conn.types()))
        self.transcript("what is the weather", item="u2")
        self.answer("r2")
        self.pump(timeout=0.4)
        self.assertEqual(self.speaks(), [], "nothing is spoken while muted")
        self.assertFalse(any(m.get("content") == "what is the weather" for m in self.app.history))
        self.transcript("speak again", item="u3")
        self.assertTrue(self.pump(lambda: not self.app.muted))
        self.answer("r3")  # the server's answer to "speak again" is dropped too
        self.pump(timeout=0.4)
        self.assertEqual(self.speaks(), [])
        self.server.respond(["Hello again. "], tone(1.0))
        self.assertTrue(self.pump(lambda: bool(self.speaks())), "answers again after unmuting")


class PluginSourceTests(unittest.TestCase):
    def test_toggle_in_the_config_tab_right_column_with_bold_help_left(self):
        link = src("AppLink.cs")
        self.assertIn('public const string MuteLabel = "Mute AI (stop talking and listening)";', link)
        build = method_body(link, "public void BuildConfigTab(UiPage page, UnityEngine.Events.UnityAction reload)")
        self.assertTrue(build.strip().lstrip("{").strip().startswith("page.Toggle(_mutedJson);"))
        self.assertNotIn("page.Text(", build)
        self.assertNotIn("page.Note(", build)
        info = method_body(link, "public string MuteInfoText()")
        self.assertIn('"<b>" + MuteLabel + "</b>', info)
        for phrase in ("shut up", "halt's Maul", "halt die Klappe", "sei still", "sprich mit mir", "speak again",
                       "go ahead talking"):
            self.assertIn(phrase, info)
        self.assertIn("_link.MuteInfoText()", src("AIBody.cs"))

    def test_not_saved_and_reset_to_default_unmutes(self):
        link = src("AppLink.cs")
        self.assertIn("_mutedJson.isStorable = false;", link)
        self.assertIn("_mutedJson.isRestorable = false;", link)
        self.assertNotIn("SettingsDefaults.Bool(_plugin, _mutedJson)", link)
        self.assertIn('new JSONStorableBool(MuteLabel, false, OnMuteToggled)', link)
        confirm = method_body(src("AIBody.cs"), "private void ConfirmReset()")
        self.assertIn("_link.ResetMute();", confirm)
        self.assertIn("_mutedJson.val = false;", method_body(link, "public void ResetMute()"))

    def test_sync_both_ways_over_the_existing_link(self):
        link = src("AppLink.cs")
        toggled = method_body(link, "private void OnMuteToggled(bool muted)")
        self.assertIn("if (_syncingMute) return;", toggled)
        self.assertIn("_mutePending = true;", toggled)
        send = method_body(link, "private void SendMute(bool muted)")
        self.assertIn("Protocol.NewEvent(Protocol.EvtMute)", send)
        self.assertIn("Send(evt);", send)  # the link's transport: socket, else the file outbox
        apply = method_body(link, "private void ApplyMuteState(JSONClass msg)")
        self.assertIn('Protocol.GetBool(msg, "muted", false)', apply)
        self.assertIn("_syncingMute = true;", apply)
        self.assertIn("ApplyMuteState(msg);", method_body(link, "private void HandleCompanionHeartbeat(JSONClass msg)"))
        self.assertIn('public const string EvtMute = "mute";', src("Protocol.cs"))

    def test_sandbox(self):
        text = src("AppLink.cs")
        start = text.index("// ---------------------------------------------------------------- mute (version 55)")
        part = text[start:text.index("public void ClearToken()")]
        for bad in ("System.Reflection", "UnityWebRequest", "System.Net", "System.IO", ".Keys", ".Values", "this["):
            self.assertNotIn(bad, part)


if __name__ == "__main__":
    unittest.main()
