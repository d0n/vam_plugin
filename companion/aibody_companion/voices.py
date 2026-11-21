"""The xAI voice list for the plugin's Voice menu (after version 40).

Source: the official xAI text-to-speech page (https://docs.x.ai/developers/model-capabilities/audio/text-to-speech,
read 21.11.2026) lists these built-in voices and the endpoint GET /v1/tts/voices, which answers
{"voices": [{"voice_id": ..., "name": ..., "language": ...}]}. The companion asks that endpoint (in the background,
with the xAI key, at most every REFRESH_S) and sends the names in its heartbeat ("voices"); until it answered, or
without a key or network, the static list below is used. No names are invented: the static list is the page's list.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

# The 28 built-in voices of docs.x.ai (text-to-speech page, 21.11.2026), in the page's order. Voice ids are
# case-insensitive there; the plugin sends them lower case.
XAI_VOICES = (
    "carina", "zagan", "helix", "orion", "luna", "iris", "altair", "zenith", "perseus", "helios", "lux", "kepler",
    "rigel", "cosmo", "celeste", "ursa", "sirius", "lumen", "castor", "naksh", "atlas", "aurora", "liora", "ara",
    "eve", "leo", "rex", "sal",
)
VOICES_PATH = "/tts/voices"
REFRESH_S = 6 * 3600.0
RETRY_S = 300.0  # after a failed request


def parse_voices(body: bytes | str) -> list[str]:
    """{"voices": [{"voice_id": "eve", ...}]} -> ["eve", ...] (lower case, unique, in the answer's order)."""
    data = json.loads(body)
    out: list[str] = []
    for item in (data.get("voices") if isinstance(data, dict) else None) or []:
        vid = item.get("voice_id") if isinstance(item, dict) else item
        if isinstance(vid, str) and vid.strip():
            v = vid.strip().lower()
            if v not in out:
                out.append(v)
    return out


def fetch_xai_voices(http: Any, base_url: str, key: str, timeout: float = 10.0) -> list[str]:
    """GET {base_url}/tts/voices with the key; raises ApiError / ValueError on failure."""
    with http.open("xAI", "GET", base_url.rstrip("/") + VOICES_PATH, {"Authorization": f"Bearer {key}"}, None,
                   timeout) as resp:
        return parse_voices(resp.read())


class VoiceCatalog:
    """names() at once (static list or the last answer); a stale list starts ONE background request.
    fetcher=None (tests, offline) never asks the network."""

    def __init__(self, fetcher: Callable[[str, str], list[str]] | None = None,
                 clock: Callable[[], float] = time.monotonic, background: bool = True):
        self._fetcher = fetcher
        self._clock = clock
        self._background = background
        self._voices: list[str] = list(XAI_VOICES)
        self.source = "static list (docs.x.ai)"
        self._next = 0.0
        self._key_seen = ""
        self._busy = False
        self._lock = threading.Lock()

    def names(self, key: str | None, base_url: str) -> list[str]:
        if self._fetcher and key:
            now = self._clock()
            with self._lock:
                due = not self._busy and (now >= self._next or key != self._key_seen)
                if due:
                    self._busy, self._key_seen = True, key
            if due:
                if self._background:
                    threading.Thread(target=self._fetch, args=(key, base_url), daemon=True,
                                     name="xai-voices").start()
                else:
                    self._fetch(key, base_url)
        with self._lock:
            return list(self._voices)

    def _fetch(self, key: str, base_url: str) -> None:
        ok = False
        try:
            found = self._fetcher(key, base_url) if self._fetcher else []
            if found:
                merged = list(found)
                with self._lock:
                    self._voices, self.source = merged, f"xAI {VOICES_PATH} ({len(merged)} voices)"
                ok = True
                log.info("Voices: %d from xAI %s", len(merged), VOICES_PATH)
            else:
                log.info("Voices: xAI %s gave no list; the static list (%d) stays", VOICES_PATH, len(XAI_VOICES))
        except Exception as e:  # noqa: BLE001 - network / parse errors: keep the list we have
            log.info("Voices: xAI %s not reachable (%s); the %s stays", VOICES_PATH, e, self.source)
        finally:
            with self._lock:
                self._busy = False
                self._next = self._clock() + (REFRESH_S if ok else RETRY_S)
