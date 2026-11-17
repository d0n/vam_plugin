"""Command line entry point: python -m aibody_companion --help"""
from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time

from . import settings_file
from .audio import EchoGate, MicController
from .config import Config, load_config
from .orchestrator import Companion
from .pipeline.engines import EngineSet
from .transport import FileTransport, Transport

log = logging.getLogger("aibody_companion")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aibody_companion", description="Companion app for the VaM AIBody plugin")
    p.add_argument("--config", help="JSON config file (see config.example.json)")
    p.add_argument("--vam-root", dest="vam_root", help="VaM install folder (required)")
    p.add_argument(
        "--channel",
        help="AIBody plugin channel (default: connection.channel from Saves/PluginData/AIBody/config.json)",
    )
    p.add_argument("--no-mic", action="store_true", help="never open the microphone (text input only)")
    p.add_argument("--no-stdin", action="store_true", help="do not read typed messages from stdin")
    p.add_argument("--list-devices", action="store_true", help="print input devices and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def build_transport(cfg: Config) -> Transport:
    """The only link to the plugin: JSON files in <vam_root>/Saves/PluginData/AIBody/<channel>/."""
    return FileTransport(cfg.channel_dir)


def build_stack(cfg: Config, use_mic: bool = True) -> Companion:
    """Engines from config.json (engines + ai section); API keys from the environment or key files.
    Turns run on a worker thread so the link stays alive during slow network requests."""
    cfg.audio_dir.mkdir(parents=True, exist_ok=True)
    mic = MicController(cfg.sample_rate, cfg.frame_ms) if use_mic else None
    engines = EngineSet(cfg.ai)
    for kind, states in engines.status().items():
        for name, state in states.items():
            log.info("Engine %s/%s: %s", kind, name, state)
    companion = Companion(cfg, build_transport(cfg), gate=EchoGate(), mic=mic, engines=engines,
                          background_turns=True)
    log.info("Modus: %s -> %s (%s)", companion.mode_requested, companion.active_mode, companion.mode_note)
    p = companion.proactive
    log.info("Proaktiv: %s, nach %.0f s Stille", "an" if p.enabled else "aus", p.idle_seconds)
    return companion


def start_stdin_reader() -> queue.Queue[str | None]:
    lines: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        for line in sys.stdin:
            lines.put(line.rstrip("\n"))
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    return lines


def run(companion: Companion, read_stdin: bool, poll_interval: float) -> None:
    lines = start_stdin_reader() if read_stdin else None
    if lines:
        print("Type a message and press Enter to make the body speak (Ctrl+D / Ctrl+Z to stop typing).")
    while True:
        companion.tick()
        if lines is not None:
            try:
                line = lines.get_nowait()
            except queue.Empty:
                line = ""
            if line is None:
                lines = None  # stdin closed; keep serving the plugin and the mic
                if not companion.mic:
                    return
            elif line.strip():
                companion.handle_user_text(line.strip())
        time.sleep(poll_interval)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.list_devices:
        from .audio import list_input_devices

        devices, error = list_input_devices()
        if error:
            print(error)
        for d in devices:
            print(f"{d['index']:3d}  {'*' if d['default'] else ' '} {d['name']}")
        return 0 if not error else 1

    cfg = load_config(args.config, {
        "vam_root": args.vam_root, "channel": args.channel,
    })
    errors = cfg.validate()
    if errors:
        for e in errors:
            log.error(e)
        return 2
    for problem in settings_file.apply_to_config(cfg, channel_from_cli=args.channel is not None):
        log.warning("config.json: %s", problem)
    errors = cfg.validate()  # re-check after config.json (channel, engines)
    if errors:
        for e in errors:
            log.error(e)
        return 2

    companion = build_stack(cfg, use_mic=not args.no_mic)
    companion.transport.start()
    try:
        run(companion, read_stdin=not args.no_stdin, poll_interval=cfg.poll_interval_s)
    except KeyboardInterrupt:
        pass
    finally:
        companion.shutdown()
        companion.transport.stop()
    return 0
