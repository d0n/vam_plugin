"""Gaze control (version 25): the look_at command, the AI's look_at tool, and the plugin's GazeController /
menu (checked on the C# sources, like the other plugin menu tests)."""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from aibody_companion import body_tools, protocol, settings_file
from tests import test_body_tools as tb
from tests.fakes import FakeClock, FakeHttp, FakePlugin, FakeResponse, text_stream
from tests.test_e2e_simulation import Sim
from tests.test_plugin_menu import ROOT, method_body, source
from tests.test_realtime import RealtimeSim, tone


class LookAtCommandTests(unittest.TestCase):
    def test_command_fields_and_validation(self):
        cmd = protocol.make_command("look_at", target="client", seconds=4)
        self.assertEqual((cmd["type"], cmd["target"], cmd["seconds"]), ("look_at", "client", 4))
        self.assertIn("look_at", protocol.BODY_COMMANDS)
        self.assertEqual(protocol.validate_command(protocol.make_command("look_at", target="atom", atom="Lamp")), [])
        for bad in ({"target": "moon"}, {"target": "atom"}, {"target": "client", "seconds": -1},
                    {"target": "client", "seconds": 61}, {"target": "client", "seconds": "3"}):
            with self.subTest(bad=bad):
                self.assertTrue(protocol.validate_command({"type": "look_at", **bad}), bad)
        with self.assertRaises(ValueError):
            protocol.make_command("look_at", target="client", bogus=1)  # unknown field
        with self.assertRaises(ValueError):
            protocol.make_command("look_at")  # target missing

    def test_schema_knows_the_command_and_the_status_fields(self):
        cmd = json.loads((ROOT / "protocol/schema/command.schema.json").read_text(encoding="utf-8"))
        self.assertIn("look_at", cmd["properties"]["type"]["enum"])
        self.assertEqual(cmd["properties"]["target"]["enum"], list(protocol.LOOK_TARGETS))
        self.assertEqual(cmd["properties"]["seconds"]["maximum"], protocol.LOOK_MAX_SECONDS)
        evt = json.loads((ROOT / "protocol/schema/event.schema.json").read_text(encoding="utf-8"))
        self.assertIn("gaze_control", evt["properties"])
        self.assertIn("gaze_atoms", evt["properties"])

    def test_config_defaults_match_the_plugin(self):
        body = settings_file.DEFAULTS["body"]
        self.assertEqual((body["gaze_control"], body["gaze_default"], body["gaze_follows_speaker"]),
                         (True, "default", False))
        data, errors = settings_file.validate({"body": {"gaze_default": "atom:Lamp", "gaze_control": "false"}})
        self.assertEqual(errors, [])
        self.assertEqual((data["body"]["gaze_default"], data["body"]["gaze_control"]), ("atom:Lamp", False))


class ToolUnitTests(unittest.TestCase):
    def lists(self, gaze=True, atoms=("Lamp", "Sofa Table")):
        return body_tools.BodyLists(["neutral"], ["nod"], [], gaze, list(atoms))

    def test_tool_only_with_gaze_and_lists_the_atoms(self):
        self.assertEqual([t["name"] for t in body_tools.tools(self.lists(gaze=False))], ["express"])
        tools = body_tools.tools(self.lists())
        self.assertEqual([t["name"] for t in tools], ["express", "look_at"])
        enum = tools[1]["parameters"]["properties"]["target"]["enum"]
        self.assertEqual(enum, ["client", "camera", "forward", "away", "off", "Lamp", "Sofa Table"])
        self.assertIn("look_at", body_tools.rules(self.lists()))
        self.assertNotIn("look_at", body_tools.rules(self.lists(gaze=False)))

    def test_older_plugin_without_gaze_info_offers_no_tool(self):
        lists = body_tools.BodyLists.from_body_info({"gestures": []}, ["neutral"], [])
        self.assertFalse(lists.gaze)
        lists = body_tools.BodyLists.from_body_info({"gaze_control": "true", "gaze_atoms": ["Lamp", ""]}, ["neutral"], [])
        self.assertEqual((lists.gaze, lists.gaze_atoms), (True, ["Lamp"]), "VaM writes booleans as strings")

    def test_resolve_targets_aliases_atoms_and_seconds(self):
        lists = self.lists()
        cmds, result = body_tools.resolve("look_at", {"target": "client"}, lists, True)
        self.assertEqual((cmds, result), ([("look_at", {"target": "client"})], {"ok": True, "target": "client"}))
        self.assertEqual(body_tools.resolve("look_at", {"target": "Camera", "seconds": 5}, lists, True)[0],
                         [("look_at", {"target": "camera", "seconds": 5.0})])
        self.assertEqual(body_tools.resolve("look_at", {"target": "user"}, lists, True)[0][0][1]["target"], "client")
        self.assertEqual(body_tools.resolve("look_at", {"target": "side"}, lists, True)[0][0][1]["target"], "away")
        self.assertEqual(body_tools.resolve("look_at", {"target": "stop"}, lists, True)[0][0][1]["target"], "off")
        self.assertEqual(body_tools.resolve("look_at", {"target": "sofa table"}, lists, True)[0],
                         [("look_at", {"target": "atom", "atom": "Sofa Table"})])
        self.assertEqual(body_tools.resolve("look_at", {"target": "away", "seconds": 999}, lists, True)[0][0][1]["seconds"], 60.0)
        for junk in (0, -3, "x", True):
            self.assertNotIn("seconds", body_tools.resolve("look_at", {"target": "away", "seconds": junk}, lists, True)[0][0][1])
        # every command it builds passes the protocol check
        for args in ({"target": "client"}, {"target": "Lamp", "seconds": 2}, {"target": "away"}):
            (_, fields), = body_tools.resolve("look_at", args, lists, True)[0]
            self.assertEqual(protocol.validate_command(protocol.make_command("look_at", **fields)), [])

    def test_errors_tell_the_model_what_it_can_use(self):
        cmds, result = body_tools.resolve("look_at", {"target": "the moon"}, self.lists(), True)
        self.assertEqual(cmds, [])
        self.assertFalse(result["ok"])
        self.assertIn("client, camera, forward, away, off, Lamp, Sofa Table", result["error"])
        cmds, result = body_tools.resolve("look_at", {"target": "client"}, self.lists(gaze=False), True)
        self.assertEqual(cmds, [])
        self.assertIn("another plugin", result["error"])
        self.assertEqual(body_tools.resolve("look_at", {"target": "client"}, self.lists(), False, "body control is off")[1],
                         {"ok": False, "error": "body control is off"})


class ChainGazeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.http = FakeHttp()
        self.http.route("/tts", lambda r: FakeResponse(b"\x10\x00" * 4800, "audio/pcm"))
        self.answers = []
        self.http.route("/responses", lambda r: FakeResponse(self.answers.pop(0), "text/event-stream"))

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, gaze=True, mode="chain", body_control=True):
        self.sim = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": tb.KEY}, mode=mode)
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(Path(self.tmp.name), self.clock, mode=mode)
        self.plugin.ui["engines"] = {"stt": "xai", "llm": "xai", "tts": "xai"}
        self.plugin.gaze_control = gaze
        self.plugin.gaze_atoms = ["Lamp"]
        self.plugin.body_control = body_control
        self.plugin.start()
        self.sim.run(self.plugin, 3)

    def requests(self):
        return [json.loads(r.data) for r in self.http.requests if "/responses" in r.full_url]

    def test_look_at_call_becomes_a_command_and_the_result_goes_back(self):
        self.answers = [tb.tool_only_stream("resp-1", tb.call_item("c1", "look_at", {"target": "camera", "seconds": 4}),
                                            tb.call_item("c2", "look_at", {"target": "Lamp"})),
                        text_stream(["Hallo!"], "resp-2")]
        self.start()
        self.app.handle_user_text("Schau mich an.")
        self.sim.run(self.plugin, 3)
        first, second = self.requests()
        self.assertEqual([t["name"] for t in first["tools"]], ["express", "look_at"])
        self.assertIn('"look_at"', first["instructions"])
        sent = self.sim.sent(self.plugin, "look_at")
        self.assertEqual([(m["target"], m.get("atom"), m.get("seconds")) for m in sent],
                         [("camera", None, 4.0), ("atom", "Lamp", None)])
        outputs = [json.loads(i["output"]) for i in second["input"] if i.get("type") == "function_call_output"]
        self.assertEqual(outputs, [{"ok": True, "target": "camera"}, {"ok": True, "target": "Lamp"}])

    def test_no_tool_when_the_plugin_does_not_allow_gaze(self):
        self.answers = [tb.tool_only_stream("resp-1", tb.call_item("c1", "look_at", {"target": "client"})),
                        text_stream(["Okay."], "resp-2")]
        self.start(gaze=False)  # menu switch off, or Glance on the Person
        self.app.handle_user_text("Schau mich an.")
        self.sim.run(self.plugin, 3)
        first, second = self.requests()
        self.assertEqual([t["name"] for t in first["tools"]], ["express"])
        self.assertEqual(self.sim.sent(self.plugin, "look_at"), [])
        out = json.loads(second["input"][0]["output"])
        self.assertFalse(out["ok"])

    def test_qa_mode_and_body_control_off_offer_no_look_at(self):
        self.answers = [text_stream(["Hallo."])]
        self.start(mode="qa")
        self.assertEqual(self.app.offered_tools(), [])
        self.start(body_control=False)
        self.assertEqual(self.app.offered_tools(), [])


class RealtimeGazeTests(RealtimeSim):
    def test_session_offers_look_at_and_a_call_becomes_a_command(self):
        self.start()
        self.plugin.gaze_control = True
        self.plugin.gaze_atoms = ["Lamp"]
        self.connect()
        self.pump(lambda: self.app.body_info.get("gaze_atoms") == ["Lamp"])
        self.assertEqual([t["name"] for t in self.app.offered_tools()], ["express", "look_at"])
        self.server.respond(["Okay."], tone(1.0), call={"name": "look_at", "arguments": {"target": "client"}})
        self.assertTrue(self.pump(lambda: bool(self.sim.sent(self.plugin, "look_at"))))
        self.assertEqual(self.sim.sent(self.plugin, "look_at")[0]["target"], "client")


del RealtimeSim


class PluginGazeSourceTests(unittest.TestCase):
    """Source checks: only evidenced APIs, coexistence rules, menu and settings."""

    def setUp(self):
        self.gaze = source("GazeController.cs")

    def test_in_the_single_plugin_and_wired_up(self):
        self.assertIn("GazeController.cs", source("AIBody.cslist"))
        self.assertIn('CmdLookAt = "look_at"', source("Protocol.cs"))
        self.assertIn("CmdBreathing, CmdLookAt", source("Protocol.cs"))
        router = source("CommandRouter.cs")
        self.assertIn("case Protocol.CmdLookAt:", router)
        self.assertIn("_gaze.LookAt(", router)
        self.assertIn("type == Protocol.CmdLookAt", method_body(router, "private static bool IsBodyCommand(string type)"))
        for key in ('"target"', '"atom"', '"seconds"'):
            self.assertIn(key, router)

    def test_uses_the_evidenced_eye_apis(self):
        for part in ('GetStorableByID("Eyes") as EyesControl', "currentLookMode", "EyesControl.LookMode.Target",
                     '"eyeTargetControl"', "_eyeTarget.control.position", "centerCameraTarget",
                     "SuperController.singleton.GetAtoms()", "mainController", 'GetStorableByID("headControl")',
                     "Vector3.forward"):
            self.assertIn(part, self.gaze)
        stubs = (ROOT / "tools/stubs/VaMStubs.cs").read_text(encoding="utf-8")
        for member in ("class EyesControl", "currentLookMode", "centerCameraTarget", "GetAtoms()", "freeControllers",
                       "mainController", "Transform control"):
            line = next((l for l in stubs.splitlines() if member in l), "")
            self.assertRegex(line, r"E(12|28)\b", f"{member}: stub needs its evidence key")
        for banned in ("LookMode.Custom", "LookMode.Player", "LookMode.None", "Linq", "foreach", "lookAt1", "lookAt2",
                       "Destroy(", "new GameObject"):
            self.assertNotIn(banned, self.gaze, "not evidenced / not needed: " + banned)

    def test_does_not_fight_other_plugins(self):
        self.assertIn('EndsWith("Glance")', self.gaze)
        update = method_body(self.gaze, "public void Update(float dt, bool aiSpeaking, bool userSpeaking)")
        self.assertIn("_otherPlugin.Length > 0", update)
        self.assertRegex(update, r"_taken && _eyes\.currentLookMode != EyesControl\.LookMode\.Target")
        self.assertIn("_yielded = true", update)
        release = method_body(self.gaze, "public void Release()")
        self.assertIn("_eyes.currentLookMode = _restoreMode", release)
        self.assertIn("control.position = _restorePosition", release)
        look = method_body(self.gaze, "public string LookAt(string target, string atomName, float seconds)")
        self.assertIn("_otherPlugin.Length > 0", look)
        self.assertIn("if (_yielded)", look)
        self.assertIn("Gaze control is off", look)
        take = method_body(self.gaze, "private void Take()")
        self.assertLess(take.index("_restoreMode ="), take.index("LookMode.Target"), "remember before changing")

    def test_body_menu_status_and_settings(self):
        body = source("Body.cs")
        tab = method_body(body, "public void BuildCharacterTab(UiPage page)")
        for control in ("page.Toggle(_gazeControlJson)", "page.ScrollablePopup(_gazeDefaultJson)",
                        "page.Toggle(_gazeFollowJson)"):
            self.assertIn(control, tab)
        self.assertLess(tab.index("<b>Gaze and blinking</b>"), tab.index("<b>Body</b>"))
        for name in ('"Gaze control"', '"Default gaze"', '"Gaze follows speaker"'):
            self.assertIn(name, body)
        self.assertIn("RegisterStringChooser(_gazeDefaultJson)", body)
        self.assertIn("popupOpenCallback = RefreshGazeChoices", body)
        status = method_body(body, "public void AddStatus(JSONClass s)")
        self.assertIn('s["gaze_control"]', status)
        self.assertIn('s["gaze_atoms"]', status)
        write = method_body(body, "public void WriteSettings(JSONClass root)")
        apply = method_body(body, "public void ApplySettings(JSONClass root)")
        for key in ("gaze_control", "gaze_default", "gaze_follows_speaker"):
            self.assertIn(f'"{key}"', write)
            self.assertIn(f'"{key}"', apply)
            self.assertIn(key, settings_file.DEFAULTS["body"])
        self.assertIn("_gazeBroken = true", body, "a gaze error stops only the gaze, not the whole body")

    def test_info_texts_are_simple_english_in_the_left_field(self):
        info = method_body(source("Body.cs"), "public string GazeInfoText()")
        for text in ("Default gaze is where the eyes look when the AI gave no order", "'VaM default' leaves the eyes alone",
                     "Gaze follows speaker", "Gaze control off: AIBody never moves the eyes",
                     "If the Glance plugin or Life's Gaze is on this Person, AIBody stays out of the eyes", "Gaze now: "):
            self.assertIn(text, info)
        self.assertIn("GazeInfoText()", method_body(source("Body.cs"), "public string CharacterInfoText()"))
        self.assertNotIn("page.Text(", method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)"))

    def test_menu_labels_map_to_the_config_keys(self):
        body = source("Body.cs")
        for label, key in (("GazeLabelClient", "KeyClient"), ("GazeLabelCamera", "KeyCamera"), ("GazeLabelForward", "KeyForward")):
            self.assertRegex(body, rf"label == {label}\) return GazeController\.{key}")
            self.assertRegex(body, rf"key == GazeController\.{key}\) return {label}")
        keys = dict(re.findall(r'public const string (Key\w+) = "(\w+)"', self.gaze))
        self.assertEqual(keys["KeyClient"], "client")
        for key in ("client", "camera", "forward", "away", "off"):
            self.assertIn(key, protocol.LOOK_TARGETS)
            self.assertIn(key, keys.values())

    def test_follows_speaker_uses_the_level_reports(self):
        mic = source("MicConfig.cs")
        self.assertIn("public bool UserSpeaking", mic)
        self.assertIn("if (speech) _speechAge = 0f;", mic)
        self.assertIn("_body.UserSpeaking = () => _link != null && _link.UserSpeaking;", source("AIBody.cs"))


if __name__ == "__main__":
    unittest.main()
