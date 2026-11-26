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
    ("poses",): "Tab 'AI Character', section 'Pose commands' (version 32): the ONLY way a pose is applied. A pose is applied "
                "when the user's input contains a command text as whole words (version 58: also inside a sentence, case and "
                "punctuation ignored, not after a negation such as don't / never; the longest command wins). Written by the plugin ('Add Pose' / 'Delete Pose')",
    ("poses", "commands"): "List of {command, pose}: command = the text the user says or types (the eleven built-in commands by default); "
                           "pose = id of a pose of the character (gestures.json pose or pose file; names compare ignoring case, "
                           "spaces, '_' and '-'). Version 59: every command runs; when its pose is missing or its file is broken, "
                           "a random pose of the idle pool is loaded instead (failed files and the current pose skipped), else "
                           "idle_pose_default. v32-v58 starter commands still linked to their own pose are replaced by the "
                           "version 59 built-in commands. Missing key, empty list or a list without one usable entry = the built-in commands "
                           "(version 35)",
    ("setup",): "First-start questions of the companion app (version 36, file only, no tab; the plugin only reads it). "
                "Asked once in the app's console; 'python -m aibody_companion --setup' asks again. Two independent points: "
                "the background (yes / no / abort, and its color) and what to use (Scene / Plugin)",
    ("setup", "asked"): "true = the questions were answered (they are not asked again on start; Abort leaves it false)",
    ("setup", "background"): "Answer to 'Do you want a greenscreen background?': true = the plugin switches its toggle "
                             "'Set background color' (tab Config) on with background_color, once per revision",
    ("setup", "background_color"): "Answer to 'Set your color for transparency' as #RRGGBB (default #00FF00, green)",
    ("setup", "choice"): "Answer to 'Choose what to use': scene = the app wrote Saves/scene/AIBody/AI-Buddy.json; "
                         "plugin = nothing written; empty = not answered yet",
    ("setup", "revision"): "Grows by one with every answered setup; the plugin applies a background answer once per revision",
    ("characters",): "Tab 'AI Character', section 'Characters' (after version 37): answers of the character "
                     "configuration wizard. Recorded as AI prompt context only; the plugin does not change a "
                     "Person's gender, body or clothing (no evidenced API). Clothing is not stored.",
    ("characters", "setup_answered"): "true = the gate 'Do you want to configure your characters?' was answered "
                                      "(Yes or No). false = the question is shown again",
    ("characters", "setup_wanted"): "true = the user chose Yes (the gender steps are shown). false after answering = "
                                    "skipped, until 'Configure characters' is pressed",
    ("characters", "ai_gender"): "Menu 'AI gender/body': Female, Male, or empty if not chosen yet",
    ("characters", "user_gender"): "Menu 'Your character gender': Female, Male, or empty if not chosen yet",
    ("ui", "background_setup_applied"): "The setup.revision whose background answer the plugin has applied (version 36; "
                                        "written by the plugin)",
    ("body", "idle_poses"): "Toggle 'Idle poses' (version 35): when nothing happens for a while the character takes an "
                            "available pose of the pose commands by itself and next time goes back to idle_pose_default",
    ("body", "idle_pose_pool"): "Menu 'Idle pose pool' (version 66, default aibody; replaces the version 54 toggle "
                                "idle_poses_all_files): aibody = 'AIBody poses only': the pose files in "
                                "Custom/Atom/Person/Pose/AIBody plus the gestures.json poses, the pose-command poses and "
                                "idle_pose_default; all = 'All pose files': every pose file of the library plus those. An old "
                                "idle_poses_all_files is migrated (true = all, false = aibody); this key wins when both exist",
    ("body", "idle_pose_interval_s"): "Slider 'Idle pose interval (s)' (version 59): quiet time before an idle pose change; "
                                      "each wait is this value +/- 25 % at random (30-18000, default 165). Old "
                                      "idle_pose_min_s / idle_pose_max_s are migrated to their mean",
    ("body", "pose_root_reset"): "Toggle 'Center body on control point' (version 63, default on): when a pose is applied "
                                 "the pose is kept, but the hips are put back over the AI character's control point "
                                 "(flat distance only, the height stays); not for Dollmaster montages",
    ("body", "idle_pose_default"): "Menu 'Idle default pose': the pose the character returns to between idle poses "
                                   "(a pose name of the character; not found = no return pose)",
    ("remote",): "Remote control (version 31, file only, no tab; the plugin keeps this section unchanged): a local web page / "
                 "HTTP API and an optional OSC listener of the companion app, off by default, bound to 127.0.0.1 only. "
                 "Applies when the app starts. See docs/REMOTE.md",
    ("remote", "enabled"): "true = the app opens the remote control (web page and HTTP API on http_port, OSC on osc_port if above 0). "
                           "Default false",
    ("remote", "http_port"): "TCP port of the web page and HTTP API on 127.0.0.1 (1024-65535, default 38438)",
    ("remote", "osc_port"): "UDP port of the OSC listener on 127.0.0.1; 0 = no OSC listener (default). OSC has no token",
    ("remote", "token"): "Secret the HTTP API requires (Authorization: Bearer <token>). Empty = the app generates one into this "
                         "file when remote.enabled is true. Never share this file with a token in it",
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
    if isinstance(default, list):  # poses.commands: a list of {command, pose}
        return {"type": "array", "maxItems": 100, "items": {
            "type": "object", "additionalProperties": False, "required": ["command", "pose"],
            "properties": {"command": {"type": "string", "minLength": 1, "maxLength": 60},
                           "pose": {"type": "string", "minLength": 1, "maxLength": 200}}},
            "default": default}
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
