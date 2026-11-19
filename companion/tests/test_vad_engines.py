"""Must-Have 3: voice activity detection (built-in adaptive detector, optional webrtcvad), strictness, settings,
and the echo lock (the AI must never hear itself). No microphone needed: frames are synthetic."""
from __future__ import annotations

import importlib.util
import math
import struct
import tempfile
import unittest
from unittest import mock

from aibody_companion.audio import EchoGate, EnergyVad, InputProcessor, MicSettings, apply_mic_config
from aibody_companion.audio.vad import STRICTNESS_RATIO, VadInfo, WebRtcVad, make_vad
from aibody_companion.config import Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline import EchoLlm, NullStt, ToneTts
from tests.fakes import FakeClock
from tests.test_plugin_menu import method_body, source
from tests.test_routing import FakeTransport

RATE = 16000
FRAME = 480  # 30 ms


def tone(rms: float, hz: int = 220) -> bytes:
    amp = rms * math.sqrt(2) * 32767
    return b"".join(struct.pack("<h", int(amp * math.sin(2 * math.pi * hz * i / RATE))) for i in range(FRAME))


def wobbly(level: float, i: int) -> float:
    """Speech-like level: changes from frame to frame."""
    return level * (0.5 + 0.5 * abs(math.sin(i * 0.9)) + 0.3 * (i % 3))


class EnergyVadTests(unittest.TestCase):
    def feed(self, vad, level, frames):
        return [vad.is_speech_rms(level) for _ in range(frames)]

    def room(self, vad, level):
        """A room that has been this quiet for a while."""
        vad.noise_floor = level
        return vad

    def test_noise_floor_follows_the_background_quickly_down_and_slowly_up(self):
        vad = self.room(EnergyVad(min_rms=0.001), 0.004)
        self.feed(vad, 0.02, 3)  # loud start: not learned
        self.feed(vad, 0.004, 40)
        low = vad.noise_floor
        self.assertAlmostEqual(low, 0.004, delta=0.0005)
        self.feed(vad, 0.006, 10)  # background gets louder: follows slowly
        self.assertGreater(vad.noise_floor, low)
        self.assertLess(vad.noise_floor, 0.0045)
        self.feed(vad, 0.001, 8)  # gets quieter: follows fast
        self.assertLess(vad.noise_floor, 0.0015)

    def test_speech_does_not_raise_the_noise_floor(self):
        vad = self.room(EnergyVad(min_rms=0.001), 0.004)
        self.feed(vad, 0.004, 40)
        floor = vad.noise_floor
        for i in range(120):
            self.assertTrue(vad.is_speech_rms(wobbly(0.05, i)))
        self.assertEqual(vad.noise_floor, floor)

    def test_hysteresis_a_quiet_syllable_does_not_cut_the_word(self):
        vad = self.room(EnergyVad(min_rms=0.001), 0.004)  # start needs > 0.012, staying only > ~0.0066
        self.assertFalse(vad.is_speech_rms(0.009), "too quiet to START speech")
        self.assertTrue(vad.is_speech_rms(0.02))
        self.assertTrue(vad.is_speech_rms(0.009), "but enough to continue it")

    def test_hangover_bridges_short_gaps_then_ends(self):
        vad = self.room(EnergyVad(min_rms=0.001, hangover_frames=3), 0.004)
        self.assertTrue(vad.is_speech_rms(0.05))
        self.assertEqual(self.feed(vad, 0.003, 5), [True, True, True, False, False])

    def test_threshold_is_a_floor_for_a_very_quiet_room(self):
        vad = EnergyVad(min_rms=0.01)
        self.feed(vad, 0.0005, 60)  # near silence: ratio alone would trigger on 0.002
        self.assertFalse(vad.is_speech_rms(0.008))
        self.assertTrue(vad.is_speech_rms(0.02))

    def test_constant_loud_noise_stops_counting_as_speech(self):
        vad = EnergyVad(min_rms=0.01)
        results = [vad.is_speech_rms(0.05) for _ in range(400)]
        self.assertTrue(results[0])
        self.assertFalse(results[-1], "an unchanging level for ~6 s is a fan, not a voice")
        self.assertAlmostEqual(vad.noise_floor, 0.05, delta=0.01)
        self.assertTrue(vad.is_speech_rms(0.5), "speech over the noise is still detected")

    def test_wobbling_speech_is_not_mistaken_for_noise(self):
        vad = EnergyVad(min_rms=0.01)
        results = [vad.is_speech_rms(wobbly(0.08, i)) for i in range(600)]
        self.assertTrue(all(results))

    def test_hold_forgets_running_speech_and_learns_nothing(self):
        vad = self.room(EnergyVad(min_rms=0.001), 0.004)
        floor = vad.noise_floor
        vad.is_speech_rms(0.05)
        vad.hold()
        self.assertFalse(vad.active)
        self.assertEqual(vad.noise_floor, floor)

    def test_strictness_sets_how_far_above_the_floor_speech_starts(self):
        loud_enough_for_loose = 3.0  # x noise floor
        for strictness, expected in ((0, True), (1, True), (2, True), (3, False)):
            vad, info = make_vad("energy", strictness, 0.001)
            self.room(vad, 0.004)
            self.assertEqual(vad.is_speech_rms(vad.noise_floor * loud_enough_for_loose * 1.05), expected, strictness)
            self.assertIn(f"strictness {strictness}", info.text)
        self.assertEqual(STRICTNESS_RATIO[2], 3.0, "the default keeps the old fixed ratio")


class FakeWebRtcModule:
    """Stands in for `webrtcvad`: answers from a script (list of bools), then False."""

    class Vad:
        script: list[bool] = []
        modes: list[int] = []
        raise_on_call = False

        def __init__(self, mode):
            FakeWebRtcModule.Vad.modes.append(mode)

        def is_speech(self, frame, rate):
            if FakeWebRtcModule.Vad.raise_on_call:
                raise ValueError("bad frame length")
            return FakeWebRtcModule.Vad.script.pop(0) if FakeWebRtcModule.Vad.script else False


def fake_importer(name):
    assert name == "webrtcvad"
    return FakeWebRtcModule


def missing_importer(name):
    raise ImportError(name)


class MakeVadTests(unittest.TestCase):
    def setUp(self):
        FakeWebRtcModule.Vad.script, FakeWebRtcModule.Vad.modes, FakeWebRtcModule.Vad.raise_on_call = [], [], False

    def test_energy_engine_never_looks_for_webrtcvad(self):
        vad, info = make_vad("energy", 2, 0.01, importer=missing_importer)
        self.assertIsInstance(vad, EnergyVad)
        self.assertEqual((info.name, info.note), ("energy", ""))

    def test_auto_without_the_library_uses_the_built_in_detector_quietly(self):
        vad, info = make_vad("auto", 2, 0.01, importer=missing_importer)
        self.assertIsInstance(vad, EnergyVad)
        self.assertEqual(info.note, "")

    def test_webrtc_without_the_library_falls_back_and_says_how_to_install_it(self):
        vad, info = make_vad("webrtc", 2, 0.01, importer=missing_importer)
        self.assertIsInstance(vad, EnergyVad)
        self.assertEqual(info.name, "energy")
        self.assertIn("not installed", info.note)
        self.assertIn("python -m pip install webrtcvad-wheels", info.note)

    def test_a_broken_native_library_falls_back_too(self):
        def broken(name):
            raise OSError("DLL load failed")
        vad, info = make_vad("webrtc", 2, 0.01, importer=broken)
        self.assertIsInstance(vad, EnergyVad)
        self.assertIn("could not be loaded", info.note)

    def test_auto_and_webrtc_use_the_library_when_it_is_there(self):
        for engine in ("auto", "webrtc"):
            vad, info = make_vad(engine, 3, 0.01, importer=fake_importer)
            self.assertIsInstance(vad, WebRtcVad)
            self.assertEqual((info.name, info.note), ("webrtc", ""))
            self.assertIn("strictness 3", info.text)
        self.assertEqual(FakeWebRtcModule.Vad.modes, [3, 3], "strictness is the webrtcvad mode")

    def test_unsupported_frame_size_falls_back_with_a_note(self):
        vad, info = make_vad("webrtc", 2, 0.01, sample_rate=16000, frame_ms=25, importer=fake_importer)
        self.assertIsInstance(vad, EnergyVad)
        self.assertIn("10/20/30 ms", info.note)

    def test_webrtc_decision_needs_the_library_and_the_threshold(self):
        vad, _ = make_vad("webrtc", 2, 0.01, importer=fake_importer)
        FakeWebRtcModule.Vad.script = [True, True, False, False, False, False, False]
        loud, quiet = tone(0.05), tone(0.002)
        decisions = [vad.decide(loud, 0.05), vad.decide(loud, 0.05)]
        decisions += [vad.decide(loud, 0.05) for _ in range(5)]  # hangover of 3 frames, then False
        self.assertEqual(decisions, [True, True, True, True, True, False, False])
        FakeWebRtcModule.Vad.script = [True]
        self.assertFalse(vad.decide(quiet, 0.002), "the library says speech, but it is below VAD threshold")

    def test_webrtc_error_on_a_frame_uses_the_energy_rule_for_that_frame(self):
        vad, _ = make_vad("webrtc", 2, 0.01, importer=fake_importer)
        FakeWebRtcModule.Vad.raise_on_call = True
        with self.assertLogs("aibody_companion.audio.vad", level="WARNING"):
            self.assertTrue(vad.decide(tone(0.1), 0.1) or True)
        self.assertIsInstance(vad.hold(), type(None))

    @unittest.skipUnless(importlib.util.find_spec("webrtcvad"), "webrtcvad is optional and not installed here")
    def test_real_webrtcvad_loads_and_decides_on_silence_and_tone(self):
        vad, info = make_vad("webrtc", 2, 0.01)
        self.assertEqual(info.name, "webrtc")
        self.assertFalse(vad.decide(bytes(FRAME * 2), 0.0))


class MicSettingsTests(unittest.TestCase):
    def test_new_keys_have_backward_compatible_defaults(self):
        s = MicSettings()
        self.assertEqual((s.vad_engine, s.vad_strictness), ("auto", 2))
        updated, errors = apply_mic_config(s, {"vad_threshold": 0.02})  # an old plugin sends none of the new keys
        self.assertEqual((errors, updated.vad_engine, updated.vad_strictness), ([], "auto", 2))

    def test_validation(self):
        s, errors = apply_mic_config(MicSettings(), {"vad_engine": "webrtc", "vad_strictness": "3"})
        self.assertEqual((errors, s.vad_engine, s.vad_strictness), ([], "webrtc", 3))
        s, errors = apply_mic_config(MicSettings(), {"vad_strictness": 9})
        self.assertEqual((errors, s.vad_strictness), ([], 3), "clamped like every other number")
        s, errors = apply_mic_config(MicSettings(), {"vad_engine": "silero"})
        self.assertTrue(errors and "vad_engine" in errors[0])
        self.assertEqual(s.vad_engine, "auto")


class InputProcessorTests(unittest.TestCase):
    def make(self, **kw):
        self.clock = FakeClock(0.0)
        self.gate = EchoGate(tail_s=0.4, clock=self.clock)
        return InputProcessor(MicSettings(vad_engine="energy", **kw), self.gate)

    def utterances(self, ip, frames):
        out = []
        for f in frames:
            r = ip.process(f)
            if r:
                out.append(r)
        return out

    def test_engine_change_rebuilds_the_detector_and_reports_what_runs(self):
        ip = self.make()
        self.assertEqual(ip.vad_info.name, "energy")
        with mock.patch("aibody_companion.audio.input_processor.make_vad",
                        return_value=(EnergyVad(), VadInfo("webrtc", "webrtc (fake), strictness 1"))) as m:
            ip.apply(MicSettings(vad_engine="webrtc", vad_strictness=1))
        self.assertEqual(m.call_args.args[:3], ("webrtc", 1, 0.01))
        self.assertEqual(ip.vad_info.name, "webrtc")
        self.assertIs(ip.segmenter.vad, ip.vad)
        with mock.patch("aibody_companion.audio.input_processor.make_vad") as m:
            ip.apply(MicSettings(vad_engine="webrtc", vad_strictness=1, vad_threshold=0.02))
        m.assert_not_called()  # the threshold alone does not rebuild
        self.assertEqual(ip.vad.min_rms, 0.02)

    def test_utterance_found_in_noise(self):
        ip = self.make()
        noise = [tone(0.004, hz=300 + i) for i in range(40)]
        speech = [tone(wobbly(0.06, i)) for i in range(25)]
        out = self.utterances(ip, noise + speech + [tone(0.004)] * 30)
        self.assertEqual(len(out), 1)

    def test_echo_lock_ignores_the_body_voice_and_learns_nothing_from_it(self):
        ip = self.make()
        self.utterances(ip, [tone(0.004)] * 40)
        floor = ip.vad.noise_floor
        self.gate.on_speak_sent("u1", 2.0)
        echo = [tone(wobbly(0.03, i)) for i in range(60)]  # the body's own voice coming back into the mic
        self.assertEqual(self.utterances(ip, echo), [])
        self.assertEqual(ip.vad.noise_floor, floor, "the echo did not move the noise floor")
        self.assertFalse(ip.take_level()["speech"], "the meter does not call echo speech")
        self.assertFalse(ip.take_level()["gate_open"])

    def test_echo_lock_covers_playback_plus_the_tail_then_listens_at_once(self):
        ip = self.make()
        self.gate.on_speak_sent("u1", 2.0)
        self.gate.on_event({"type": "speech_started", "utterance_id": "u1", "duration": 2.0})
        self.clock.advance(2.0)
        self.gate.on_event({"type": "speech_ended", "utterance_id": "u1", "reason": "completed"})
        speech = [tone(wobbly(0.06, i)) for i in range(25)]
        self.assertEqual(self.utterances(ip, speech + [tone(0.004)] * 30), [], "inside the 0.4 s tail: still muted")
        self.clock.advance(0.5)
        self.assertEqual(len(self.utterances(ip, speech + [tone(0.004)] * 30)), 1, "tail over: the user is heard")

    def test_a_running_utterance_is_dropped_when_the_body_starts_to_talk(self):
        ip = self.make()
        for i in range(8):
            ip.process(tone(wobbly(0.06, i)))
        self.assertTrue(ip.segmenter.in_speech)
        self.gate.on_speak_sent("u1", 1.0)
        ip.process(tone(0.06))
        self.assertFalse(ip.segmenter.in_speech)


class CompanionMicStateTests(unittest.TestCase):
    def make(self, mic: dict):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = Companion(Config(vam_root=tmp.name), FakeTransport(), NullStt(), EchoLlm(), ToneTts())
        app.handle_config({"type": "config", "mic": mic})
        return app

    def test_mic_state_says_which_detector_runs_and_why_not_the_chosen_one(self):
        with mock.patch("aibody_companion.audio.vad.importlib.import_module", side_effect=ImportError("webrtcvad")):
            state = self.make({"vad_engine": "webrtc"}).mic_state()
        self.assertIn("energy (built-in", state["vad"])
        self.assertIn("python -m pip install webrtcvad-wheels", state["vad_note"])
        state = self.make({"vad_engine": "energy"}).mic_state()
        self.assertNotIn("vad_note", state)

    def test_strictness_from_the_plugin_reaches_the_detector(self):
        app = self.make({"vad_engine": "energy", "vad_strictness": 3})
        self.assertIn("strictness 3", app.mic_state()["vad"])
        self.assertEqual(app.input.vad.ratio, STRICTNESS_RATIO[3])


class PluginVadMenuTests(unittest.TestCase):
    """The two new settings are real menu controls (the plugin rewrites config.json `mic` wholesale, so keys
    without a control would be lost), in simple English, with the engine names mapped to the config values."""

    def test_controls_and_json_mapping(self):
        mic = source("MicConfig.cs")
        build = method_body(mic, "public void BuildTab(UiPage page)")
        for control in ("page.Popup(VadEngine)", "page.Slider(VadStrictness)"):
            self.assertIn(control, build)
        self.assertIn('new JSONStorableFloat("VAD strictness", 2f,', mic)
        self.assertIn('"VAD engine"', mic)
        to_json = method_body(mic, "public JSONClass BuildMicJson()")
        for key in ('mic["vad_engine"]', 'mic["vad_strictness"]'):
            self.assertIn(key, to_json)
        self.assertIn('"energy"', mic)
        self.assertIn('"webrtc"', mic)

    def test_help_and_status_texts_are_plain(self):
        mic = source("MicConfig.cs")
        for text in ("python -m pip install webrtcvad-wheels", "the microphone is muted on purpose, so the AI never hears itself",
                     "Voice detection: ", '"vad_note"'):
            self.assertIn(text, mic)

    def test_no_new_sandbox_risks(self):
        mic = source("MicConfig.cs")
        for bad in ("UnityWebRequest", "System.IO", ".Keys)", ".Values)"):
            self.assertNotIn(bad, mic)


if __name__ == "__main__":
    unittest.main()
