"""Version 66 (26.11.2026): the AI's facial-expression path (per-morph fade speeds, one fallback expression per answer with a
gap, no sad / angry fallback, a mild symmetric "thinking") and the stronger idle head motion and breathing. The pure C#
(MorphBlendLayer) runs in a dotnet harness."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from aibody_companion import emotion

from .test_plugin_menu import method_body
from . import test_version35 as v35

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
HARNESS = Path(__file__).parent / "csharp_blend_harness" / "Program.cs"


def src(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def layer_source() -> str:
    text = src("MorphHelper.cs")
    start = text.index("public class MorphBlendLayer")
    return "using System.Collections.Generic;\nusing UnityEngine;\nnamespace AIBody\n{\n    " + text[start:text.rindex("}")] + "}\n"


class MorphBlendLayerHarnessTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        shutil.copy(HARNESS, folder / "Program.cs")
        (folder / "Layer.cs").write_text(layer_source(), encoding="utf-8")
        (folder / "Harness.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType><Nullable>disable</Nullable>
  <EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup>
  <ItemGroup><Compile Include="Program.cs" /><Compile Include="Layer.cs" /></ItemGroup>
</Project>""", encoding="utf-8")
        result = subprocess.run([v35.DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder,
                                capture_output=True, text=True, timeout=240, env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
        if result.returncode != 0:
            raise AssertionError("harness build failed:\n" + result.stdout + result.stderr)
        cls.exe = folder / "out" / "Harness.dll"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cmds(self, *cmds):
        proc = subprocess.run([v35.DOTNET, str(self.exe)], input="".join(c + "\n" for c in cmds),
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.splitlines()

    @staticmethod
    def values(line):
        head = line.split("|")[0]
        return {k: float(v) for k, v in (x.split("=") for x in head.split(";") if x)}

    def test_old_expression_fades_in_its_own_time_not_in_17_seconds(self):
        # a smile at 0.85 is released (blend 0.4 s); a new sad brow (0.1 away from 0) is set at the same time.
        # up to v65 the layer's single speed came from the newest (tiny) target, so the smile took ~17 s to fade
        out = self.run_cmds("morph\tsmile\t0", "morph\tbrow\t0", "blend\t0.5", "set\tsmile\t0.85", "update\t0.05\t20", "print",
                            "blend\t0.4", "releaseall", "set\tbrow\t0.1", "update\t0.05\t10", "print")
        before, after = out[1], out[3]
        self.assertAlmostEqual(self.values(before)["smile"], 0.85, places=2)
        self.assertAlmostEqual(self.values(after)["smile"], 0.0, places=3, msg="faded out within 0.5 s")
        self.assertIn("active=1", after, "only the new brow is still held; the smile was dropped when its fade ended")

    def test_each_entry_has_its_own_speed(self):
        # two releases with different distances: the far morph moves faster; both arrive at the same time (blend 1 s)
        out = self.run_cmds("morph\ta\t0", "morph\tb\t0", "blend\t0.01", "set\ta\t1.0", "set\tb\t0.2", "update\t0.1\t5", "print",
                            "blend\t1.0", "releaseall", "update\t0.1\t5", "print", "update\t0.1\t6", "print")
        mid, end = self.values(out[3]), self.values(out[4])
        self.assertAlmostEqual(mid["a"], 0.5, places=2)
        self.assertAlmostEqual(mid["b"], 0.1, places=2, msg="b moves at its own, slower speed")
        self.assertEqual((end["a"], end["b"]), (0.0, 0.0))
        self.assertIn("active=0", out[4])

    def test_setting_a_target_uses_the_distance_to_the_current_value(self):
        out = self.run_cmds("morph\tm\t0.5", "blend\t0.5", "set\tm\t0.5", "update\t0.1", "print", "set\tm\t1.5", "update\t0.1", "print")
        # first: distance 0 -> at least 0.05 / 0.5 = 0.1 per second (no division by ~0, no stuck entry); second: 1.0 / 0.5 = 2 per s
        self.assertAlmostEqual(self.values(out[1])["m"], 0.5, places=3)
        self.assertAlmostEqual(self.values(out[3])["m"], 0.7, places=3)

    def test_release_all_except_keeps_the_kept_ones_and_releases_the_rest(self):
        out = self.run_cmds("morph\tkeep\t0", "morph\tgo\t0", "blend\t0.1", "set\tkeep\t0.6", "set\tgo\t0.6", "update\t0.1\t10",
                            "blend\t0.5", "releaseexcept\tkeep", "update\t0.1\t10", "print")
        self.assertAlmostEqual(self.values(out[2])["keep"], 0.6, places=3)
        self.assertAlmostEqual(self.values(out[2])["go"], 0.0, places=3)
        self.assertIn("active=1", out[2])

    def test_unknown_morph_is_reported_missing(self):
        self.assertEqual(self.run_cmds("set\tnope\t1"), ["missing"])

    def test_speed_rule_is_the_one_from_the_brief(self):
        layer = src("MorphHelper.cs")
        self.assertIn("return Mathf.Max(distance, MinDistance) / Mathf.Max(blendSeconds, MinBlend);", layer)
        self.assertIn("public const float MinDistance = 0.05f;", layer)
        self.assertIn("public const float MinBlend = 0.05f;", layer)
        self.assertNotIn("public float Speed =", layer, "no layer-wide speed any more")


class ExpressionSourceTests(TestCase):
    def setUp(self):
        self.ec = src("ExpressionController.cs")
        self.body = src("Body.cs")

    def test_no_layer_wide_speed_any_more(self):
        self.assertNotIn("_layer.Speed", self.ec)
        self.assertNotIn("SetSpeedFor", self.ec)
        self.assertIn("_layer.BlendSeconds = blendTime;", method_body(self.ec, "public void Reset(float blendTime)"))

    def test_auto_expressions_come_back_only_after_the_release_has_finished(self):
        end = method_body(self.ec, "private void EndShowing()")
        self.assertIn("_layer.ActiveCount == 0", end)
        self.assertIn("_releasePending = true;", end)
        update = method_body(self.ec, "public void Update(float deltaTime)")
        self.assertLess(update.index("_layer.Update(deltaTime);"), update.index("_releasePending && _layer.ActiveCount == 0"))
        # a new expression while the release is pending cancels it
        self.assertIn("if (on) _releasePending = false;", method_body(self.ec, "private void SetShowing(bool on)"))

    def test_reset_expression_still_goes_back_to_the_original_look_not_to_zero(self):
        layer = src("MorphHelper.cs")
        self.assertIn("e.Target = e.Original;", layer)
        self.assertIn("Original = morph.morphValue", layer)
        self.assertNotIn("Target = 0f", layer)

    def test_thinking_is_symmetric_and_mild(self):
        match = re.search(r'_presets\["thinking"\] = Preset\(([^;]*)\);', self.ec)
        self.assertIsNotNone(match)
        args = match.group(1)
        self.assertIn('"Brow Inner Up"', args)
        self.assertIn('"Brow Outer Up Left"', args)
        self.assertIn('"Brow Outer Up Right"', args)
        self.assertNotIn("Down", args, "no frown")
        self.assertNotIn("Side-Side", args, "no one-sided mouth")
        values = [float(x) for x in re.findall(r"(\d\.\d+)f", args)]
        self.assertTrue(values and max(values) <= 0.2, values)
        pairs = dict(re.findall(r'"([^"]+)", (\d\.\d+)f', args))
        self.assertEqual(pairs["Brow Outer Up Left"], pairs["Brow Outer Up Right"])

    def test_missing_auto_expressions_is_logged_once_at_info(self):
        pause = method_body(self.body, "private void PauseAutoExpressions(bool showing)")
        self.assertIn("if (enabled == null)", pause)
        self.assertIn("Log.Info(\"Auto Expressions:", pause)
        self.assertIn("_autoMissingLogged", pause)


class EmotionFallbackTests(TestCase):
    def setUp(self):
        self.now = [100.0]
        self.d = emotion.EmotionDirector({}, lambda: self.now[0])
        self.have = ["neutral", "happy", "sad", "angry", "thinking", "surprised", "listening"]

    def test_constants(self):
        self.assertEqual(self.d.FALLBACK_MIN_GAP_S, 4.0)
        self.assertEqual(self.d.FALLBACK_NEVER, ("sad", "angry"))

    def test_sad_and_angry_are_never_fallbacks_for_any_word(self):
        for text in ("Leider habe ich das vergessen.", "Das ist traurig, schade, sorry.", "Ich hasse das, wütend, damn!"):
            self.d.begin_answer()
            self.now[0] += 10
            got = self.d.for_speech(text, self.have)
            self.assertTrue(got is None or got[0] not in ("sad", "angry"), (text, got))

    def test_at_most_one_per_answer_whatever_the_sentences(self):
        self.d.begin_answer()
        sent = [self.d.for_speech(t, self.have) for t in ("Das freut mich!", "Hmm, vielleicht.", "Wow, unglaublich!", "Super, toll!")]
        self.assertEqual([x[0] for x in sent if x], ["happy"])

    def test_gap_between_two_answers_and_after_the_gap_it_works_again(self):
        self.d.begin_answer()
        self.assertEqual(self.d.for_speech("Das freut mich!", self.have)[0], "happy")
        self.d.note_sent("happy")
        self.now[0] += 3.9
        self.d.begin_answer()
        self.assertIsNone(self.d.for_speech("Wow, unglaublich!", self.have))
        self.now[0] += 0.2
        self.assertEqual(self.d.for_speech("Wow, unglaublich!", self.have)[0], "surprised")

    def test_the_ai_choice_and_the_listening_reset_are_not_touched(self):
        self.d.begin_answer()
        self.d.note_ai_expression()
        self.assertIsNone(self.d.for_speech("Das freut mich!", self.have))
        self.d.note_sent("listening")
        self.d.begin_answer()
        self.assertEqual(self.d.for_speech("Es ist Dienstag.", self.have), ("neutral", 1.0, 0.7))


class IdleMotionVisibilityTests(TestCase):
    def test_idle_head_and_chest_angles_are_doubled(self):
        idle = src("IdleController.cs")
        self.assertIn("public float MaxAngle = 8f;", idle)
        self.assertIn("public float MaxChestAngle = 5f;", idle)
        self.assertNotIn("MaxAngle = 4f", idle)
        self.assertNotIn("MaxChestAngle = 2.5f", idle)

    def test_tempo_is_roughly_doubled(self):
        idle = src("IdleController.cs")
        self.assertIn("public const float TempoFactor = 2f;", idle)
        self.assertIn("private const float ShiftMin = 2.5f;", idle)
        self.assertIn("private const float ShiftMax = 5.5f;", idle)
        self.assertEqual(len(re.findall(r"_time \* [\d.]+f \* TempoFactor", idle)), 5)

    def test_breathing_is_about_twice_as_deep_and_settings_still_scale(self):
        breath = src("BreathingController.cs")
        self.assertIn("public const float VisibilityGain = 2f;", breath)
        self.assertIn("_currentDepth * VisibilityGain", breath)
        self.assertIn("public float Depth = 0.35f;", breath, "the setting default is unchanged: it stays the scaler")
        idle = src("IdleController.cs")
        self.assertIn("public const float BreathHeadDegrees = 3f;", idle)
        self.assertIn("public const float BreathChestDegrees = 4f;", idle)
        self.assertIn("breathCycle * breathDepth * BreathHeadDegrees", idle)
        self.assertIn("breathCycle * breathDepth * BreathChestDegrees", idle)


class DocsTests(TestCase):
    def test_notes_spec_and_protocol(self):
        notes = (ROOT / "docs" / "RELEASE_NOTES_V66.md").read_text(encoding="utf-8")
        for part in ("Idle head motion and breathing are about twice as strong", "Facial expressions of the AI fixed",
                     "never *sad* or *angry*", "Reset Expression", "Grok Bot", "fewer than two entries", "T123"):
            self.assertIn(part, notes)
        self.assertNotIn("Le" + "on", notes)
        self.assertNotIn("did not work", notes)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        for part in ("**Idle motion and breathing about 2x**", "**AI facial expression path**", "FALLBACK_MIN_GAP_S"):
            self.assertIn(part, spec)
        self.assertIn("## T123 ", (ROOT / "docs" / "TEST_PROTOCOL.md").read_text(encoding="utf-8"))
