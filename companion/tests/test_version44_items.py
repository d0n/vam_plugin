"""Version 44 (Leon, 21.11.2026 20:39-21:09): the setup carries and copies d0n.AIBody.<v>.var, removes the other
d0n.AIBody.<n>.var on every install, says when the same / an older version is installed, ends a running companion
before replacing its files (pystray refused Restart Manager), writes a log; Speech volume up to 3 for speech and test tones:
a plain linear gain on the companion's WAVs (no limiter, Leon 21:16) and louder copies of the bundled test tone."""
from __future__ import annotations

import array
import importlib.util
import io
import json
import math
import struct
import tempfile
import wave
from pathlib import Path
from unittest import TestCase

from aibody_companion import settings_file, winapp
from aibody_companion.orchestrator import Companion as Orchestrator
from aibody_companion.pipeline import tts

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
ISS = ROOT / "packaging" / "companion" / "AIBodyCompanion.iss"
WF = ROOT / ".github" / "workflows" / "companion-windows.yml"


def build_var_module():
    spec = importlib.util.spec_from_file_location("build_var", ROOT / "tools" / "build_var.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sine(peak: float, n: int = 2205) -> bytes:
    return b"".join(struct.pack("<h", int(peak * math.sin(2 * math.pi * 440 * i / 22050) * 32767)) for i in range(n))


def samples(pcm: bytes) -> array.array:
    a = array.array("h")
    a.frombytes(pcm)
    return a


def rms(a) -> float:
    return math.sqrt(sum(x * x for x in a) / len(a))


class VolumeTests(TestCase):
    def tearDown(self):
        tts.set_output_gain(1.0)

    def test_gain_mapping_and_ranges(self):
        self.assertEqual([tts.output_gain_for(v) for v in (0, 0.5, 1, 1.7, 3, 9, "x", float("nan"))],
                         [1.0, 1.0, 1.0, 1.7, 3.0, 3.0, 1.0, 1.0])
        self.assertEqual(settings_file.RANGES[("body", "speech_volume")], (0.0, 3.0))
        self.assertEqual(settings_file.DEFAULTS["body"]["speech_volume"], 1.0)   # default unchanged
        schema = json.loads((ROOT / "protocol" / "schema" / "config.schema.json").read_text(encoding="utf-8"))
        self.assertIn('"maximum": 3.0', json.dumps(schema["properties"]["body"]["properties"]["speech_volume"]))

    def test_plain_linear_gain_without_limiter(self):
        pcm = sine(0.2)
        self.assertEqual(tts.apply_gain(pcm, 1.0), pcm)                     # volume <= 1: unchanged bytes
        for gain in (1.5, 2.0, 3.0):
            out, src = samples(tts.apply_gain(pcm, gain)), samples(pcm)
            self.assertEqual(list(out), [max(-32768, min(32767, int(round(x * gain)))) for x in src])   # exactly linear
        loud = samples(tts.apply_gain(sine(0.7), 3.0))
        self.assertEqual(max(loud), 32767)                                  # only cut to the 16-bit range
        self.assertEqual(min(loud), -32768)
        self.assertEqual((tts.gained_sample(1000, 2.5), tts.gained_sample(-20000, 2.0), tts.gained_sample(30000, 3.0)),
                         (2500, -32768, 32767))
        src = (ROOT / "companion" / "aibody_companion" / "pipeline" / "tts.py").read_text(encoding="utf-8")
        self.assertNotIn("tanh", src)
        self.assertNotIn("soft_limit", src)

    def test_every_written_wav_gets_the_gain(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, riff = Path(tmp) / "a.wav", Path(tmp) / "b.wav"
            tts.set_output_gain(2.0)
            tts.write_pcm_wav(sine(0.2), 22050, raw)
            tts.write_audio(tts.pcm_to_wav_bytes(sine(0.2), 22050), 22050, riff)   # engines that return a WAV
            for path in (raw, riff):
                with wave.open(str(path), "rb") as w:
                    out = samples(w.readframes(w.getnframes()))
                self.assertAlmostEqual(rms(out) / rms(samples(sine(0.2))), 2.0, delta=0.05, msg=path.name)
            tts.set_output_gain(1.0)
            tts.write_pcm_wav(sine(0.2), 22050, raw)
            with wave.open(str(raw), "rb") as w:
                self.assertEqual(w.readframes(w.getnframes()), sine(0.2))

    def test_config_event_and_config_json_set_the_gain(self):
        self.assertEqual(Orchestrator.apply_body(None, {"speech_volume": 2.5}), [])
        self.assertEqual(tts.output_gain(), 2.5)
        self.assertEqual(Orchestrator.apply_body(None, {"speech_volume": 0.4}), [])
        self.assertEqual(tts.output_gain(), 1.0)
        self.assertTrue(Orchestrator.apply_body(None, {"speech_volume": 4}))
        self.assertTrue(Orchestrator.apply_body(None, {"speech_volume": "loud"}))
        self.assertEqual(Orchestrator.apply_body(None, None), [])
        orch = (ROOT / "companion" / "aibody_companion" / "orchestrator.py").read_text(encoding="utf-8")
        self.assertIn('errors += self.apply_body(event.get("body"))', orch)
        sf = (ROOT / "companion" / "aibody_companion" / "settings_file.py").read_text(encoding="utf-8")
        self.assertIn('tts.set_output_gain(data["body"]["speech_volume"])', sf)

    def test_plugin_slider_head_volume_and_config_event(self):
        body = (SRC / "Body.cs").read_text(encoding="utf-8")
        # 22.11.2026 (Leon 04:15): percent slider 0..300; the factor storable stays (no slider) for saved scenes
        self.assertIn('new JSONStorableFloat("Speech volume (%)", 100f, (float v) => SetSpeechVolume(v), 0f, VolumePercentMax);', body)
        self.assertIn('new JSONStorableFloat("Speech volume", 1f, (float v) => SetLegacySpeechVolume(v), 0f, 3f);', body)
        self.assertIn("folder + \"/\" + TestToneFileFor(SpeechVolume)", body)
        self.assertIn('if (volume >= 2.5f) return "AIBodyTest3.wav";', body)
        self.assertIn('if (volume >= 1.5f) return "AIBodyTest2.wav";', body)
        sp = (SRC / "SpeechPlayer.cs").read_text(encoding="utf-8")
        self.assertIn("public float HeadVolume { get { return Mathf.Min(_volume, 1f); } }", sp)
        self.assertNotIn("_control.volume = _volume;", sp)
        self.assertIn("public const float MaxVolume = 3f;", sp)
        main = (SRC / "AIBody.cs").read_text(encoding="utf-8")
        self.assertIn('body["speech_volume"].AsFloat = _body.SpeechVolume;', main)
        self.assertIn('evt["body"] = body;', main)
        self.assertIn("<b>Speech volume (%)</b> 100 is the full volume", (SRC / "AppLink.cs").read_text(encoding="utf-8"))

    def test_louder_test_tone_copies_use_the_same_linear_gain(self):
        bv = build_var_module()
        for v, g in ((1000, 2), (-20000, 2), (30000, 3), (-5, 3)):
            self.assertEqual(bv.gained_sample(v, g), tts.gained_sample(v, g))
        self.assertEqual(bv.LOUD_TEST_TONES, {2: "AIBodyTest2.wav", 3: "AIBodyTest3.wav"})
        self.assertNotIn("tanh", (ROOT / "tools" / "build_var.py").read_text(encoding="utf-8"))
        tones = []
        for gain in (1, 2, 3):
            with wave.open(io.BytesIO(bv.test_tone_wav(gain=gain)), "rb") as w:
                tones.append(samples(w.readframes(w.getnframes())))
        quiet = [i for i, x in enumerate(tones[0]) if abs(x) < 8000]       # no 16-bit cut there even at 3x
        for i in quiet[:500]:
            self.assertEqual(tones[1][i], tones[0][i] * 2)
            self.assertEqual(tones[2][i], tones[0][i] * 3)
        self.assertLess(rms(tones[0]) * 1.6, rms(tones[1]))
        self.assertLess(rms(tones[1]) * 1.1, rms(tones[2]))


class TrayCloseTests(TestCase):
    def test_close_requests_quit_instead_of_being_refused(self):
        class Icon:
            def __init__(self):
                self._message_handlers = {}
        icon, quits = Icon(), []
        self.assertTrue(winapp.add_close_handlers(icon, lambda: quits.append(1)))
        h = icon._message_handlers
        self.assertEqual(h[winapp.WM_QUERYENDSESSION](0, 1), 1)            # TRUE: may be closed (was 0 = refuse)
        h[winapp.WM_ENDSESSION](0, 0)
        self.assertEqual(quits, [])                                         # session goes on: stay
        h[winapp.WM_ENDSESSION](1, 0)
        h[winapp.WM_CLOSE](0, 0)
        self.assertEqual(quits, [1, 1])
        self.assertEqual((winapp.WM_CLOSE, winapp.WM_QUERYENDSESSION, winapp.WM_ENDSESSION), (0x10, 0x11, 0x16))
        self.assertFalse(winapp.add_close_handlers(object(), lambda: None))
        src = (ROOT / "companion" / "aibody_companion" / "winapp.py").read_text(encoding="utf-8")
        self.assertIn("add_close_handlers(icon, on_quit)", src)
        self.assertIn('"version": __version__', src)
        self.assertIn("pystray==0.19.5", WF.read_text(encoding="utf-8"))


class InstallerTests(TestCase):
    def setUp(self):
        self.iss = ISS.read_text(encoding="utf-8")

    def test_package_is_bundled_and_copied(self):
        self.assertIn("#error VarFile is not defined", self.iss)
        self.assertIn('Source: "{#VarFile}"; DestDir: "{code:AddonDir}"; Flags: ignoreversion; Check: HaveVamDir', self.iss)
        self.assertIn("Result := AddBackslash(ChosenVamDir()) + 'AddonPackages';", self.iss)
        wf = WF.read_text(encoding="utf-8")
        self.assertLess(wf.index("python tools/build_var.py --version"), wf.index("& $iscc"))
        self.assertIn('"/DVarFile=${{ steps.var.outputs.path }}" "/DVarSha256=${{ steps.var.outputs.sha256 }}"', wf)
        self.assertIn("dist/d0n.AIBody.${{ steps.ver.outputs.version }}.var", wf)   # artifact = the release VAR

    def test_old_packages_removed_on_every_install(self):
        # since Leon 22:25 without an option, and only after the new package is in place (test_package_after_install.py)
        self.assertNotIn("removeoldvars", self.iss)
        step = self.iss[self.iss.index("procedure PlacePackage"):self.iss.index("procedure RegisterPreviousData")]
        self.assertIn("DeleteOwnVars(Dir, ThisVar);", step)
        self.assertNotIn("InstalledVersion", step)                           # not tied to an existing install
        self.assertNotIn("[InstallDelete]", self.iss)                        # VARs are the only cleanup (Leon 21:08)
        wf = WF.read_text(encoding="utf-8")
        self.assertIn('Assert-Packages "fresh install"', wf)
        self.assertIn("Existing install: none \\(new install\\)", wf)

    def test_running_companion_is_ended_and_logging_on(self):
        self.assertIn("CloseApplications=force", self.iss)
        self.assertIn("SetupLogging=yes", self.iss)
        prep = self.iss[self.iss.index("function PrepareToInstall"):]
        self.assertIn("StopCompanion();", prep[:200])
        self.assertIn("'/F /IM \"AIBody Companion.exe\"'", self.iss)        # no /T since Leon 21:25
        self.assertIn("if Code = 128 then", self.iss)
        wf = WF.read_text(encoding="utf-8")
        self.assertIn("$running = Start-Process -FilePath $exe -PassThru", wf)
        self.assertIn("if (-not $running.HasExited) { throw \"the running companion was not ended by the reinstall\" }", wf)
        self.assertIn('Assert-Packages "same-version reinstall"', wf)

    def test_existing_install_is_reported(self):
        init = self.iss[self.iss.index("function InitializeSetup"):self.iss.index("procedure InitializeWizard")]
        self.assertIn("Result := CheckExistingInstall();", init)
        check = self.iss[self.iss.index("function CheckExistingInstall"):self.iss.index("function InitializeSetup")]
        for text in ("' is already installed ('", "'OK: reinstall / repair.", "'Update from AIBody '",
                     "'Cancel: stop the setup and change nothing.'", "if WizardSilent() then",
                     "MsgBox(Text, mbConfirmation, MB_OKCANCEL) <> IDOK", "ThisVarState(Dir)"):
            self.assertIn(text, check)
        self.assertIn("Sha := GetSHA256OfFile(Path);", self.iss)
        self.assertIn("RegQueryStringValue(HKCU, UninstKey(), 'DisplayVersion', Result)", self.iss)
        wf = WF.read_text(encoding="utf-8")
        self.assertIn("Existing install: same version $v", wf)
        self.assertIn('"Update from AIBody 43 to $v"', wf)
