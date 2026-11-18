#!/usr/bin/env python3
"""Microphone test without VaM and without the companion app (Windows; also runs elsewhere).

    python tools/mic_test.py
    python tools/mic_test.py --vam-root "C:\\VaM" [--channel default]

Prints
  1. Python, sounddevice and PortAudio versions, the default devices,
  2. every audio device exactly as PortAudio reports it (raw),
  3. the input devices grouped per host API (MME, DirectSound, WASAPI, WDM-KS),
  4. the exact list the companion app sends to the plugin (same function: list_input_devices),
and writes
  - mic_test_output.txt   everything printed (send this file back),
  - mic_test_devices.json the "devices" message the plugin would receive.
With --vam-root the same "devices" message is also put into the plugin's inbox
(<VaM>/Saves/PluginData/AIBody/<channel>/inbox/), as if the companion app had sent it: with the
scene open, the tab Client Character then has to show this list in "Mic device" and in the info field.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))

from aibody_companion import protocol
from aibody_companion.audio import capture
from aibody_companion.config import PLUGIN_DATA_SUBDIR


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str = "") -> None:
        print(text)
        self.lines.append(text)


def _versions(sd: Any, out: Report) -> None:
    out(f"Python {sys.version.split()[0]} on {platform.platform()}")
    out(f"sounddevice {getattr(sd, '__version__', '?')}")
    try:
        out(f"PortAudio {sd.get_portaudio_version()[1]}")
    except Exception as e:  # noqa: BLE001
        out(f"PortAudio version unknown: {e}")
    try:
        out(f"sd.default.device = {list(sd.default.device)} (input, output)")
    except Exception as e:  # noqa: BLE001
        out(f"sd.default.device unreadable: {e}")
    try:
        out(f"sd.default.hostapi = {sd.default.hostapi}")
    except Exception as e:  # noqa: BLE001
        out(f"sd.default.hostapi unreadable: {e}")


def run(sd: Any, out: Report) -> dict[str, Any]:
    """Prints the sections and returns the "devices" message (also when sounddevice is missing)."""
    if sd is not None:
        _versions(sd, out)
        try:
            apis = list(sd.query_hostapis())
        except Exception as e:  # noqa: BLE001
            apis = []
            out(f"query_hostapis failed: {e}")
        try:
            devices = list(sd.query_devices())
        except Exception as e:  # noqa: BLE001
            devices = []
            out(f"query_devices failed: {e}")

        def api_name(i: Any) -> str:
            return str(apis[i].get("name", "?")) if isinstance(i, int) and 0 <= i < len(apis) else f"?{i}"

        out("")
        out("== Host-APIs ==")
        for i, a in enumerate(apis):
            out(f"  [{i}] {a.get('name')}  default input: {a.get('default_input_device')}")
        out("")
        out(f"== All devices, raw ({len(devices)}) ==")
        for i, d in enumerate(devices):
            out(f"  {i:3d}  in={d.get('max_input_channels', 0)} out={d.get('max_output_channels', 0)}"
                f"  {api_name(d.get('hostapi')):22s}  {d.get('default_samplerate')}  {d.get('name')!r}")
        out("")
        out("== Input devices per host API ==")
        for i in range(len(apis)) if apis else []:
            names = [(n, d) for n, d in enumerate(devices) if d.get("hostapi") == i and d.get("max_input_channels", 0) > 0]
            out(f"  {api_name(i)}: {len(names)}")
            for n, d in names:
                out(f"    {n:3d}  {d.get('name')!r}")
    else:
        out(f"Python {sys.version.split()[0]} on {platform.platform()}")
        out("sounddevice is NOT installed: pip install sounddevice")

    found, error = capture.list_input_devices()
    out("")
    out(f"== List the companion app sends to the plugin ({len(found)}) ==")
    if error:
        out(f"  Error: {error}")
    for d in found:
        out(f"  {d['index']:3d}  {'*' if d['default'] else ' '} {d['name']!r}  ({d['hostapi']})")
    out("  (* = Windows default; the plugin menu always lists 'System default microphone' first)")
    return protocol.make_command("devices", devices=found, error=error)


def write_inbox(vam_root: Path, channel: str, message: dict[str, Any]) -> Path:
    """Same file format as the companion's FileTransport.send (tmp file + rename)."""
    inbox = Path(vam_root) / PLUGIN_DATA_SUBDIR / channel / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    name = f"{time.time_ns():020d}_{0:06d}"
    tmp = inbox / f"{name}.tmp"
    tmp.write_text(json.dumps(message), encoding="utf-8")
    final = inbox / f"{name}.json"
    os.replace(tmp, final)
    return final


def main(argv: list[str] | None = None, out_dir: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIBody microphone test (without VaM and the companion app)")
    parser.add_argument("--vam-root", help="VaM root folder: also drops the list into the plugin inbox")
    parser.add_argument("--channel", default="default", help="plugin channel (default: default)")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")  # Windows console code pages and odd device names
    except (AttributeError, ValueError):
        pass
    sd = capture._sounddevice()
    out = Report()
    out(f"AIBody mic_test {time.strftime('%Y-%m-%d %H:%M:%S')}")
    message = run(sd, out)
    folder = Path(out_dir) if out_dir else Path.cwd()
    (folder / "mic_test_devices.json").write_text(json.dumps(message, indent=2, ensure_ascii=False), encoding="utf-8")
    out("")
    out(f"written: {folder / 'mic_test_devices.json'}")
    if args.vam_root:
        path = write_inbox(Path(args.vam_root), args.channel, message)
        out(f"dropped into the plugin inbox: {path}")
        out("  -> in VaM open tab 'Client Character': the 'Mic device' menu and the info panel now show this list.")
    out(f"output saved: {folder / 'mic_test_output.txt'} (please send it back)")
    (folder / "mic_test_output.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    return 0 if message.get("devices") else 1


if __name__ == "__main__":
    sys.exit(main())
