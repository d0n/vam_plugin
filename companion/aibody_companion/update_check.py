"""Update notice of the installed AIBody Companion (Don, 21.11.2026 20:05, version 43).

On start the launcher asks GitHub once for the latest release of d0n/vam_plugin (one anonymous HTTPS GET of the
public releases API, no key, nothing sent about the user) and, when its number is higher than this app's, offers to
open the release page. Nothing is downloaded or installed. Offline, rate-limited, or any other problem: silently
nothing (one line in launcher.log). Switch it off with "update_check": false in launcher.json
(%LOCALAPPDATA%\\AIBody Companion). The VaM plugin itself never goes online (sandbox).
"""
from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Callable
from typing import Any

REPO = "d0n/vam_plugin"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
TIMEOUT_S = 5.0
_TAG = re.compile(r"^v?(\d+)$")


def parse_latest(body: bytes) -> tuple[int, str] | None:
    """(release number, release page) from the releases/latest answer; None for drafts, pre-releases or odd tags.
    The page link is always built for this repository (never a URL taken from the answer)."""
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    m = _TAG.match(str(data.get("tag_name") or "").strip())
    if not m:
        return None
    number = int(m.group(1))
    return number, f"{RELEASES_PAGE}/tag/v{number}"


def _get(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "AIBody-Companion-update-check"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310 - fixed https URL
        return resp.read(200_000)


def newer_release(current: str, get: Callable[[str, float], bytes] = _get) -> tuple[int, str] | None:
    """(number, page) when GitHub's latest release is newer than `current`; None otherwise or on ANY failure."""
    try:
        mine = int(str(current).strip())
        latest = parse_latest(get(LATEST_URL, TIMEOUT_S))
    except Exception:  # noqa: BLE001 - offline, DNS, TLS, HTTP 403/404, timeouts: never an error for the user
        return None
    if latest is None or latest[0] <= mine:
        return None
    return latest


def notice(current: str, latest: tuple[int, str]) -> str:
    number, page = latest
    return (f"A newer AIBody is available: version {number} (you have version {current}).\n\n{page}\n\n"
            "Open the release page now? (Download d0n.AIBody.{n}.var and AIBody Companion Setup.exe there.)"
            .replace("{n}", str(number)))


def enabled(settings: dict[str, Any]) -> bool:
    return settings.get("update_check", True) is not False
