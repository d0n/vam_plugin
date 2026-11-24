"""Pose commands (version 32): the exact-match gate, the {"pose": "<id>"} reply, the vocabulary in config.json, and the
plugin's own PoseVocabulary.cs run for real (dotnet) against the same test vectors as the companion."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from aibody_companion import pose_commands, protocol, settings_file
from aibody_companion.pose_commands import PoseVocabulary, STARTER_COMMANDS

from .fakes import FakeClock, FakeHttp, FakePlugin, FakeResponse, text_stream
from .test_body_tools import call_item, tool_only_stream
from .test_e2e_simulation import Sim
from .test_realtime import RealtimeSim, tone

ROOT = Path(__file__).resolve().parents[2]
KEY = "xai-FAKE-NOT-A-KEY-pose"
STARTERS = ["Sit Down", "Lay Down", "Prone", "Stand Up", "Spread Your Legs", "Ankle Your Knees", "Ankle Your Elbows",
            "Turn Around", "Crawl on all fours", "Bend Over"]

# Every one of these must NOT trigger: the whole input has to equal a command.
NEAR_MISSES = ["please sit down", "sit down and smile", "Sit Down please", "sit", "down", "sit  down now", "Sit-Down",
               "sit_down", "sitdown", "Sit Dow", "Sit Downs", "Can you sit down?", "sit down, then stand up",
               "stand up sit down", "lay", "prone position", "Turn around twice", "crawl on all four", "bend over!!x",
               "", "   ", "...", "?!", "Sit Down\nand smile", "Sit. Down", "Sit Down; Lay Down", "Setz dich hin"]


class GateTests(unittest.TestCase):
    def setUp(self):
        self.vocab = PoseVocabulary(pose_commands.starter_entries())

    def test_the_starter_set_is_exactly_leons_ten_commands_in_his_wording(self):
        self.assertEqual(list(STARTER_COMMANDS), STARTERS)
        self.assertEqual([e["command"] for e in pose_commands.starter_entries()], STARTERS)
        self.assertEqual([e["pose"] for e in pose_commands.starter_entries()], STARTERS)

    def test_every_command_matches_exactly(self):
        for command in STARTERS:
            self.assertEqual(self.vocab.match(command)["command"], command)

    def test_case_punctuation_and_whitespace_are_ignored_only_at_the_edges(self):
        for text in ("sit down", "SIT DOWN", "sIt dOwN", "Sit Down.", "Sit Down!", "Sit Down?", "Sit Down?!", "Sit Down...",
                     "  Sit Down  ", "\tSit\u00a0Down\n", "Sit    Down", "sit down!!!", "Sit Down \u2026", "  sit   down . ! ?  "):
            self.assertEqual((self.vocab.match(text) or {}).get("command"), "Sit Down", repr(text))
        self.assertEqual(self.vocab.match("CRAWL ON ALL FOURS!")["command"], "Crawl on all fours")

    def test_near_misses_never_trigger(self):
        for text in NEAR_MISSES:
            self.assertIsNone(self.vocab.match(text), repr(text))
        for text in (None, 5, [], {}):
            self.assertIsNone(self.vocab.match(text))

    def test_punctuation_is_only_ignored_at_the_end(self):
        self.assertIsNone(self.vocab.match("!Sit Down"))
        self.assertIsNone(self.vocab.match("Sit! Down"))
        self.assertIsNone(self.vocab.match("\"Sit Down\""))

    def test_a_pose_is_only_available_when_a_pose_file_matches(self):
        entry = {"command": "Sit Down", "pose": "Sit Down"}
        self.assertIsNone(PoseVocabulary.resolve(entry, []))
        self.assertIsNone(PoseVocabulary.resolve(entry, ["Stand Up", "sitting"]))
        for names in (["Sit Down"], ["sit_down"], ["Sit-Down"], ["SIT  DOWN"]):
            self.assertEqual(PoseVocabulary.resolve(entry, names), names[0])
        v = PoseVocabulary(pose_commands.starter_entries())
        self.assertEqual([e["command"] for e in v.available(["Sit Down", "Prone"])], ["Sit Down", "Prone"])
        self.assertEqual(len(v.unavailable(["Sit Down", "Prone"])), 8)
        self.assertEqual(len(v.unavailable([])), 10)

    def test_reply_json_and_strict_parsing(self):
        entry = {"command": "Sit Down", "pose": "Sit Down"}
        self.assertEqual(PoseVocabulary.reply_json(entry), '{"pose":"Sit Down"}')
        self.assertEqual(pose_commands.parse_pose_json('{"pose":"Sit Down"}'), ("Sit Down", ""))
        self.assertEqual(pose_commands.parse_pose_json(' {"pose" : "A\\u00e4\\"b"} ')[0], 'Aä"b')
        for bad in ("", "pose", "[]", "{}", '{"pose":""}', '{"pose":"  "}', '{"pose":5}', '{"pose":null}',
                    '{"pose":"a","x":1}', '{"pose":"a","pose":"b"}', '{"Pose":"a"}', '{"pose":"a"} x', '{"pose":"a"',
                    '{"pose":"a",}', "{'pose':'a'}", '{"pose":["a"]}', None, 7, '{"pose":"' + "a" * 500 + '"}'):
            pose, error = pose_commands.parse_pose_json(bad)
            self.assertIsNone(pose, repr(bad))
            self.assertTrue(error, repr(bad))

    def test_vocabulary_validation(self):
        entries, errors = pose_commands.validate_entries([{"command": " Sit  Down ", "pose": "x"},
                                                          {"command": "sit down!", "pose": "y"},
                                                          {"command": "", "pose": "z"}, {"command": "A"}, "junk",
                                                          {"command": "Wave", "pose": "wave", "extra": 1}])
        self.assertEqual([e["command"] for e in entries], ["Sit Down", "Wave"])
        self.assertEqual(len(errors), 4, errors)
        self.assertEqual(pose_commands.validate_entries([])[0], [], "an empty list is a valid (empty) vocabulary")
        self.assertEqual(len(pose_commands.validate_entries([{"command": f"c{i}", "pose": "p"} for i in range(150)])[0]),
                         pose_commands.MAX_COMMANDS)


class ProtocolTests(unittest.TestCase):
    def cmd(self, **fields):
        return {"v": 3, "type": "pose", "id": "p-1", **fields}

    def test_a_pose_command_needs_strict_pose_json(self):
        self.assertEqual(protocol.validate_command(self.cmd(json='{"pose":"Sit Down"}', command="Sit Down")), [])
        for bad in ({}, {"name": "sit"}, {"path": "Custom/x.vap"}, {"json": "nope"}, {"json": '{"pose":""}'},
                    {"json": '{"pose":"a","x":1}'}, {"json": '{"pose":5}'}):
            self.assertTrue(protocol.validate_command(self.cmd(**bad)), bad)


class SettingsTests(unittest.TestCase):
    def test_default_config_carries_the_starters(self):
        self.assertEqual([e["command"] for e in settings_file.DEFAULTS["poses"]["commands"]], STARTERS)
        self.assertIn("poses", settings_file.PLUGIN_CATEGORIES)

    def test_validate_keeps_the_user_vocabulary_and_reports_junk(self):
        data = {"poses": {"commands": [{"command": "Wave Hello", "pose": "wave"}, {"command": "", "pose": "x"}]}}
        result, errors = settings_file.validate(data)
        self.assertEqual(result["poses"]["commands"], [{"command": "Wave Hello", "pose": "wave"}])
        self.assertTrue(errors)
        result, errors = settings_file.validate({"poses": {"commands": []}})
        self.assertEqual(([e["command"] for e in result["poses"]["commands"]], errors), (STARTERS, []),
                         "version 35: an empty list = the starter commands")
        result, errors = settings_file.validate({"poses": {"commands": [{"command": "", "pose": "x"}]}})
        self.assertEqual([e["command"] for e in result["poses"]["commands"]], STARTERS, "no usable entry = the starters")
        result, errors = settings_file.validate({})
        self.assertEqual([e["command"] for e in result["poses"]["commands"]], STARTERS)
        self.assertTrue(settings_file.validate({"poses": {"other": 1}})[1])

    def test_the_vocabulary_survives_a_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = settings_file.defaults()
            data["poses"]["commands"] = [{"command": "Wave Hello", "pose": "wave"}]
            path = settings_file.settings_path(tmp)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = settings_file.validate(json.loads(path.read_text(encoding="utf-8")))[0]
            self.assertEqual(loaded["poses"]["commands"], [{"command": "Wave Hello", "pose": "wave"}])


class Chain(unittest.TestCase):
    """Typed text and spoken input in the chain path (text -> model -> speech)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = FakeClock()
        self.http = FakeHttp()
        self.said = ["Sit Down."]
        self.http.route("/stt", lambda r: FakeResponse(json.dumps({"text": self.said[0]}).encode()))
        self.http.route("/tts", lambda r: FakeResponse(b"\x10\x00" * 4800, "audio/pcm"))
        self.answers = []
        self.http.route("/responses", lambda r: FakeResponse(self.answers.pop(0) if self.answers else text_stream(["Okay."]),
                                                             "text/event-stream"))

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, poses=("Sit Down", "Prone"), mode="chain", body_control=True, commands=None):
        self.sim = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": KEY}, mode=mode)
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(self.root, self.clock, mode=mode)
        self.plugin.ui["engines"] = {"stt": "xai", "llm": "xai", "tts": "xai"}
        self.plugin.poses = list(poses)
        self.plugin.body_control = body_control
        if commands is not None:
            self.plugin.pose_commands = commands
        self.plugin.start()
        self.sim.run(self.plugin, 3)

    def requests(self):
        return [r for r in self.http.requests if "/responses" in r.full_url]

    def ask(self, text):
        self.app.handle_user_text(text)
        self.sim.run(self.plugin, 3)

    def poses_sent(self):
        return self.sim.sent(self.plugin, "pose")

    def test_a_matching_input_sends_the_pose_json_and_nothing_else(self):
        self.start()
        self.ask("sit down!")
        sent = self.poses_sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["json"], '{"pose":"Sit Down"}')
        self.assertEqual(sent[0]["command"], "Sit Down")
        self.assertEqual(self.requests(), [], "the language model is not asked: the gate is deterministic code")
        self.assertEqual(self.sim.sent(self.plugin, "speak"), [], "a pose command gets no spoken reply")
        self.assertEqual(protocol.validate_command(sent[0]), [], "the command is valid for the protocol")

    def test_the_vocabulary_command_sends_the_linked_pose_id_not_the_label(self):
        self.start(poses=("Sitting",), commands=[{"command": "Sit Down", "pose": "sitting"}])
        self.ask("Sit Down")
        self.assertEqual(self.poses_sent()[0]["json"], '{"pose":"sitting"}', "the linked pose id from the config is sent")
        self.assertEqual(self.poses_sent()[0]["command"], "Sit Down")

    def test_near_misses_go_to_the_conversation_and_never_apply_a_pose(self):
        # version 58 (Leon 16:07): "please sit down" IS a pose command now (the command inside a sentence); a negated
        # command or a word that only contains it ("sitting down") is ordinary conversation
        self.start(poses=STARTERS)
        for text in ("don't sit down", "I like sitting down"):
            self.ask(text)
        self.assertEqual(self.poses_sent(), [])
        self.assertEqual(len(self.requests()), 2, "they are ordinary conversation")
        first = json.loads(self.requests()[0].data)
        self.assertEqual([t["name"] for t in first.get("tools", [])], ["express"], "the model never gets a pose tool")

    def test_every_available_starter_applies_by_exact_match(self):
        self.start(poses=STARTERS)
        for command in STARTERS:
            self.ask(command.upper() + ".")
        self.assertEqual([json.loads(p["json"])["pose"] for p in self.poses_sent()], STARTERS)

    def test_an_unavailable_command_is_never_applied(self):
        # version 58: an own command without its pose stays unavailable (a built-in one gets a substitute in the plugin)
        self.start(poses=("Prone",), commands=[{"command": "Have a seat", "pose": "sitting"}, {"command": "Prone", "pose": "Prone"}])
        self.ask("Have a seat")
        self.assertEqual(self.poses_sent(), [])
        self.assertEqual(self.requests(), [], "still a pose command: no model answer that could invent a pose")
        self.ask("Prone")
        self.assertEqual(len(self.poses_sent()), 1)

    def test_a_builtin_command_without_its_pose_is_sent_for_a_substitute(self):
        self.start(poses=("Prone",))
        self.ask("Sit Down")
        self.assertEqual([p["json"] for p in self.poses_sent()], ['{"pose":"Sit Down"}'], "the plugin picks the substitute")
        self.assertEqual(self.requests(), [])

    def test_body_control_off_leaves_the_words_to_the_conversation(self):
        self.start(body_control=False)
        self.ask("Sit Down")
        self.assertEqual(self.poses_sent(), [])
        self.assertEqual(len(self.requests()), 1)

    def test_spoken_input_goes_through_the_same_gate(self):
        self.start()
        self.said[0] = "Sit down."
        import math, struct

        def frame(loud):
            n = 16000 * 30 // 1000
            return struct.pack(f"<{n}h", *(int(6000 * math.sin(i / 3)) if loud else 0 for i in range(n)))
        for loud in [True] * 40 + [False] * 30:
            self.app.handle_audio_frame(frame(loud))
        self.sim.run(self.plugin, 4)
        self.assertEqual([p["json"] for p in self.poses_sent()], ['{"pose":"Sit Down"}'])
        self.assertEqual(self.requests(), [])
        self.said[0] = "Please sit down now."   # version 58: inside a sentence
        for loud in [True] * 40 + [False] * 30:
            self.app.handle_audio_frame(frame(loud))
        self.sim.run(self.plugin, 4)
        self.assertEqual(len(self.poses_sent()), 2)
        self.assertEqual(self.requests(), [])
        self.said[0] = "Please don't sit down."
        for loud in [True] * 40 + [False] * 30:
            self.app.handle_audio_frame(frame(loud))
        self.sim.run(self.plugin, 4)
        self.assertEqual(len(self.poses_sent()), 2)
        self.assertEqual(len(self.requests()), 1)

    def test_a_pose_call_from_the_model_is_refused(self):
        self.answers = [tool_only_stream("resp-1", call_item("c1", "pose", {"name": "Sit Down"})), text_stream(["No."], "resp-2")]
        self.start()
        self.ask("hello there")
        self.assertEqual(self.poses_sent(), [], "poses come only from the vocabulary gate")

    def test_the_gate_is_part_of_the_plugin_status_and_the_prompt_does_not_mention_poses(self):
        self.start()
        self.ask("hello")
        instructions = json.loads(self.requests()[0].data)["instructions"]
        self.assertNotIn('"pose"', instructions)


class RealtimeGate(RealtimeSim):
    def transcript(self, text, item="u1"):
        self.server.conn.send({"type": "conversation.item.input_audio_transcription.completed", "item_id": item,
                               "transcript": text})

    def start_connected(self, poses=("Sit Down",)):
        self.start()
        self.plugin.poses = list(poses)
        self.connect()
        self.pump(lambda: self.app.body_info.get("poses") == list(poses))

    def test_a_matching_transcript_applies_the_pose_and_cancels_the_answer(self):
        self.start_connected()
        c = self.server.conn
        c.send({"type": "input_audio_buffer.speech_stopped", "item_id": "u1"})
        self.transcript("Sit down.")
        self.assertTrue(self.pump(lambda: bool(self.sim.sent(self.plugin, "pose"))))
        self.assertEqual(self.sim.sent(self.plugin, "pose")[0]["json"], '{"pose":"Sit Down"}')
        # the server answers anyway (it was faster than the transcript): the answer is cancelled and never spoken
        c.send({"type": "response.created", "response": {"id": "r1"}})
        c.send({"type": "response.output_audio_transcript.delta", "response_id": "r1", "delta": "Sure, I sit down. "})
        c.send({"type": "response.output_audio.delta", "response_id": "r1",
                "delta": __import__("base64").b64encode(tone(1.0)).decode()})
        self.assertTrue(self.pump(lambda: "response.cancel" in self.server.conn.types()))
        self.pump(timeout=0.4)
        self.assertEqual(self.speaks(), [])
        self.assertEqual(len(self.sim.sent(self.plugin, "pose")), 1)

    def test_a_near_miss_is_a_normal_conversation(self):
        self.start_connected()
        self.server.conn.send({"type": "input_audio_buffer.speech_stopped", "item_id": "u1"})
        self.transcript("Please don't sit down.")   # version 58: "please sit down" is a command now; negated is not
        self.pump(timeout=0.3)
        self.assertEqual(self.sim.sent(self.plugin, "pose"), [])
        self.server.respond(["Of course. "], tone(1.0))
        self.assertTrue(self.pump(lambda: bool(self.speaks())))

    def test_an_unavailable_command_sends_no_pose(self):
        self.start_connected(poses=("Prone",))
        self.plugin.pose_commands = [{"command": "Have a seat", "pose": "sitting"}]
        self.pump(lambda: (self.app.body_info.get("pose_commands") or [{}])[0].get("command") == "Have a seat")
        self.server.conn.send({"type": "input_audio_buffer.speech_stopped", "item_id": "u1"})
        self.transcript("Have a seat")
        self.pump(timeout=0.4)
        self.assertEqual(self.sim.sent(self.plugin, "pose"), [])

    def test_the_session_has_no_pose_tool(self):
        self.start_connected()
        ups = [e for e in self.server.conn.received if e["type"] == "session.update"]
        self.assertEqual([t["name"] for t in ups[-1]["session"].get("tools", [])], ["express"])
        self.assertNotIn('"pose"', ups[-1]["session"]["instructions"])


del RealtimeSim


# -- the plugin's real PoseVocabulary.cs, outside VaM -------------------------------------------------------------

DOTNET = shutil.which("dotnet") or str(Path.home() / ".dotnet" / "dotnet")

VECTORS = ["Sit Down", "  Sit   Down!!  ", "SIT DOWN?!", "sit\tdown", "Sit Down.\n", "Sit\u00a0Down", "Sit\u3000Down\uff01",
           "Sit Down\u2026", "Ä Ö Ü ß", "Crawl on all fours.", "", "   ", "...", "a.b", "a  b  c", "?!x", "!Sit",
           "\u00c4nkle Your Knees", "Turn  Around ...", "Sit\u2003Down", "tab\there", "x\u000b y", "x\u0085y",
           "Sit down,", "Sit down;", "Sit down:", "Lay down\uff0c", "Turn around\u3001", ",Sit", "Sit, down", "a ,"]
KEYS = ["Preset_Sit Down", "sit_down", "Sit-Down", "SIT  DOWN", "Ankle Your Knees", "Ä-ö_ü", "", "___", "a1 b2", "Pose 01"]
PARSE = ['{"pose":"Sit Down"}', ' { "pose" : "x" } ', '{"pose":"A\\u00e4\\"b"}', '{"pose":"a\\\\b\\/c\\n"}', "", "pose", "[]", "{}",
         '{"pose":""}', '{"pose":5}', '{"pose":null}', '{"pose":"a","x":1}', '{"pose":"a","pose":"b"}', '{"Pose":"a"}',
         '{"pose":"a"} x', '{"pose":"a"', '{"pose":"a",}', "{'pose':'a'}", '{"pose":["a"]}', '{"pose":"a\\x"}',
         '{"pose":"a\\u12"}', '{"pose":"' + "a" * 500 + '"}', '{"pose":"tab\there"}']


@unittest.skipUnless(Path(DOTNET).exists(), "dotnet SDK not installed")
class RealPoseVocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        shutil.copy(Path(__file__).parent / "csharp_pose_harness" / "Program.cs", folder / "Program.cs")
        (folder / "Harness.csproj").write_text(f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType>
  <EnableDefaultCompileItems>false</EnableDefaultCompileItems><NoWarn>CS0618</NoWarn></PropertyGroup>
  <ItemGroup><Compile Include="Program.cs" /><Compile Include="{ROOT / 'src/AIBody/PoseVocabulary.cs'}" /></ItemGroup>
</Project>""", encoding="utf-8")
        result = subprocess.run([DOTNET, "build", "-nologo", "-v", "q", "-o", str(folder / "out")], cwd=folder,
                                capture_output=True, text=True, timeout=240,
                                env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
        if result.returncode != 0:
            raise AssertionError("harness build failed:\n" + result.stdout + result.stderr)
        cls.exe = folder / "out" / "Harness.dll"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_ops(self, ops):
        proc = subprocess.run([DOTNET, str(self.exe)], input="\n".join(json.dumps(o) for o in ops) + "\n",
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), len(ops), proc.stdout)
        return [json.loads(line) for line in lines]

    def test_normalization_matches_the_companion(self):
        got = self.run_ops([["norm", v] for v in VECTORS])
        self.assertEqual(got, [pose_commands.normalize_input(v) for v in VECTORS])

    def test_pose_keys_match_the_companion(self):
        self.assertEqual(self.run_ops([["key", v] for v in KEYS]), [pose_commands.pose_key(v) for v in KEYS])

    def test_the_gate_matches_the_companion_on_every_vector(self):
        texts = STARTERS + NEAR_MISSES + VECTORS + [c.upper() + "!" for c in STARTERS] + ["  " + c.lower() + " ?" for c in STARTERS]
        vocab = PoseVocabulary(pose_commands.starter_entries())
        got = self.run_ops([["match", t] for t in texts])
        want = [(vocab.match(t) or {}).get("command") for t in texts]
        self.assertEqual(got, want)
        self.assertGreaterEqual(sum(1 for w in want if w), 30, "the vectors really contain matches")
        for text in NEAR_MISSES:
            self.assertIsNone(got[texts.index(text)], text)

    def test_strict_json_parsing_agrees_with_the_companion(self):
        got = self.run_ops([["parse", p] for p in PARSE])
        for text, result in zip(PARSE, got):
            pose, error = pose_commands.parse_pose_json(text)
            self.assertEqual(result[0] == "ok", pose is not None, f"{text!r}: C# {result}, Python {(pose, error)}")
            if pose is not None:
                self.assertEqual(result[1], pose, text)

    def test_the_reply_json_round_trips_in_both_directions(self):
        poses = ["Sit Down", 'Say "hi"', "Ä\\ö", "a/b", "tab\tx"]
        replies = self.run_ops([["reply", p] for p in poses])
        for pose, reply in zip(poses, replies):
            self.assertEqual(pose_commands.parse_pose_json(reply)[0], pose)
            self.assertEqual(self.run_ops([["parse", pose_commands.PoseVocabulary.reply_json({"pose": pose})]])[0], ["ok", pose])
        self.assertEqual(replies[0], PoseVocabulary.reply_json({"pose": "Sit Down"}))

    def test_add_delete_restore_logic(self):
        out = self.run_ops([["script", [["match", "sit down"], ["remove", "SIT DOWN!"], ["match", "Sit Down"],
                                        ["add", "  Wave   Hello ", "wave"], ["match", "wave hello."], ["byid", "WAVE"],
                                        ["add", "wave hello", "wave2"], ["add", "", "x"], ["add", "...", "x"],
                                        ["add", "Dance", ""], ["add", "x" * 61, "p"], ["remove", "nothing"],
                                        ["restore"], ["restore"], ["clear"], ["match", "Prone"], ["restore"]]]])[0]
        messages, entries = out
        self.assertEqual(messages[0], "Sit Down>Sit Down")
        self.assertEqual(messages[1:3], ["removed", "-"])
        self.assertEqual(messages[3:6], ["ok", "Wave Hello>wave", "Wave Hello"])
        self.assertEqual(messages[6], "ok", "the same command again only re-links it")
        for refusal in messages[7:11]:
            self.assertNotEqual(refusal, "ok")
        self.assertEqual(messages[11], "missing")
        self.assertEqual(messages[12:14], ["restored 1", "restored 0"], "restoring adds only the starters that are missing")
        self.assertEqual(messages[14:17], ["cleared", "-", "restored 10"])
        self.assertEqual(entries, [f"{c}>{c}" for c in STARTERS])


# -- the plugin sources ---------------------------------------------------------------------------------------------

class PluginSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "src" / "AIBody").glob("*.cs")}

    def test_ui_has_add_pose_and_delete_pose_in_the_character_tab(self):
        body = self.src["Body.cs"]
        for label in ('"Add Pose"', '"Delete Pose"', '"Restore starter poses"'):
            self.assertIn(label, body)
        self.assertLess(body.index("void BuildCharacterTab"), body.index('"Add Pose"'), "the buttons are in the Character tab")

    def test_vocabulary_is_stored_in_the_ai_character_config_only(self):
        self.assertIn('root["poses"]', self.src["Body.cs"])
        self.assertIn('["commands"]', self.src["Body.cs"])

    def test_the_router_applies_poses_only_from_the_validated_json(self):
        router = self.src["CommandRouter.cs"]
        self.assertIn("ApplyPoseJson", router)
        block = router[router.index("CmdPose"):]
        block = block[:block.index("}\n", block.index("{"))]
        self.assertNotIn("LoadPose", block)
        self.assertNotIn('"name"', block, "no free pose name is accepted from the companion")
        self.assertNotIn('"path"', block)

    def test_no_dictionary_keys_or_values_are_enumerated(self):
        for name in ("PoseVocabulary.cs", "PoseController.cs", "Body.cs", "CommandRouter.cs"):
            self.assertIsNone(re.search(r"foreach\s*\([^)]*\.(Keys|Values)\b", self.src[name]), name)

    def test_the_vocabulary_is_pure_and_the_plugin_warns_in_english(self):
        vocab = self.src["PoseVocabulary.cs"]
        for forbidden in ("UnityEngine", "SimpleJSON", "System.Linq", "Dictionary<"):
            self.assertNotIn(forbidden, vocab)
        self.assertIn("Pose ignored", self.src["CommandRouter.cs"])
        self.assertIn("Poses are applied only through pose commands", self.src["PoseController.cs"])


class CreditsTests(unittest.TestCase):
    """docs/CREDITS.md thanks the sources the docs reference and invents none."""

    def setUp(self):
        self.credits = (ROOT / "docs" / "CREDITS.md").read_text(encoding="utf-8")
        files = [p for p in (ROOT / "docs").glob("*.md") if p.name != "CREDITS.md"] + [ROOT / "README.md"]
        self.others = "\n".join(p.read_text(encoding="utf-8") for p in files)

    def test_every_link_in_the_credits_is_a_link_the_docs_have(self):
        urls = {u.rstrip(".,;:") for u in re.findall(r"https?://[^\s)>\]`\"']+", self.credits)}
        self.assertGreater(len(urls), 40)
        self.assertEqual([u for u in sorted(urls) if u not in self.others], [])

    def test_the_main_sources_are_thanked(self):
        for name in ("MacGruber", "Acid Bubbles", "Timeline", "VAMDeluxe", "Dollmaster", "ToySerialController", "Voxta",
                     "VAMLaunch", "Neptune", "Glance", "Life", "webrtcvad", "Silero", "Ollama", "xAI", "ElevenLabs",
                     "Meshed VR", "onnxruntime", "sounddevice", "Unity"):
            self.assertIn(name, self.credits)

    def test_the_readme_points_to_the_credits(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/CREDITS.md", readme)
        self.assertIn("Credits and special thanks", readme)


if __name__ == "__main__":
    unittest.main()
