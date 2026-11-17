"""Reading JSON written by VaM.

VaM's SimpleJSON stores every number and boolean as a quoted string: a plugin that sets
`node["active"].AsBool = true` writes `"active":"true"`, `AsFloat = 0.5` writes `"0.5"`
(VaM scene files look the same, e.g. `"on" : "true"`, `"x" : "0.5"`; see docs/API_AUDIT.md E21).
Everything this app reads from the plugin (events in outbox/, config.json) therefore goes
through these helpers, which accept both the real JSON types and their string form.
"""
from __future__ import annotations

import math
from typing import Any


def as_bool(value: Any) -> bool | None:
    """True/False for a bool or "true"/"false" (any case), else None."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "true":
            return True
        if v == "false":
            return False
    return None


def as_number(value: Any) -> float | None:
    """The number for an int/float or a numeric string ("0.5", "1e-3"), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None
