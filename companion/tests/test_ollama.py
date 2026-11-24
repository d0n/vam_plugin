"""Version 29: the local language model Ollama (no key, NDJSON streaming, conversation kept by the app)."""
from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion.config import ENGINES_AVAILABLE
from aibody_companion.pipeline.engines import EngineSet
from aibody_companion.pipeline.http import ApiError, HttpClient
from aibody_companion.pipeline.ollama import OllamaLlm
from aibody_companion.pipeline.sentences import Directive
from tests.fakes import FakeClock, FakeHttp, FakePlugin, FakeResponse, http_error
from tests.test_e2e_simulation import Sim


def ndjson(*parts: str, error: str | None = None) -> bytes:
    lines = [{"model": "m", "message": {"role": "assistant", "content": p}, "done": False} for p in parts]
    lines.append({"model": "m", "message": {"role": "assistant", "content": ""}, "done": True})
    if error:
        lines = [{"error": error}]
    return b"".join(json.dumps(x).encode() + b"\n" for x in lines)


SETTINGS = {"base_url": "http://127.0.0.1:11434", "model": "llama3.2", "max_output_tokens": 123,
            "temperature": 0.5, "keep_alive": "10m", "max_messages": 4, "timeout_s": 30.0}


class OllamaLlmTests(unittest.TestCase):
    def setUp(self):
        self.http = FakeHttp()
        self.answers = [ndjson("<<happy nod>> Hallo", " Don. Schön, dich zu sehen.")]
        self.http.route("/api/chat", lambda r: FakeResponse(self.answers.pop(0), "application/x-ndjson"))
        self.llm = OllamaLlm(SETTINGS, HttpClient(self.http), persona="Du bist Anna.")

    def sent(self, i=-1):
        return json.loads(self.http.requests[i].data)

    def test_request_and_answer(self):
        items = list(self.llm.stream("Hi", [], ["happy", "sad"], ["nod"]))
        self.assertEqual(items[0], Directive("happy", "nod"))
        self.assertEqual([i for i in items if isinstance(i, str)], ["Hallo Don.", "Schön, dich zu sehen."])
        payload = self.sent()
        self.assertEqual(self.http.requests[0].full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual((payload["model"], payload["stream"], payload["keep_alive"]), ("llama3.2", True, "10m"))
        self.assertEqual(payload["options"], {"num_predict": 123, "temperature": 0.5})
        system = payload["messages"][0]
        self.assertEqual(system["role"], "system")
        self.assertIn("Du bist Anna.", system["content"])
        self.assertIn("happy, sad", system["content"])
        self.assertEqual(payload["messages"][1], {"role": "user", "content": "Hi"})
        self.assertNotIn("Authorization", self.http.requests[0].headers, "no key anywhere")

    def test_conversation_is_kept_trimmed_and_reset(self):
        self.answers[:] = [ndjson("Eins."), ndjson("Zwei."), ndjson("Drei.")]
        for text in ("a", "b", "c"):
            list(self.llm.stream(text, [], [], []))
        roles = [m["content"] for m in self.sent()["messages"][1:]]
        self.assertEqual(roles, ["a", "Eins.", "b", "Zwei.", "c"], "the kept turns plus the new one")
        self.assertEqual(len(self.llm.messages), 4)
        self.llm.reset()
        self.assertEqual(self.llm.messages, [])

    def test_a_failed_answer_does_not_enter_the_conversation(self):
        self.answers[:] = [ndjson(error="boom")]
        with self.assertRaises(ApiError):
            list(self.llm.stream("x", [], [], []))
        self.assertEqual(self.llm.messages, [])

    def test_model_not_installed_and_server_down_have_plain_messages(self):
        self.http.route("/api/chat", lambda r: http_error(r.full_url, 404, {"error": "model 'llama3.2' not found"}))
        with self.assertRaises(ApiError) as e:
            list(self.llm.stream("x", [], [], []))
        self.assertIn("ollama pull llama3.2", str(e.exception))
        self.http.route("/api/chat", lambda r: urllib.error.URLError("refused"))
        with self.assertRaises(ApiError) as e:
            list(self.llm.stream("x", [], [], []))
        self.assertIn("ollama serve", str(e.exception))
        self.assertEqual(e.exception.status, 0)

    def test_error_inside_the_stream(self):
        self.answers[:] = [ndjson(error="model 'llama3.2' not found")]
        with self.assertRaises(ApiError) as e:
            list(self.llm.stream("x", [], [], []))
        self.assertIn("ollama pull", str(e.exception))

    def test_complete_is_one_plain_request_without_conversation(self):
        self.http.route("/api/chat", lambda r: FakeResponse(json.dumps({"message": {"content": '["a"]'}, "done": True}).encode()))
        self.assertEqual(self.llm.complete("summarize", "text"), '["a"]')
        payload = self.sent()
        self.assertEqual((payload["stream"], payload["options"]["temperature"], payload["options"]["num_predict"]), (False, 0.2, 2000))
        self.assertEqual(self.llm.messages, [])

    def test_reply_protocol(self):
        reply = self.llm.reply("Hi", [])
        self.assertIn("Hallo Don.", reply.say)


class EngineTests(unittest.TestCase):
    def test_listed_everywhere(self):
        self.assertIn("ollama", ENGINES_AVAILABLE["llm"])
        data, errors = settings_file.validate({"engines": {"llm": "ollama"}, "ai": {"ollama": {"model": "qwen3:8b", "max_messages": "10"}}})
        self.assertEqual(errors, [])
        self.assertEqual((data["engines"]["llm"], data["ai"]["ollama"]["model"], data["ai"]["ollama"]["max_messages"]),
                         ("ollama", "qwen3:8b", 10))
        clamped, _ = settings_file.validate({"ai": {"ollama": {"temperature": 9}}})
        self.assertLessEqual(clamped["ai"]["ollama"]["temperature"], 2.0)

    def test_selected_without_any_key(self):
        engines = EngineSet({}, http=HttpClient(FakeHttp()), env={})
        self.assertEqual(engines.select("llm", "ollama"), [], "no note: it runs as selected")
        self.assertEqual(engines.active_names["llm"], "ollama")
        self.assertIsInstance(engines.instances["llm"], OllamaLlm)
        self.assertIn("local", engines.status()["llm"]["ollama"])
        self.assertNotIn("ollama", engines.key_info())

    def test_persona_text_reaches_the_model_and_memory_stays_local(self):
        engines = EngineSet({"persona": "Du bist Marc."}, http=HttpClient(FakeHttp()), env={"XAI_API_KEY": "dummy-not-a-key"})
        engines.select("llm", "ollama")
        self.assertIn("Du bist Marc.", engines.instances["llm"].persona)
        self.assertIsInstance(engines.memory_llm(), OllamaLlm, "with Ollama selected the notes are summarized locally")
        engines.select("llm", "xai")
        self.assertNotIsInstance(engines.memory_llm(), OllamaLlm)


class ChainEndToEndTests(unittest.TestCase):
    def test_typed_question_is_answered_by_ollama_and_spoken(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            http = FakeHttp()
            http.route("/api/chat", lambda r: FakeResponse(ndjson("Mir geht es gut."), "application/x-ndjson"))
            sim = Sim(tmp, clock, http, env={}, mode="chain")
            app = sim.start_app()
            plugin = FakePlugin(Path(tmp), clock, mode="chain")
            plugin.ui["engines"]["llm"] = "ollama"  # the menu choice
            plugin.start()
            sim.run(plugin, 3)
            app.handle_user_text("Wie geht es dir?")
            sim.run(plugin, 1)
            speaks = sim.sent(plugin, "speak")
            self.assertEqual([s["text"] for s in speaks], ["Mir geht es gut."])
            beat = sim.sent(plugin, "companion_heartbeat")[-1]
            self.assertEqual(beat["engines_active"]["llm"], "ollama")
            self.assertIn("ollama", beat["engines_available"]["llm"])

    def test_server_down_falls_back_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            http = FakeHttp()
            http.route("/api/chat", lambda r: urllib.error.URLError("refused"))
            sim = Sim(tmp, clock, http, env={}, mode="chain")
            app = sim.start_app()
            plugin = FakePlugin(Path(tmp), clock, mode="chain")
            plugin.ui["engines"]["llm"] = "ollama"  # the menu choice
            plugin.start()
            sim.run(plugin, 3)
            app.handle_user_text("Hallo")
            sim.run(plugin, 1)
            self.assertIn("ollama serve", app.turn_status)
            self.assertTrue(sim.sent(plugin, "speak"), "the test model answers instead")


if __name__ == "__main__":
    unittest.main()
