"""Function tools for the AI's body: the same commands the plugin already runs, nothing new.

  express(expression, gesture?)  -> "expression" (+ "gesture") command; expressions from
                                    expressions.json / the built-ins, gestures from gestures.json
                                    (head nod / shake / tilt, Timeline animations, triggers)
  (no pose tool since version 32: a pose is applied only when the user's whole input equals a pose command,
   see pose_commands.py; the AI never sees or chooses poses)
  (no look_at tool since the change after version 36: the eyes belong to VaM; a model that still calls it gets an
   {"ok": false} answer)


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

TOOL_RULES = """To show a facial expression or a gesture, call the function "express"; never say expression
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
        expressions = offered_expressions(info.get("expressions") or default_expressions)
        return cls(expressions, gestures, poses)


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
    return out


def rules(lists: BodyLists) -> str:
    return TOOL_RULES


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
    if name == "look_at":  # no such tool after version 36 (the eyes belong to VaM)
        return [], {"ok": False, "error": "the eyes cannot be directed; they are left to VaM"}
    return [], {"ok": False, "error": f"unknown function {name!r}"}

