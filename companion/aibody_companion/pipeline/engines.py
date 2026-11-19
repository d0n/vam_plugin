"""Engine registry: builds the STT / LLM / TTS engines selected in config.json (engines {stt,
llm, tts}, changeable live from the plugin's tab Voice > AI Character) with their settings from the "ai"
section, and falls back when an engine cannot run.

  stt   null (offline, recognizes nothing) | xai
  llm   echo (offline test model)         | xai (Grok, Responses API, streaming) | ollama (local, no key)
  tts   tone (offline test tone)          | xai | elevenlabs

A cloud engine without an API key is "not configured": it stays selectable (so the plugin
can keep the choice until the key arrives), but the configured fallback (ai.fallback, default
null / echo / tone) runs instead, and the status says so. Keys come from the environment
(XAI_API_KEY, ELEVENLABS_API_KEY) or from a key file named in config.json; refresh() re-reads
key files, so a key file added later is picked up without restarting.

xAI key precedence (version 24): 1. the token typed into the plugin's "XAI API Token" field (arrives
in the config event as keys.xai, set_ui_key), 2. ai.xai.api_key in config.json (plain text; the plugin
writes the field there, so after a restart it is the same token), 3. the XAI_API_KEY environment variable,
4. the key file ai.xai.key_file. An empty field falls through. ElevenLabs has no menu field.

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
from . import elevenlabs, ollama, xai
from .http import HttpClient, is_key_rejection
from ..logsetup import add_secret
from ..personas import Persona, memory_block
from .keys import resolve_key
from .llm import EchoLlm
from .stt import NullStt
from .tts import ToneTts

log = logging.getLogger(__name__)

KINDS = ("stt", "llm", "tts")
OFFLINE = {"stt": "null", "llm": "echo", "tts": "tone"}
READY = "ready"
NOT_CONFIGURED = "not configured"

# engine name -> (environment variable, settings section) for engines that need a key
KEYED = {"xai": (xai.ENV_KEY, "xai"), "elevenlabs": (elevenlabs.ENV_KEY, "elevenlabs")}
# where a key typed into the plugin comes from (only xAI has a menu field; never the key itself)
UI_KEY_SOURCE = {"xai": "plugin field 'XAI API Token'"}
# a key stored in config.json (provider -> key in its "ai" section); plain text, never logged
CONFIG_KEY = {"xai": "api_key"}
CONFIG_KEY_SOURCE = {"xai": "config.json ai.xai.api_key"}
# What kind of key works. xAI: an API key from console.x.ai (pay-as-you-go API credit); the login /
# subscription of grok.com or the X app (SuperGrok, Premium) is no API key and is refused by api.x.ai.
KEY_HINT = {
    "xai": ("You need an xAI API key: create one at console.x.ai (it starts with 'xai-'). "
            "A Grok subscription or a grok.com login does not work."),
    "elevenlabs": "You need an ElevenLabs API key: elevenlabs.io > your profile > API Keys.",
}


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
        self.ui_keys: dict[str, str] = {}  # provider -> token typed into the plugin (xai only)
        self.rejected: dict[str, str] = {}  # provider -> why the server refused its key (401/403)
        self.override: dict[str, str] | None = None  # kind -> engine run instead of the selection
        self.persona: Persona | None = None  # selected persona (personas.py); its prompt / language / voice win
        self.memory_facts: list[str] = []  # notes about the user (memory.json), put into the instructions
        self._read_keys()
        for kind in KINDS:
            self.fallbacks[kind] = self._create(kind, self.fallback_name(kind))

    # -- keys / status ---------------------------------------------------------------------

    def _read_keys(self) -> bool:
        """Reads all keys; True if anything changed."""
        keys = {}
        for name, (env_name, section) in KEYED.items():
            typed = self.ui_keys.get(name, "")
            if typed:
                add_secret(typed)  # before anything can log it
                keys[name] = (typed, UI_KEY_SOURCE[name])
                continue
            stored = str(self.ai[section].get(CONFIG_KEY.get(name, "")) or "").strip() if name in CONFIG_KEY else ""
            if stored:
                add_secret(stored)
                keys[name] = (stored, CONFIG_KEY_SOURCE[name])
                continue
            keys[name] = resolve_key(env_name, str(self.ai[section].get("key_file") or ""), self.env)
        changed = {n: k[0] for n, k in keys.items()} != {n: k[0] for n, k in self._keys.items()}
        for name in keys:
            if keys[name][0] != self._keys.get(name, (None, ""))[0]:
                self.rejected.pop(name, None)  # a new key gets a new chance
        self._keys = keys
        return changed

    def set_ui_key(self, name: str, value: str) -> bool:
        """The token from the plugin's text field (plain text, no format check; "" = field empty).
        True if the key in effect changed."""
        if name not in UI_KEY_SOURCE:
            return False
        value = value.strip()
        if value == self.ui_keys.get(name, ""):
            return False
        if not value and name in CONFIG_KEY:
            # The user emptied the field: the plugin writes "" into config.json too, so forget the stored key here.
            self.ai[KEYED[name][1]][CONFIG_KEY[name]] = ""
        add_secret(value)
        self.ui_keys[name] = value
        return self.refresh()

    def note_api_error(self, error: Any) -> None:
        """Remembers a refused key (HTTP 401/403, xAI: 400 "Incorrect API key") for the key status."""
        status = getattr(error, "status", 0)
        if not is_key_rejection(status, getattr(error, "message", str(error))):
            return
        provider = str(getattr(error, "service", "")).lower()
        if provider in KEYED:
            self.rejected[provider] = f"rejected by the server (HTTP {status})"
            log.warning("The %s API key was rejected (HTTP %s), so it cannot be used. %s", provider, status, KEY_HINT[provider])

    def key_info(self) -> dict[str, dict[str, str]]:
        """Per provider: state configured / missing / rejected and where the key comes from (never the key)."""
        info = {}
        for name in KEYED:
            key, where = self._keys.get(name, (None, ""))
            if name in self.rejected:
                info[name] = {"state": "rejected", "detail": f"{self.rejected[name]}; {where}", "hint": KEY_HINT[name]}
            elif key:
                info[name] = {"state": "configured", "detail": where}
            else:
                info[name] = {"state": "missing", "detail": where, "hint": KEY_HINT[name]}
        return info

    def rebuild(self, kind: str) -> None:
        """Re-creates the running engine of one kind (after a setting such as the voice changed)."""
        self.fallbacks[kind] = self._create(kind, self.fallback_name(kind))
        self.active_names[kind] = ""
        self._activate(kind)

    # -- persona (prompt, language and voice of the selected persona win over config.json) -----------------

    def persona_text(self) -> str:
        """The AI's character text: persona prompt (or ai.persona), the name, and the memory notes."""
        p = self.persona
        base = (p.prompt if p and p.prompt else str(self.ai.get("persona") or "")).strip()
        parts = [f"Your name is {p.display_name}." if p and p.display_name else "", base,
                 memory_block(self.memory_facts)]
        return "\n\n".join(x for x in parts if x)

    def language(self) -> str:
        return (self.persona.language if self.persona and self.persona.language else "") \
            or str(self.ai.get("language") or "auto")

    def xai_settings(self) -> dict[str, Any]:
        """ai.xai; with a persona voice a copy with that voice (else the live dict, so menu changes still count)."""
        if self.persona and self.persona.voice:
            return {**self.ai["xai"], "voice": self.persona.voice}
        return self.ai["xai"]

    def realtime_settings(self) -> dict[str, Any]:
        if self.persona and self.persona.voice:
            return {**self.ai["realtime"], "voice": self.persona.voice}
        return self.ai["realtime"]

    def elevenlabs_settings(self) -> dict[str, Any]:
        if self.persona and self.persona.elevenlabs_voice_id:
            return {**self.ai["elevenlabs"], "voice_id": self.persona.elevenlabs_voice_id}
        return self.ai["elevenlabs"]

    def memory_llm(self) -> Any:
        """A language model for memory summaries (xAI with the key there is), or None."""
        if self.effective("llm") == "ollama":  # the notes about the user stay on this computer
            return ollama.OllamaLlm(self.ai["ollama"], self.http)
        key = self.key("xai")
        return xai.XaiLlm(self.ai["xai"], key, self.http) if key else None

    def key(self, name: str) -> str | None:
        return self._keys.get(name, (None, ""))[0]

    def status_of(self, name: str) -> str:
        if name == "ollama":
            s = self.ai["ollama"]
            return f"{READY} (local: model {s['model']} at {s['base_url']}; reachable is checked when it is used)"
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
        language = self.language()
        if name == OFFLINE[kind]:
            return {"stt": NullStt, "llm": EchoLlm, "tts": ToneTts}[kind]()
        if name == "xai":
            settings, key = self.xai_settings(), self.key("xai")
            if kind == "stt":
                return xai.XaiStt(settings, key, self.http, language=language)
            if kind == "llm":
                return xai.XaiLlm(settings, key, self.http, persona=self.persona_text())
            return xai.XaiTts(settings, key, self.http, language=language)
        if name == "ollama" and kind == "llm":
            return ollama.OllamaLlm(self.ai["ollama"], self.http, persona=self.persona_text())
        if name == "elevenlabs" and kind == "tts":
            return elevenlabs.ElevenLabsTts(self.elevenlabs_settings(), self.key("elevenlabs"), self.http,
                                            language=language)
        raise ValueError(f"unknown {kind} engine {name!r}")

    def select(self, kind: str, name: str) -> list[str]:
        """Selects an engine. Returns notes for the user (empty if it runs as selected)."""
        if name not in ENGINES_AVAILABLE[kind]:
            return [f"{kind}: {name!r} does not exist (available: {', '.join(ENGINES_AVAILABLE[kind])})"]
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
            notes.append(f"{kind} engine {name!r}: {self.status_of(name)} - using the test engine instead (Fallback {run!r}). "
                         "Add the missing API key (see the key status in tab Voice).")
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
