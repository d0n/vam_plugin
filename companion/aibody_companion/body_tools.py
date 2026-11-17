"""Function tools for the AI's body: the same commands the plugin already runs, nothing new.

  express(expression, gesture?)  -> "expression" (+ "gesture") command; expressions from
                                    expressions.json / the built-ins, gestures from gestures.json
                                    (head nod / shake / tilt, Timeline animations, triggers)
  pose(name)                     -> "pose" command by name (gestures.json entries of kind pose and
                                    the preset files in Custom/Atom/Person/Pose, as the plugin lists
                                    them in "poses")

No look-at / gaze tool: the plugin has no gaze control (see the roadmap, Glance is recommended).

When tools are offered: not in the simple Q&A mode (speech only, fastest path; no tool round trip
in the chain) and not while the plugin's "Body control" is off. A call that arrives anyway (an
older realtime session, a model that ignores the list) gets a result {"ok": false, "error": ...}
so the model never waits for an answer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

TOOL_RULES = """To show a facial expression or a gesture, call the function "express"{pose}; never say expression
names, gestures, poses or tags aloud and never describe what you do with your body."""


@dataclass
class BodyLists:
    expressions: list[str]
    gestures: list[str]
    poses: list[str] = field(default_factory=list)

    @classmethod
    def from_body_info(cls, info: dict[str, Any], default_expressions: list[str],
                       default_gestures: list[str]) -> BodyLists:
        poses = [str(p) for p in info.get("poses") or [] if str(p)]
        gestures = [str(g) for g in info.get("gestures") or default_gestures if str(g) and str(g) not in poses]
        return cls(list(info.get("expressions") or default_expressions), gestures, poses)


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
    if lists.poses:
        out.append({
            "type": "function",
            "name": "pose",
            "description": "Silently changes the posture of your 3D body to one of the saved poses, e.g. when "
                           "the user asks you to sit, stand or strike a pose. It is never spoken.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string", "enum": list(lists.poses)}},
                           "required": ["name"]},
        })
    return out


def rules(lists: BodyLists) -> str:
    return TOOL_RULES.format(pose=' or "pose" to change your posture' if lists.poses else "")


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
    if name == "pose":
        pose = _pick(args.get("name"), lists.poses)
        if not pose:
            return [], {"ok": False, "error": f"unknown pose; available: {', '.join(lists.poses) or 'none'}"}
        return [("pose", {"name": pose})], {"ok": True, "pose": pose}
    return [], {"ok": False, "error": f"unknown function {name!r}"}
