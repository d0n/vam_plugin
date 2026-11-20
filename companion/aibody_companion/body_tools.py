"""Function tools for the AI's body: the same commands the plugin already runs, nothing new.

  express(expression, gesture?)  -> "expression" (+ "gesture") command; expressions from
                                    expressions.json / the built-ins, gestures from gestures.json
                                    (head nod / shake / tilt, Timeline animations, triggers)
  (no pose tool since version 32: a pose is applied only when the user's whole input equals a pose command,
   see pose_commands.py; the AI never sees or chooses poses)

  look_at(target, seconds?)      -> "look_at" command: where the eyes look (client, camera, forward, away, off,
                                    or the name of an atom in the scene). Only offered while the plugin says
                                    "gaze_control" (menu switch on, no Glance on the Person, eyes not taken
                                    by another plugin), so the AI never fights another eye plugin.

When tools are offered: not in the simple Q&A mode (speech only, fastest path; no tool round trip
in the chain) and not while the plugin's "Body control" is off. A call that arrives anyway (an
older realtime session, a model that ignores the list) gets a result {"ok": false, "error": ...}
so the model never waits for an answer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .emotion import offered as offered_expressions
from .protocol import LOOK_MAX_SECONDS
from .vamjson import as_bool

TOOL_RULES = """To show a facial expression or a gesture, call the function "express"{gaze}; never say expression
names, gestures, poses, gaze targets or tags aloud and never describe what you do with your body."""

GAZE_RULE = (' and "look_at" to direct your eyes (look at the user when you talk to them, glance away briefly '
             "while you think)")

# Words a model may use instead of the exact target names.
LOOK_ALIASES = {
    "user": "client", "player": "camera", "viewer": "camera", "screen": "camera", "me": "client", "you": "client",
    "ahead": "forward", "straight": "forward", "front": "forward", "side": "away", "aside": "away",
    "down": "away", "none": "off", "default": "off", "stop": "off", "release": "off", "reset": "off",
}
LOOK_TARGETS = ("client", "camera", "forward", "away", "off")


@dataclass
class BodyLists:
    expressions: list[str]
    gestures: list[str]
    poses: list[str] = field(default_factory=list)
    gaze: bool = False  # the plugin lets the AI direct the eyes
    gaze_atoms: list[str] = field(default_factory=list)  # atoms in the scene the AI can look at

    @classmethod
    def from_body_info(cls, info: dict[str, Any], default_expressions: list[str],
                       default_gestures: list[str]) -> BodyLists:
        poses = [str(p) for p in info.get("poses") or [] if str(p)]
        gestures = [str(g) for g in info.get("gestures") or default_gestures if str(g) and str(g) not in poses]
        atoms = info.get("gaze_atoms") or []
        atoms = [str(a) for a in atoms if str(a)] if isinstance(atoms, list) else []
        gaze = as_bool(info.get("gaze_control")) is True  # an older plugin has no gaze control
        expressions = offered_expressions(info.get("expressions") or default_expressions)
        return cls(expressions, gestures, poses, gaze, atoms)


def tools(lists: BodyLists) -> list[dict[str, Any]]:
    props: dict[str, Any] = {"expression": {"type": "string", "enum": list(lists.expressions) or ["neutral"]}}
    if lists.gestures:
        props["gesture"] = {"type": "string", "enum": list(lists.gestures)}
    out = [{
        "type": "function",
        "name": "express",
        "description": "Silently shows a facial expression and optionally a gesture on your 3D body. "
                       "Call it at the start of an answer when your mood changes. It is never spoken.",
        "parameters": {"type": "object", "properties": props, "required": ["expression"]},
    }]
    if lists.gaze:
        out.append({
            "type": "function",
            "name": "look_at",
            "description": "Silently directs your eyes. target: 'client' = the user's character in the scene (the "
                           "camera if there is none), 'camera' = the real person looking at the screen or in VR, "
                           "'forward' = straight ahead, 'away' = a short glance to the side (for example while "
                           "thinking), 'off' = stop directing your eyes. Any other value must be the name of an "
                           "atom in the scene. seconds (optional, 0-60): how long to keep looking, then your eyes "
                           "go back to their default; without it they stay until you change them. It is never spoken.",
            "parameters": {"type": "object", "properties": {
                "target": {"type": "string", "enum": [*LOOK_TARGETS, *lists.gaze_atoms]},
                "seconds": {"type": "number", "minimum": 0, "maximum": 60}}, "required": ["target"]},
        })
    return out


def rules(lists: BodyLists) -> str:
    return TOOL_RULES.format(gaze=GAZE_RULE if lists.gaze else "")


def _pick(value: Any, names: list[str]) -> str | None:
    text = str(value or "").strip().lower()
    return next((n for n in names if n.lower() == text), None) if text else None


def parse_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    try:
        args = json.loads(arguments or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return args if isinstance(args, dict) else {}


def resolve(name: str, arguments: Any, lists: BodyLists, allowed: bool,
            why_not: str = "") -> tuple[list[tuple[str, dict[str, Any]]], dict[str, Any]]:
    """A function call -> ([(command type, fields)], result for the model)."""
    if not allowed:
        return [], {"ok": False, "error": why_not or "body control is off"}
    args = parse_arguments(arguments)
    if name == "express":
        expression = _pick(args.get("expression"), lists.expressions)
        gesture = _pick(args.get("gesture"), lists.gestures)
        commands: list[tuple[str, dict[str, Any]]] = []
        if expression:
            commands.append(("expression", {"name": expression, "intensity": 1.0, "blend": 0.4}))
        if gesture:
            commands.append(("gesture", {"name": gesture}))
        if not commands:
            return [], {"ok": False, "error": "unknown expression / gesture"}
        return commands, {"ok": True, "expression": expression, "gesture": gesture}
    if name == "pose":  # no such tool since version 32 (a model that still calls it gets this answer)
        return [], {"ok": False, "error": "poses cannot be chosen by the AI; they change only when the user says an exact pose command"}
    if name == "look_at":
        return _look_at(args, lists)
    return [], {"ok": False, "error": f"unknown function {name!r}"}


def _look_at(args: dict[str, Any], lists: BodyLists) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, Any]]:
    if not lists.gaze:
        return [], {"ok": False, "error": "gaze control is off or taken by another plugin; the eyes cannot be directed"}
    raw = str(args.get("target") or "").strip()
    key = raw.lower()
    key = LOOK_ALIASES.get(key, key)
    fields: dict[str, Any]
    if key in LOOK_TARGETS:
        fields = {"target": key}
        shown = key
    else:
        atom = _pick(raw, lists.gaze_atoms)
        if not atom:
            options = ", ".join([*LOOK_TARGETS, *lists.gaze_atoms])
            return [], {"ok": False, "error": f"unknown target {raw!r}; available: {options}"}
        fields = {"target": "atom", "atom": atom}
        shown = atom
    seconds = args.get("seconds")
    if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and seconds > 0:
        fields["seconds"] = min(float(seconds), LOOK_MAX_SECONDS)
    return [("look_at", fields)], {"ok": True, "target": shown}
