"""Version 28: several figures in one companion app (multi.py) and the plugin's Channel field.

One Companion per channel, one shared microphone: the frames go to the active figure only, a name at
the start or end of a sentence switches, the gates are linked, the proactive timers stay in step."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aibody_companion import cli, protocol, settings_file
from aibody_companion.audio import LinkedGate, MicController
from aibody_companion.config import Config
from aibody_companion.multi import Fleet, find_address, parse_channels
from aibody_companion.orchestrator import Companion
from aibody_companion.personas import Persona
from aibody_companion.pipeline import EchoLlm, ToneTts
from aibody_companion.realtime_voice import RealtimeVoice
from aibody_companion.transport import FileTransport
from tests.fakes import FakeClock, FakePlugin
from tests.test_plugin_menu import method_body, source
from tests.test_vad_engines import tone, wobbly


class ScriptedStt:
    def __init__(self):
        self.texts: list[str] = []

    def transcribe(self, pcm16, sample_rate):
        return self.texts.pop(0) if self.texts else ""


class FrameSource:
    queued: list[bytes] = []

    def __init__(self, rate, ms):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def frames(self):
        frames, FrameSource.queued = FrameSource.queued, []
        return iter(frames)


class ChannelListTests(unittest.TestCase):
    def test_parse_channels(self):
        self.assertEqual(parse_channels("anna, marc;eve"), ["anna", "marc", "eve"])
        self.assertEqual(parse_channels("a,a,b"), ["a", "b"])
        self.assertEqual(parse_channels("my chan/x"), ["my", "chan_x"])
        self.assertEqual(parse_channels("") + parse_channels(None), [])
        self.assertEqual(len(parse_channels(",".join(f"c{i}" for i in range(20)))), 8)


class AddressTests(unittest.TestCase):
    NAMES = {"a": ["Anna", "anna"], "m": ["Marc"], "j": ["Jean Luc"]}

    def test_name_at_start_or_end(self):
        self.assertEqual(find_address("Anna, wie geht es dir", self.NAMES), "a")
        self.assertEqual(find_address("Hey Marc wie war dein Tag", self.NAMES), "m")
        self.assertEqual(find_address("Wie geht es dir heute, Marc?", self.NAMES), "m")
        self.assertEqual(find_address("hallo JEAN LUC", self.NAMES), "j")

    def test_name_in_the_middle_is_a_topic_not_an_address(self):
        self.assertIsNone(find_address("Gestern habe ich im Park lange mit Anna und Freunden geredet und gelacht", self.NAMES))
        self.assertIsNone(find_address("", self.NAMES))
        self.assertIsNone(find_address("wie spät ist es", self.NAMES))

    def test_earliest_mention_wins_and_short_names_are_ignored(self):
        self.assertEqual(find_address("Marc sag Anna hallo", self.NAMES), "m")
        self.assertEqual(find_address("Anna sag Marc hallo", self.NAMES), "a")
        self.assertIsNone(find_address("Al, hallo", {"x": ["Al"]}))

    def test_umlauts(self):
        self.assertEqual(find_address("Jörg, hörst du mich", {"j": ["Jörg"]}), "j")


class FleetBase(unittest.TestCase):
    CHANNELS = ("anna", "marc")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.stt = ScriptedStt()
        self.mic = MicController(capture_factory=FrameSource)
        FrameSource.queued = []
        self.fleet = Fleet(self.mic)
        self.plugins: dict[str, FakePlugin] = {}
        for ch in self.CHANNELS:
            cfg = Config(vam_root=self.tmp.name, channel=ch, mic={"enabled": True, "mode": "vad", "echo_tail_s": 0.4})
            cfg.audio_dir.mkdir(parents=True, exist_ok=True)
            transport = FileTransport(cfg.channel_dir, clock=self.clock)
            transport.start()
            member = Companion(cfg, transport, self.stt, EchoLlm(), ToneTts(), gate=LinkedGate(clock=self.clock),
                               mic=self.fleet.new_tap(), clock=self.clock)
            self.fleet.add(member)
            plugin = FakePlugin(Path(self.tmp.name), self.clock, channel=ch, mode="chain")
            plugin.start()
            self.plugins[ch] = plugin
        self.fleet.link()
        self.run_for(3)

    def tearDown(self):
        self.fleet.shutdown()
        self.tmp.cleanup()

    def run_for(self, seconds, dt=0.1):
        for _ in range(int(round(seconds / dt))):
            self.clock.advance(dt)
            for p in self.plugins.values():
                p.tick(dt)
            self.fleet.tick()

    def speaks(self, channel):
        return [m for m in self.plugins[channel].received if m.get("type") == "speak"]

    def figure(self, channel):
        return self.fleet.members[self.CHANNELS.index(channel)]

    def say_into_mic(self, text):
        self.stt.texts.append(text)
        FrameSource.queued = [tone(0.003)] * 40 + [tone(wobbly(0.08, i)) for i in range(25)] + [tone(0.003)] * 40


class FleetRoutingTests(FleetBase):
    def test_typed_text_goes_to_the_named_figure_then_sticks(self):
        self.assertEqual(self.fleet.active, self.figure("anna"), "the first figure starts as the active one")
        self.fleet.handle_user_text("Marc, hallo du")
        self.run_for(1)
        self.assertEqual((len(self.speaks("anna")), len(self.speaks("marc"))), (0, 1))
        self.fleet.handle_user_text("und wie geht es dir")  # nobody named: Marc still listens
        self.run_for(8)
        self.assertEqual((len(self.speaks("anna")), len(self.speaks("marc"))), (0, 2))
        self.fleet.handle_user_text("Anna, und du?")
        self.run_for(8)
        self.assertEqual((len(self.speaks("anna")), len(self.speaks("marc"))), (1, 2))
        self.assertEqual(self.fleet.active, self.figure("anna"))

    def test_each_figure_has_its_own_history(self):
        self.fleet.handle_user_text("Marc, geheim")
        self.run_for(1)
        self.assertEqual([m["content"] for m in self.figure("marc").history if m["role"] == "user"], ["Marc, geheim"])
        self.assertEqual(self.figure("anna").history, [])

    def test_persona_name_and_channel_name_both_address(self):
        marc = self.figure("marc")
        marc.engine_set.persona = Persona(name="m1", display_name="Maximilian")
        self.fleet.handle_user_text("Maximilian, hallo")
        self.run_for(1)
        self.assertEqual(len(self.speaks("marc")), 1)
        self.fleet.handle_user_text("m1 bist du da")
        self.run_for(8)
        self.assertEqual(len(self.speaks("marc")), 2)

    def test_a_figure_without_a_plugin_is_not_chosen_by_stickiness(self):
        self.plugins["anna"].stop_speaking("x")
        self.plugins["anna"].send("shutdown")
        # anna's plugin goes silent: after the timeout only marc is connected
        for _ in range(100):
            self.clock.advance(0.1)
            self.plugins["marc"].tick(0.1)
            self.fleet.tick()
        self.assertFalse(self.figure("anna").transport.connected)
        self.fleet.handle_user_text("irgendwas ohne Namen")
        self.run_for(1)
        self.assertEqual((len(self.speaks("anna")), len(self.speaks("marc"))), (0, 1))

    def test_the_figure_that_speaks_gets_the_next_answer(self):
        self.fleet.handle_user_text("Marc, hi")
        self.run_for(8)
        self.fleet.active = self.figure("anna")
        self.fleet.note_speaker(self.figure("marc"))
        self.assertEqual(self.fleet.active, self.figure("marc"))


class FleetMicTests(FleetBase):
    def test_frames_reach_only_the_active_figure(self):
        self.say_into_mic("Hallo zusammen")
        self.run_for(1)
        self.assertEqual((len(self.speaks("anna")), len(self.speaks("marc"))), (1, 0), "anna was active")
        self.assertEqual(self.stt.texts, [], "transcribed once, not once per figure")

    def test_the_spoken_name_hands_the_sentence_over(self):
        self.say_into_mic("Marc, kannst du mich hören")
        self.run_for(1)
        self.assertEqual((len(self.speaks("anna")), len(self.speaks("marc"))), (0, 1))
        self.assertEqual([m["content"] for m in self.figure("marc").history if m["role"] == "user"],
                         ["Marc, kannst du mich hören"])
        self.assertEqual(self.figure("anna").history, [], "the wrong figure keeps nothing of it")
        self.assertEqual(self.fleet.active, self.figure("marc"))
        self.run_for(10)
        self.say_into_mic("danke")  # no name: marc keeps listening
        self.run_for(1)
        self.assertEqual((len(self.speaks("anna")), len(self.speaks("marc"))), (0, 2))

    def test_mic_settings_are_applied_once_to_the_one_device(self):
        self.assertTrue(self.mic.capturing)
        self.assertTrue(self.figure("anna").mic.capturing)
        self.assertEqual(self.figure("marc").mic.error, self.mic.error)
        self.assertIsNone(self.figure("anna").mic.stop())
        self.assertTrue(self.mic.capturing, "a figure stopping its tap does not close the shared microphone")


class FleetRealtimeTests(FleetBase):
    """Realtime: the transcript arrives while the server may already answer; a named figure takes over."""

    def make(self, channel):
        member = self.figure(channel)
        member.realtime = RealtimeVoice(member, "dummy-key", connector=lambda *a, **k: None)
        member.realtime.client.send = mock.Mock(return_value=True)
        member.realtime.client.ready = True
        member._update_mode = lambda: None
        return member

    def transcript(self, member, text):
        member.realtime.handle({"type": "conversation.item.input_audio_transcription.completed", "transcript": text})

    def test_named_other_figure_takes_the_sentence(self):
        anna, marc = self.make("anna"), self.make("marc")
        self.transcript(anna, "Marc, wie spät ist es")
        self.assertEqual(anna.history, [], "anna does not keep a sentence meant for marc")
        self.assertEqual([m["content"] for m in marc.history], ["Marc, wie spät ist es"])
        sent = [c.args[0] for c in marc.realtime.client.send.call_args_list]
        self.assertEqual([m["type"] for m in sent], ["conversation.item.create", "response.create"])
        self.assertEqual(sent[0]["item"]["content"][0]["text"], "Marc, wie spät ist es")
        self.assertEqual(self.fleet.active, marc)

    def test_own_name_or_no_name_stays_with_this_figure(self):
        anna, marc = self.make("anna"), self.make("marc")
        self.transcript(anna, "Anna, hallo")
        self.transcript(anna, "und sonst so")
        self.assertEqual(len(anna.history), 2)
        self.assertEqual(marc.history, [])
        marc.realtime.client.send.assert_not_called()


class FleetRoomTests(FleetBase):
    def test_a_speaking_figure_closes_every_gate(self):
        anna, marc = self.figure("anna"), self.figure("marc")
        self.assertTrue(anna.gate.is_open and marc.gate.is_open)
        marc.gate.on_speak_sent("u1", 3.0)
        self.assertFalse(marc.gate.is_open)
        self.assertFalse(anna.gate.is_open, "anna must not hear marc's voice as the user")
        marc.gate.on_event({"type": "speech_ended", "utterance_id": "u1"})
        self.clock.advance(1.0)
        self.assertTrue(anna.gate.is_open and marc.gate.is_open)

    def test_figures_do_not_start_a_nudge_while_a_peer_is_busy(self):
        anna, marc = self.figure("anna"), self.figure("marc")
        self.assertTrue(anna._can_speak_now())
        marc._busy.set()
        self.assertFalse(anna._can_speak_now())
        marc._busy.clear()
        marc.gate.on_speak_sent("u2", 2.0)
        self.assertFalse(anna._can_speak_now())

    def test_proactive_timers_follow_what_any_figure_does(self):
        marc = self.figure("marc")
        with mock.patch.object(marc.proactive, "ai_activity") as ai, mock.patch.object(marc.proactive, "user_activity") as user:
            self.figure("anna").on_user_activity()
            self.assertEqual((ai.call_count, user.call_count), (0, 1))
            self.plugins["anna"].send("speech_started", utterance_id="x", duration=1)
            self.run_for(0.5)
            self.assertGreaterEqual(ai.call_count, 1, "anna spoke: marc waits too")

    def test_heartbeats_tell_the_plugins_who_listens(self):
        self.fleet.handle_user_text("Marc, hi")
        self.run_for(3)
        for ch in self.CHANNELS:
            beats = [m for m in self.plugins[ch].received if m.get("type") == "companion_heartbeat"]
            self.assertEqual(beats[-1]["figures"], ["anna", "marc"])
            self.assertEqual(beats[-1]["active_figure"], "marc")
            self.assertEqual(protocol.validate_command(beats[-1]), [])

    def test_two_plugins_on_one_config_keep_separate_ai_settings(self):
        for ch in self.CHANNELS:
            self.plugins[ch].ai_ui["persona_name"] = ""
        self.plugins["marc"].ai_ui["mode"] = "qa"
        self.plugins["marc"].send_config()
        self.run_for(1)
        self.assertEqual(self.figure("marc").engine_set.ai["mode"], "qa")
        self.assertNotEqual(self.figure("anna").engine_set.ai["mode"], "qa")


class SingleFigureTests(unittest.TestCase):
    def test_no_fleet_no_extra_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            cfg = Config(vam_root=tmp)
            cfg.audio_dir.mkdir(parents=True, exist_ok=True)
            t = FileTransport(cfg.channel_dir, clock=clock)
            t.start()
            app = Companion(cfg, t, clock=clock)
            self.assertIsNone(app.fleet)
            self.assertEqual(app._figure_fields(), {})
            self.assertEqual(app.peers, [])
            app.shutdown()


class BuildTests(unittest.TestCase):
    def test_build_fleet_gives_each_figure_its_own_channel_and_linked_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(vam_root=tmp)
            fleet = cli.build_fleet(cfg, ["anna", "marc"], use_mic=False)
            try:
                self.assertEqual(fleet.channels, ["anna", "marc"])
                self.assertEqual(cfg.channel, "default", "the base config is not changed")
                a, m = fleet.members
                self.assertNotEqual(a.cfg.channel_dir, m.cfg.channel_dir)
                self.assertIsNot(a.engine_set.ai, m.engine_set.ai)
                self.assertIs(a.gate.peers[0], m.gate)
                self.assertIs(a.fleet, fleet)
                self.assertIsNone(a.mic, "--no-mic: no microphone anywhere")
                self.assertTrue(a.cfg.audio_dir.is_dir() and m.cfg.audio_dir.is_dir())
            finally:
                fleet.shutdown()

    def test_the_setting_ai_channels(self):
        data, errors = settings_file.validate({"ai": {"channels": "anna,marc"}})
        self.assertEqual(errors, [])
        self.assertEqual(data["ai"]["channels"], "anna,marc")
        self.assertEqual(settings_file.defaults()["ai"]["channels"], "")

    def test_cli_help_and_channel_list(self):
        self.assertIn("anna,marc", cli.build_parser().format_help())
        args = cli.build_parser().parse_args(["--channel", "a,b"])
        self.assertEqual(parse_channels(args.channel), ["a", "b"])


class PluginSourceTests(unittest.TestCase):
    def setUp(self):
        self.link = source("AppLink.cs")

    def test_channel_field_in_the_config_tab_with_a_pause_before_restart(self):
        build = method_body(self.link, "public void BuildConfigTab(UiPage page, UnityEngine.Events.UnityAction reload)")
        self.assertIn("page.TextInput(_channelJson)", build)
        self.assertIn("ChannelHint", build)
        self.assertIn('new JSONStorableString("Channel", "default", OnChannelEdited)', self.link)
        edited = method_body(self.link, "private void OnChannelEdited(string v)")
        self.assertNotIn("Restart()", edited, "not on every keystroke")
        tick = method_body(self.link, "private void TickChannelEdit(float dt)")
        self.assertIn("ChannelQuietSeconds", tick)
        self.assertIn("Restart();", tick)
        self.assertIn("TickChannelEdit(dt);", method_body(self.link, "public void Update(float dt)"))

    def test_reload_config_json_keeps_each_figures_channel(self):
        self.assertIn("seedChannel", method_body(self.link, "public void ApplySettings(JSONClass root, bool seedChannel = true)"))
        self.assertIn("ApplySettings(file, false)", source("AIBody.cs"))

    def test_channel_is_still_cleaned_to_safe_characters(self):
        self.assertIn("if (!(char.IsLetterOrDigit(c) || c == '-' || c == '_')) chars[i] = '_';", self.link)

    def test_heartbeat_fields_are_shown(self):
        self.assertIn('msg["figures"] as JSONArray', self.link)
        self.assertIn('msg["active_figure"]', self.link)
        self.assertIn("Figures in this app: ", self.link)

    def test_plain_english_hint(self):
        self.assertIn("--channel anna,marc", self.link)

    def test_no_sandbox_risks(self):
        for bad in ("UnityWebRequest", "System.IO", ".Keys)", ".Values)"):
            self.assertNotIn(bad, self.link)


class ConfigFileKeepsFigureListTests(unittest.TestCase):
    def test_ai_channels_survive_the_plugin_rewriting_config_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            path = settings_file.settings_path(tmp)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"ai": {"channels": "anna,marc"}}), encoding="utf-8")
            cfg = Config(vam_root=tmp)
            settings_file.apply_to_config(cfg)
            self.assertEqual(parse_channels(cfg.ai["channels"]), ["anna", "marc"])
            plugin = FakePlugin(Path(tmp), clock, channel="anna", mode="chain")
            plugin.start()
            plugin.write_settings()
            self.assertEqual(json.loads(path.read_text())["ai"]["channels"], "anna,marc")


if __name__ == "__main__":
    unittest.main()
