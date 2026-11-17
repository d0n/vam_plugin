"""Message protocol between the companion app and the AIBody VaM plugin (version 3).

The authoritative description is protocol/PROTOCOL.md; JSON schemas live in
protocol/schema/. Keep this module, the schemas and src/AIBody/Protocol.cs in sync.

The VaM side is ONE plugin (AIBody.cslist) on the AI character's Person atom: its app link
talks to this companion app and hands body commands in-process to its body. There is no
routing and no target atom: one plugin = one character.
"""
from __future__ import annotations

import itertools
import time
import uuid
from typing import Any

from . import PROTOCOL_VERSION
from .vamjson import as_bool

# Messages companion -> plugin ("commands").
# command type -> (required fields, optional fields)
COMMANDS: dict[str, tuple[set[str], set[str]]] = {
    "ping": (set(), set()),
    # audio: WAV/OGG path relative to the VaM folder (Saves/PluginData/AIBody/<channel>/audio/...)
    "speak": ({"audio"}, {"text", "expression", "intensity", "queue", "duration"}),
    "stop_speaking": (set(), set()),
    "expression": ({"name"}, {"intensity", "blend", "hold"}),
    "set_morphs": ({"morphs"}, {"blend", "release_others"}),
    "reset_morphs": (set(), {"blend"}),
    "gesture": ({"name"}, {"duration", "amplitude"}),
    "pose": ({"path"}, set()),
    "trigger": ({"storable"}, {"action", "param", "value", "value_type"}),
    "idle": (set(), {"enabled", "intensity"}),
    "breathing": (set(), {"enabled", "rate", "depth"}),
    # replies / feedback for the plugin's microphone menu
    "config_ack": (set(), {"reply_to", "applied", "errors", "mic_state"}),
    "devices": ({"devices"}, {"error", "reply_to"}),
    "mic_state": ({"enabled", "capturing"}, {"device", "mode", "ptt_active", "error"}),
    "mic_level": ({"rms"}, {"speech", "gate_open"}),
    # liveness + identity of the companion app (lets the plugin detect restarts over files)
    # engines_status: kind -> engine -> "bereit" / "nicht konfiguriert: ..."; engines_active: kind -> engine
    # that really runs (the fallback when the selected one is not configured).
    "companion_heartbeat": ({"session"}, {"version", "engines_available", "engines_status", "engines_active",
                                          "mic_capturing"}),
}

# Commands for the plugin's body (everything else is handled by its app link).
BODY_COMMANDS = {
    "speak", "stop_speaking", "expression", "set_morphs", "reset_morphs",
    "gesture", "pose", "trigger", "idle", "breathing",
}

SPEAK_QUEUE_MODES = ("append", "interrupt")

ENVELOPE_FIELDS = {"v", "type", "id", "ts", "ack"}

# Messages plugin -> companion ("events").
EVENTS = {
    "config",
    "ptt",
    "list_devices",
    "ready",
    "heartbeat",
    "pong",
    "ack",
    "error",
    "speech_started",
    "speech_ended",
    "gesture_done",
    "shutdown",
}

_counter = itertools.count(1)


def new_id(prefix: str = "cmd") -> str:
    return f"{prefix}-{int(time.time() * 1000)}-{next(_counter)}-{uuid.uuid4().hex[:6]}"


def make_command(type_: str, id_: str | None = None, ack: bool = False, **fields: Any) -> dict[str, Any]:
    """Builds a command envelope and validates it. Raises ValueError on invalid input."""
    msg: dict[str, Any] = {"v": PROTOCOL_VERSION, "type": type_, "id": id_ or new_id(), "ts": time.time()}
    if ack:
        msg["ack"] = True
    msg.update({k: v for k, v in fields.items() if v is not None})
    errors = validate_command(msg)
    if errors:
        raise ValueError("; ".join(errors))
    return msg


def validate_command(msg: Any) -> list[str]:
    """Returns a list of problems (empty if the command is valid)."""
    if not isinstance(msg, dict):
        return ["command must be a JSON object"]
    errors: list[str] = []
    type_ = msg.get("type")
    if type_ not in COMMANDS:
        return [f"unknown command type {type_!r}"]
    if msg.get("v", PROTOCOL_VERSION) != PROTOCOL_VERSION:
        errors.append(f"unsupported protocol version {msg.get('v')!r}")
    required, optional = COMMANDS[type_]
    for field in sorted(required - msg.keys()):
        errors.append(f"{type_}: missing field {field!r}")
    unknown = msg.keys() - required - optional - ENVELOPE_FIELDS
    for field in sorted(unknown):
        errors.append(f"{type_}: unknown field {field!r}")
    if type_ == "set_morphs":
        morphs = msg.get("morphs")
        if not isinstance(morphs, dict) or not all(isinstance(v, (int, float)) for v in morphs.values()):
            errors.append("set_morphs: 'morphs' must map morph names to numbers")
    if type_ == "speak":
        if not (isinstance(msg.get("audio"), str) and msg["audio"]):
            errors.append("speak: 'audio' must be a non-empty path")
        if msg.get("queue", "append") not in SPEAK_QUEUE_MODES:
            errors.append(f"speak: queue must be one of {SPEAK_QUEUE_MODES}")
    if type_ == "devices" and not isinstance(msg.get("devices"), list):
        errors.append("devices: 'devices' must be a list")
    if type_ == "trigger" and not (msg.get("action") or msg.get("param")):
        errors.append("trigger: needs 'action' or 'param'")
    return errors


def is_event(msg: Any) -> bool:
    return isinstance(msg, dict) and msg.get("type") in EVENTS


def validate_event(msg: Any) -> list[str]:
    """Light validation of plugin events (unknown fields are allowed for forward compatibility)."""
    if not isinstance(msg, dict):
        return ["event must be a JSON object"]
    type_ = msg.get("type")
    if type_ not in EVENTS:
        return [f"unknown event type {type_!r}"]
    errors: list[str] = []
    if type_ == "config" and not isinstance(msg.get("mic"), dict):
        errors.append("config: 'mic' must be an object")
    if type_ == "ptt" and as_bool(msg.get("active")) is None:  # VaM writes "true"/"false"
        errors.append("ptt: 'active' must be true/false")
    return errors
