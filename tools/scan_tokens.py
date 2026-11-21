"""Fails (exit 1) when a file below the given paths holds something shaped like an API key or a saved key.

Used by the Windows companion build (CI) on the PyInstaller folder and the installer, and usable on the repo / a .var.
Binary files are scanned as bytes. Known harmless test strings are allowed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

KEY = re.compile(rb"\b(?:xai-|sk-|sk_)[A-Za-z0-9_-]{20,}")
SAVED = re.compile(rb'"api_key"\s*:\s*"[^"]{8,}"')
ALLOWED = {b"xai-0123456789abcdefghij"}
FORBIDDEN_NAMES = {"config.json"}


def scan(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for base in paths:
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
        for f in files:
            if f.name in FORBIDDEN_NAMES:
                hits.append(f"{f}: a config.json must not be shipped")
            try:
                data = f.read_bytes()
            except OSError as e:
                hits.append(f"{f}: unreadable ({e})")
                continue
            for m in KEY.finditer(data):
                if m.group(0) not in ALLOWED:
                    hits.append(f"{f}: key-shaped string at byte {m.start()}")
            for m in SAVED.finditer(data):
                hits.append(f"{f}: saved api_key at byte {m.start()}")
    return hits


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or [Path(".")]
    hits = scan(paths)
    for h in hits:
        print(h)
    print(f"token scan: {len(hits)} finding(s) in {', '.join(map(str, paths))}")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
