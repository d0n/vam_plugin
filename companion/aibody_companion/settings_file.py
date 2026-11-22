"""config.json: the input parameters shared by the AIBody plugin and this app.

Location: <vam_root>/Saves/PluginData/AIBody/config.json, ONE global file, in the per-plugin folder
below Saves/PluginData that established plugins use for their settings. Key reference:
README.md section 4. Categories (kept from the first schema; they no longer match the tabs 1:1):

  connection  active (tab Voice), network_active (tab Config), network_port (file only), paths {expressions, gestures,
              audio} (file only)
  engines     stt, llm, tts (tab Voice > AI Character)
  mic         microphone + push-to-talk settings (tab Client Character; audio/mic_settings.py)
  body        speech_volume, full_volume_distance, body_control, idle_motion, idle_intensity, breathing,
              breaths_per_minute, breath_depth, breath_morph, idle_poses, idle_pose_min_s, idle_pose_max_s, idle_pose_default
              (tab AI Character)
  advanced    file_poll_interval_s (slider "Companion inbox poll interval (s)": how often the
              plugin reads the companion inbox, not config.json), verbose_log (tab Config)

  poses       commands: [{command, pose}, ...] (version 32, tab AI Character: 'Add Pose' / 'Delete Pose'; a list)
  characters  setup_answered, setup_wanted, ai_gender, user_gender (after version 37, tab AI Character >
              Characters): answers of the character configuration wizard, recorded as AI context

plus two categories this app owns (the plugin keeps them unchanged when it writes, except the "ai" keys
it has controls for):

  remote      enabled, http_port, osc_port, token (file only, version 31): local web page / HTTP API / OSC, off by
              default, 127.0.0.1 only (docs/REMOTE.md)
  setup       asked, background, background_color, choice, revision (version 36): the answers to the first-start
              questions (setup.py); the plugin only reads it (background answer -> its toggle "Set background color")

  ai          mode, persona, persona_name, memory {...}, emotion {...}, language, fallback {stt, llm, tts}, realtime {...}, proactive {...},
              xai {...}, elevenlabs {...}
              plugin controls: mode (tab Voice), language, persona_name and memory.enabled (tab Voice), proactive.enabled /
              idle_seconds (tab Voice), barge_in.enabled (tab Client Character),
              realtime.voice + xai.voice (tab Voice), xai.key_file /
              elevenlabs.key_file (no menu field since version 15; the plugin keeps the path it read)

The plugin UI wins: the plugin writes its values back after every change. This app reads the
file on start (initial mic and engine settings before the plugin connects) and creates
it with the defaults if it does not exist yet (or adds missing "ai" keys); live changes
still arrive as `config` events. The message folder is fixed (Saves/PluginData/AIBody/default).
The plugin's sliders cover exactly RANGES / mic LIMITS (tests/test_plugin_ranges.py), so a value
from the file is not clamped and written back changed.

The plugin writes with VaM's SimpleJSON, which stores numbers and booleans as strings
("0.5", "true"); validate() accepts both (vamjson.py).

API keys: the xAI token typed into the plugin field "XAI API Token" is stored here IN PLAIN TEXT as
ai.xai.api_key (version 24; Leon's explicit decision, see ai.xai.api_key_warning, which holds the same warning).
Anything else is a PATH of a key file (ai.xai.key_file, ai.elevenlabs.key_file) or the environment
variables XAI_API_KEY / ELEVENLABS_API_KEY. The key is never written to the log (logsetup.add_secret).
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any

from .audio.mic_settings import MicSettings, apply_mic_config
from . import pose_commands
from .config import ENGINES_AVAILABLE, PLUGIN_DATA_SUBDIR
from .pipeline.context import DEFAULT_NUDGE_PROMPT, DEFAULT_SCENE_EVENT_PROMPT
from .pipeline.realtime import PCM_RATES
from .logsetup import add_secret
from .vamjson import as_bool, as_number

log = logging.getLogger(__name__)

FILE_NAME = "config.json"
VERSION = 1

# category -> key -> (type, default); numbers carry (min, max) in RANGES
# Written into config.json as ai.xai.key_hint (JSON has no comments). Any text is accepted.
KEY_HINT_TEXT = (
    "An xAI API key from console.x.ai is required (a Grok subscription does not work). Provide it in one of "
    "four ways: (1) in VaM, plugin tab Voice > Companion connection, field 'XAI API Token' (below API Reconnect); the plugin "
    "saves it here as ai.xai.api_key; (2) write it into ai.xai.api_key yourself; (3) the environment variable "
    "XAI_API_KEY; (4) ai.xai.key_file = path of a text file that holds the key. If several are set, the plugin "
    "field (while VaM runs) wins, then ai.xai.api_key, then XAI_API_KEY, then key_file.")
# Same text as AppLink.XaiTokenWarning in the plugin, without its <b> markup (tests/test_token_storage.py compares them).
KEY_WARNING_TEXT = (
    "SECURITY NOTICE: the XAI API Token is stored as plain text in config.json (ai.xai.api_key), "
    "so anyone who can read that file can read your token and you should not share or publish it; since version 31 no scene holds the token any more, "
    "but a scene saved with AIBody version 21 to 23 still contains the full token, so do not publish such a scene.")

DEFAULTS: dict[str, dict[str, Any]] = {
    "connection": {
        "active": True,
        # Loopback socket to the plugin (version 30). network_active = the plugin toggle "Network Active" (mirrored);
        # network_port = UDP port on 127.0.0.1 where this app listens (0 = no listener, files only).
        "network_active": True,
        "network_port": 38437,
        "paths": {
            "expressions": "Saves/PluginData/AIBody/expressions.json",
            "gestures": "Saves/PluginData/AIBody/gestures.json",
            # where the companion writes the speech WAVs; "" = automatic: Custom/Sounds/AIBody/<channel>,
            # once switched to Saves/PluginData/AIBody/<channel>/audio if VaM cannot load them there
            "audio": "",
        },
    },
    # Version 50 (Leon, call 20:35): xai by default, the real engines (before: the offline test engines null / echo /
    # tone, so a fresh or reset config understood no speech). Without an xAI key the app uses ai.fallback below.
    "engines": {"stt": "xai", "llm": "xai", "tts": "xai"},
    "mic": MicSettings().to_dict(),
    "body": {
        "speech_volume": 1.0,
        # version 48 (Leon 12:58): the plugin sets its head audio minDistance to this when idle (EasyMoan pattern)
        "full_volume_distance": 3.0,
        "body_control": True,  # false = speech only, expressions / gestures / poses are ignored
        "idle_motion": True,
        "idle_intensity": 0.5,
        "breathing": True,
        "breaths_per_minute": 14.0,
        "breath_depth": 0.35,
        "breath_morph": "Breath1",
        # Idle poses (version 35): after idle_pose_min_s..idle_pose_max_s seconds without speech or a pose command the
        # character takes a random pose of all its poses (version 51; idle_pose_default is one of them, never twice in a row).
        "idle_poses": True,
        # version 51 (Leon 20:38-20:51): random pose of ALL poses, every idle_pose_min_s..idle_pose_max_s seconds
        "idle_pose_min_s": 30.0,
        "idle_pose_max_s": 300.0,
        "idle_pose_default": "Stand Up",  # a pose name of the character; not found = no return pose
    },
    "advanced": {"file_poll_interval_s": 0.1, "verbose_log": False},
    # Plugin UI state (version 30): the first-run note about the xAI token was closed or answered once.
    # Version 36: background_setup_applied = the setup.revision whose background answer the plugin has applied.
    "ui": {"first_run_hint_dismissed": False, "background_setup_applied": 0},
    # Pose commands (version 32; AI Character): the only way a pose is applied. A pose is applied only when the user's
    # WHOLE input equals a command text (case, spaces and trailing . ! ? ignored); the command links to a pose id
    # (a pose of the character: gestures.json pose or pose file, names compare ignoring case, spaces, _ and -).
    # Written by the plugin ('Add Pose' / 'Delete Pose'); a list. A missing "commands" key = the ten starter commands,
    # and (version 35) an empty or unusable list = the starters too. See docs/SPEC.md "Pose commands".
    "poses": {"commands": pose_commands.starter_entries()},
    # Character configuration wizard (after version 37, tab AI Character > Characters). Recorded
    # settings only: gender/body of the AI character and gender of the user's character, used as
    # prompt context. Empty gender = not chosen yet. Clothing is not stored (free choice in VaM).
    "characters": {
        "setup_answered": False,
        "setup_wanted": False,
        "ai_gender": "",
        "user_gender": "",
    },
    # Remote control (version 31; this app only, file only, off by default): a local web page / HTTP API and an
    # optional OSC listener. Both bind 127.0.0.1 only. The HTTP API needs the token (generated into this file on
    # the first start with enabled = true); OSC has no token. Changes apply when the app starts. See docs/REMOTE.md.
    # First start questions (version 36, this app only, asked once in the console; python -m aibody_companion --setup
    # asks again). Two independent points: background (+ its color) and what to use (scene / plugin).
    "setup": {
        "asked": False,
        "background": False,
        "background_color": "#00FF00",
        "choice": "",
        "revision": 0,
    },
    "remote": {
        "enabled": False,
        "http_port": 38438,
        "osc_port": 0,  # 0 = no OSC listener
        "token": "",  # secret for the HTTP API; empty = the app generates one when remote.enabled is true
    },
    # Companion app; the plugin's tabs set only mode, proactive.enabled / idle_seconds,
    # barge_in.enabled, realtime.voice, xai.voice and the key file paths (xai / elevenlabs
    # key_file), and keep the rest of this section.
    "ai": {
        # qa = simple questions and answers: STT -> LLM -> TTS with xai instead of the offline test
        # engines (with an xAI key), speech only, no proactive nudges (the default);
        # auto = realtime when an xAI key is there (and TTS is not elevenlabs), else chain;
        # realtime = Grok Voice speech-to-speech; chain = STT -> LLM -> TTS (exactly the engines above)
        "mode": "qa",
        "persona": "You are a friendly, curious character living in a 3D scene. You talk with the user "
                   "face to face. Answer briefly and naturally, in the language the user speaks.",
        # the menu "Language" (tab Voice, 22.11.2026 Leon): "auto" or a code of the xAI TTS list (languages.py);
        # default "de". Sent to text to speech with every sentence, to speech to text, and as "Always answer in ..." to
        # the language model / realtime session. Not "auto": it wins over a persona's language.
        "language": "de",
        # Persona folder below Saves/PluginData/AIBody/personas ("" = none: the persona text above). The plugin's
        # menu "Persona" sets it; a persona.json can replace persona text, language and voice (personas.py).
        # Version 50 (Leon 20:35): no "none" in the menu any more; default the female starter persona Anna (Marc = male).
        "persona_name": "Anna",
        # Memory (opt-in, menu switch "Memory"): facts the user told the AI, kept in personas/<name>/memory.json and
        # given to the AI as notes. Updated after session_idle_minutes of silence (at least min_exchanges questions),
        # on a persona change and when the app stops.
        "memory": {
            "enabled": True,  # on by default since version 50 (Leon 20:35)
            "max_facts": 30,
            "session_idle_minutes": 10,
            "min_exchanges": 2,
        },
        # Used when the selected engine is not configured (no API key) or a request fails.
        "fallback": {"stt": "null", "llm": "echo", "tts": "tone"},
        "realtime": {
            "url": "wss://api.x.ai/v1/realtime",
            "model": "grok-voice-latest",
            "voice": "eve",
            "sample_rate": 24000,  # answer audio (16-bit PCM, written as WAV for VaM)
            "speed": 1.0,
            "reasoning_effort": "none",  # "none" = faster answers, "high" = API default
            "first_segment_s": 1.2,  # first audio segment as soon as a sentence ends after this
            "max_segment_s": 6.0,  # longer stretches without a sentence end are cut
            "connect_timeout_s": 15.0,
        },
        "proactive": {
            "enabled": True,
            "idle_seconds": 90.0,  # silence (no user speech, no AI speech) before a nudge
            "prompt": DEFAULT_NUDGE_PROMPT,
        },
        # Scene events: a VaM trigger sets the plugin's "Scene event" text; the AI may react (or stay silent).
        # {event} in the prompt is replaced by the text. Not used in simple Q&A mode.
        "scene_events": {
            "enabled": True,
            "prompt": DEFAULT_SCENE_EVENT_PROMPT,
        },
        # Expressions without the AI's help (version 27; config.json only, no menu): fallback = derive an expression
        # from the spoken words when the AI chose none; fade = back to neutral fade_after_s seconds after the last
        # speech (blended over fade_seconds); listening = a very small expression while the user talks.
        "emotion": {
            "fallback": True,
            "fade": True,
            "fade_after_s": 6.0,
            "fade_seconds": 2.5,
            "listening": True,
        },
        # Voice barge-in (version 29 rule; since 22.11.2026 the menu toggle "Voice barge-in (headphones)", ON by default,
        # chain and realtime mode, Leon): while the body speaks the mic stays closed for the AI (echo protection, always on);
        # a stretch of min_ms that is `ratio` times louder than the learned echo of her own voice (and above `floor`,
        # RMS 0..1) counts as the user talking: the body stops, the running answer is cancelled and what the user said is
        # processed. With headphones there is no echo and a normal voice is enough; with speakers talk clearly louder.
        "barge_in": {
            "enabled": True,
            "ratio": 2.0,
            "min_ms": 600,
            "floor": 0.02,
        },
        "xai": {
            "base_url": "https://api.x.ai/v1",
            "key_hint": KEY_HINT_TEXT,  # a note for the reader of this file (JSON has no comments); ignored by the app
            "api_key": "",  # the xAI token in PLAIN TEXT (the plugin writes the field here); used after the plugin field, before XAI_API_KEY
            "api_key_warning": KEY_WARNING_TEXT,  # a note for the reader of this file (JSON has no comments); ignored by the app
            "key_file": "",  # path of a file holding the key; used after the plugin field, api_key and XAI_API_KEY
            "model": "grok-4.7",
            "max_output_tokens": 400,
            "stt_model": "grok-voice-transcribe-2.0",
            "voice": "eve",
            "speed": 1.0,
            "sample_rate": 24000,
            "timeout_s": 60.0,
        },
        # Local language model (version 29): choose "ollama" as Language model. No key. The model must be installed
        # (ollama pull <model>). Chain mode only (not realtime); no body tools, the answer carries the <<tag>>.
        "ollama": {
            "base_url": "http://127.0.0.1:11434",
            "model": "llama3.2",
            "max_output_tokens": 400,
            "temperature": 0.7,
            "keep_alive": "10m",  # how long Ollama keeps the model loaded after the last answer
            "max_messages": 40,  # conversation turns kept in memory (the app sends them again each time)
            "timeout_s": 120.0,
        },
        "elevenlabs": {
            "base_url": "https://api.elevenlabs.io/v1",
            "key_file": "",  # path of a file holding the key; ELEVENLABS_API_KEY (environment) wins
            "voice_id": "JBFqnCBsd6RMkjVDRZzb",
            "model_id": "eleven_multilingual_v2",
            "output_format": "pcm_24000",
            "timeout_s": 60.0,
        },
    },
}

RANGES: dict[tuple[str, str], tuple[float, float]] = {
    ("connection", "network_port"): (0, 65535),
    ("remote", "http_port"): (1024, 65535),
    ("remote", "osc_port"): (0, 65535),
    ("body", "speech_volume"): (0.0, 10.0),  # version 44 (0..3), 22.11.2026 0..10 (plugin 1000 %, Leon 04:16): above 1 the companion boosts its WAVs (pipeline/tts.py)
    ("body", "full_volume_distance"): (0.3, 10.0),  # version 48: the plugin's head audio minDistance (m)
    ("body", "idle_intensity"): (0.0, 1.0),
    ("body", "breaths_per_minute"): (4.0, 40.0),
    ("body", "breath_depth"): (0.0, 1.0),
    ("body", "idle_pose_min_s"): (30.0, 18000.0),   # version 51: 30 s to 300 min
    ("body", "idle_pose_max_s"): (30.0, 18000.0),
    ("advanced", "file_poll_interval_s"): (0.02, 2.0),
    ("ai", "xai", "max_output_tokens"): (16, 8000),
    ("ai", "xai", "speed"): (0.7, 1.5),
    ("ai", "xai", "timeout_s"): (5.0, 600.0),
    ("ai", "barge_in", "ratio"): (1.2, 10.0),
    ("ai", "barge_in", "min_ms"): (150, 3000),
    ("ai", "barge_in", "floor"): (0.002, 0.5),
    ("ai", "ollama", "max_output_tokens"): (16, 8000),
    ("ai", "ollama", "temperature"): (0.0, 2.0),
    ("ai", "ollama", "max_messages"): (2, 400),
    ("ai", "ollama", "timeout_s"): (5.0, 3600.0),
    ("ai", "elevenlabs", "timeout_s"): (5.0, 600.0),
    ("ai", "realtime", "speed"): (0.7, 1.5),
    ("ai", "realtime", "first_segment_s"): (0.3, 5.0),
    ("ai", "realtime", "max_segment_s"): (1.0, 20.0),
    ("ai", "realtime", "connect_timeout_s"): (3.0, 60.0),
    ("ai", "memory", "max_facts"): (1, 100),
    ("ai", "memory", "session_idle_minutes"): (1, 240),
    ("ai", "memory", "min_exchanges"): (1, 50),
    ("ai", "emotion", "fade_after_s"): (1.0, 120.0),
    ("ai", "emotion", "fade_seconds"): (0.2, 10.0),
    ("ai", "proactive", "idle_seconds"): (0.0, 3600.0),  # 0 = nudges off (proactive.py MIN_ACTIVE_S)
}

# Allowed values for some strings.
CHOICES: dict[tuple[str, ...], tuple[str, ...]] = {
    ("setup", "choice"): ("", "scene", "plugin"),
    ("characters", "ai_gender"): ("", "Female", "Male"),
    ("characters", "user_gender"): ("", "Female", "Male"),
    ("ai", "mode"): ("qa", "auto", "realtime", "chain"),
    ("ai", "realtime", "sample_rate"): tuple(str(r) for r in PCM_RATES),
    ("ai", "realtime", "reasoning_effort"): ("none", "high"),
    ("ai", "xai", "sample_rate"): ("8000", "16000", "22050", "24000", "44100", "48000"),
    ("ai", "elevenlabs", "output_format"): ("pcm_16000", "pcm_22050", "pcm_24000", "pcm_44100", "pcm_48000"),
    ("ai", "fallback", "stt"): tuple(ENGINES_AVAILABLE["stt"]),
    ("ai", "fallback", "llm"): tuple(ENGINES_AVAILABLE["llm"]),
    ("ai", "fallback", "tts"): tuple(ENGINES_AVAILABLE["tts"]),
}

CATEGORIES = tuple(DEFAULTS)
PLUGIN_CATEGORIES = ("connection", "engines", "mic", "body", "advanced", "ui", "poses", "characters")  # written by the plugin
COMPANION_CATEGORIES = ("ai", "remote", "setup")  # read only by this app, preserved by the plugin


def settings_path(vam_root: str | Path) -> Path:
    return Path(vam_root) / PLUGIN_DATA_SUBDIR / FILE_NAME


def defaults() -> dict[str, Any]:
    data = json.loads(json.dumps(DEFAULTS))
    return {"version": VERSION, "written_by": "AIBody companion app (defaults)", **data}


def _check_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    p = value.replace("\\", "/")
    return (p.startswith("Saves/") or p.startswith("Custom/")) and ".." not in p and ":" not in p


def looks_like_secret(value: str) -> bool:
    """True if a "key_file" value looks like a pasted API key instead of a file path."""
    v = value.strip()
    if not v:
        return False
    if v.startswith(("xai-", "sk_", "sk-")):
        return True
    return len(v) >= 24 and not any(c in v for c in "/\\.~") and " " not in v


def _check_value(path: tuple[str, ...], default: Any, value: Any, errors: list[str]) -> Any:
    """Returns the checked value, or the default (and adds an error)."""
    name = ".".join(path)
    if isinstance(default, bool):
        flag = as_bool(value)
        if flag is None:
            errors.append(f"{name}: must be true/false")
            return default
        return flag
    if isinstance(default, (int, float)):
        number = as_number(value)
        if number is None:
            errors.append(f"{name}: must be a number")
            return default
        if path in RANGES:
            lo, hi = RANGES[path]
            number = min(max(number, lo), hi)
        if path in CHOICES and str(int(number)) not in CHOICES[path]:
            errors.append(f"{name}: must be one of {', '.join(CHOICES[path])}")
            return default
        return int(round(number)) if isinstance(default, int) else float(number)
    # strings (VaM may write a number-looking string; Python callers may pass numbers)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(int(value)) if float(value).is_integer() else str(value)
    if not isinstance(value, str):
        errors.append(f"{name}: must be a string")
        return default
    if path in CHOICES and value not in CHOICES[path]:
        errors.append(f"{name}: must be one of {', '.join(CHOICES[path])}")
        return default
    if path[-1] == "key_file" and looks_like_secret(value):
        errors.append(f"{name}: looks like an API key, not a file path - ignored. Put the key into a file "
                      "and enter that file's path here, or use the environment variable.")
        return default
    return value


# Keys of versions that no longer exist; an old config.json that still has them keeps working.
LEGACY_KEYS = {("connection", "channel"), ("ai", "channels"),
               ("setup", "green_background"), ("setup", "example_scene"),  # version 35 answers (replaced in 36)
               # removed after version 36 (Leon, 20.11.2026): the eyes (gaze, blinking) belong to VaM
               ("body", "gaze_follows_speaker"), ("body", "gaze_control"), ("body", "gaze_default"),
               ("body", "blink_control"),
               # replaced on 22.11.2026 by ai.barge_in.enabled (the menu toggle; echo protection always on, Leon)
               ("ai", "realtime", "send_while_speaking")}


def _merge(path: tuple[str, ...], default: dict[str, Any], data: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    result = json.loads(json.dumps(default))
    for key, value in data.items():
        sub = (*path, key)
        if sub in LEGACY_KEYS:
            continue  # left behind by version 28 (several characters): ignored without a warning
        if key not in default:
            errors.append(f"{'.'.join(path)}: unknown key {key!r}")
        elif sub == ("connection", "paths"):
            if not isinstance(value, dict):
                errors.append("connection.paths: must be an object")
                continue
            for name, p in value.items():
                if name not in default[key]:
                    errors.append(f"connection.paths: unknown key {name!r}")
                elif name == "audio" and p == "":
                    result[key][name] = ""
                elif not _check_path(p):
                    errors.append(f"connection.paths.{name}: must be relative, below Saves/ or Custom/")
                else:
                    result[key][name] = p.replace("\\", "/")
        elif isinstance(default[key], dict):
            if isinstance(value, dict):
                result[key] = _merge(sub, default[key], value, errors)
            else:
                errors.append(f"{'.'.join(sub)}: must be an object")
        else:
            result[key] = _check_value(sub, default[key], value, errors)
    return result


def validate(data: Any) -> tuple[dict[str, Any], list[str]]:
    """Returns (settings with defaults filled in and bad values replaced, problems)."""
    result = defaults()
    errors: list[str] = []
    if not isinstance(data, dict):
        return result, ["config.json must contain a JSON object"]
    for key in data:
        if key not in CATEGORIES and key not in ("version", "written_by"):
            errors.append(f"unknown category {key!r}")
    for cat in CATEGORIES:
        section = data.get(cat)
        if section is None:
            continue
        if not isinstance(section, dict):
            errors.append(f"{cat}: must be an object")
            continue
        if cat == "mic":
            mic, mic_errors = apply_mic_config(MicSettings(), section)
            result["mic"] = mic.to_dict()
            errors += [f"mic: {e}" for e in mic_errors]
            continue
        if cat == "poses":
            if "commands" in section:
                commands, pose_errors = pose_commands.validate_entries(section["commands"])
                # version 35: an empty (or unusable) list = the starter commands, never an empty vocabulary
                result["poses"] = {"commands": commands or pose_commands.starter_entries()}
                errors += pose_errors
            for key in section:
                if key != "commands":
                    errors.append(f"poses: unknown key {key!r}")
            continue
        result[cat] = _merge((cat,), DEFAULTS[cat], section, errors)
    if "version" in data and as_number(data["version"]) != VERSION:
        errors.append(f"version {data['version']!r} is not {VERSION}; reading what is compatible")
    return result, errors


def load(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Reads and validates the file. Returns (settings or None if missing/unreadable, problems)."""
    path = Path(path)
    if not path.is_file():
        return None, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return None, [f"{path.name} is not readable JSON: {e}"]
    return validate(data)


def write_defaults_if_missing(path: Path) -> bool:
    """Creates the file with the defaults (atomically) if it does not exist. True if written."""
    path = Path(path)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(defaults(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return True


def _fill_missing(default: dict[str, Any], data: dict[str, Any], prefix: str, added: list[str]) -> None:
    for key, value in default.items():
        if key not in data:
            data[key] = json.loads(json.dumps(value))
            added.append(prefix + key)
        elif isinstance(value, dict) and isinstance(data[key], dict):
            _fill_missing(value, data[key], prefix + key + ".", added)


def add_missing_companion_sections(path: Path) -> list[str]:
    """Adds the companion-only settings (ai, and keys a newer version introduced inside it) with
    their defaults to an existing file that lacks them (e.g. written first by the plugin, which
    only writes ai.mode / ai.proactive / ...), so the settings are there to edit. Everything
    else is kept as it is. Returns the added keys."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    added: list[str] = []
    for cat in COMPANION_CATEGORIES:
        if not isinstance(data.get(cat), dict):
            data[cat] = json.loads(json.dumps(DEFAULTS[cat]))
            added.append(cat)
        else:
            _fill_missing(DEFAULTS[cat], data[cat], cat + ".", added)
    if not added:
        return []
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return added


MIN_REMOTE_TOKEN_CHARS = 16


def ensure_remote_token(path: Path, cfg_remote: dict[str, Any]) -> str:
    """The HTTP token of the remote control: remote.token from config.json, or a new random one that is written
    there (atomically, the rest of the file unchanged). Returns "" (and does not write) if the file is unreadable."""
    token = str(cfg_remote.get("token") or "").strip()
    if token:
        return token
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    section = data.get("remote")
    if not isinstance(section, dict):
        section = json.loads(json.dumps(DEFAULTS["remote"]))
        data["remote"] = section
    existing = section.get("token")
    if isinstance(existing, str) and existing.strip():  # written meanwhile (plugin or user)
        add_secret(existing.strip())
        cfg_remote["token"] = existing.strip()
        return existing.strip()
    token = secrets.token_urlsafe(24)
    section["token"] = token
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    add_secret(token)
    cfg_remote["token"] = token
    return token


def apply_to_config(cfg: Any) -> list[str]:
    """Creates config.json if missing, then copies its mic and engine settings into cfg. They override the app's own --config file: config.json holds
    the plugin's last values. Returns problems."""
    path = settings_path(cfg.vam_root)
    if write_defaults_if_missing(path):
        log.info("Created %s with default settings", path)
    else:
        added = add_missing_companion_sections(path)
        if added:
            log.info("Added default settings to %s: %s", path, ", ".join(added))
    data, errors = load(path)
    if data is None:
        return errors
    cfg.network_port = int(data["connection"]["network_port"])
    cfg.mic = dict(data["mic"])
    cfg.audio_folder = data["connection"]["paths"]["audio"].strip("/")
    for kind in ("stt", "llm", "tts"):
        name = data["engines"][kind]
        if name in ENGINES_AVAILABLE[kind]:
            setattr(cfg, kind, name)
        else:
            errors.append(f"engines.{kind} {name!r} is not available here (have: {ENGINES_AVAILABLE[kind]}); "
                          f"using {getattr(cfg, kind)!r}")
    cfg.ai = json.loads(json.dumps(data["ai"]))
    cfg.remote = dict(data["remote"])
    cfg.poses = json.loads(json.dumps(data["poses"]))
    cfg.characters = json.loads(json.dumps(data["characters"]))
    add_secret(str(cfg.remote.get("token") or ""))
    cfg.verbose_log = bool(data["advanced"]["verbose_log"])
    from .pipeline import tts  # version 44: Speech volume above 1 = louder WAVs from the first sentence on
    gain = tts.set_output_gain(data["body"]["speech_volume"])
    if gain != 1.0:
        log.info("Speech volume %s from %s: speech WAVs x%.2f (linear gain)", data["body"]["speech_volume"], path, gain)
    add_secret(str(data["ai"]["xai"].get("api_key") or ""))  # before anything can log it
    log.info("Settings from %s: engines %s, mic mode %s", path, data["engines"], data["mic"]["mode"])
    return errors
