"""config.json: the input parameters shared by the AIBody plugin and this app.

Location: <vam_root>/Saves/PluginData/AIBody/config.json, ONE global file, in the per-plugin folder
below Saves/PluginData that established plugins use for their settings. Key reference (German):
README.md section 4. Categories (kept from the first schema; they no longer match the tabs 1:1):

  connection  channel (file only since version 15), active (tab Voice), paths {expressions, gestures,
              audio} (file only)
  engines     stt, llm, tts (tab Voice > AI Character)
  mic         microphone + push-to-talk settings (tab Client Character; audio/mic_settings.py)
  body        speech_volume, body_control, gaze_control, gaze_default, gaze_follows_speaker, idle_motion, idle_intensity, breathing,
              breaths_per_minute, breath_depth, breath_morph (tab AI Character)
  advanced    file_poll_interval_s (slider "Companion inbox poll interval (s)": how often the
              plugin reads the companion inbox, not config.json), verbose_log (tab Config)

plus one category this app owns (the plugin keeps it unchanged when it writes, except the keys
it has controls for):

  ai          mode, persona, persona_name, channels, memory {...}, emotion {...}, language, fallback {stt, llm, tts}, realtime {...}, proactive {...},
              xai {...}, elevenlabs {...}
              plugin controls: mode (tab Voice), persona_name and memory.enabled (tab Voice), proactive.enabled /
              idle_seconds (tab Voice), realtime.send_while_speaking (tab Client Character),
              realtime.voice + xai.voice (tab Voice), xai.key_file /
              elevenlabs.key_file (no menu field since version 15; the plugin keeps the path it read)

The plugin UI wins: the plugin writes its values back after every change. This app reads the
file on start (channel, initial mic and engine settings before the plugin connects) and creates
it with the defaults if it does not exist yet (or adds missing "ai" keys); live changes
still arrive as `config` events. Only `--channel` on the command line overrides the channel.
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
import re
from pathlib import Path
from typing import Any

from .audio.mic_settings import MicSettings, apply_mic_config
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
    "four ways: (1) in VaM, plugin tab Voice > Voice Mode, field 'XAI API Token' (below API Reconnect); the plugin "
    "saves it here as ai.xai.api_key; (2) write it into ai.xai.api_key yourself; (3) the environment variable "
    "XAI_API_KEY; (4) ai.xai.key_file = path of a text file that holds the key. If several are set, the plugin "
    "field (while VaM runs) wins, then ai.xai.api_key, then XAI_API_KEY, then key_file.")
# Same text as AppLink.XaiTokenWarning in the plugin (tests/test_token_storage.py compares them).
KEY_WARNING_TEXT = (
    "SECURITY NOTICE: Your xAI token is stored as plain text in config.json (ai.xai.api_key). "
    "Anyone who can read that file can read your token, so do not share or publish it. "
    "Scenes keep only the masked token, but a scene saved with AIBody version 21 to 23 still contains the full token: "
    "do not publish such a scene.")

DEFAULTS: dict[str, dict[str, Any]] = {
    "connection": {
        "channel": "default",
        "active": True,
        "paths": {
            "expressions": "Saves/PluginData/AIBody/expressions.json",
            "gestures": "Saves/PluginData/AIBody/gestures.json",
            # where the companion writes the speech WAVs; "" = automatic: Custom/Sounds/AIBody/<channel>,
            # once switched to Saves/PluginData/AIBody/<channel>/audio if VaM cannot load them there
            "audio": "",
        },
    },
    "engines": {"stt": "null", "llm": "echo", "tts": "tone"},
    "mic": MicSettings().to_dict(),
    "body": {
        "speech_volume": 1.0,
        "body_control": True,  # false = speech only, expressions / gestures / poses are ignored
        "idle_motion": True,
        "idle_intensity": 0.5,
        "breathing": True,
        "breaths_per_minute": 14.0,
        "breath_depth": 0.35,
        "breath_morph": "Breath1",
        # Gaze (tab AI Character > Gaze; the plugin keeps these, the app only reads gaze_control from the heartbeat)
        "gaze_control": True,  # false = AIBody never moves the eyes (no look_at tool for the AI)
        "gaze_default": "default",  # default | natural | client | camera | forward | atom:<name>; default = leave the eyes alone
        "gaze_follows_speaker": False,  # look at the client while someone talks
        "blink_control": False,  # true = AIBody blinks (VaM's auto blink is switched off meanwhile)
    },
    "advanced": {"file_poll_interval_s": 0.1, "verbose_log": False},
    # Companion app; the plugin's tabs set only mode, proactive.enabled / idle_seconds,
    # realtime.send_while_speaking / voice, xai.voice and the key file paths (xai / elevenlabs
    # key_file), and keep the rest of this section.
    "ai": {
        # qa = simple questions and answers: STT -> LLM -> TTS with xai instead of the offline test
        # engines (with an xAI key), speech only, no proactive nudges (the default);
        # auto = realtime when an xAI key is there (and TTS is not elevenlabs), else chain;
        # realtime = Grok Voice speech-to-speech; chain = STT -> LLM -> TTS (exactly the engines above)
        "mode": "qa",
        "persona": "You are a friendly, curious character living in a 3D scene. You talk with the user "
                   "face to face. Answer briefly and naturally, in the language the user speaks.",
        "language": "auto",  # "auto" or a language code such as "de" / "en" (STT bias, TTS language)
        # Persona folder below Saves/PluginData/AIBody/personas ("" = none: the persona text above). The plugin's
        # menu "Persona" sets it; a persona.json can replace persona text, language and voice (personas.py).
        "persona_name": "",
        # Several figures in one app (version 28): channel names separated by commas, e.g. "anna,marc". Each figure is
        # an AIBody plugin with that channel. "" = one figure on connection.channel. --channel a,b on the command line wins.
        "channels": "",
        # Memory (opt-in, menu switch "Memory"): facts the user told the AI, kept in personas/<name>/memory.json and
        # given to the AI as notes. Updated after session_idle_minutes of silence (at least min_exchanges questions),
        # on a persona change and when the app stops.
        "memory": {
            "enabled": False,
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
            "send_while_speaking": False,  # true = mic stays open while the body talks (headphones!)
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
    ("body", "speech_volume"): (0.0, 1.0),
    ("body", "idle_intensity"): (0.0, 1.0),
    ("body", "breaths_per_minute"): (4.0, 40.0),
    ("body", "breath_depth"): (0.0, 1.0),
    ("advanced", "file_poll_interval_s"): (0.02, 2.0),
    ("ai", "xai", "max_output_tokens"): (16, 8000),
    ("ai", "xai", "speed"): (0.7, 1.5),
    ("ai", "xai", "timeout_s"): (5.0, 600.0),
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
PLUGIN_CATEGORIES = ("connection", "engines", "mic", "body", "advanced")  # written by the plugin
COMPANION_CATEGORIES = ("ai",)  # read only by this app, preserved by the plugin


def settings_path(vam_root: str | Path) -> Path:
    return Path(vam_root) / PLUGIN_DATA_SUBDIR / FILE_NAME


def defaults(channel: str = "default") -> dict[str, Any]:
    data = json.loads(json.dumps(DEFAULTS))
    data["connection"]["channel"] = channel
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


def _merge(path: tuple[str, ...], default: dict[str, Any], data: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    result = json.loads(json.dumps(default))
    for key, value in data.items():
        sub = (*path, key)
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


def write_defaults_if_missing(path: Path, channel: str) -> bool:
    """Creates the file with the defaults (atomically) if it does not exist. True if written."""
    path = Path(path)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(defaults(channel), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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


def apply_to_config(cfg: Any, channel_from_cli: bool = False) -> list[str]:
    """Creates config.json if missing, then copies its channel (unless --channel was given), mic
    and engine settings into cfg. They override the app's own --config file: config.json holds
    the plugin's last values. Returns problems."""
    path = settings_path(cfg.vam_root)
    if write_defaults_if_missing(path, cfg.channel):
        log.info("Created %s with default settings", path)
    else:
        added = add_missing_companion_sections(path)
        if added:
            log.info("Added default settings to %s: %s", path, ", ".join(added))
    data, errors = load(path)
    if data is None:
        return errors
    # Same rule as the plugin's channel field: letters, digits, '-' and '_' only.
    channel = re.sub(r"[^A-Za-z0-9_-]", "_", data["connection"]["channel"])
    if not channel_from_cli and channel:
        cfg.channel = channel
    elif channel != cfg.channel:
        errors.append(f"connection.channel is {channel!r}, --channel {cfg.channel!r} wins")
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
    cfg.verbose_log = bool(data["advanced"]["verbose_log"])
    add_secret(str(data["ai"]["xai"].get("api_key") or ""))  # before anything can log it
    log.info("Settings from %s: engines %s, mic mode %s", path, data["engines"], data["mic"]["mode"])
    return errors
