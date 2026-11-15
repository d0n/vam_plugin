"""config.json: the input parameters shared by the AIBody plugin and this app.

Location: <vam_root>/Saves/PluginData/AIBody/config.json, ONE global file (see docs/CONFIG.md),
in the per-plugin folder below Saves/PluginData that established plugins use for their settings.
One object per category, the same categories as the plugin's tabs:

  connection  channel, active, paths {expressions, gestures}
  engines     stt, llm, tts
  mic         microphone + push-to-talk settings (audio/mic_settings.py)
  body        speech_volume, idle_motion, idle_intensity, breathing, breaths_per_minute,
              breath_depth, breath_morph
  advanced    file_poll_interval_s, verbose_log

The plugin UI wins: the plugin writes its values back after every change. This app reads the
file on start (channel, initial mic and engine settings before the plugin connects) and creates
it with the defaults if it does not exist yet; live changes still arrive as `config` events.
Only `--channel` on the command line overrides the channel from this file.
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

log = logging.getLogger(__name__)

FILE_NAME = "config.json"
VERSION = 1

# category -> key -> (type, default); numbers carry (min, max) in RANGES
DEFAULTS: dict[str, dict[str, Any]] = {
    "connection": {
        "channel": "default",
        "active": True,
        "paths": {
            "expressions": "Saves/PluginData/AIBody/expressions.json",
            "gestures": "Saves/PluginData/AIBody/gestures.json",
        },
    },
    "engines": {"stt": "null", "llm": "echo", "tts": "tone"},
    "mic": MicSettings().to_dict(),
    "body": {
        "speech_volume": 1.0,
        "idle_motion": True,
        "idle_intensity": 0.5,
        "breathing": True,
        "breaths_per_minute": 14.0,
        "breath_depth": 0.35,
        "breath_morph": "Breath1",
    },
    "advanced": {"file_poll_interval_s": 0.1, "verbose_log": False},
}

RANGES: dict[tuple[str, str], tuple[float, float]] = {
    ("body", "speech_volume"): (0.0, 1.0),
    ("body", "idle_intensity"): (0.0, 1.0),
    ("body", "breaths_per_minute"): (4.0, 40.0),
    ("body", "breath_depth"): (0.0, 1.0),
    ("advanced", "file_poll_interval_s"): (0.02, 2.0),
}

CATEGORIES = tuple(DEFAULTS)


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


def validate(data: Any) -> tuple[dict[str, Any], list[str]]:
    """Returns (settings with defaults filled in and bad values replaced, problems)."""
    result = defaults()
    errors: list[str] = []
    if not isinstance(data, dict):
        return result, ["settings.json must contain a JSON object"]
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
        for key, value in section.items():
            if key not in DEFAULTS[cat]:
                errors.append(f"{cat}: unknown key {key!r}")
                continue
            default = DEFAULTS[cat][key]
            if key == "paths":
                if not isinstance(value, dict):
                    errors.append("connection.paths: must be an object")
                    continue
                for name, path in value.items():
                    if name not in default:
                        errors.append(f"connection.paths: unknown key {name!r}")
                    elif not _check_path(path):
                        errors.append(f"connection.paths.{name}: must be relative, below Saves/ or Custom/")
                    else:
                        result["connection"]["paths"][name] = path.replace("\\", "/")
            elif isinstance(default, bool):
                if isinstance(value, bool):
                    result[cat][key] = value
                else:
                    errors.append(f"{cat}.{key}: must be true/false")
            elif isinstance(default, float):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(f"{cat}.{key}: must be a number")
                else:
                    lo, hi = RANGES[(cat, key)]
                    result[cat][key] = float(min(max(value, lo), hi))
            elif isinstance(value, str):
                result[cat][key] = value
            else:
                errors.append(f"{cat}.{key}: must be a string")
    if "version" in data and data["version"] != VERSION:
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
    tmp.write_text(json.dumps(defaults(channel), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return True


def apply_to_config(cfg: Any, channel_from_cli: bool = False) -> list[str]:
    """Creates config.json if missing, then copies its channel (unless --channel was given), mic
    and engine settings into cfg. They override the app's own --config file: config.json holds
    the plugin's last values. Returns problems."""
    path = settings_path(cfg.vam_root)
    if write_defaults_if_missing(path, cfg.channel):
        log.info("Created %s with default settings", path)
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
    for kind in ("stt", "llm", "tts"):
        name = data["engines"][kind]
        if name in ENGINES_AVAILABLE[kind]:
            setattr(cfg, kind, name)
        else:
            errors.append(f"engines.{kind} {name!r} is not available here (have: {ENGINES_AVAILABLE[kind]}); "
                          f"using {getattr(cfg, kind)!r}")
    log.info("Settings from %s: engines %s, mic mode %s", path, data["engines"], data["mic"]["mode"])
    return errors
