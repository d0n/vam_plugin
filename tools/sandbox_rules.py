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
    # Network (version 30, spec changed by Leon 19.11.2026): sockets exist in exactly ONE file, SocketLink.cs, and
    # only as a loopback UDP link (see NETWORK_FILE and NETWORK_ONLY below). Everything else stays banned.
    ("TCP / HTTP / web clients",
     r"\b(?:TcpClient|TcpListener|HttpListener|WebClient|HttpClient|WebRequest|HttpWebRequest|WebSocket\w*)\b"),
    ("non-loopback address (only IPAddress.Loopback is allowed)",
     r"\bIPAddress\s*\.\s*(?:Any|IPv6Any|IPv6Loopback|Broadcast|Parse|TryParse)\b|\bnew\s+IPAddress\b|0\.0\.0\.0|\bDns\b"),
    ("Process", r"\bProcess\b"),
    ("System.Diagnostics", r"\bSystem\s*\.\s*Diagnostics\b"),
    ("Reflection",
     r"\bReflection\b|\bGetMethod\s*\(|\bGetField\s*\(|\bGetProperty\s*\(|\bInvokeMember\b|\bActivator\b"),
    ("Assembly loading", r"\bAssembly\s*\.\s*Load"),
    ("DllImport / native interop", r"\bDllImport\b|\bInteropServices\b|\bMarshal\s*\."),
    ("UnityEngine.Microphone", r"UnityEngine\s*\.\s*Microphone|\bMicrophone\s*\."),
    ("Application.OpenURL", r"\bOpenURL\b"),
    ("optional HTTP build flag", r"AIBODY_HTTP"),
    # VaM's own C# compiler (old Mono mcs), not the sandbox: version 13 failed in VaM with
    # "CS584: Internal compiler error ... Dictionary<TKey,TValue>.ValueCollection.Enumerator" for a
    # foreach over dict.Values. Our stub compile (Roslyn) does not see this, so these constructs are
    # banned outright: iterate the dictionary itself (KeyValuePair) or copy into a List first.
    ("VaM security check: indexer (emits System.Reflection.DefaultMemberAttribute)", r"\bthis\s*\["),
    ("VaM compiler: foreach over Dictionary .Keys/.Values (CS584)",
     r"\bin\s+[\w.\[\]()\"]+\.(?:Keys|Values)\s*\)"),
    ("VaM compiler: member access / LINQ on .Keys/.Values (CS584 risk)", r"\.(?:Keys|Values)\s*\.\s*\w"),
    ("VaM compiler: KeyCollection/ValueCollection types (CS584 risk)", r"\b(?:KeyCollection|ValueCollection)\b"),
]

# Allowed ONLY in this file (matched against the file name, also inside the .var).
NETWORK_FILE = "SocketLink.cs"
NETWORK_ONLY: list[tuple[str, str]] = [
    ("System.Net outside SocketLink.cs", r"\bSystem\s*\.\s*Net\b"),
    ("sockets outside SocketLink.cs", r"\b(?:Socket|UdpClient|IPEndPoint|IPAddress)\b"),
    ("threads outside SocketLink.cs", r"\bSystem\s*\.\s*Threading\b|\bnew\s+Thread\b"),
]

_COMPILED = [(label, re.compile(rx)) for label, rx in FORBIDDEN]
_COMPILED_NETWORK_ONLY = [(label, re.compile(rx)) for label, rx in NETWORK_ONLY]


def scan_text(name: str, text: str) -> list[str]:
    """Returns one problem line per forbidden match in `text`."""
    problems = []
    rules = list(_COMPILED)
    if name.replace("\\", "/").rsplit("/", 1)[-1] != NETWORK_FILE:
        rules += _COMPILED_NETWORK_ONLY
    for label, rx in rules:
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
