"""Character setup answers from the plugin wizard (after version 37, Leon).

Recorded settings only: the AI character's gender/body and the user's character gender,
used as persona / prompt context. The wizard does not change a Person in VaM (no evidenced
API for switching gender or opening the Clothing tab). Clothing is not stored here.
"""
from __future__ import annotations

from typing import Any

GENDERS = ("", "Female", "Male")
DEFAULTS: dict[str, Any] = {
    "setup_answered": False,
    "setup_wanted": False,
    "ai_gender": "",
    "user_gender": "",
}


def normalize_gender(value: Any) -> str:
    """Female / Male, or empty if missing or not one of those two."""
    if value is None:
        return ""
    text = str(value).strip()
    return text if text in ("Female", "Male") else ""


def normalize(data: Any) -> dict[str, Any]:
    """A complete characters object; unknown or bad values become the defaults."""
    result = dict(DEFAULTS)
    if not isinstance(data, dict):
        return result
    if data.get("setup_answered") is True or str(data.get("setup_answered", "")).lower() == "true":
        result["setup_answered"] = True
    if data.get("setup_wanted") is True or str(data.get("setup_wanted", "")).lower() == "true":
        result["setup_wanted"] = True
    result["ai_gender"] = normalize_gender(data.get("ai_gender"))
    result["user_gender"] = normalize_gender(data.get("user_gender"))
    return result


def context_text(ai_gender: str = "", user_gender: str = "") -> str:
    """A short paragraph for the AI instructions, or empty if nothing is set."""
    ai = normalize_gender(ai_gender)
    user = normalize_gender(user_gender)
    parts: list[str] = []
    if ai:
        parts.append(f"The AI character's body is {ai.lower()}.")
    if user:
        parts.append(f"The user's character is {user.lower()}.")
    return " ".join(parts)
