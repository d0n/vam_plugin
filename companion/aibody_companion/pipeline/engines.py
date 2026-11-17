"""Engine registry: builds the STT / LLM / TTS engines selected in config.json (engines {stt,
llm, tts}, changeable live from the plugin's Engines tab) with their settings from the "ai"
section, and falls back when an engine cannot run.

  stt   null (offline, recognizes nothing) | xai
  llm   echo (offline test model)         | xai (Grok, Responses API, streaming)
  tts   tone (offline test tone)          | xai | elevenlabs

A cloud engine without an API key is "nicht konfiguriert": it stays selectable (so the plugin
can keep the choice until the key arrives), but the configured fallback (ai.fallback, default
null / echo / tone) runs instead, and the status says so. Keys come from the environment
(XAI_API_KEY, ELEVENLABS_API_KEY) or from a key file named in config.json; refresh() re-reads
key files, so a key file added later is picked up without restarting.

set_override() runs other engines than the selected ones without touching the selection: with an
xAI key the simple Q&A mode (and typed text / the realtime fallback) uses xai instead of the
offline test engines, while the plugin's menus keep showing what the user chose.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from ..config import ENGINES_AVAILABLE
from . import elevenlabs, xai
from .http import HttpClient, is_key_rejection
from .keys import resolve_key
from .llm import EchoLlm
from .stt import NullStt
from .tts import ToneTts

log = logging.getLogger(__name__)

KINDS = ("stt", "llm", "tts")
OFFLINE = {"stt": "null", "llm": "echo", "tts": "tone"}
READY = "bereit"
NOT_CONFIGURED = "nicht konfiguriert"

# engine name -> (environment variable, settings section) for engines that need a key
KEYED = {"xai": (xai.ENV_KEY, "xai"), "elevenlabs": (elevenlabs.ENV_KEY, "elevenlabs")}


def ai_settings(ai: Mapping[str, Any] | None) -> dict[str, Any]:
    """The "ai" section with defaults filled in and values checked."""
    from ..settings_file import DEFAULTS, _merge  # local import: settings_file imports config

    errors: list[str] = []
    merged = _merge(("ai",), DEFAULTS["ai"], dict(ai or {}), errors)
    for e in errors:
        log.warning("config.json: %s", e)
    return merged


class EngineSet:
    def __init__(self, ai: Mapping[str, Any] | None = None, http: HttpClient | None = None,
                 env: Mapping[str, str] | None = None):
        self.ai = ai_settings(ai)
        self.http = http or HttpClient()
        self.env = os.environ if env is None else env
        self.requested = dict(OFFLINE)
        self.active_names = dict(OFFLINE)
        self.instances: dict[str, Any] = {"stt": NullStt(), "llm": EchoLlm(), "tts": ToneTts()}
        self.fallbacks: dict[str, Any] = {}
        self._keys: dict[str, tuple[str | None, str]] = {}
        self.rejected: dict[str, str] = {}  # provider -> why the server refused its key (401/403)
        self.override: dict[str, str] | None = None  # kind -> engine run instead of the selection
        self._read_keys()
        for kind in KINDS:
            self.fallbacks[kind] = self._create(kind, self.fallback_name(kind))

    # -- keys / status ---------------------------------------------------------------------

    def _read_keys(self) -> bool:
        """Reads all keys; True if anything changed."""
        keys = {}
        for name, (env_name, section) in KEYED.items():
            keys[name] = resolve_key(env_name, str(self.ai[section].get("key_file") or ""), self.env)
        changed = {n: k[0] for n, k in keys.items()} != {n: k[0] for n, k in self._keys.items()}
        for name in keys:
            if keys[name][0] != self._keys.get(name, (None, ""))[0]:
                self.rejected.pop(name, None)  # a new key gets a new chance
        self._keys = keys
        return changed

    def note_api_error(self, error: Any) -> None:
        """Remembers a refused key (HTTP 401/403, xAI: 400 "Incorrect API key") for the key status."""
        status = getattr(error, "status", 0)
        if not is_key_rejection(status, getattr(error, "message", str(error))):
            return
        provider = str(getattr(error, "service", "")).lower()
        if provider in KEYED:
            self.rejected[provider] = f"vom Server abgelehnt (HTTP {status})"
            log.warning("%s API key rejected (HTTP %s)", provider, status)

    def key_info(self) -> dict[str, dict[str, str]]:
        """Per provider: state configured / missing / rejected and where the key comes from (never the key)."""
        info = {}
        for name in KEYED:
            key, where = self._keys.get(name, (None, ""))
            if name in self.rejected:
                info[name] = {"state": "rejected", "detail": f"{self.rejected[name]}; {where}"}
            elif key:
                info[name] = {"state": "configured", "detail": where}
            else:
                info[name] = {"state": "missing", "detail": where}
        return info

    def rebuild(self, kind: str) -> None:
        """Re-creates the running engine of one kind (after a setting such as the voice changed)."""
        self.fallbacks[kind] = self._create(kind, self.fallback_name(kind))
        self.active_names[kind] = ""
        self._activate(kind)

    def key(self, name: str) -> str | None:
        return self._keys.get(name, (None, ""))[0]

    def status_of(self, name: str) -> str:
        if name not in KEYED:
            return f"{READY} (offline)"
        key, where = self._keys.get(name, (None, ""))
        return f"{READY} ({where})" if key else f"{NOT_CONFIGURED}: {where}"

    def configured(self, name: str) -> bool:
        return name not in KEYED or bool(self.key(name))

    def status(self) -> dict[str, dict[str, str]]:
        return {kind: {name: self.status_of(name) for name in ENGINES_AVAILABLE[kind]} for kind in KINDS}

    def fallback_name(self, kind: str) -> str:
        name = str(self.ai["fallback"].get(kind) or OFFLINE[kind])
        if name not in ENGINES_AVAILABLE[kind] or not self.configured(name):
            return OFFLINE[kind]
        return name

    # -- building --------------------------------------------------------------------------

    def _create(self, kind: str, name: str) -> Any:
        language = str(self.ai.get("language") or "auto")
        if name == OFFLINE[kind]:
            return {"stt": NullStt, "llm": EchoLlm, "tts": ToneTts}[kind]()
        if name == "xai":
            settings, key = self.ai["xai"], self.key("xai")
            if kind == "stt":
                return xai.XaiStt(settings, key, self.http, language=language)
            if kind == "llm":
                return xai.XaiLlm(settings, key, self.http, persona=str(self.ai.get("persona") or ""))
            return xai.XaiTts(settings, key, self.http, language=language)
        if name == "elevenlabs" and kind == "tts":
            return elevenlabs.ElevenLabsTts(self.ai["elevenlabs"], self.key("elevenlabs"), self.http,
                                            language=language)
        raise ValueError(f"unknown {kind} engine {name!r}")

    def select(self, kind: str, name: str) -> list[str]:
        """Selects an engine. Returns notes for the user (empty if it runs as selected)."""
        if name not in ENGINES_AVAILABLE[kind]:
            return [f"{kind}: {name!r} gibt es nicht (verfügbar: {', '.join(ENGINES_AVAILABLE[kind])})"]
        self.requested[kind] = name
        return self._activate(kind)

    def effective(self, kind: str) -> str:
        """The engine that should run: the override (simple Q&A / realtime fallback) or the selection."""
        return (self.override or {}).get(kind) or self.requested[kind]

    def set_override(self, names: Mapping[str, str] | None) -> bool:
        """Runs other engines than the selected ones without changing the selection (the simple
        Q&A mode uses xai instead of the offline test engines). None = the selection again."""
        names = {k: v for k, v in (names or {}).items() if k in KINDS and v in ENGINES_AVAILABLE[k]} or None
        if names == self.override:
            return False
        self.override = names
        for kind in KINDS:
            self._activate(kind)
        return True

    def _activate(self, kind: str) -> list[str]:
        name = self.effective(kind)
        notes = []
        run = name
        if not self.configured(name):
            run = self.fallback_name(kind)
            notes.append(f"{kind} {name!r} {self.status_of(name)} - Fallback {run!r}")
        if run != self.active_names[kind]:  # same engine: keep it (and the LLM's conversation)
            self.instances[kind] = self._create(kind, run)
            self.active_names[kind] = run
        for note in notes:
            log.warning("Engine: %s", note)
        if not notes:
            log.info("Engine %s: %s (%s)", kind, run, self.status_of(run))
        return notes

    def refresh(self) -> bool:
        """Re-reads the keys (key files may appear later); re-selects engines if anything changed."""
        if not self._read_keys():
            return False
        log.info("API keys changed: %s", {n: self.status_of(n) for n in KEYED})
        for kind in KINDS:
            self.fallbacks[kind] = self._create(kind, self.fallback_name(kind))
            self.active_names[kind] = ""  # force rebuild
            self._activate(kind)
        return True

    def fallback(self, kind: str) -> tuple[str, Any]:
        """The engine to use when the active one fails (name, instance)."""
        return self.fallback_name(kind), self.fallbacks[kind]
