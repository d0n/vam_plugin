"""Generates protocol/schema/config.schema.json and examples/config.json from
companion/aibody_companion/settings_file.py (DEFAULTS, RANGES, CHOICES).

    python tools/gen_config_schema.py          # write both files
    python tools/gen_config_schema.py --check  # exit 1 if they are out of date (used by the tests)

Numbers and booleans may also be strings: the plugin writes config.json with VaM's SimpleJSON,
which stores "0.5" / "true" (docs/API_AUDIT.md E21).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))

from aibody_companion import __version__
from aibody_companion.audio.mic_settings import LIMITS, MODES, VAD_ENGINES
from aibody_companion.settings_file import CHOICES, DEFAULTS, RANGES, defaults

SCHEMA_PATH = ROOT / "protocol" / "schema" / "config.schema.json"
EXAMPLE_PATH = ROOT / "examples" / "config.json"

DESCRIPTIONS = {
    ("connection",): "Connection (link on/off in tab 'Voice'): data file paths "
                     "(relative to the VaM folder, below Saves/ or Custom/)",
    ("engines",): "Tab 'Voice', section 'Voice > AI Character': stt null|xai, llm echo|xai, tts tone|xai|elevenlabs. A cloud engine without API key "
                  "stays selected but the fallback (ai.fallback) runs",
    ("mic",): "Tab 'Client Character': captured by the companion app; push-to-talk state itself is never saved",
    ("body",): "Tab 'AI Character', section 'Body (this Person only)'",
    ("ui",): "Plugin UI state: first_run_hint_dismissed = the short note about the xAI token at the top of the plugin UI was closed or answered, "
             "so it is not shown again",
    ("advanced",): "Tab 'Config' (companion inbox poll interval, verbose log)",
    ("advanced", "file_poll_interval_s"): "Slider 'Companion inbox poll interval (s)' (stored name 'File poll interval (s)'): "
                                          "how often the plugin checks the companion app's inbox folder "
                                          "Saves/PluginData/AIBody/<channel>/inbox/ for messages (speech, poses, "
                                          "expressions). Does not reload config.json",
    ("ai",): "Companion app only (no tab; the plugin keeps this section unchanged, except the keys it has controls for). "
             "The only API key stored here is the xAI token in PLAIN TEXT (xai.api_key, written by the plugin field). "
             "xAI key precedence: 1. the plugin field 'XAI API Token' (tab Voice; sent in the config event while VaM runs), "
             "2. xai.api_key, 3. XAI_API_KEY, 4. the PATH of a key file (key_file). "
             "ElevenLabs: ELEVENLABS_API_KEY or key_file (no menu field)",
    ("ai", "persona"): "Persona / system prompt for the language model (xAI: 'instructions')",
    ("ai", "language"): "'auto' or a language code (de, en, ...): STT bias and TTS language",
    ("ai", "fallback"): "Engines used when the selected one has no API key or a request fails",
    ("ai", "xai"): "xAI (https://api.x.ai/v1): Grok via POST /v1/responses (stream), "
                   "STT POST /v1/stt, TTS POST /v1/tts",
    ("ai", "xai", "key_hint"): "Note for the reader (JSON has no comments): an xAI API key is required; the plugin field "
                               "'XAI API Token', XAI_API_KEY or key_file. Not used by the app; any text is accepted",
    ("ai", "xai", "api_key"): "The xAI API token in PLAIN TEXT. The plugin writes the field 'XAI API Token' here and fills "
                              "the field from it on start; the app reads it too. Used after the live plugin field and "
                              "before XAI_API_KEY and key_file. Never log, share or publish this file with a token in it",
    ("ai", "xai", "api_key_warning"): "Note for the reader (JSON has no comments): security notice for api_key. "
                                      "Not used by the app; the plugin keeps it",
    ("ai", "xai", "key_file"): "Path of a file holding the xAI key (absolute, or relative to the home folder); "
                               "used after the plugin field 'XAI API Token', xai.api_key and XAI_API_KEY",
    ("ai", "elevenlabs"): "ElevenLabs TTS: POST /v1/text-to-speech/{voice_id}?output_format=pcm_*",
    ("ai", "elevenlabs", "key_file"): "Path of a file holding the ElevenLabs key; ELEVENLABS_API_KEY wins; no menu field",
}

NUM_STRING = {"type": "string", "pattern": r"^\s*-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?\s*$"}
BOOL_STRING = {"type": "string", "enum": ["true", "false", "True", "False"]}


def leaf(path: tuple[str, ...], default):
    if isinstance(default, bool):
        return {"anyOf": [{"type": "boolean"}, BOOL_STRING], "default": default}
    if isinstance(default, (int, float)):
        num: dict = {"type": "integer" if isinstance(default, int) else "number"}
        rng = RANGES.get(path) or (LIMITS.get(path[-1]) if path[0] == "mic" else None)
        if rng:
            num["minimum"], num["maximum"] = rng
        if path in CHOICES:
            num["enum"] = [int(c) for c in CHOICES[path]]
        return {"anyOf": [num, NUM_STRING], "default": default}
    node: dict = {"type": "string", "default": default}
    if path in CHOICES:
        node["enum"] = list(CHOICES[path])
    if path == ("mic", "mode"):
        node["enum"] = list(MODES)
    if path == ("mic", "vad_engine"):
        node["enum"] = list(VAD_ENGINES)
    if path[:2] == ("connection", "paths"):
        node["pattern"] = "^$|^(Saves|Custom)/" if path[-1] == "audio" else "^(Saves|Custom)/"
    return node


def obj(path: tuple[str, ...], defaults_: dict) -> dict:
    node: dict = {"type": "object", "additionalProperties": False, "properties": {}}
    if path in DESCRIPTIONS:
        node["description"] = DESCRIPTIONS[path]
    for key, value in defaults_.items():
        sub = (*path, key)
        child = obj(sub, value) if isinstance(value, dict) else leaf(sub, value)
        if sub in DESCRIPTIONS and "description" not in child:
            child["description"] = DESCRIPTIONS[sub]
        node["properties"][key] = child
    return node


def schema() -> dict:
    root = obj((), DEFAULTS)
    root = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/d0n/vam_plugin/protocol/schema/config.schema.json",
        "title": "AIBody shared settings: <VaM>/Saves/PluginData/AIBody/config.json (one object per plugin tab, "
                 "plus 'ai' for the companion app; the 'Status' tab has no settings)",
        "type": "object",
        "additionalProperties": False,
        "properties": {"version": {"anyOf": [{"const": 1}, {"const": "1"}]}, "written_by": {"type": "string"},
                       **root["properties"]},
    }
    return root


def example() -> dict:
    data = defaults()
    data["written_by"] = f"AIBody companion app {__version__} (example)"
    return data


def render(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    outputs = {SCHEMA_PATH: render(schema()), EXAMPLE_PATH: render(example())}
    if "--check" in sys.argv:
        stale = [p for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            print(f"out of date: {p.relative_to(ROOT)} (run python tools/gen_config_schema.py)")
        return 1 if stale else 0
    for p, text in outputs.items():
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
