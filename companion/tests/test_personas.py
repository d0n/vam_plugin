"""Version 27: personas (folders with persona.json) and memory (facts about the user, local files)."""
from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

from aibody_companion import personas, settings_file
from tests.fakes import FakeHttp, FakeResponse, text_stream
from tests.test_plugin_menu import ROOT, method_body, source
from tests.test_realtime import RealtimeSim

ANNA = {"name": "Anna", "prompt": "You are Anna, a calm librarian.", "language": "de", "voice": "ara"}
OLD_FACTS = ["Heißt Leon"]


class ParseTests(unittest.TestCase):
    def test_valid_persona(self):
        p, problems = personas.parse_persona("Anna", {**ANNA, "elevenlabs_voice_id": "abc_DEF-1", "memory": False})
        self.assertEqual(problems, [])
        self.assertEqual((p.name, p.label, p.prompt, p.language, p.voice, p.elevenlabs_voice_id, p.memory),
                         ("Anna", "Anna", "You are Anna, a calm librarian.", "de", "ara", "abc_DEF-1", False))

    def test_bad_values_are_reported_and_skipped(self):
        p, problems = personas.parse_persona("X", {"prompt": 5, "voice": "a/b", "language": "Deutsch!", "memory": "yes",
                                                   "colour": "red", "name": "A" * 100})
        text = " | ".join(problems)
        for needle in ("prompt must be a string", "voice 'a/b' is not valid", "language 'Deutsch!' is not valid",
                       "memory must be true or false", "unknown key 'colour'", "longer than 40", "no prompt"):
            self.assertIn(needle, text)
        self.assertEqual((p.voice, p.language, p.prompt, p.memory), ("", "", "", True))
        self.assertEqual(len(p.display_name), 40)
        self.assertIsNone(personas.parse_persona("X", ["not", "an", "object"])[0])

    def test_names_are_folder_names_only(self):
        for bad in ("../x", "a/b", "a\\b", "", ".hidden", "x" * 41, "end.", "end ", "C:", None):
            with self.subTest(name=bad):
                self.assertFalse(personas.valid_name(bad))
        for good in ("Anna", "Dr. Who", "marc_2", "a-b"):
            self.assertTrue(personas.valid_name(good))

    def test_store_lists_and_loads(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            store = personas.PersonaStore(Path(tmp) / "personas")
            self.assertEqual(store.names(), [])
            for name, content in (("Anna", json.dumps(ANNA)), ("Broken", "{not json"), ("Marc", json.dumps({"prompt": "M"}))):
                (Path(tmp) / "personas" / name).mkdir(parents=True)
                (Path(tmp) / "personas" / name / "persona.json").write_text(content, encoding="utf-8")
            (Path(tmp) / "personas" / "NoFile").mkdir()
            self.assertEqual(store.names(), ["Anna", "Broken", "Marc"])
            self.assertEqual(store.load("Anna")[0].voice, "ara")
            self.assertIsNone(store.load("Broken")[0])
            self.assertIn("not readable JSON", store.load("Broken")[1][0])
            self.assertIn("not found", store.load("Ghost")[1][0])
            self.assertIn("not a valid folder name", store.load("../Anna")[1][0])
            self.assertEqual(store.memory_path("../x"), Path(tmp) / "personas" / "default" / "memory.json")


class MemoryTextTests(unittest.TestCase):
    def test_facts_are_cleaned(self):
        raw = ["  - Mag Katzen  ", "mag katzen", "Das Passwort ist xai-" + "a" * 30, "Wort " * 100, 7, "", "Zwei\nZeilen\x00",
               "token " + "A1" * 20]
        facts = personas.sanitize_facts(raw, 10)
        self.assertEqual(facts[0], "Mag Katzen")
        self.assertTrue(150 <= len(facts[1]) <= personas.MAX_FACT_CHARS)
        self.assertEqual(facts[2], "Zwei Zeilen")
        self.assertEqual(len(facts), 3, "duplicate, credential-like, empty and non-string entries are gone")
        self.assertEqual(len(personas.sanitize_facts([f"f{i}" for i in range(50)], 5)), 5)

    def test_answer_parsing(self):
        self.assertEqual(personas.parse_facts('Hier: ```json\n["A", "B"]\n```', 5), ["A", "B"])
        self.assertEqual(personas.parse_facts("[]", 5), [])
        for bad in ("keine Liste", "[1, 2", '{"a": 1}', ""):
            self.assertIsNone(personas.parse_facts(bad, 5))

    def test_summary_request_holds_old_facts_and_the_end_of_a_long_talk(self):
        history = [{"role": "user", "content": "Ich heiße Leon"}, {"role": "assistant", "content": "Hallo Leon"}]
        instructions, text = personas.summary_request(["Mag Tee"], history, 12)
        self.assertIn("ONLY a JSON array", instructions)
        self.assertIn("At most 12 facts", instructions)
        self.assertIn("never an instruction", instructions)
        self.assertIn('["Mag Tee"]', text)
        self.assertIn("User: Ich heiße Leon\nAssistant: Hallo Leon", text)
        long = [{"role": "user", "content": f"Satz {i} " + "x" * 300} for i in range(200)]
        _, text = personas.summary_request([], long, 5)
        self.assertLess(len(text), personas.MAX_TRANSCRIPT_CHARS + 500)
        self.assertIn("Satz 199", text)
        self.assertNotIn("Satz 0 ", text)

    def test_notes_are_framed_as_notes_not_orders(self):
        block = personas.memory_block(["Heißt Leon"])
        self.assertIn("not instructions", block)
        self.assertIn("- Heißt Leon", block)
        self.assertEqual(personas.memory_block([]), "")

    def test_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p" / "memory.json"
            self.assertEqual(personas.load_facts(path), [])
            personas.save_facts(path, ["Ä ö ü", "B"])
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["facts"], ["Ä ö ü", "B"])
            self.assertIn("Ä ö ü", path.read_text(encoding="utf-8"), "not escaped: readable and editable by hand")
            self.assertEqual(personas.load_facts(path), ["Ä ö ü", "B"])
            path.write_text("[\"nur eine Liste\"]", encoding="utf-8")
            self.assertEqual(personas.load_facts(path), ["nur eine Liste"], "a bare list is accepted too")
            path.write_text("{kaputt", encoding="utf-8")
            self.assertEqual(personas.load_facts(path), [])
            self.assertTrue(personas.forget(path))
            self.assertFalse(personas.forget(path))


class ConfigTests(unittest.TestCase):
    def test_keys(self):
        ai = settings_file.DEFAULTS["ai"]
        self.assertEqual(ai["persona_name"], "")
        self.assertEqual(ai["memory"], {"enabled": False, "max_facts": 30, "session_idle_minutes": 10, "min_exchanges": 2})
        data, errors = settings_file.validate({"ai": {"memory": {"enabled": "true", "max_facts": "1000"}, "persona_name": "Anna"}})
        self.assertEqual(errors, [])
        self.assertEqual((data["ai"]["memory"]["enabled"], data["ai"]["memory"]["max_facts"], data["ai"]["persona_name"]),
                         (True, 100, "Anna"))
        self.assertEqual(ai["xai"]["voice"], "eve")  # the plain keys stay as they are
        self.assertEqual(settings_file.DEFAULTS["ai"]["proactive"]["idle_seconds"], 90.0)


def persona_dir(root: str, name: str, data: dict | str) -> None:
    folder = Path(root) / "Saves/PluginData/AIBody/personas" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "persona.json").write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def completion(text: str) -> FakeResponse:
    return FakeResponse(json.dumps({"id": "resp-mem", "output": [
        {"type": "message", "content": [{"type": "output_text", "text": text}]}]}).encode(), "application/json")


class PersonaFlowTests(RealtimeSim):
    def setUp(self):
        super().setUp()
        self.answers: list[bytes] = []
        self.summary = ['["Heißt Leon", "Mag Katzen"]']
        self.http = FakeHttp()
        self.http.route("/responses", self.responses)
        self.http.route("/tts", lambda r: FakeResponse(b"\x01\x00" * 24000, "audio/pcm"))

    def responses(self, request):
        payload = json.loads(request.data)
        if payload.get("stream") is False:
            return completion(self.summary.pop(0) if self.summary else "[]")
        return FakeResponse(self.answers.pop(0) if self.answers else text_stream(["Okay."], "r"), "text/event-stream")

    def begin(self, persona="", memory=None, personas_on_disk=("Anna",), idle_minutes=None):
        for name in personas_on_disk:
            persona_dir(self.tmp.name, name, ANNA if name == "Anna" else {"prompt": f"You are {name}."})
        ai: dict = {"proactive": {"idle_seconds": 0}}
        if persona:
            ai["persona_name"] = persona
        if memory is not None:
            ai["memory"] = {"enabled": memory, **({"session_idle_minutes": idle_minutes} if idle_minutes else {})}
        self.start(mode="chain", http=self.http, ai=ai)
        self.plugin.ai_ui["persona_name"] = persona
        self.plugin.ui["engines"] = {"stt": "null", "llm": "xai", "tts": "xai"}
        if memory is not None:
            self.plugin.ai_ui["memory"]["enabled"] = memory
        self.pump(lambda: bool(self.plugin.app_alive))
        self.sim.run(self.plugin, 3)

    def ask(self, text="Hallo"):
        self.app.handle_user_text(text)
        self.sim.run(self.plugin, 0.5)
        self.assertTrue(self.app.wait_turns())
        self.sim.run(self.plugin, 0.5)

    def llm(self):
        return [json.loads(r.data) for r in self.http.requests if r.full_url.endswith("/responses")
                and json.loads(r.data).get("stream") is not False]

    def summaries(self):
        return [json.loads(r.data) for r in self.http.requests if r.full_url.endswith("/responses")
                and json.loads(r.data).get("stream") is False]

    def tts_voices(self):
        return [json.loads(r.data).get("voice_id") for r in self.http.requests if r.full_url.endswith("/tts")]

    def memory_path(self, name="default"):
        return Path(self.tmp.name) / "Saves/PluginData/AIBody/personas" / name / "memory.json"

    def wait_for(self, check, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if check():
                return True
            time.sleep(0.01)
        return check()

    # -- personas ----------------------------------------------------------------------------

    def test_menu_list_and_persona_from_the_start(self):
        self.begin("Anna", personas_on_disk=("Anna", "Marc"))
        self.assertEqual(self.plugin.personas, ["Anna", "Marc"])
        self.assertEqual((self.plugin.persona_in_use, self.plugin.persona_note), ("Anna", ""))
        self.ask()
        instructions = self.llm()[0]["instructions"]
        self.assertIn("Your name is Anna.", instructions)
        self.assertIn("You are Anna, a calm librarian.", instructions)
        self.assertNotIn("friendly, curious character", instructions, "the persona replaces ai.persona")
        self.assertEqual(self.tts_voices(), ["ara"], "the persona's voice, not the menu's eve")

    def test_no_persona_is_the_old_behaviour(self):
        self.begin("")
        self.ask()
        self.assertIn("friendly, curious character", self.llm()[0]["instructions"])
        self.assertNotIn("Your name is", self.llm()[0]["instructions"])
        self.assertEqual(self.tts_voices(), ["eve"])
        self.assertEqual(self.plugin.persona_in_use, "")

    def test_a_missing_persona_falls_back_and_says_why(self):
        self.begin("Ghost")
        self.assertEqual(self.plugin.persona_in_use, "")
        self.assertIn("not found", self.plugin.persona_note)
        self.ask()
        self.assertIn("friendly, curious character", self.llm()[0]["instructions"])

    def test_switching_persona_starts_a_new_conversation(self):
        self.begin("", personas_on_disk=("Anna", "Marc"))
        self.ask("Hallo")
        self.assertEqual(len(self.app.history), 2)
        self.plugin.choose_persona("Marc")
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.plugin.persona_in_use, "Marc")
        self.assertEqual(self.app.history, [], "a new persona, a new conversation")
        self.ask("Hallo nochmal")
        second = self.llm()[1]
        self.assertNotIn("previous_response_id", second)
        self.assertIn("You are Marc.", second["instructions"])
        self.plugin.choose_persona("")
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.plugin.persona_in_use, "")

    def test_realtime_session_uses_persona_voice_language_and_notes(self):
        self.begin("Anna", memory=True)
        personas.save_facts(self.memory_path("Anna"), OLD_FACTS)
        self.app._load_memory()
        from aibody_companion.realtime_voice import RealtimeVoice
        rv = RealtimeVoice(self.app, "k")
        config = rv.session_config()
        self.assertEqual(config["voice"], "ara")
        self.assertEqual(config["audio"]["input"]["transcription"], {"language_hint": "de"})
        self.assertIn("Your name is Anna.", config["instructions"])
        self.assertIn("- Heißt Leon", config["instructions"])

    # -- memory ------------------------------------------------------------------------------

    def test_memory_is_off_by_default(self):
        self.begin("", memory=None)
        self.ask("Ich heiße Leon")
        self.ask("Ich mag Katzen")
        self.sim.run(self.plugin, 800, dt=5)
        self.assertEqual(self.summaries(), [])
        self.assertFalse(self.memory_path().exists())
        self.assertEqual(self.plugin.memory_info["enabled"], False)

    def test_summary_after_silence_is_saved_and_used_next_time(self):
        self.begin("", memory=True, idle_minutes=1)
        self.ask("Ich heiße Leon")
        self.ask("Ich mag Katzen")
        self.assertEqual(self.summaries(), [], "still talking")
        self.sim.run(self.plugin, 70, dt=1)
        self.assertTrue(self.wait_for(self.memory_path().exists))
        self.assertEqual(personas.load_facts(self.memory_path()), ["Heißt Leon", "Mag Katzen"])
        request = self.summaries()[0]
        self.assertFalse(request["store"], "documented: the response is not kept on the server")
        self.assertIn("User: Ich heiße Leon", request["input"][0]["content"])
        self.assertIn("ONLY a JSON array", request["instructions"])
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.plugin.memory_info["facts"], 2)
        self.sim.run(self.plugin, 120, dt=1)
        self.assertEqual(len(self.summaries()), 1, "the same talk is not summarized twice")
        # the next start puts the notes into the instructions
        self.app.shutdown()
        self.setUp_second_run()
        self.ask("Hallo")
        self.assertIn("- Heißt Leon", self.llm()[-1]["instructions"])
        self.assertIn("- Mag Katzen", self.llm()[-1]["instructions"])

    def setUp_second_run(self):
        self.http.requests.clear()
        self.sim.start_app()
        self.app = self.sim.app
        self.plugin.start()
        self.pump(lambda: bool(self.plugin.app_alive))
        self.sim.run(self.plugin, 3)

    def test_too_short_a_talk_is_not_summarized(self):
        self.begin("", memory=True, idle_minutes=1)
        self.ask("Hallo")
        self.sim.run(self.plugin, 200, dt=1)
        self.assertEqual(self.summaries(), [], "min_exchanges is 2")

    def test_summary_when_the_app_stops(self):
        self.begin("", memory=True)
        self.ask("Ich heiße Leon")
        self.ask("Ich mag Katzen")
        self.app.shutdown()
        self.assertEqual(len(self.summaries()), 1)
        self.assertEqual(personas.load_facts(self.memory_path()), ["Heißt Leon", "Mag Katzen"])

    def test_summary_when_the_persona_changes_goes_to_the_old_persona(self):
        self.begin("Anna", memory=True, personas_on_disk=("Anna", "Marc"))
        self.ask("Ich heiße Leon")
        self.ask("Ich mag Katzen")
        self.plugin.choose_persona("Marc")
        self.assertTrue(self.wait_for(lambda: self.sim.run(self.plugin, 0.2) or self.memory_path("Anna").exists()))
        self.assertFalse(self.memory_path("Marc").exists())
        self.assertEqual(personas.load_facts(self.memory_path("Anna")), ["Heißt Leon", "Mag Katzen"])

    def test_a_persona_can_opt_out_of_memory(self):
        persona_dir(self.tmp.name, "Anna", {**ANNA, "memory": False})
        self.begin("Anna", memory=True, personas_on_disk=())
        self.ask("Ich heiße Leon")
        self.ask("Ich mag Katzen")
        self.app.shutdown()
        self.assertEqual(self.summaries(), [])
        self.assertFalse(self.memory_path("Anna").exists())

    def test_a_bad_answer_keeps_the_old_notes(self):
        personas.save_facts(self.memory_path(), OLD_FACTS)
        self.summary = ["Ich kann das nicht.", "[]"]
        self.begin("", memory=True)
        self.assertEqual(self.plugin.memory_info["facts"], 1)
        self.ask("A")
        self.ask("B")
        self.app.finish_memory_session("test", wait=True)
        self.assertEqual(personas.load_facts(self.memory_path()), OLD_FACTS)
        self.assertIn("not a usable list", self.app.memory_note)
        self.ask("C")
        self.ask("D")
        self.app.finish_memory_session("test", wait=True)
        self.assertEqual(personas.load_facts(self.memory_path()), OLD_FACTS, "an empty list never wipes the notes")

    def test_api_error_keeps_the_notes_and_the_app_running(self):
        from tests.fakes import http_error
        personas.save_facts(self.memory_path(), OLD_FACTS)
        self.begin("", memory=True)
        self.http.route("/responses", lambda r: http_error(r.full_url, 500, {"error": "boom"})
                        if json.loads(r.data).get("stream") is False else FakeResponse(text_stream(["Okay."], "r"), "text/event-stream"))
        self.ask("A")
        self.ask("B")
        self.app.finish_memory_session("test", wait=True)
        self.assertEqual(personas.load_facts(self.memory_path()), OLD_FACTS)
        self.assertIn("memory not updated", self.app.memory_note)

    def test_secret_looking_facts_never_reach_the_file(self):
        self.summary = ['["Mag Tee", "Mein Schlüssel ist xai-' + "q" * 30 + '"]']
        self.begin("", memory=True)
        self.ask("A")
        self.ask("B")
        self.app.finish_memory_session("test", wait=True)
        self.assertEqual(personas.load_facts(self.memory_path()), ["Mag Tee"])
        self.assertNotIn("xai-", self.memory_path().read_text(encoding="utf-8"))

    def test_no_key_no_summary_and_no_crash(self):
        self.start(mode="chain", http=self.http, env={}, ai={"memory": {"enabled": True}})
        self.plugin.ai_ui["memory"]["enabled"] = True
        self.pump(lambda: bool(self.plugin.app_alive))
        self.app.history += [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]
        self.app.finish_memory_session("test", wait=True)
        self.assertIn("no xAI key", self.app.memory_note)

    def test_forget_button_deletes_the_file_and_starts_fresh(self):
        personas.save_facts(self.memory_path(), OLD_FACTS)
        self.begin("", memory=True)
        self.ask("Hallo")
        self.assertIn("- Heißt Leon", self.llm()[0]["instructions"])
        self.plugin.forget_memory()
        self.sim.run(self.plugin, 3)
        self.assertFalse(self.memory_path().exists())
        self.assertEqual(self.plugin.memory_info["facts"], 0)
        self.assertEqual(self.app.history, [])
        self.ask("Hallo")
        self.assertNotIn("Heißt Leon", self.llm()[1]["instructions"])
        self.assertNotIn("previous_response_id", self.llm()[1])

    def test_memory_switch_live(self):
        personas.save_facts(self.memory_path(), OLD_FACTS)
        self.begin("", memory=False)
        self.assertEqual(self.plugin.memory_info["facts"], 0)
        self.plugin.set_memory(True)
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.plugin.memory_info, {"enabled": True, "facts": 1})
        self.ask("Hallo")
        self.assertIn("- Heißt Leon", self.llm()[0]["instructions"])
        self.plugin.set_memory(False)
        self.sim.run(self.plugin, 3)
        self.assertEqual(self.plugin.memory_info["facts"], 0)


class PluginSourceTests(unittest.TestCase):
    def setUp(self):
        self.link = source("AppLink.cs")

    def test_menu_controls(self):
        for needle in ('new JSONStorableStringChooser("Persona"', 'new JSONStorableBool("Memory", false', "page.Popup(_personaJson)",
                       "page.Toggle(_memoryJson)", 'page.Button("Forget memory", ForgetMemory)',
                       'ai["persona_name"] = PersonaName', 'memory["enabled"].AsBool = _memoryJson.val',
                       'MergeSection(target, ui, "memory", "enabled")', 'target["persona_name"] = ui["persona_name"].Value',
                       "SetPersonaChoices(msg[\"personas\"] as JSONArray)", "EvtMemoryForget"):
            self.assertIn(needle, self.link + source("Protocol.cs"))
        self.assertIn('EvtMemoryForget = "memory_forget"', source("Protocol.cs"))

    def test_menu_does_not_send_the_none_label(self):
        self.assertIn('_personaJson.val == PersonaNone ? "" : _personaJson.val', self.link)

    def test_info_text_explains_persona_and_memory(self):
        info = method_body(self.link, "private string PersonaInfoText()")
        for text in ("docs/PERSONAS.md", "<b>Memory</b> is off", "Forget memory", "is not in use"):
            self.assertIn(text, info)
        self.assertIn("PersonaInfoText()", method_body(self.link, "public string VoiceInfoText()"))


if __name__ == "__main__":
    unittest.main()
