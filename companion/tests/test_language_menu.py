"""Menu "Language" (tab Voice, AI section; Leon, 22.11.2026 call): Auto plus the 20 xAI text to speech languages,
default German; ai.language reaches TTS (every sentence), STT, the language model and the realtime session
("Always answer in <language>"), and wins over a persona's language unless it is Auto."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from aibody_companion import languages, personas, settings_file
from aibody_companion.personas import Persona
from aibody_companion.pipeline.engines import EngineSet
from tests.test_realtime import RealtimeSim

ROOT = Path(__file__).resolve().parents[2]
APPLINK = (ROOT / "src" / "AIBody" / "AppLink.cs").read_text(encoding="utf-8")


def engines(language: str, persona_language: str = "") -> EngineSet:
    ai = settings_file.defaults()["ai"]
    ai["language"] = language
    es = EngineSet(ai, env={"XAI_API_KEY": "test-key-not-real"})
    if persona_language:
        es.persona = Persona(name="Anna", display_name="Anna", prompt="You are Anna.", language=persona_language)
    return es


class DefaultsTests(unittest.TestCase):
    def test_german_by_default(self):
        self.assertEqual(settings_file.defaults()["ai"]["language"], "de")
        self.assertEqual(personas.STARTER_PERSONAS["Anna"]["language"], "de")
        anna = json.loads((ROOT / "examples" / "personas" / "Anna" / "persona.json").read_text(encoding="utf-8"))
        self.assertEqual(anna["language"], "de")
        self.assertIn('"language": "de"', (ROOT / "examples" / "config.json").read_text(encoding="utf-8"))

    def test_xai_tts_codes(self):
        self.assertEqual(len(languages.LANGUAGES), 20)
        for code in ("de", "en", "fr", "es-ES", "pt-BR", "ja", "ar-AE"):
            self.assertIn(code, languages.CODES)
        self.assertEqual(languages.CODES[0], "auto")


class PrecedenceTests(unittest.TestCase):
    def test_menu_wins_over_the_persona(self):
        self.assertEqual(engines("en", persona_language="de").language(), "en")

    def test_auto_lets_the_persona_decide(self):
        self.assertEqual(engines("auto", persona_language="de").language(), "de")
        self.assertEqual(engines("auto").language(), "auto")

    def test_answer_rule_in_the_instructions(self):
        text = engines("de").persona_text()
        self.assertIn("Always answer in German", text)
        self.assertNotIn("Always answer in", engines("auto").persona_text())

    def test_reaches_tts_and_stt(self):
        es = engines("pt-BR")
        self.assertEqual(es._create("tts", "xai").language, "pt-BR")   # sent with every sentence (XaiTts.synthesize)
        self.assertEqual(es._create("stt", "xai").language, "pt")       # speech to text gets the plain language
        self.assertEqual(engines("de")._create("tts", "xai").language, "de")

    def test_tts_payload_carries_the_language(self):
        src = (ROOT / "companion" / "aibody_companion" / "pipeline" / "xai.py").read_text(encoding="utf-8")
        self.assertIn('"language": self.language,', src)


class LiveChangeTests(RealtimeSim):
    def test_realtime_session_and_menu_change(self):
        self.start(ai={"language": "de"})
        self.connect()
        session = self.app.realtime.session_config()
        self.assertIn("Always answer in German", session["instructions"])
        self.assertEqual(session["audio"]["input"]["transcription"], {"language_hint": "de"})
        before = self.app.realtime
        errors = self.app.apply_ai({"language": "en"})
        self.assertEqual(errors, [])
        self.assertEqual(self.app.engine_set.language(), "en")
        self.assertIn("Always answer in English", self.app.engine_set.persona_text())
        self.assertIsNot(self.app.realtime, before, "the realtime session reconnects with the new language")


class PluginMenuTests(unittest.TestCase):
    def test_chooser_lists_the_same_codes(self):
        block = APPLINK[APPLINK.index("public static readonly string[] Languages = {"):]
        block = block[:block.index("};")]
        labels = re.findall(r'"([^"]+)"', block)
        codes = ["auto"] + [re.search(r"\(([^()]+)\)$", label).group(1) for label in labels]
        self.assertEqual(codes, list(languages.CODES))
        self.assertIn("LanguageAuto, ", block)

    def test_default_german_and_wiring(self):
        self.assertIn('public const string LanguageDefault = "German (de)";', APPLINK)
        self.assertIn('new JSONStorableStringChooser("Language", new List<string>(Languages), LanguageDefault, "Language",', APPLINK)
        self.assertIn("page.ScrollablePopup(_languageJson);", APPLINK)
        self.assertIn('ai["language"] = LanguageCode(_languageJson.val);', APPLINK)
        self.assertIn('if (Protocol.Has(ui, "language")) target["language"] = ui["language"].Value;', APPLINK)
        self.assertIn('if (Protocol.Has(ai, "language")) SetLanguage(ai["language"].Value);', APPLINK)
        # the explanation is in the left info field, nothing new on the right
        self.assertIn('"<b>Language</b> is "', APPLINK)
