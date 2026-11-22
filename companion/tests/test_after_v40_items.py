"""After version 40, Leon 21.11.2026 17:19-17:27 (items 4-10 and his companion.log):
audio readiness (loadState Loaded + LoadAudioData, the evidenced play sequence, [audio] debug lines), the
installer's message box, all xAI voices (GET /v1/tts/voices + the docs list), every persona, Apply pose command +
Add Pose, the right column, and tool calls the model writes into its text (they were spoken).
"""
from __future__ import annotations

import json
import re
import tempfile
import threading
import time
from pathlib import Path
from unittest import TestCase

from aibody_companion import personas, protocol, voices, winapp
from aibody_companion.pipeline.sentences import InlineToolCall, StreamParser, ToolTextFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def method_body(text: str, signature: str) -> str:
    start = text.index(signature)
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise AssertionError(signature)


DOC_VOICES = ["carina", "zagan", "helix", "orion", "luna", "iris", "altair", "zenith", "perseus", "helios", "lux",
              "kepler", "rigel", "cosmo", "celeste", "ursa", "sirius", "lumen", "castor", "naksh", "atlas", "aurora",
              "liora", "ara", "eve", "leo", "rex", "sal"]


class AudioReadinessTests(TestCase):
    def setUp(self):
        self.sp = source("SpeechPlayer.cs")

    def test_ready_means_audio_data_loaded(self):
        ready = method_body(self.sp, "private bool ClipReady(")
        self.assertIn("loadState", ready)
        self.assertIn("AudioDataLoadState.Loaded", ready)
        self.assertIn("LoadAudioData()", ready)
        self.assertIn("AudioDataLoadState.Failed", self.sp)

    def test_existing_clip_is_reused_with_normalize_load_path(self):
        self.assertIn("NormalizeLoadPath(", self.sp)
        self.assertIn("GetClip(", self.sp)
        self.assertIn("QueueClip(", self.sp)

    def test_play_sequence_of_the_audited_plugins(self):
        play = method_body(self.sp, "PlayNow(")
        for call in ("PlayNowClearQueue(", ".PlayNow(", 'CallAction("PlayNow"'):
            self.assertIn(call, play)
        self.assertLess(play.index("PlayNowClearQueue("), play.index(".PlayNow("))

    def test_debug_lines_behind_verbose_log(self):
        self.assertGreaterEqual(self.sp.count('Log.Debug("[audio]'), 4)
        self.assertNotIn('Log.Info("[audio]', self.sp)

    def test_api_audit_cites_the_reference_plugins(self):
        audit = (ROOT / "docs" / "API_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("| E36 |", audit)
        for ref in ("BreathController.cs", "FreeMMD", "mmd2timeline", "Breathe.cs", "LoadAudioData"):
            self.assertIn(ref, audit)

    def test_stub_members_are_evidenced(self):
        stubs = (ROOT / "tools" / "stubs" / "UnityStubs.cs").read_text(encoding="utf-8")
        self.assertIn("enum AudioDataLoadState", stubs)
        self.assertIn("LoadAudioData", stubs)


class InstallerMessageBoxTests(TestCase):
    def test_show_note_is_a_message_box_with_ok(self):
        body = Path(winapp.__file__).read_text(encoding="utf-8")
        self.assertIn("messagebox.showinfo", body)
        self.assertIn("Click OK", winapp.RUNNING_NOTE)


class VoiceListTests(TestCase):
    def test_static_list_is_the_docs_list(self):
        self.assertEqual(list(voices.XAI_VOICES), DOC_VOICES)
        self.assertEqual(len(set(voices.XAI_VOICES)), 28)

    def test_plugin_carries_the_same_list(self):
        app = source("AppLink.cs")
        block = app[app.index("XaiVoices = {"):]
        block = block[:block.index("};")]
        self.assertEqual(re.findall(r'"([a-z]+)"', block), DOC_VOICES)
        self.assertIn('new List<string>(XaiVoices), "eve"', app)
        self.assertIn('SetVoiceChoices(msg["voices"] as JSONArray);', app)
        self.assertNotIn('{ "eve", "ara", "rex", "sal", "leo" }', app)

    def test_parse_endpoint_answer(self):
        body = json.dumps({"voices": [{"voice_id": "Eve", "name": "Eve", "language": "multilingual"},
                                      {"voice_id": "ara", "name": "Ara"}, {"voice_id": "eve"}, {"name": "x"}]})
        self.assertEqual(voices.parse_voices(body), ["eve", "ara"])

    def test_fetch_uses_get_tts_voices_with_the_key(self):
        seen = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"voices": [{"voice_id": "rex"}]}'

        class Http:
            def open(self, service, method, url, headers, body, timeout):
                seen.update(method=method, url=url, auth=headers.get("Authorization"))
                return Resp()

        self.assertEqual(voices.fetch_xai_voices(Http(), "https://api.x.ai/v1/", "k1"), ["rex"])
        self.assertEqual(seen, {"method": "GET", "url": "https://api.x.ai/v1/tts/voices", "auth": "Bearer k1"})

    def test_catalog_static_without_fetcher_or_key(self):
        self.assertEqual(voices.VoiceCatalog().names("k", "u"), DOC_VOICES)
        calls = []
        cat = voices.VoiceCatalog(fetcher=lambda k, b: calls.append(k) or ["x"], background=False)
        self.assertEqual(cat.names(None, "u"), DOC_VOICES)
        self.assertEqual(calls, [])

    def test_catalog_takes_the_endpoint_list_and_keeps_static_on_error(self):
        t = [0.0]
        cat = voices.VoiceCatalog(fetcher=lambda k, b: ["rex", "eve"], clock=lambda: t[0], background=False)
        self.assertEqual(cat.names("k", "u"), ["rex", "eve"])
        bad = voices.VoiceCatalog(fetcher=lambda k, b: (_ for _ in ()).throw(OSError("offline")), clock=lambda: t[0],
                                  background=False)
        self.assertEqual(bad.names("k", "u"), DOC_VOICES)

    def test_catalog_refreshes_once_per_interval(self):
        t = [0.0]
        calls = []
        cat = voices.VoiceCatalog(fetcher=lambda k, b: calls.append(1) or ["rex"], clock=lambda: t[0], background=False)
        cat.names("k", "u")
        cat.names("k", "u")
        self.assertEqual(len(calls), 1)
        t[0] = voices.REFRESH_S + 1
        cat.names("k", "u")
        self.assertEqual(len(calls), 2)
        cat.names("k2", "u")   # a new key asks again
        self.assertEqual(len(calls), 3)

    def test_background_fetch_does_not_block(self):
        gate = threading.Event()
        cat = voices.VoiceCatalog(fetcher=lambda k, b: (gate.wait(2), ["rex"])[1])
        start = time.monotonic()
        self.assertEqual(cat.names("k", "u"), DOC_VOICES)
        self.assertLess(time.monotonic() - start, 0.5)
        gate.set()
        for _ in range(100):
            if cat.names("k", "u") == ["rex"]:
                break
            time.sleep(0.01)
        self.assertEqual(cat.names("k", "u"), ["rex"])

    def test_heartbeat_allows_voices(self):
        self.assertIn("voices", protocol.COMMANDS["companion_heartbeat"][1])


class InlineToolCallTests(TestCase):
    """Leon's companion.log (21.11.2026 17:13, 17:25): Say: '<tool_call>{"name": "express", ...' - it was spoken."""

    def run_parser(self, deltas):
        p = StreamParser(["smile", "neutral"], ["nod", "tilt"])
        items = []
        for d in deltas:
            items += p.feed(d)
        return items + p.finish()

    def test_split_over_deltas_is_run_not_spoken(self):
        items = self.run_parser(['<tool', '_call>{"name": "express",', ' "parameters": {"expression": "smile", '
                                 '"gesture": "nod"}}</tool_', 'call>Hello. ', "I'm still here."])
        self.assertIsInstance(items[0], InlineToolCall)
        self.assertEqual(items[0].name, "express")
        self.assertEqual(json.loads(items[0].arguments), {"expression": "smile", "gesture": "nod"})
        self.assertEqual(items[1:], ["Hello.", "I'm still here."])
        self.assertFalse(any("tool_call" in str(i) for i in items[1:]))

    def test_in_the_middle_and_with_a_tag(self):
        items = self.run_parser(["<<smile>>Hi there. ", '<tool_call>{"name":"express","arguments":{"gesture":"tilt"}}'
                                 "</tool_call>", "Nice."])
        self.assertEqual([type(i).__name__ for i in items], ["Directive", "str", "InlineToolCall", "str"])

    def test_unclosed_tag_never_reaches_speech(self):
        items = self.run_parser(['Okay. <tool_call>{"name": "express"'])
        self.assertEqual(items, ["Okay."])

    def test_plain_text_with_angle_brackets_stays(self):
        f = ToolTextFilter()
        text, calls = f.feed("a < b and <tool")
        self.assertEqual((text, calls), ("a < b and ", []))
        text2, _ = f.feed("s are fine. ")
        self.assertEqual(text + text2 + f.flush(), "a < b and <tools are fine. ")

    def test_orchestrator_and_realtime_run_it(self):
        orch = (ROOT / "companion" / "aibody_companion" / "orchestrator.py").read_text(encoding="utf-8")
        self.assertIn('ToolCall(call_id="inline", name=item.name, arguments=item.arguments)', orch)
        rt = (ROOT / "companion" / "aibody_companion" / "realtime_voice.py").read_text(encoding="utf-8")
        self.assertIn("isinstance(item, InlineToolCall)", rt)


class PersonaListTests(TestCase):
    def test_loose_json_files_and_starters_beside_own_personas(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "Mine").mkdir()
            (root / "Mine" / "persona.json").write_text('{"name": "Mine"}', encoding="utf-8")
            (root / "Loose.json").write_text('{"name": "Loose", "persona": "x"}', encoding="utf-8")
            (root / "memory.json").write_text("{}", encoding="utf-8")
            written = personas.seed_starter_personas(root)
            self.assertEqual(sorted(written), ["Anna", "Marc"])
            names = personas.PersonaStore(root).names()
            self.assertEqual(names, ["Anna", "Loose", "Marc", "Mine"])

    def test_only_two_starters_are_shipped(self):
        self.assertEqual(sorted(personas.STARTER_PERSONAS), ["Anna", "Marc"])


class PoseCommandTests(TestCase):
    """v41 pose command menu; version 42 (Leon 18:27) replaced the Apply buttons: choosing applies (test_version42_items)."""

    def setUp(self):
        self.body = source("Body.cs")

    def test_pose_command_menu_is_scrollable(self):
        tab = method_body(self.body, "public void BuildCharacterTab(UiPage page)")
        self.assertIn("page.ScrollablePopup(_poseCommandChoiceJson);\n", tab.replace("\r\n", "\n"))
        self.assertIn('page.Button("Add Pose", StartAddPose);', tab)

    def test_apply_logs_result_and_error(self):
        apply = method_body(self.body, "private void ApplyPoseCommand(string command)")
        self.assertIn("PoseVocabulary.Resolve(entry, _poses.PoseNames)", apply)
        self.assertIn("_poses.ApplyPose(pose)", apply)
        self.assertIn("<color=red>", apply)


class RightColumnTests(TestCase):
    """Leon 17:19: right column = headers and controls only; no new info fields without his approval."""

    def test_only_the_approved_caption_is_a_note(self):
        notes = []
        for f in SRC.glob("*.cs"):
            notes += re.findall(r"\b_?page\.Note\((\w+)\)", f.read_text(encoding="utf-8"))
        self.assertEqual(notes, ["BackgroundHint"])   # Leon's own request in version 36 (SPEC, Background color)

    def test_plain_headers_are_labels_of_the_control_below(self):
        allowed = {"HintText", "XaiTokenLabel", "BreathMorphLabel", "NewPoseCommandLabel", "GateQuestion"}
        for f in SRC.glob("*.cs"):
            for arg in re.findall(r"\b_?page\.Header\(([^)]*)\)", f.read_text(encoding="utf-8")):
                if arg.startswith('"<b>'):
                    continue
                self.assertIn(arg, allowed, f"{f.name}: right-column text {arg}")

    def test_labels_carry_no_explanation(self):
        self.assertIn('BreathMorphLabel = "Breath morph";', source("Body.cs"))
