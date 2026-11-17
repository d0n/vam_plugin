"""API keys: from an environment variable, else from a key FILE whose path is in config.json.

The key itself never goes into config.json, the repository or the log. Missing key = the
engine reports "nicht konfiguriert" and the app uses the fallback engine; nothing else stops.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from ..logsetup import add_secret


def resolve_key(env_name: str, key_file: str, env: Mapping[str, str] | None = None) -> tuple[str | None, str]:
    """Returns (key or None, where it came from / why it is missing - never the key)."""
    env = os.environ if env is None else env
    value = (env.get(env_name) or "").strip()
    if value:
        add_secret(value)
        return value, f"Umgebungsvariable {env_name}"
    if key_file:
        path = Path(key_file).expanduser()
        if not path.is_absolute():
            path = Path.home() / path
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None, f"{env_name} nicht gesetzt, Key-Datei {path} nicht lesbar"
        if text:
            key = text.splitlines()[0].strip()
            add_secret(key)
            return key, f"Key-Datei {path}"
        return None, f"{env_name} nicht gesetzt, Key-Datei {path} ist leer"
    return None, f"{env_name} nicht gesetzt und kein key_file in config.json"
