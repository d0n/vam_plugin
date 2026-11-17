"""Cloud engines against a fake HTTP server (no real keys, no network)."""
import json
import logging
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from aibody_companion import settings_file
from aibody_companion.config import ENGINES_AVAILABLE, Config
from aibody_companion.orchestrator import Companion
from aibody_companion.pipeline import Directive, SentenceSplitter, StreamParser
from aibody_companion.pipeline.elevenlabs import ElevenLabsTts
from aibody_companion.pipeline.engines import KINDS, EngineSet, ai_settings
from aibody_companion.pipeline.http import ApiError, HttpClient, iter_sse
from aibody_companion.pipeline.keys import resolve_key
from aibody_companion.pipeline.xai import XaiLlm, XaiStt, XaiTts
from aibody_companion.vamjson import as_bool, as_number
from tests.fakes import FakeHttp, FakeResponse, http_error, sse, text_stream

KEY = "test-key-not-real-abcdef123456"


def pcm(seconds: float, rate: int = 24000) -> bytes:
    return b"\x10\x00" * int(seconds * rate)


class XaiLlmTests(unittest.TestCase):
    def setUp(self):
        self.http = FakeHttp()
        self.ai = ai_settings({})
        self.llm = XaiLlm(self.ai["xai"], KEY, HttpClient(self.http), persona="Du bist Anna.")

    def test_request_and_streamed_sentences(self):
        self.http.route("/responses", lambda r: FakeResponse(
            text_stream(["<<thinking tilt>>Hm. ", "Das ist eine gute Frage. Ich", " denke nach."]),
            "text/event-stream"))
        items = list(self.llm.stream("Warum?", [], ["neutral", "thinking"], ["nod", "tilt"]))
        self.assertEqual(items[0], Directive("thinking", "tilt"))
        self.assertEqual(items[1:], ["Hm.", "Das ist eine gute Frage.", "Ich denke nach."])
        req = self.http.requests[0]
        self.assertEqual(req.full_url, "https://api.x.ai/v1/responses")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), f"Bearer {KEY}")
        body = json.loads(req.data)
        self.assertEqual(body["model"], "grok-4.7")
        self.assertTrue(body["stream"])
        self.assertEqual(body["input"], [{"role": "user", "content": "Warum?"}])
        self.assertTrue(body["instructions"].startswith("Du bist Anna."))
        self.assertIn("thinking", body["instructions"])
        self.assertNotIn("previous_response_id", body)
        self.assertEqual(self.llm.previous_response_id, "resp-1")

    def test_conversation_continues_without_instructions(self):
        self.http.route("/responses", lambda r: FakeResponse(text_stream(["Ja."], "resp-7"), "text/event-stream"))
        list(self.llm.stream("eins", [], [], []))
        list(self.llm.stream("zwei", [], [], []))
        second = json.loads(self.http.requests[1].data)
        self.assertEqual(second["previous_response_id"], "resp-7")
        self.assertNotIn("instructions", second, "docs: instructions cannot be combined with previous_response_id")

    def test_expired_conversation_starts_again(self):
        self.llm.previous_response_id = "old"
        calls = []

        def handler(r):
            calls.append(json.loads(r.data))
            if len(calls) == 1:
                return http_error(r.full_url, 404, {"error": "response not found"})
            return FakeResponse(text_stream(["Neu."], "resp-new"), "text/event-stream")

        self.http.route("/responses", handler)
        self.assertEqual(list(self.llm.stream("hi", [], [], [])), ["Neu."])
        self.assertNotIn("previous_response_id", calls[1])
        self.assertIn("instructions", calls[1])

    def test_non_streaming_json_answer(self):
        body = {"id": "r9", "output": [{"type": "message", "content": [{"type": "output_text", "text": "Hallo du."}]}]}
        self.http.route("/responses", lambda r: FakeResponse(json.dumps(body).encode(), "application/json"))
        self.assertEqual(list(self.llm.stream("hi", [], [], [])), ["Hallo du."])
        self.assertEqual(self.llm.previous_response_id, "r9")

    def test_stream_error_and_http_errors(self):
        self.http.route("/responses", lambda r: FakeResponse(
            sse({"type": "response.failed", "response": {"error": {"message": "overloaded"}}}), "text/event-stream"))
        with self.assertRaises(ApiError) as cm:
            list(self.llm.stream("hi", [], [], []))
        self.assertIn("overloaded", str(cm.exception))
        self.http.route("/responses", lambda r: http_error(r.full_url, 401, {"error": "Incorrect API key"}))
        with self.assertRaises(ApiError) as cm:
            list(self.llm.stream("hi", [], [], []))
        self.assertEqual(cm.exception.status, 401)

    def test_key_never_logged(self):
        self.http.route("/responses", lambda r: http_error(r.full_url, 500, {"error": "boom"}))
        with self.assertLogs(level=logging.DEBUG) as logs:
            logging.getLogger("aibody_companion").debug("start")
            try:
                list(self.llm.stream("hi", [], [], []))
            except ApiError as e:
                logging.getLogger("aibody_companion").warning("failed: %s", e)
        self.assertFalse(any(KEY in line for line in logs.output))


class XaiSpeechTests(unittest.TestCase):
    def setUp(self):
        self.http = FakeHttp()
        self.ai = ai_settings({})
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_stt_multipart_with_file_last(self):
        self.http.route("/stt", lambda r: FakeResponse(json.dumps({"text": " Hallo Welt ", "language": "de"}).encode()))
        stt = XaiStt(self.ai["xai"], KEY, HttpClient(self.http), language="de")
        self.assertEqual(stt.transcribe(pcm(0.5, 16000), 16000), "Hallo Welt")
        req = self.http.requests[0]
        self.assertEqual(req.full_url, "https://api.x.ai/v1/stt")
        self.assertIn("multipart/form-data; boundary=", req.get_header("Content-type"))
        body = req.data
        self.assertLess(body.index(b'name="model"'), body.index(b'name="file"'), "file must be the last field")
        self.assertIn(b"grok-voice-transcribe-2.0", body)
        self.assertIn(b'name="language"\r\n\r\nde', body)
        self.assertIn(b"RIFF", body)

    def test_stt_auto_language_is_not_sent(self):
        self.http.route("/stt", lambda r: FakeResponse(b'{"text": "hi"}'))
        XaiStt(self.ai["xai"], KEY, HttpClient(self.http)).transcribe(pcm(0.2, 16000), 16000)
        self.assertNotIn(b'name="language"', self.http.requests[0].data)

    def test_tts_pcm_to_wav(self):
        self.http.route("/tts", lambda r: FakeResponse(pcm(1.5), "audio/pcm"))
        out = Path(self.tmp.name) / "a.wav"
        duration = XaiTts(self.ai["xai"], KEY, HttpClient(self.http)).synthesize("Hallo!", out)
        self.assertAlmostEqual(duration, 1.5, places=3)
        body = self.http.json_body()
        self.assertEqual(body["voice_id"], "eve")
        self.assertEqual(body["language"], "auto")
        self.assertEqual(body["output_format"], {"codec": "pcm", "sample_rate": 24000})
        self.assertNotIn("speed", body)
        with wave.open(str(out), "rb") as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 24000))

    def test_tts_rejects_json_instead_of_audio(self):
        self.http.route("/tts", lambda r: FakeResponse(b'{"error": "x"}', "application/json"))
        with self.assertRaises(ApiError):
            XaiTts(self.ai["xai"], KEY, HttpClient(self.http)).synthesize("x", Path(self.tmp.name) / "b.wav")


class ElevenLabsTests(unittest.TestCase):
    def setUp(self):
        self.http = FakeHttp()
        self.ai = ai_settings({})
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_request_and_wav(self):
        self.http.route("api.elevenlabs.io", lambda r: FakeResponse(pcm(0.75), "audio/pcm"))
        out = Path(self.tmp.name) / "e.wav"
        tts = ElevenLabsTts(self.ai["elevenlabs"], KEY, HttpClient(self.http), language="de")
        self.assertAlmostEqual(tts.synthesize("Guten Tag.", out), 0.75, places=3)
        req = self.http.requests[0]
        self.assertEqual(req.full_url,
                         "https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb?output_format=pcm_24000")
        self.assertEqual(req.get_header("Xi-api-key"), KEY)
        body = json.loads(req.data)
        self.assertEqual(body, {"text": "Guten Tag.", "model_id": "eleven_multilingual_v2"},
                         "no language_code for multilingual_v2 (docs)")
        self.assertTrue(out.is_file())

    def test_language_code_for_other_models(self):
        self.http.route("api.elevenlabs.io", lambda r: FakeResponse(pcm(0.1), "audio/pcm"))
        settings = dict(self.ai["elevenlabs"], model_id="eleven_flash_v2_5")
        tts = ElevenLabsTts(settings, KEY, HttpClient(self.http), language="de")
        tts.synthesize("x", Path(self.tmp.name) / "f.wav")
        self.assertEqual(self.http.json_body()["language_code"], "de")

    def test_missing_key_does_not_block(self):
        engines = EngineSet({}, http=HttpClient(self.http), env={})
        notes = engines.select("tts", "elevenlabs")
        self.assertTrue(notes and "nicht konfiguriert" in notes[0])
        self.assertEqual(engines.active_names["tts"], "tone")
        self.assertEqual(engines.requested["tts"], "elevenlabs")
        self.assertTrue(engines.status()["tts"]["elevenlabs"].startswith("nicht konfiguriert"))
        self.assertFalse(self.http.requests, "no request without a key")

    def test_key_file_added_later_is_picked_up(self):
        key_file = Path(self.tmp.name) / "elevenlabs.key"
        engines = EngineSet({"elevenlabs": {"key_file": str(key_file)}}, http=HttpClient(self.http), env={})
        engines.select("tts", "elevenlabs")
        self.assertEqual(engines.active_names["tts"], "tone")
        key_file.write_text(KEY + "\n")
        self.assertTrue(engines.refresh())
        self.assertEqual(engines.active_names["tts"], "elevenlabs")
        self.assertIn("Key-Datei", engines.status()["tts"]["elevenlabs"])
        self.assertNotIn(KEY, json.dumps(engines.status()))


class KeyTests(unittest.TestCase):
    def test_env_wins_over_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".key", delete=False) as f:
            f.write("from-file\n")
        try:
            self.assertEqual(resolve_key("XAI_API_KEY", f.name, {"XAI_API_KEY": "from-env"})[0], "from-env")
            key, where = resolve_key("XAI_API_KEY", f.name, {})
            self.assertEqual(key, "from-file")
            self.assertIn("Key-Datei", where)
        finally:
            os.unlink(f.name)

    def test_relative_key_file_is_below_home(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / "keys").mkdir()
            (Path(home) / "keys" / "xai.txt").write_text("k1")
            with mock.patch("pathlib.Path.home", return_value=Path(home)):
                self.assertEqual(resolve_key("X", "keys/xai.txt", {})[0], "k1")

    def test_missing(self):
        key, why = resolve_key("XAI_API_KEY", "", {})
        self.assertIsNone(key)
        self.assertIn("XAI_API_KEY", why)

    def test_pasted_key_in_config_is_refused(self):
        data, errors = settings_file.validate({"ai": {"xai": {"key_file": "xai-FAKE-NOT-A-KEY"}}})
        self.assertEqual(data["ai"]["xai"]["key_file"], "")
        self.assertTrue(any("looks like an API key" in e for e in errors))
        data, errors = settings_file.validate({"ai": {"xai": {"key_file": "~/keys/xai.txt"}}})
        self.assertEqual((data["ai"]["xai"]["key_file"], errors), ("~/keys/xai.txt", []))


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.http = FakeHttp()
        from tests.test_routing import FakeTransport

        self.transport = FakeTransport()
        self.cfg = Config(vam_root=self.tmp.name, llm="xai", tts="xai")
        self.engines = EngineSet({}, http=HttpClient(self.http), env={"XAI_API_KEY": KEY})
        self.c = Companion(self.cfg, self.transport, engines=self.engines)

    def tearDown(self):
        self.tmp.cleanup()

    def speaks(self):
        return [m for m in self.transport.sent if m["type"] == "speak"]

    def test_tts_failure_falls_back_to_tone(self):
        self.http.route("/responses", lambda r: FakeResponse(text_stream(["Hallo. Wie geht's?"]), "text/event-stream"))
        self.http.route("/tts", lambda r: http_error(r.full_url, 500, {"error": "tts down"}))
        self.c.handle_user_text("hi")
        self.assertEqual([s["text"] for s in self.speaks()], ["Hallo.", "Wie geht's?"])
        for s in self.speaks():
            self.assertTrue((Path(self.tmp.name) / s["audio"]).is_file())

    def test_llm_failure_falls_back_to_echo(self):
        self.http.route("/responses", lambda r: http_error(r.full_url, 401, {"error": "bad key"}))
        self.http.route("/tts", lambda r: FakeResponse(pcm(0.2), "audio/pcm"))
        self.c.handle_user_text("Hallo")
        self.assertEqual([s["text"] for s in self.speaks()], ["You said: Hallo"])

    def test_stt_failure_hears_nothing(self):
        self.engines.select("stt", "xai")
        self.http.route("/stt", lambda r: http_error(r.full_url, 503, {"error": "busy"}))
        self.assertEqual(self.c.handle_utterance(pcm(0.5, 16000)), "")
        self.assertFalse(self.speaks())

    def test_live_switch_from_plugin(self):
        self.c.handle_config({"id": "c1", "mic": {}, "engines": {"stt": "null", "llm": "echo", "tts": "elevenlabs"}})
        ack = [m for m in self.transport.sent if m["type"] == "config_ack"][-1]
        self.assertEqual(ack["applied"]["engines"]["tts"], "elevenlabs")
        self.assertTrue(any("Fallback 'tone'" in e for e in ack["errors"]))
        self.assertEqual(self.c.engine_set.active_names, {"stt": "null", "llm": "echo", "tts": "tone"})


class TextTests(unittest.TestCase):
    def test_sentence_splitter(self):
        s = SentenceSplitter()
        out = s.feed("Das kostet ca. 3.50 Euro, z.B. heute. Wirklich?! Ja")
        self.assertEqual(out, ["Das kostet ca. 3.50 Euro, z.B. heute.", "Wirklich?!"])
        self.assertEqual(s.flush(), ["Ja"])

    def test_long_text_without_end_is_cut(self):
        s = SentenceSplitter()
        out = s.feed("wort " * 100)
        self.assertTrue(out and all(len(x) <= 241 for x in out))

    def test_tag_parser(self):
        p = StreamParser(["happy", "sad"], ["nod"])
        items = p.feed("<<ha") + p.feed("ppy nod>> Hi") + p.feed(" there. Bye") + p.finish()
        self.assertEqual(items, [Directive("happy", "nod"), "Hi there.", "Bye"])
        p = StreamParser(["happy"], [])
        self.assertEqual(p.feed("Kein Tag. ") + p.finish(), ["Kein Tag."])
        p = StreamParser(["happy"], [])
        self.assertEqual(p.feed("<<unknown>> Text.") + p.finish(), ["Text."])

    def test_sse_parser(self):
        raw = b": keep-alive\n\nevent: a\ndata: {\"x\": 1}\n\ndata: [DONE]\n\ndata: ignored\n\n"
        self.assertEqual(list(iter_sse(iter(raw.splitlines(keepends=True)))), [("a", '{"x": 1}')])

    def test_vam_values(self):
        self.assertIs(as_bool("true"), True)
        self.assertIs(as_bool("False"), False)
        self.assertIsNone(as_bool("yes"))
        self.assertEqual(as_number("0.25"), 0.25)
        self.assertIsNone(as_number("nan"))
        self.assertIsNone(as_number(True))


class RegistryTests(unittest.TestCase):
    def test_every_available_engine_can_be_built(self):
        engines = EngineSet({}, env={"XAI_API_KEY": KEY, "ELEVENLABS_API_KEY": KEY})
        for kind in KINDS:
            for name in ENGINES_AVAILABLE[kind]:
                self.assertEqual(engines.select(kind, name), [], f"{kind}/{name}")
                self.assertEqual(engines.active_names[kind], name)

    def test_vam_written_ai_section(self):
        ai = ai_settings({"xai": {"speed": "1.25", "max_output_tokens": "300", "sample_rate": "16000"},
                          "fallback": {"tts": "tone"}})
        self.assertEqual((ai["xai"]["speed"], ai["xai"]["max_output_tokens"], ai["xai"]["sample_rate"]),
                         (1.25, 300, 16000))


if __name__ == "__main__":
    unittest.main()
