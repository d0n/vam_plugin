"""Version 47 (Don 22.11.2026 12:17, v46 test): in v46 the AI's speech no longer started (companion.log: every clip
"did not start playing within 15 s", also from the Saves/PluginData fallback folder), only the test tone was heard,
and the sound was worse than in v45. Diff v45 (169940c) .. v46 (eb7992b) on the audio path: the companion writes the
same WAV bytes (only a level log was added), the percent slider maps 100 % to the old factor 1; the plugin's
playback changed in one place: SpeechPlayer.ApplyHeadAudio wrote the head AudioSourceControl's storable params
"volume", "minDistance" (2 m) and "maxDistance" (500) when the head audio was found, on every volume change and
before EVERY clip (Play), and the scene's HeadAudioSource minDistance went 0.04 -> 2. v47 goes back to v45 there:
only _control.volume = HeadVolume, no distance params, scene minDistance 0.04, no "Full volume distance (m)" slider
(version 48 brings the slider back the EasyMoan way, outside the playback path: test_version48.py).
Plus the two small items of the same test: no Breath morph / Breath1 boxes, the scene thumbnail always in the VAR."""
from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest import TestCase

from aibody_companion import settings_file

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def git_show(rev_path: str) -> str | None:
    try:
        return subprocess.run(["git", "show", rev_path], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None   # no git history (e.g. a source tarball): the checks below still run on the current files


class HeadAudioLikeV45Tests(TestCase):
    def test_player_writes_no_head_audio_params(self):
        # version 48 brought a distance setting back (test_version48.py), but outside the v45 playback path
        sp = source("SpeechPlayer.cs")
        for gone in ("ApplyHeadAudio", "RestoreHeadAudio", 'GetFloatJSONParam("volume")', 'SetFloatParamValue("volume"'):
            self.assertNotIn(gone, sp)

    def test_volume_is_set_exactly_like_v45(self):
        sp = source("SpeechPlayer.cs")
        play = sp[sp.index("private void Play(Utterance u)"):sp.index("private void PlayNow(Utterance u)")]
        self.assertIn("_control.volume = HeadVolume;", play)
        self.assertEqual(sp.count("_control.volume = HeadVolume;"), 3)   # found, Volume setter, Play: as in v45
        self.assertIn("if (_control != null) _control.volume = HeadVolume;", sp)
        self.assertIn("public float HeadVolume { get { return Mathf.Min(_volume, 1f); } }", sp)

    def test_v45_playback_functions_unchanged(self):
        old = git_show("169940c:src/AIBody/SpeechPlayer.cs")
        if old is None:
            self.skipTest("no git history")
        new = source("SpeechPlayer.cs")
        for start, end in (("private bool Resolve()", "public bool IsSpeaking"),
                           ("private void Play(Utterance u)", "/// <summary>\n        /// True once the clip's audio DATA"),
                           ("public void Update(float deltaTime)", "/// <summary>\n        /// Readiness signal")):
            seg = new[new.index(start):new.index(end)]
            # version 54 (Don 23:31): the only additions are the stale-clip check in Update and its own method
            seg = seg.replace("            DropStale(DateTime.UtcNow);   // version 54\n", "")
            if "/// <summary>Version 54: nothing started" in seg:
                seg = seg[:seg.index("/// <summary>Version 54: nothing started")]
            self.assertEqual(old[old.index(start):old.index(end)], seg, start)

    def test_scene_head_audio_back_to_v45(self):
        scene = json.loads((ROOT / "examples" / "scenes" / "AI-Buddy.json").read_text(encoding="utf-8"))
        ai = [a for a in scene["atoms"] if a["id"] == "AI"][0]
        head = [s for s in ai["storables"] if s["id"] == "HeadAudioSource"][0]
        self.assertEqual(head["minDistance"], "0.04")
        self.assertEqual(head["spatialize"], "false")

    def test_percent_100_is_v45_factor_1(self):
        body = source("Body.cs")
        self.assertIn('new JSONStorableFloat("Speech volume (%)", 100f,', body)
        self.assertIn("public float SpeechVolume { get { return _volumeJson != null ? _volumeJson.val / 100f : 1f; } }", body)
        self.assertIn("if (_speech != null) _speech.Volume = percent / 100f;", body)
        self.assertIn("speech.Volume = SpeechVolume;", body)


class TestToneSelectionTests(TestCase):
    """The test tone file is chosen only in Body.PlayTestTone; speech from the companion never goes through it."""

    def test_only_play_test_tone_uses_the_test_tone_files(self):
        body = source("Body.cs")
        self.assertEqual(body.count("TestToneFileFor("), 2)   # definition + PlayTestTone
        tone = body[body.index("public string PlayTestTone()"):body.index("private static bool IsLocal")]
        self.assertIn("TestToneFileFor(SpeechVolume)", tone)
        for name in ("CommandRouter.cs", "AppLink.cs", "SpeechPlayer.cs"):
            self.assertNotIn("AIBodyTest", source(name), name)


class BreathMorphBoxesTests(TestCase):
    def test_boxes_gone_storable_kept(self):
        body = source("Body.cs")
        tab = body[body.index("public void BuildCharacterTab(UiPage page)"):body.index("public const string BreathMorphLabel")]
        self.assertNotIn("page.Header(BreathMorphLabel)", tab)
        self.assertNotIn("_breathMorphJson", tab)
        for kept in ("page.Toggle(_breathingJson);", "page.Slider(_breathRateJson);", "page.Slider(_breathDepthJson);"):
            self.assertIn(kept, tab)
        self.assertLess(tab.index("page.Slider(_breathDepthJson);"), tab.index('"<b>Expression and gesture</b>"'))
        self.assertIn('new JSONStorableString("Breath morph", "Breath1"', body)
        self.assertIn("SettingsDefaults.Text(_plugin, _breathMorphJson);", body)
        self.assertIn('body["breath_morph"] = _breathMorphJson.val;', body)
        self.assertIn('_breathMorphJson.val = Protocol.GetString(body, "breath_morph", _breathMorphJson.val);', body)
        self.assertIn("new BreathingController(_morphs, _breathMorphJson != null ? _breathMorphJson.val : \"Breath1\")", body)


class SceneThumbnailTests(TestCase):
    def test_the_shipped_thumbnail_is_the_one(self):
        thumb = (ROOT / "examples" / "scenes" / "AI-Buddy.jpg").read_bytes()
        self.assertEqual(len(thumb), 9280)
        self.assertTrue(thumb.startswith(b"\xff\xd8"))

    def test_build_var_checks_the_thumbnail(self):
        sys.path.insert(0, str(ROOT / "tools"))
        try:
            import build_var
        finally:
            sys.path.pop(0)
        self.assertEqual(build_var.SCENE_THUMB_PATH, "Saves/scene/AIBody/AI-Buddy.jpg")
        self.assertEqual(build_var.SCENE_PATH[:-5], build_var.SCENE_THUMB_PATH[:-4])   # same folder, same base name
        import json
        import tempfile
        meta = json.dumps({"contentList": [build_var.SCENE_PATH, build_var.SCENE_THUMB_PATH]})
        with tempfile.TemporaryDirectory() as tmp:
            # version 54: the check also wants meta.json's contentList and the loose release pair next to the .var
            (Path(tmp) / build_var.LOOSE_SCENE).write_text("{}", encoding="utf-8")
            (Path(tmp) / build_var.LOOSE_THUMB).write_bytes(build_var.SCENE_THUMB.read_bytes())
            good = Path(tmp) / "good.var"
            with zipfile.ZipFile(good, "w") as z:
                z.writestr("meta.json", meta)
                z.writestr(build_var.SCENE_PATH, "{}")
                z.writestr(build_var.SCENE_THUMB_PATH, build_var.SCENE_THUMB.read_bytes())
            self.assertIsNone(build_var.check_scene_thumbnail(good))
            bad = Path(tmp) / "bad.var"
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr("meta.json", meta)
                z.writestr(build_var.SCENE_PATH, "{}")
                z.writestr("Saves/scene/AI-Buddy.jpg", build_var.SCENE_THUMB.read_bytes())   # wrong folder
            self.assertIn("has no", build_var.check_scene_thumbnail(bad))
            other = Path(tmp) / "other.var"
            with zipfile.ZipFile(other, "w") as z:
                z.writestr("meta.json", meta)
                z.writestr(build_var.SCENE_PATH, "{}")
                z.writestr(build_var.SCENE_THUMB_PATH, b"\xff\xd8not a jpeg\xff\xd9")
            self.assertIn("differs", build_var.check_scene_thumbnail(other))

    def test_built_var_has_it(self):
        version = json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"]
        var = ROOT / "dist" / f"d0n.AIBody.{version}.var"
        if not var.is_file():
            self.skipTest(f"{var.name} not built")
        with zipfile.ZipFile(var) as z:
            self.assertEqual(z.read("Saves/scene/AIBody/AI-Buddy.jpg"),
                             (ROOT / "examples" / "scenes" / "AI-Buddy.jpg").read_bytes())
