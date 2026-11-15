"""Strict sandbox rules for the AIBody VaM plugin, shared by check_plugin.py and build_var.py.

Every pattern is matched against the FULL text of every plugin source (code, comments and
strings alike), so the plugin sources contain zero mentions of these APIs. See
docs/API_AUDIT.md for the APIs that are allowed and the evidence for each.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# (label, regex)
FORBIDDEN: list[tuple[str, str]] = [
    ("UnityWebRequest", r"UnityWebRequest\w*"),
    ("UnityEngine.Networking", r"UnityEngine\s*\.\s*Networking"),
    ("Networking namespace", r"\bNetworking\b"),
    ("WWW", r"\bWWW\w*\b"),
    ("System.IO", r"\bSystem\s*\.\s*IO\b"),
    ("File/Directory/Path (System.IO types)",
     r"\b(?:File|Directory|Path|StreamReader|StreamWriter|FileStream)\s*\.\s*[A-Z]"),
    ("System.Net", r"\bSystem\s*\.\s*Net\b"),
    ("sockets / web clients",
     r"\b(?:Socket|TcpClient|TcpListener|UdpClient|HttpListener|WebClient|HttpClient|WebRequest)\b"),
    ("Process", r"\bProcess\b"),
    ("System.Diagnostics", r"\bSystem\s*\.\s*Diagnostics\b"),
    ("Reflection",
     r"\bReflection\b|\bGetMethod\s*\(|\bGetField\s*\(|\bGetProperty\s*\(|\bInvokeMember\b|\bActivator\b"),
    ("Assembly loading", r"\bAssembly\s*\.\s*Load"),
    ("DllImport / native interop", r"\bDllImport\b|\bInteropServices\b|\bMarshal\s*\."),
    ("UnityEngine.Microphone", r"UnityEngine\s*\.\s*Microphone|\bMicrophone\s*\."),
    ("Application.OpenURL", r"\bOpenURL\b"),
    ("optional HTTP build flag", r"AIBODY_HTTP"),
]

_COMPILED = [(label, re.compile(rx)) for label, rx in FORBIDDEN]


def scan_text(name: str, text: str) -> list[str]:
    """Returns one problem line per forbidden match in `text`."""
    problems = []
    for label, rx in _COMPILED:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            problems.append(f"{name}:{line}: forbidden ({label}): '{m.group(0)}'")
    return problems


def scan_files(items: Iterable[tuple[str, str]]) -> list[str]:
    """items: (display name, text) pairs."""
    problems: list[str] = []
    for name, text in items:
        problems += scan_text(name, text)
    return problems
