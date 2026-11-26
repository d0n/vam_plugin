"""Version 51 (Don, 22.11.2026 20:58): after 'Reset to Default' no dropdown may be empty. Enumerates every chooser of
the plugin source and checks that it has a non-empty built-in list or is refilled after the reset; runs the plugin's
real list code (EnsureChoices, the reset loop of SettingsDefaults.ResetAll, Body.SetMenu) with a fake chooser in dotnet."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from .test_plugin_menu import method_body, source

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
DOTNET = shutil.which("dotnet") or str(Path.home() / ".dotnet" / "dotnet")

# chooser field -> how it gets a non-empty list after the reset (the AI model text field is no chooser)
REFILLED_BY_APPLINK = ["_sttJson", "_llmJson", "_ttsJson", "_aiModeJson", "_voiceJson", "_languageJson"]


def all_choosers():
    found = []
    for path in sorted(SRC.glob("*.cs")):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"(\w+)\s*=\s*new JSONStorableStringChooser\(([^;]*)", text):
            found.append((path.name, m.group(1), m.group(2)))
    return found


class ChooserEnumerationTests(unittest.TestCase):
    def test_every_chooser_is_known_and_has_a_list_after_the_reset(self):
        choosers = all_choosers()
        names = {f"{f}:{v}" for f, v, _ in choosers}
        expected = {
            "AppLink.cs:_aiModeJson", "AppLink.cs:_voiceJson", "AppLink.cs:_personaJson", "AppLink.cs:_languageJson",
            "AppLink.cs:c",                                        # the 3 engine menus (Engine(name, choices, default))
            "Body.cs:_idlePoolJson",                               # version 66: a fixed list of two labels, nothing to refill
            "Body.cs:_idlePoseDefaultJson", "Body.cs:_poseCommandChoiceJson",
            "CharacterWizard.cs:_aiGenderJson", "CharacterWizard.cs:_userGenderJson",
            "MicConfig.cs:Mode", "MicConfig.cs:VadEngine",
            "DmPluginState.cs:personalityChoice", "DmThrustController.cs:thrustAtomChooser",   # Dollmaster: not reset
        }
        self.assertEqual(names, expected, "a new chooser needs a list after Reset to Default (add it here and refill it)")
        link = method_body(source("AppLink.cs"), "public void RefreshAllChoices()")
        for field in REFILLED_BY_APPLINK:
            self.assertIn(f"EnsureChoices({field},", link, field)
        self.assertIn("RefreshPersonaChoices();", link)
        self.assertIn("_mic.RefreshChoices();", link)
        mic = method_body(source("MicConfig.cs"), "public void RefreshChoices()")
        self.assertIn("EnsureChoices(Mode, new[] { ModeVad, ModePtt })", mic)
        self.assertIn("EnsureChoices(VadEngine, new[] { VadAuto, VadBuiltIn, VadWebRtc, VadSilero })", mic)
        chars = method_body(source("Body.cs"), "public void RefreshCharacterChoices()")
        for part in ("_poseCommandChoiceJson.choices = commands;", "_idlePoseDefaultJson.choices = homes;"):
            self.assertIn(part, chars, part)
        for gone in ("_expressionChoiceJson", "_gestureChoiceJson", "SetMenu("):   # version 66: the menus are gone
            self.assertNotIn(gone, chars, gone)
        engine = method_body(source("AppLink.cs"), "private JSONStorableStringChooser Engine(")
        self.assertIn("new List<string>(choices)", engine)
        for f, v, args in choosers:
            if f in ("CharacterWizard.cs",):
                self.assertIn("genders", args)   # "", Female, Male: "" = not answered yet (the wizard asks)
            if f == "MicConfig.cs" or v in ("_aiModeJson",):
                self.assertIn("new List<string> {", args, v)

    def test_reset_refills_every_menu_after_reset_all(self):
        reset = method_body(source("AIBody.cs"), "private void ConfirmReset()")
        i = reset.index("Defaults.ResetAll(this)")
        self.assertLess(i, reset.index("_link.RefreshAllChoices();"))
        self.assertLess(i, reset.index("_body.RefreshCharacterChoices();"))
        self.assertLess(reset.index("_body.RefreshCharacterChoices();"), reset.index("_body.RebuildTab = true;"))
        loop = method_body(source("UiHelper.cs"), "public int ResetAll(MVRScript plugin)")
        self.assertIn("withDefault.Insert(0, _chooserDefaults[i]);", loop)


# -- the real list code with a fake chooser ------------------------------------------------------------------------

HARNESS = r"""
using System;
using System.Collections.Generic;
using System.Text.Json;
public class JSONStorableStringChooser
{
    public string name; public string val; public List<string> choices;
    public JSONStorableStringChooser(string n, List<string> c, string v) { name = n; choices = c; val = v; }
}
public static class Real
{
    public static void EnsureChoices__ENSURE__
    public static void ResetLoop(List<JSONStorableStringChooser> _choosers, List<string> _chooserDefaults)
    { int changed = 0; __LOOP__ }
}
public static class Program
{
    public static int Main()
    {
        // the plugin's choosers with their start lists and defaults (version 51 source), then a "broken" state as
        // reported (heartbeat lists replaced, values not in the list), then the reset path of ConfirmReset
        var engines = new[] { "stt|xai,null", "llm|xai,ollama,echo", "tts|xai,elevenlabs,tone" };
        var all = new List<JSONStorableStringChooser>(); var defaults = new List<string>(); var builtIn = new Dictionary<string, string[]>();
        foreach (string e in engines) { string[] p = e.Split('|'); var b = p[1].Split(','); builtIn[p[0]] = b; all.Add(new JSONStorableStringChooser(p[0], new List<string>(b), "xai")); defaults.Add("xai"); }
        string[][] fixedLists = {
            new[] { "AI mode", "qa", "qa,auto,realtime,chain" }, new[] { "Voice", "eve", "eve,ara,rex,sal,leo" },
            new[] { "Language", "en", "en,de" }, new[] { "Mic mode", "vad", "vad,ptt" }, new[] { "VAD engine", "auto", "auto,builtin,webrtc,silero" },
            new[] { "Persona", "Anna", "Anna,Marc" }, new[] { "Idle default pose", "Stand Up", "Stand Up" } };
        foreach (var f in fixedLists) { builtIn[f[0]] = f[2].Split(','); all.Add(new JSONStorableStringChooser(f[0], new List<string>(builtIn[f[0]]), f[1])); defaults.Add(f[1]); }
        foreach (var c in all) { c.choices = new List<string>(); c.val = "echo"; }   // emptied lists, foreign values
        Real.ResetLoop(all, defaults);
        foreach (var c in all) Real.EnsureChoices(c, builtIn[c.name]);
        var rows = new List<string>();
        foreach (var c in all) rows.Add(c.name + "=" + c.val + "|" + string.Join(",", c.choices));
        Console.WriteLine(JsonSerializer.Serialize(rows));
        return 0;
    }
}
"""


def signature_rest(text, signature):
    body = method_body(text, signature)
    start = text.index(signature) + len(signature)
    return text[start:text.index(body, start)] + body


@unittest.skipUnless(Path(DOTNET).exists(), "dotnet SDK not installed")
class RealListCodeTests(unittest.TestCase):
    def test_after_the_reset_every_menu_has_its_list_and_its_value_is_in_it(self):
        applink, body, ui = source("AppLink.cs"), source("Body.cs"), source("UiHelper.cs")
        # version 65: EnsureChoices / SetMenu call UiChooser; include that class (it only needs .val / .choices)
        start = ui.index("public static class UiChooser")
        depth, end = 0, start
        for i, ch in enumerate(ui[start:], start):
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        uichooser = ui[start:end] + "\n"
        ensure = signature_rest(applink, "public static void EnsureChoices")
        reset = method_body(ui, "public int ResetAll(MVRScript plugin)")
        loop = reset[reset.index("for (int i = 0; i < _choosers.Count; i++)"):reset.index("for (int i = 0; i < _colorNames.Count; i++)")]
        code = HARNESS.replace("__ENSURE__", ensure).replace("__LOOP__", loop)
        code = code.replace("using System.Text.Json;", "using System.Text.Json;\n" + uichooser, 1)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Program.cs").write_text(code, encoding="utf-8")
            (folder / "H.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework>
<OutputType>Exe</OutputType><Nullable>disable</Nullable><NoWarn>CS0219</NoWarn></PropertyGroup></Project>""", encoding="utf-8")
            env = {**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}
            build = subprocess.run([DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder,
                                   capture_output=True, text=True, timeout=240, env=env)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([DOTNET, str(folder / "out" / "H.dll")], capture_output=True, text=True, timeout=60, env=env)
            self.assertEqual(run.returncode, 0, run.stderr)
        rows = json.loads(run.stdout.splitlines()[0])
        self.assertEqual(len(rows), 10)   # version 66: no Expression menu any more
        for row in rows:
            name, rest = row.split("=", 1)
            val, choices = rest.split("|", 1)
            entries = choices.split(",")
            self.assertTrue(choices and all(entries), row)
            self.assertIn(val, entries, row)
        by_name = {r.split("=", 1)[0]: r for r in rows}
        self.assertTrue(by_name["llm"].startswith("llm=xai|xai,ollama,echo"), by_name["llm"])
        self.assertTrue(by_name["stt"].startswith("stt=xai|xai,null"), by_name["stt"])
        self.assertNotIn("Expression", by_name)


if __name__ == "__main__":
    unittest.main()
