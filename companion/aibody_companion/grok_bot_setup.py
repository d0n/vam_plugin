"""Optional Grok Bot install from the AIBody setup (version 61; opt-in, never part of the default install).

The setup (packaging/companion/AIBodyCompanion.iss) offers an UNCHECKED task "Grok Bot (optional)" with two choices:

  * local: install the Grok Bot desktop app on this computer and switch AIBody to the Grok Bot bridge. The setup runs
    ``AIBody Companion.exe --setup-grok-bot local --vam-root <VaM>``, which calls install_local() below:
      1. reads the official release feed https://api2.cursor.sh/updates/api/download/stable/<platform>/sand
         (docs.x.ai/grok-bot/deployment: Windows x64 = win32-x64-user, Arm64 = win32-arm64-user) and takes its
         ``downloadUrl`` (only https://downloads.cursor.com/... *.exe is accepted);
      2. downloads that Setup .exe into the temp folder and runs it silently with ``/S`` (per-user install into
         %LOCALAPPDATA%\\Programs, no admin rights, exactly as the deployment docs describe);
      3. writes config.json ``ai.driver = "grok_bot"`` and ``remote.enabled = true`` (the bridge; the app creates the
         token on its next start). Everything else in config.json stays as it is.
  * cloud: install nothing more; AIBody keeps the direct method, which already uses Grok's cloud (the xAI API).

What a setup cannot do (Grok Bot has no scripted configuration for single users): sign in with the Cursor account
(browser), allow local execution on this computer (Settings > Computer, or "always allow" on the first command) and the
user's own auto-review rules. The setup's last page says so. A failed download or install never fails the AIBody
setup: the result is written to <VaM>/Saves/PluginData/AIBody/logs/grok_bot_setup.log and the direct method stays.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

FEED_URL = "https://api2.cursor.sh/updates/api/download/stable/{platform}/sand"
DOWNLOAD_HOST = "downloads.cursor.com"
PLATFORMS = {"amd64": "win32-x64-user", "x86_64": "win32-x64-user", "arm64": "win32-arm64-user", "aarch64": "win32-arm64-user"}
TIMEOUT_S = 60.0
INSTALL_TIMEOUT_S = 900.0
MAX_FEED_BYTES = 64 * 1024
MAX_INSTALLER_BYTES = 1024 * 1024 * 1024
MANUAL_STEPS = (
    "Open Grok Bot and sign in with your Cursor account (in the browser).",
    "Allow local execution on this computer (Settings > Computer, or 'always allow' on the first command).",
    "Ask Grok Bot to read docs/GROK_BOT_BRIDGE.md of AIBody: it explains the bridge (127.0.0.1, token in config.json).",
)


class SetupError(RuntimeError):
    pass


def windows_platform(machine: str | None = None) -> str:
    key = (machine if machine is not None else platform.machine()).strip().lower()
    return PLATFORMS.get(key, "win32-x64-user")


def _fetch(url: str, limit: int, opener: Callable[..., Any]) -> bytes:
    request = Request(url, headers={"User-Agent": "AIBody-Companion-Setup"})
    with opener(request, timeout=TIMEOUT_S) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise SetupError(f"{url}: answer larger than {limit} bytes")
    return data


def installer_url(feed: bytes) -> tuple[str, str]:
    """(downloadUrl, version) from the release feed; only an https .exe on downloads.cursor.com is accepted."""
    try:
        data = json.loads(feed.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise SetupError(f"the Grok Bot release feed is not JSON ({e})") from None
    if not isinstance(data, dict):
        raise SetupError("the Grok Bot release feed is not a JSON object")
    url = str(data.get("downloadUrl") or "")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != DOWNLOAD_HOST or not parts.path.lower().endswith(".exe"):
        raise SetupError(f"unexpected Grok Bot download URL in the feed: {url!r}")
    return url, str(data.get("version") or "")


def enable_bridge(config_path: Path) -> None:
    """config.json: ai.driver = grok_bot, remote.enabled = true; the rest unchanged (atomic write)."""
    config_path = Path(config_path)
    data: dict[str, Any] = {}
    if config_path.is_file():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise SetupError(f"{config_path} is not readable JSON ({e}); not changed") from None
        if not isinstance(loaded, dict):
            raise SetupError(f"{config_path} is not a JSON object; not changed")
        data = loaded
    else:
        from . import settings_file
        data = settings_file.defaults()
    ai = data.get("ai") if isinstance(data.get("ai"), dict) else {}
    ai["driver"] = "grok_bot"
    data["ai"] = ai
    remote = data.get("remote") if isinstance(data.get("remote"), dict) else {}
    remote["enabled"] = True
    remote.setdefault("http_port", 38438)
    remote.setdefault("osc_port", 0)
    remote.setdefault("token", "")
    data["remote"] = remote
    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, config_path)


def install_local(vam_root: str | Path, opener: Callable[..., Any] = urlopen,
                  run: Callable[..., Any] = subprocess.run, machine: str | None = None,
                  temp_dir: str | Path | None = None) -> list[str]:
    """Downloads and silently installs Grok Bot, then switches AIBody to the bridge. Returns log lines; raises SetupError."""
    lines: list[str] = []
    feed_url = FEED_URL.format(platform=windows_platform(machine))
    url, version = installer_url(_fetch(feed_url, MAX_FEED_BYTES, opener))
    lines.append(f"Grok Bot {version or '(version not given)'}: {url}")
    folder = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="aibody-grokbot-"))
    target = folder / Path(urlsplit(url).path).name
    target.write_bytes(_fetch(url, MAX_INSTALLER_BYTES, opener))
    lines.append(f"downloaded {target} ({target.stat().st_size} bytes)")
    result = run([str(target), "/S"], timeout=INSTALL_TIMEOUT_S, check=False)
    code = getattr(result, "returncode", 0)
    if code != 0:
        raise SetupError(f"the Grok Bot installer ended with code {code}")
    lines.append("Grok Bot installed (silent, per user)")
    from . import settings_file
    path = settings_file.settings_path(vam_root)
    enable_bridge(path)
    lines.append(f"{path}: ai.driver = grok_bot, remote.enabled = true (back to the direct method: ai.driver = direct)")
    lines += ["Still to do by hand: " + step for step in MANUAL_STEPS]
    return lines


def run_setup(mode: str, vam_root: str | Path, **kwargs: Any) -> int:
    """Entry of ``--setup-grok-bot``. Never raises; 0 = done, 1 = failed (the direct method stays)."""
    mode = str(mode or "").strip().lower()
    log_path = Path(vam_root) / "Saves" / "PluginData" / "AIBody" / "logs" / "grok_bot_setup.log"
    if mode == "cloud":
        lines, code = ["cloud: nothing installed; AIBody keeps the direct method (Grok's cloud through the xAI API)"], 0
    elif mode == "local":
        try:
            lines, code = install_local(vam_root, **kwargs), 0
        except Exception as e:  # noqa: BLE001 - the AIBody setup must never fail because of this optional step
            lines, code = [f"Grok Bot setup failed: {e}", "AIBody keeps the direct method (nothing changed)"], 1
    else:
        lines, code = [f"unknown --setup-grok-bot mode {mode!r} (local or cloud); nothing done"], 1
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except OSError:
        pass
    return code
