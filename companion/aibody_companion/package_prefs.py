"""VaM's per-package plugin permission (version 67).

v66 showed as a yellow plugin without a menu on Don's PC: VaM's log said "Plugin scripts from packages d0n.AIBody.66 were not
loaded because they are in packages that have always been denied plugin loading". VaM keeps that choice per package version in
<VaM>/AddonPackagesUserPrefs/<package>.prefs ({"pluginsAlwaysEnabled": "true"|"false", "pluginsAlwaysDisabled": "true"|"false"}),
written when the user answers VaM's plugin prompt or changes it in the Package Manager (User Prefs tab). AIBody never writes it.
The companion only READS it at start and says clearly what to do; it never changes VaM's files.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PACKAGE_RE = re.compile(r"^d0n\.AIBody\.(\d+)\.var$")
HOW_TO_FIX = ("In VaM open the Package Manager, select the package, tab User Prefs, and allow plugins "
              "(untick 'Plugins always disabled' / tick 'Plugins always enabled'), then reload the scene.")


def installed_versions(vam_root: str | Path) -> list[int]:
    folder = Path(vam_root) / "AddonPackages"
    if not folder.is_dir():
        return []
    found = []
    for p in folder.iterdir():
        m = PACKAGE_RE.match(p.name)
        if m and p.is_file():
            found.append(int(m.group(1)))
    return sorted(found)


def plugins_denied(vam_root: str | Path, version: int) -> bool:
    """True when VaM's prefs for d0n.AIBody.<version> say plugins are always denied (a missing or broken file = False)."""
    prefs = Path(vam_root) / "AddonPackagesUserPrefs" / f"d0n.AIBody.{version}.prefs"
    try:
        data = json.loads(prefs.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return str(data.get("pluginsAlwaysDisabled", "false")).strip().lower() == "true"


def denied_installed(vam_root: str | Path) -> list[str]:
    """Package names (d0n.AIBody.<n>) that are installed AND have plugins always denied in VaM."""
    return [f"d0n.AIBody.{v}" for v in installed_versions(vam_root) if plugins_denied(vam_root, v)]


def warning(vam_root: str | Path) -> str | None:
    names = denied_installed(vam_root)
    if not names:
        return None
    return ("VaM will NOT load the AIBody plugin from " + ", ".join(names) + ": plugins of this package are set to "
            "'always denied' in VaM (the plugin shows yellow, no menu). " + HOW_TO_FIX)
