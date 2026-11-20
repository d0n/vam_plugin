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

from . import PROTOCOL_VERSION, pose_commands
from .logsetup import add_secret
from .vamjson import as_bool

# Messages companion -> plugin ("commands").
# command type -> (required fields, optional fields)
COMMANDS: dict[str, tuple[set[str], set[str]]] = {
    "ping": (set(), set()),
    # audio: WAV/OGG path relative to the VaM folder (default Custom/Sounds/AIBody/<channel>/...)
    "speak": ({"audio"}, {"text", "expression", "intensity", "queue", "duration"}),
    "stop_speaking": (set(), set()),
    "expression": ({"name"}, {"intensity", "blend", "hold"}),
    "set_morphs": ({"morphs"}, {"blend", "release_others"}),
    "reset_morphs": (set(), {"blend"}),
    "gesture": ({"name"}, {"duration", "amplitude"}),
    # version 32: ONLY {"json": "{\"pose\":\"<id>\"}"} (the plugin parses it and checks it against its pose vocabulary);
    # command = the matched command text (informational). The old fields path / name are no longer accepted.
    "pose": ({"json"}, {"command"}),
    "trigger": ({"storable"}, {"action", "param", "value", "value_type"}),
    "idle": (set(), {"enabled", "intensity"}),
    "breathing": (set(), {"enabled", "rate", "depth"}),
    # replies / feedback for the plugin's microphone menu
    "config_ack": (set(), {"reply_to", "applied", "errors", "mic_state"}),
    "mic_state": ({"enabled", "capturing"}, {"mode", "ptt_active", "error", "vad", "vad_note"}),
    "mic_level": ({"rms"}, {"speech", "gate_open"}),
    # liveness + identity of the companion app (lets the plugin detect restarts over files)
    # engines_status: kind -> engine -> "ready" / "not configured: ..."; engines_active: kind -> engine
    # that really runs (the fallback when the selected one is not configured).
    # mode: {requested: qa|auto|realtime|chain, active: realtime|chain, status: text};
    # proactive: {enabled, idle_seconds, status?}; audio_out: {folder, auto, note?} (speech WAV folder);
    # turn: last question / answer step or problem as text (status box)
    "companion_heartbeat": ({"session"}, {"version", "engines_available", "engines_status", "engines_active",
                                          "mic_capturing", "mode", "proactive", "keys", "audio_out", "turn",
                                          "latency", "personas", "persona", "persona_note", "memory"}),
}

# Commands for the plugin's body (everything else is handled by its app link).
BODY_COMMANDS = {
    "speak", "stop_speaking", "expression", "set_morphs", "reset_morphs",
    "gesture", "pose", "trigger", "idle", "breathing",
}
# "look_at" was removed after version 36 (the eyes belong to VaM): this app never sends it; the plugin still accepts and
# ignores it from an older app.

SPEAK_QUEUE_MODES = ("append", "interrupt")

ENVELOPE_FIELDS = {"v", "type", "id", "ts", "ack"}

# Events of older plugins (before the version without microphone selection): dropped silently.
RETIRED_EVENTS = {"list_devices"}

# Messages plugin -> companion ("events").
EVENTS = {
    "config",
    "ptt",
    "test_tone",
    "reconnect",
    "ready",
    "heartbeat",
    "pong",
    "ack",
    "error",
    "speech_started",
    "speech_ended",
    "gesture_done",
    "scene_event",
    "memory_forget",
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
    if type_ == "pose":
        pose, problem = pose_commands.parse_pose_json(msg.get("json"))
        if pose is None:
            errors.append(f"pose: {problem}")
    if type_ == "trigger" and not (msg.get("action") or msg.get("param")):
        errors.append("trigger: needs 'action' or 'param'")
    return errors


def register_event_secrets(msg: Any) -> None:
    """Registers tokens carried by a plugin event (config.keys) with the log redaction, before anything logs it."""
    keys = msg.get("keys") if isinstance(msg, dict) else None
    if isinstance(keys, dict):
        for value in keys.values():
            if isinstance(value, str):
                add_secret(value.strip())


def loggable(msg: Any) -> Any:
    """A copy of an event that is safe to log: the values of config.keys are masked."""
    if isinstance(msg, dict) and isinstance(msg.get("keys"), dict):
        return {**msg, "keys": {k: ("***" if v else "") for k, v in msg["keys"].items()}}
    return msg


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
    if type_ == "scene_event" and not (isinstance(msg.get("text"), str) and msg["text"].strip()):
        errors.append("scene_event: 'text' must be a non-empty string")
    if type_ == "ptt" and as_bool(msg.get("active")) is None:  # VaM writes "true"/"false"
        errors.append("ptt: 'active' must be true/false")
    return errors
