"""Body tools: function calls -> plugin commands, in the chain (/v1/responses) and in realtime."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aibody_companion import body_tools
from tests.fakes import FakeClock, FakeHttp, FakePlugin, FakeResponse, sse, text_stream
from tests.test_e2e_simulation import Sim
from tests.test_realtime import RealtimeSim, tone

KEY = "xai-FAKE-NOT-A-KEY-tools"


def call_item(call_id, name, args):
    return {"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(args)}


def tool_only_stream(response_id, *calls):
    return sse({"type": "response.created", "response": {"id": response_id}},
               *[{"type": "response.output_item.done", "item": c} for c in calls],
               {"type": "response.completed", "response": {"id": response_id, "output": list(calls)}})


class UnitTests(unittest.TestCase):
    def setUp(self):
        self.lists = body_tools.BodyLists(["neutral", "happy"], ["nod", "wave"], ["sit", "stand"])

    def test_tools_only_list_what_the_body_has(self):
        tools = body_tools.tools(self.lists)
        self.assertEqual([t["name"] for t in tools], ["express"], "poses are never a tool: only the exact-match gate")
        self.assertEqual([t["name"] for t in body_tools.tools(body_tools.BodyLists(["neutral"], [], []))], ["express"])

    def test_resolve(self):
        cmds, result = body_tools.resolve("express", '{"expression": "Happy", "gesture": "wave"}', self.lists, True)
        self.assertEqual(cmds, [("expression", {"name": "happy", "intensity": 1.0, "blend": 0.4}),
                                ("gesture", {"name": "wave"})])
        self.assertTrue(result["ok"])
        for name in ("sit", "fly"):
            cmds, result = body_tools.resolve("pose", {"name": name}, self.lists, True)
            self.assertEqual(cmds, [], "a pose call from the model is never turned into a command")
            self.assertFalse(result["ok"])
        self.assertFalse(body_tools.resolve("look_at", {}, self.lists, True)[1]["ok"])
        cmds, result = body_tools.resolve("express", {"expression": "happy"}, self.lists, False, "body control is off")
        self.assertEqual((cmds, result), ([], {"ok": False, "error": "body control is off"}))

    def test_poses_are_not_offered_as_gestures(self):
        lists = body_tools.BodyLists.from_body_info({"gestures": ["nod", "sit"], "poses": ["sit"]}, ["neutral"], [])
        self.assertEqual((lists.gestures, lists.poses), (["nod"], ["sit"]))


class ChainToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = FakeClock()
        self.http = FakeHttp()
        self.http.route("/tts", lambda r: FakeResponse(b"\x10\x00" * 4800, "audio/pcm"))
        self.answers = []
        self.http.route("/responses", lambda r: FakeResponse(self.answers.pop(0), "text/event-stream"))

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, mode="chain", poses=("sitting",), body_control=True):
        self.sim = Sim(self.tmp.name, self.clock, self.http, env={"XAI_API_KEY": KEY}, mode=mode)
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(self.root, self.clock, mode=mode)
        self.plugin.ui["engines"] = {"stt": "xai", "llm": "xai", "tts": "xai"}
        self.plugin.poses = list(poses)
        self.plugin.body_control = body_control
        self.plugin.start()
        self.sim.run(self.plugin, 3)

    def requests(self):
        return [json.loads(r.data) for r in self.http.requests if "/responses" in r.full_url]

    def ask(self, text):
        self.app.handle_user_text(text)
        self.sim.run(self.plugin, 3)

    def test_tool_only_answer_runs_the_commands_and_continues(self):
        self.answers = [tool_only_stream("resp-1", call_item("c1", "pose", {"name": "sitting"}),
                                         call_item("c2", "express", {"expression": "happy", "gesture": "nod"})),
                        text_stream(["Okay, ich setze mich."], "resp-2")]
        self.start()
        self.ask("Mach es dir bitte bequem.")
        first, second = self.requests()
        self.assertEqual([t["name"] for t in first["tools"]], ["express"], "no pose tool is offered")
        self.assertNotIn('"pose"', first["instructions"])
        self.assertEqual(self.sim.sent(self.plugin, "pose"), [], "a stray pose call never reaches the body")
        self.assertEqual(self.sim.sent(self.plugin, "expression")[0]["name"], "happy")
        self.assertEqual(self.sim.sent(self.plugin, "gesture")[0]["name"], "nod")
        self.assertEqual(second["previous_response_id"], "resp-1")
        outputs = [i for i in second["input"] if i.get("type") == "function_call_output"]
        self.assertEqual([o["call_id"] for o in outputs], ["c1", "c2"], "results go back, the model does not hang")
        self.assertFalse(json.loads(outputs[0]["output"])["ok"], "the stray pose call is answered with an error")
        self.assertTrue(json.loads(outputs[1]["output"])["ok"])
        self.assertNotIn("role", json.dumps(second["input"]), "no new user message in the continuation")
        self.assertEqual([s["text"] for s in self.sim.sent(self.plugin, "speak")], ["Okay, ich setze mich."])

    def test_results_of_calls_with_words_go_with_the_next_turn(self):
        words_and_call = sse({"type": "response.created", "response": {"id": "resp-1"}},
                             {"type": "response.output_text.delta", "delta": "Gern! "},
                             {"type": "response.output_item.done",
                              "item": call_item("c9", "pose", {"name": "sitting"})},
                             {"type": "response.completed", "response": {"id": "resp-1", "output": []}})
        self.answers = [words_and_call, text_stream(["Gut."], "resp-2")]
        self.start()
        self.ask("Mach es dir bequem.")
        self.assertEqual(len(self.requests()), 1, "words came: no extra round trip")
        self.ask("Und jetzt?")
        nxt = self.requests()[1]
        self.assertEqual(nxt["input"][0]["type"], "function_call_output")
        self.assertEqual(nxt["input"][0]["call_id"], "c9")
        self.assertEqual(nxt["input"][-1]["role"], "user")

    def test_qa_mode_offers_no_tools(self):
        self.answers = [text_stream(["Hallo."])]
        self.start(mode="qa")
        self.ask("Hallo")
        self.assertNotIn("tools", self.requests()[0])
        self.assertNotIn("function", self.requests()[0]["instructions"])

    def test_body_control_off_offers_no_tools_and_answers_a_stray_call(self):
        self.answers = [tool_only_stream("resp-1", call_item("c1", "pose", {"name": "sitting"})),
                        text_stream(["Mach ich nicht."], "resp-2")]
        self.start(body_control=False)
        self.ask("Mach es dir bequem.")
        first, second = self.requests()
        self.assertNotIn("tools", first)
        self.assertEqual(self.sim.sent(self.plugin, "pose"), [])
        out = json.loads(second["input"][0]["output"])
        self.assertEqual(out, {"ok": False, "error": "body control is off in the plugin"})


class RealtimeToolTests(RealtimeSim):
    def item_created(self):
        return any(e["type"] == "conversation.item.create" for e in self.server.conn.received)

    def test_session_offers_no_pose_tool_and_a_stray_pose_call_is_refused(self):
        self.start()
        self.plugin.poses = ["sitting"]
        self.connect()
        self.pump(lambda: self.app.body_info.get("poses") == ["sitting"])
        self.app.realtime.refresh_instructions()

        def tool_names():
            ups = [e for e in self.server.conn.received if e["type"] == "session.update"]
            return [t["name"] for t in ups[-1]["session"].get("tools", [])] if ups else []

        self.assertTrue(self.pump(lambda: tool_names() == ["express"]), tool_names())
        self.server.respond(["Okay."], tone(1.0), call={"name": "pose", "arguments": {"name": "sitting"}})
        self.assertTrue(self.pump(self.item_created))
        self.assertEqual(self.sim.sent(self.plugin, "pose"), [])
        out = [e for e in self.server.conn.received if e["type"] == "conversation.item.create"][-1]
        self.assertFalse(json.loads(out["item"]["output"])["ok"])

    def test_body_control_off_answers_without_commands(self):
        self.start()
        self.plugin.body_control = False
        self.connect()
        self.pump(lambda: self.app.body_info.get("body_control") in (False, "false"))
        self.assertEqual(self.app.offered_tools(), [])
        self.server.respond(["Nein."], tone(1.0), call={"name": "pose", "arguments": {"name": "sitting"}})
        self.assertTrue(self.pump(self.item_created))
        out = [e for e in self.server.conn.received if e["type"] == "conversation.item.create"][-1]
        self.assertFalse(json.loads(out["item"]["output"])["ok"])
        self.assertEqual(self.sim.sent(self.plugin, "pose"), [])


del RealtimeSim
