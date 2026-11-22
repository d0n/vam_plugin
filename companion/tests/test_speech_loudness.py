"""After v45 (Leon, 22.11.2026 04:02): "Speech volume 3 made no noticeable difference" and "much quieter away from the
head". (1) The plugin -> companion -> WAV gain chain works; a WAV cannot go above full scale, so above ~1.5x the gain
mostly clips (measured below) and the companion now logs that. (2) VaM's head audio is 3D with a logarithmic rolloff
beyond its minDistance: the plugin sets minDistance ("Full volume distance (m)", default 2) and maxDistance through the
head audio's own storable params (EasyMoan / VAMMoan, docs/API_AUDIT.md E38) and restores the scene's values."""
from __future__ import annotations

import array
import json
import math
import tempfile
import wave
from pathlib import Path
from unittest import TestCase

from aibody_companion import settings_file
from aibody_companion.orchestrator import Companion as Orchestrator
from aibody_companion.pipeline import tts

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def rms(samples) -> float:
    return math.sqrt(sum(v * v for v in samples) / len(samples))


class GainChainTests(TestCase):
    def tearDown(self):
        tts.set_output_gain(1.0)
        tts._LEVEL["logged_gain"] = None

    def test_config_event_volume_reaches_the_wav(self):
        # plugin: slider -> MarkConfigDirty -> config event "body": {"speech_volume"}; companion: apply_body -> gain
        self.assertIn('body["speech_volume"].AsFloat = _body.SpeechVolume;', source("AIBody.cs"))
        self.assertIn("if (OnSettingsChanged != null) OnSettingsChanged();", source("Body.cs"))
        errors = Orchestrator.apply_body(object(), {"speech_volume": 3})
        self.assertEqual(errors, [])
        self.assertEqual(tts.output_gain(), 3.0)
        pcm = array.array("h", [1000, -1000, 5000, -5000]).tobytes()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "u.wav"
            with self.assertLogs("aibody_companion.pipeline.tts", "INFO") as logs:
                tts.write_pcm_wav(pcm, 24000, path)
            with wave.open(str(path), "rb") as w:
                out = array.array("h", w.readframes(w.getnframes()))
        self.assertEqual(list(out), [3000, -3000, 15000, -15000])
        self.assertIn("Speech level: peak", logs.output[0])
        self.assertIn("gain x3.00", logs.output[0])

    def test_level_logged_once_per_gain(self):
        tts.set_output_gain(2.0)
        pcm = array.array("h", [30000, -30000, 100, -100]).tobytes()
        with self.assertLogs("aibody_companion.pipeline.tts", "INFO") as logs:
            tts.log_level_once(pcm)
            tts.log_level_once(pcm)
            tts.log.info("end")
        self.assertEqual(len(logs.output), 2)
        self.assertIn("50.0% of the samples cut", logs.output[0])
        self.assertIn("only adds distortion", logs.output[0])

    def test_full_scale_limits_the_gain(self):
        # the bundled test tone (peak 0.70): 3x is only ~+6.7 dB, ~1.5 dB above 2x: the file is at its limit
        tone = tts.test_tone_pcm()
        base = rms(array.array("h", tone))
        db = {}
        for g in (2.0, 3.0):
            out = array.array("h", tts.apply_gain(tone, g))
            db[g] = 20 * math.log10(rms(out) / base)
        self.assertLess(db[3.0], 7.5)
        self.assertLess(db[3.0] - db[2.0], 2.5)
        self.assertGreater(tts.level_report(tone, 3.0)["clipped"], 0.2)

    def test_schema_text_without_soft_limiter(self):
        text = (ROOT / "protocol" / "schema" / "event.schema.json").read_text(encoding="utf-8")
        self.assertNotIn("soft limiter", text)
        self.assertIn("plain linear gain, no limiter", text)


class HeadAudioDistanceTests(TestCase):
    def test_player_sets_distance_params_and_restores(self):
        sp = source("SpeechPlayer.cs")
        for part in ('GetFloatJSONParam("volume")', 'GetFloatJSONParam("minDistance")', 'GetFloatJSONParam("maxDistance")',
                     "_minDistanceParam.val = _fullVolumeDistance;", "_maxDistanceParam.val = FarDistance;",
                     "public void RestoreHeadAudio()", "_minDistanceParam.val = _savedMinDistance;",
                     "public const float DefaultFullVolumeDistance = 2f;", "public const float FarDistance = 500f;"):
            self.assertIn(part, sp)
        self.assertNotIn(".spatialBlend =", sp)     # no evidenced param: the voice stays 3D
        self.assertNotIn(".rolloffMode =", sp)
        play = sp[sp.index("private void Play(Utterance u)"):sp.index("private void PlayNow(Utterance u)")]
        self.assertIn("ApplyHeadAudio();", play)    # before every clip
        self.assertIn("_speech.RestoreHeadAudio();", source("Body.cs"))

    def test_slider_persisted_and_explained(self):
        body = source("Body.cs")
        self.assertIn('new JSONStorableFloat("Full volume distance (m)", SpeechPlayer.DefaultFullVolumeDistance,', body)
        self.assertIn("SettingsDefaults.Float(_plugin, _distanceJson);", body)
        sound = body[body.index("public void BuildSoundSection"):body.index("public bool BodyControl")]
        self.assertLess(sound.index("page.Slider(_volumeJson);"), sound.index("page.Slider(_distanceJson);"))
        self.assertIn('body["full_volume_distance"].AsFloat = _distanceJson.val;', body)
        self.assertIn('Protocol.GetFloat(body, "full_volume_distance", _distanceJson.val)', body)
        self.assertIn("<b>Full volume distance (m)</b>", source("AppLink.cs"))
        self.assertEqual(settings_file.DEFAULTS["body"]["full_volume_distance"], 2.0)
        self.assertEqual(settings_file.RANGES[("body", "full_volume_distance")], (0.3, 10.0))
        schema = json.loads((ROOT / "protocol" / "schema" / "config.schema.json").read_text(encoding="utf-8"))
        self.assertIn("full_volume_distance", schema["properties"]["body"]["properties"])

    def test_scene_head_audio_not_4_cm(self):
        # the shipped AI-Buddy scene had minDistance 0.04 m: -28 dB at 1 m, -34 dB at 2 m (Leon 22.11.2026 04:14: 2 m)
        scene = json.loads((ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8"))
        ai = [a for a in scene["atoms"] if a["id"] == "AI"][0]
        head = [s for s in ai["storables"] if s["id"] == "HeadAudioSource"][0]
        self.assertEqual(float(head["minDistance"]), 2.0)

    def test_evidence_recorded(self):
        audit = (ROOT / "docs" / "API_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("| E38 |", audit)
        self.assertIn("vam-easymoan", audit)
        self.assertIn('SetFloatParamValue("minDistance"', audit)


class PercentSliderTests(TestCase):
    """Leon 22.11.2026 04:15: Speech volume in percent 0..1000 (04:16; 0..300 at 04:15), default 100 (= factor 0..10, default 1). The companion,
    config.json and the config event keep the factor; scenes saved with the old factor storable load as percent."""

    def test_percent_slider_and_factor_everywhere_else(self):
        body = source("Body.cs")
        self.assertIn('new JSONStorableFloat("Speech volume (%)", 100f, (float v) => SetSpeechVolume(v), 0f, VolumePercentMax);', body)
        self.assertIn("public const float VolumePercentMax = 1000f;", body)
        self.assertIn("public const float MaxVolume = 10f;", source("SpeechPlayer.cs"))
        self.assertEqual(tts.MAX_SPEECH_VOLUME, 10.0)
        self.assertEqual(tts.output_gain_for(10), 10.0)
        self.assertEqual(tts.gained_sample(1000, 10.0), 10000)        # plain linear gain, no limiter
        self.assertEqual(tts.gained_sample(5000, 10.0), 32767)        # only cut to the 16-bit range
        self.assertIn("public float SpeechVolume { get { return _volumeJson != null ? _volumeJson.val / 100f : 1f; } }", body)
        self.assertIn('body["speech_volume"].AsFloat = SpeechVolume;', body)            # config.json: factor
        self.assertIn('PercentFromFactor(Protocol.GetFloat(body, "speech_volume", SpeechVolume))', body)
        self.assertIn("if (_speech != null) _speech.Volume = percent / 100f;", body)
        self.assertIn("speech.Volume = SpeechVolume;", body)
        self.assertIn('body["speech_volume"].AsFloat = _body.SpeechVolume;', source("AIBody.cs"))   # event: factor
        self.assertEqual(settings_file.RANGES[("body", "speech_volume")], (0.0, 10.0))
        schema = json.loads((ROOT / "protocol" / "schema" / "config.schema.json").read_text(encoding="utf-8"))
        self.assertIn('"maximum": 10.0', json.dumps(schema["properties"]["body"]["properties"]["speech_volume"]))
        self.assertIn("(0 to 1000, ", source("AppLink.cs"))
        self.assertIn("<b>Speech volume (%)</b> 100 is the full volume", source("AppLink.cs"))

    def test_old_scenes_migrate(self):
        body = source("Body.cs")
        self.assertIn('new JSONStorableFloat("Speech volume", 1f, (float v) => SetLegacySpeechVolume(v), 0f, 10f);', body)
        self.assertIn("SettingsDefaults.Float(_plugin, _legacyVolumeJson);", body)
        legacy = body[body.index("private void SetLegacySpeechVolume"):body.index("public static float PercentFromFactor")]
        self.assertIn("_volumeJson.val = PercentFromFactor(factor);", legacy)
        self.assertIn("if (_syncingVolume || _volumeJson == null) return;", legacy)
        conv = body[body.index("public static float PercentFromFactor"):body.index("public float SpeechVolume")]
        self.assertIn("Math.Max(0f, Math.Min(factor, VolumePercentMax / 100f)) * 100f", conv)
        # no slider for the old storable
        self.assertNotIn("page.Slider(_legacyVolumeJson)", body)

    def test_test_tone_copies_at_200_and_300(self):
        body = source("Body.cs")
        self.assertIn('if (volume >= 2.5f) return "AIBodyTest3.wav";', body)   # factor: 250 % and up -> 3x (300 %)
        self.assertIn('if (volume >= 1.5f) return "AIBodyTest2.wav";', body)   # 150..250 % -> 2x (200 %)
        self.assertIn("TestToneFileFor(SpeechVolume)", body)                  # SpeechVolume = percent / 100
