import math
import struct
import unittest

from aibody_companion.audio import (
    EchoGate,
    InputProcessor,
    MicController,
    MicSettings,
    apply_gain,
    apply_mic_config,
    frame_rms,
)

RATE = 16000
FRAME = 480


def tone(amplitude: float) -> bytes:
    return b"".join(struct.pack("<h", int(amplitude * 32767 * math.sin(2 * math.pi * 220 * i / RATE)))
                    for i in range(FRAME))


SILENCE = bytes(FRAME * 2)
LOUD = tone(0.3)
QUIET = tone(0.005)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class MicSettingsTests(unittest.TestCase):
    def test_defaults_roundtrip(self):
        s, errors = apply_mic_config(MicSettings(), MicSettings().to_dict())
        self.assertEqual(errors, [])
        self.assertEqual(s, MicSettings())

    def test_clamps_numbers(self):
        s, errors = apply_mic_config(MicSettings(), {"gain": 100, "end_silence_ms": 10, "vad_threshold": 0})
        self.assertEqual(errors, [])
        self.assertEqual(s.gain, 8.0)
        self.assertEqual(s.end_silence_ms, 200)
        self.assertIsInstance(s.end_silence_ms, int)
        self.assertEqual(s.vad_threshold, 0.001)

    def test_rejects_bad_values_and_keeps_old(self):
        s, errors = apply_mic_config(MicSettings(), {"mode": "always", "enabled": "yes", "gain": "loud", "bogus": 1})
        self.assertEqual(len(errors), 4)
        self.assertEqual(s, MicSettings())

    def test_min_must_be_below_max(self):
        s, errors = apply_mic_config(MicSettings(), {"min_utterance_ms": 5000, "max_utterance_ms": 1000})
        self.assertEqual(len(errors), 1)
        self.assertEqual((s.min_utterance_ms, s.max_utterance_ms), (300, 20000))

    def test_not_a_dict(self):
        self.assertEqual(len(apply_mic_config(MicSettings(), None)[1]), 1)


class GainTests(unittest.TestCase):
    def test_gain_scales_and_clips(self):
        self.assertAlmostEqual(frame_rms(apply_gain(QUIET, 2.0)), 2 * frame_rms(QUIET), places=3)
        self.assertLessEqual(frame_rms(apply_gain(LOUD, 8.0)), 1.0)
        self.assertIs(apply_gain(LOUD, 1.0), LOUD)


class InputProcessorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.gate = EchoGate(clock=self.clock)

    def test_vad_mode_respects_threshold_and_gain(self):
        p = InputProcessor(MicSettings(vad_threshold=0.05, end_silence_ms=300), self.gate)
        out = [p.process(f) for f in [QUIET] * 30 + [SILENCE] * 20]
        self.assertTrue(all(o is None for o in out), "quiet speech is below the threshold")
        p.apply(MicSettings(vad_threshold=0.05, end_silence_ms=300, gain=8.0))
        p.process(SILENCE)
        out = [p.process(f) for f in [tone(0.05)] * 30 + [SILENCE] * 20]
        self.assertTrue(any(o for o in out), "gain lifts it above the threshold")

    def test_vad_mode_gated_while_speaking(self):
        p = InputProcessor(MicSettings(end_silence_ms=300), self.gate)
        self.gate.on_speak_sent("u1", 5.0)
        out = [p.process(f) for f in [LOUD] * 30 + [SILENCE] * 20]
        self.assertTrue(all(o is None for o in out))

    def test_ptt_records_between_press_and_release(self):
        p = InputProcessor(MicSettings(mode="ptt", min_utterance_ms=200), self.gate)
        self.assertIsNone(p.process(LOUD))  # not pressed: ignored
        self.assertIsNone(p.set_ptt(True))
        for _ in range(20):
            self.assertIsNone(p.process(SILENCE))  # silence does not end a PTT utterance
        utterance = p.set_ptt(False)
        self.assertEqual(len(utterance), 20 * FRAME * 2)

    def test_ptt_too_short_is_dropped(self):
        p = InputProcessor(MicSettings(mode="ptt", min_utterance_ms=600), self.gate)
        p.set_ptt(True)
        for _ in range(5):
            p.process(LOUD)
        self.assertIsNone(p.set_ptt(False))

    def test_ptt_bypasses_gate_only_with_interrupts(self):
        self.gate.on_speak_sent("u1", 5.0)
        p = InputProcessor(MicSettings(mode="ptt", min_utterance_ms=100, ptt_interrupts=False), self.gate)
        p.set_ptt(True)
        for _ in range(10):
            p.process(LOUD)
        self.assertIsNone(p.set_ptt(False))
        p.apply(MicSettings(mode="ptt", min_utterance_ms=100, ptt_interrupts=True))
        p.set_ptt(True)
        for _ in range(10):
            p.process(LOUD)
        self.assertIsNotNone(p.set_ptt(False))

    def test_ptt_ignored_in_vad_mode(self):
        p = InputProcessor(MicSettings(mode="vad"), self.gate)
        p.set_ptt(True)
        self.assertFalse(p.ptt_active)

    def test_level(self):
        p = InputProcessor(MicSettings(), self.gate)
        p.process(LOUD)
        p.process(SILENCE)
        level = p.take_level()
        self.assertGreater(level["rms"], 0.1)
        self.assertTrue(level["speech"])
        self.assertTrue(level["gate_open"])
        self.assertEqual(p.take_level()["rms"], 0.0)


class FakeCapture:
    instances = []

    broken = False

    def __init__(self, rate, ms):
        self.started = False
        self.stopped = False
        FakeCapture.instances.append(self)

    def start(self):
        if FakeCapture.broken:
            raise RuntimeError("no input device available")
        self.started = True

    def stop(self):
        self.stopped = True

    def frames(self):
        return iter([SILENCE])


class MicControllerTests(unittest.TestCase):
    def setUp(self):
        FakeCapture.instances = []
        FakeCapture.broken = False
        self.mic = MicController(capture_factory=FakeCapture)

    def test_follows_enabled(self):
        self.mic.apply(MicSettings(enabled=True))
        self.assertTrue(self.mic.capturing)
        self.mic.apply(MicSettings(enabled=True))  # unchanged: no restart
        self.assertEqual(len(FakeCapture.instances), 1)
        self.mic.apply(MicSettings(enabled=True, mode="ptt"))  # other settings never reopen the stream
        self.assertEqual(len(FakeCapture.instances), 1)
        self.mic.apply(MicSettings(enabled=False))
        self.assertFalse(self.mic.capturing)
        self.assertTrue(FakeCapture.instances[0].stopped)

    def test_error_is_reported(self):
        FakeCapture.broken = True
        self.mic.apply(MicSettings(enabled=True))
        self.assertFalse(self.mic.capturing)
        self.assertIn("no input device available", self.mic.error)
        FakeCapture.broken = False
        self.mic.apply(MicSettings(enabled=False))
        self.mic.apply(MicSettings(enabled=True))
        self.assertTrue(self.mic.capturing)
        self.assertIsNone(self.mic.error)


class RetiredDeviceSettingTests(unittest.TestCase):
    """Version after 22: mic.device is gone; old scenes / config.json files may still carry it."""

    def test_old_device_key_is_ignored_without_errors(self):
        from aibody_companion import settings_file
        from aibody_companion.audio import apply_mic_config

        settings, errors = apply_mic_config(MicSettings(), {"device": "USB Mic", "gain": 2.0})
        self.assertEqual(errors, [])
        self.assertEqual(settings.gain, 2.0)
        self.assertNotIn("device", settings.to_dict())
        result, problems = settings_file.validate({"mic": {"device": "Headset", "mode": "ptt"}})
        self.assertEqual(problems, [])
        self.assertEqual(result["mic"]["mode"], "ptt")
        self.assertNotIn("device", result["mic"])
        self.assertNotIn("device", settings_file.defaults()["mic"])
        _, errors = apply_mic_config(MicSettings(), {"bogus": 1})
        self.assertTrue(errors, "genuinely unknown keys are still reported")

    def test_schemas_and_example_have_no_device_setting(self):
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        for name in ("config.schema.json", "command.schema.json"):
            self.assertNotIn('"devices"', (root / "protocol/schema" / name).read_text(encoding="utf-8"))
        config_schema = json.loads((root / "protocol/schema/config.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("device", json.dumps(config_schema["properties"]["mic"]))
        self.assertNotIn('"device"', (root / "companion/config.example.json").read_text(encoding="utf-8"))
        self.assertNotIn('"device"', (root / "examples/config.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


class FakeSd:
    """sounddevice as on Windows: every mic once per host API, MME names cut to 31 characters."""

    class default:  # noqa: N801 - mirrors sounddevice.default
        device = (3, 5)
        hostapi = 0

    def __init__(self):
        self.opened = []

    def query_hostapis(self):
        return [{"name": "MME"}, {"name": "Windows WASAPI"}]

    def query_devices(self):
        return [
            {"name": "Microsoft Sound Mapper - Input", "hostapi": 0, "max_input_channels": 2},
            {"name": "Mikrofon (USB Audio Device With", "hostapi": 0, "max_input_channels": 1},
            {"name": "Headset (Bluetooth)", "hostapi": 0, "max_input_channels": 1},
            {"name": "Mikrofon (USB Audio Device With A Long Name)", "hostapi": 1, "max_input_channels": 1,
             "default_samplerate": 48000.0},
            {"name": "Lautsprecher", "hostapi": 1, "max_input_channels": 0},
            {"name": "Headset (Bluetooth)", "hostapi": 1, "max_input_channels": 1},
            {"name": "Headset (Bluetooth)", "hostapi": 1, "max_input_channels": 1},
        ]

    def RawInputStream(self, **kw):  # noqa: N802 - sounddevice name
        self.opened.append(kw["device"])

        class S:
            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

        return S()


class DeviceListTests(unittest.TestCase):
    def setUp(self):
        from unittest import mock

        from aibody_companion.audio import capture

        self.sd = FakeSd()
        patcher = mock.patch.object(capture, "_sounddevice", lambda: self.sd)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.capture = capture

    def test_one_entry_per_mic_from_the_default_host_api(self):
        devices, error = self.capture.list_input_devices()
        self.assertIsNone(error)
        self.assertEqual([d["name"] for d in devices],
                         ["Mikrofon (USB Audio Device With A Long Name)", "Headset (Bluetooth)"])
        self.assertEqual(devices[0]["index"], 3)
        self.assertTrue(devices[0]["default"])
        self.assertEqual(devices[0]["hostapi"], "Windows WASAPI")

    def test_capture_always_opens_the_system_default_input(self):
        self.capture.MicCapture().start()
        self.assertEqual(self.sd.opened, [None], "device=None is the sounddevice default input")
        with self.assertRaises(TypeError):
            self.capture.MicCapture(device="Headset (Bluetooth)")  # no device selection any more
        self.assertFalse(hasattr(self.capture, "resolve_input_device"))

    def test_errors_are_reported(self):
        self.sd.query_devices = lambda: []
        devices, error = self.capture.list_input_devices()
        self.assertEqual(devices, [])
        self.assertIn("no input device", error)
        with unittest.mock.patch.object(self.capture, "_sounddevice", lambda: None):
            self.assertIn("sounddevice is not installed", self.capture.list_input_devices()[1])


class WindowsDeviceListTests(unittest.TestCase):
    """Version 16: typical Windows lists (4 mics under MME, DirectSound, WASAPI, WDM-KS)."""

    def _sd(self, default_in, hostapi_default=0):
        names = ["Mikrofon (Realtek(R) Audio)", "Headset (Jabra Evolve 65)", "Webcam C920", "Line In (Realtek)"]
        apis = ["MME", "Windows DirectSound", "Windows WASAPI", "Windows WDM-KS"]
        devices = []
        for a in range(len(apis)):
            devices.append({"name": "Microsoft Sound Mapper - Input" if a == 0 else "Primärer Soundaufnahmetreiber",
                            "hostapi": a, "max_input_channels": 2 if a < 2 else 0})
            for n in names:
                devices.append({"name": n[:31] if a == 0 else n, "hostapi": a, "max_input_channels": 2})
            devices.append({"name": "Lautsprecher", "hostapi": a, "max_input_channels": 0, "max_output_channels": 2})

        class Sd:
            class default:  # noqa: N801 - sounddevice name
                device = [default_in, -1]
                hostapi = hostapi_default

            def query_hostapis(self):
                return [{"name": n} for n in apis]

            def query_devices(self):
                return devices

        return Sd()

    def _list(self, sd):
        from unittest import mock

        from aibody_companion.audio import capture

        with mock.patch.object(capture, "_sounddevice", lambda: sd):
            return capture.list_input_devices()

    def test_mme_default_lists_every_mic_once(self):
        devices, error = self._list(self._sd(default_in=1))
        self.assertIsNone(error)
        self.assertEqual(len(devices), 5, [d["name"] for d in devices])  # 4 mics + Sound Mapper
        self.assertEqual({d["hostapi"] for d in devices}, {"MME"})
        self.assertEqual([d["default"] for d in devices], [False, True, False, False, False])

    def test_no_default_input_falls_back_to_the_default_host_api(self):
        devices, error = self._list(self._sd(default_in=-1, hostapi_default=2))
        self.assertIsNone(error)
        self.assertEqual([d["name"] for d in devices], ["Mikrofon (Realtek(R) Audio)", "Headset (Jabra Evolve 65)",
                                                        "Webcam C920", "Line In (Realtek)"])

    def test_raw_counts_are_logged(self):
        with self.assertLogs("aibody_companion.audio.capture", level="INFO") as logs:
            self._list(self._sd(default_in=1))
        line = [r.getMessage() for r in logs.records if "Microphones (raw)" in r.getMessage()][0]
        self.assertIn("PortAudio devices", line)
        self.assertIn("with input channels", line)

    def test_host_api_without_inputs_falls_back_to_all_inputs_once_per_name(self):
        devices, _ = self._list(self._sd(default_in=-1, hostapi_default=99))
        names = [d["name"] for d in devices]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("Webcam C920", names)


class MicTestToolTests(unittest.TestCase):
    """tools/mic_test.py: diagnostics only (what PortAudio reports); no plugin message any more."""

    def test_writes_the_output_file_only(self):
        import importlib.util
        import tempfile
        from pathlib import Path
        from unittest import mock

        from aibody_companion.audio import capture

        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("mic_test", root / "tools" / "mic_test.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        sd = WindowsDeviceListTests()._sd(default_in=13)
        sd.get_portaudio_version = lambda: (1, "PortAudio V19.7.0-fake")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(capture, "_sounddevice", lambda: sd), \
                mock.patch("builtins.print"):
            rc = tool.main([], out_dir=Path(tmp))
            self.assertEqual(rc, 0)
            text = (Path(tmp) / "mic_test_output.txt").read_text(encoding="utf-8")
            for section in ("== Host-APIs ==", "== All devices, raw (24) ==", "== Input devices per host API ==",
                            "Windows WASAPI: 4", "Input devices of the default host API (4)"):
                self.assertIn(section, text)
            self.assertEqual(sorted(f.name for f in Path(tmp).iterdir()), ["mic_test_output.txt"],
                             "no devices message, no plugin inbox")
