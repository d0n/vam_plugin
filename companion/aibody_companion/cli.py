"""Command line entry point: python -m aibody_companion --help"""
from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time

from . import __version__, logsetup, settings_file
from .audio import EchoGate, MicController
from .config import Config, load_config
from .orchestrator import Companion
from .pipeline.engines import KEY_HINT, EngineSet
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
    p.add_argument("-v", "--verbose", action="store_true",
                   help="DEBUG output of all modules plus the turn trace (else: config.json advanced.verbose_log)")
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
    log.info("Mode: %s -> %s (%s)", companion.mode_requested, companion.active_mode, companion.mode_note)
    log.info("Audio folder: %s%s", cfg.audio_rel_dir,
             " (automatic; switches once to Saves/PluginData if VaM cannot load from there)"
             if cfg.audio_auto else " (connection.paths.audio)")
    p = companion.proactive
    if p.enabled and companion.speech_only:
        log.info("Proactive: paused in Simple Q&A mode (the AI only speaks when asked)")
    else:
        log.info("Proactive: %s, after %.0f s of silence", "on" if p.enabled else "off", p.idle_seconds)
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
        print("Type a question and press Enter: it is answered like a spoken one (language model -> "
              "text to speech -> VaM). Ctrl+D / Ctrl+Z stops typing.")
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
    logsetup.setup(None, debug=args.verbose)
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
    log_path = logsetup.setup(cfg.vam_root, debug=args.verbose)
    log.info("AIBody companion %s, log file: %s", __version__, log_path or "none (folder not writable)")
    for problem in settings_file.apply_to_config(cfg, channel_from_cli=args.channel is not None):
        log.warning("config.json: %s", problem)
    logsetup.set_verbose(cfg.verbose_log)
    errors = cfg.validate()  # re-check after config.json (channel, engines)
    if errors:
        for e in errors:
            log.error(e)
        return 2

    companion = build_stack(cfg, use_mic=not args.no_mic)
    if not companion.engine_set.key("xai"):
        log.warning("No xAI API key: test engines only (echo + tone). %s; set XAI_API_KEY or a key file "
                    "in config.json (ai.xai.key_file).", KEY_HINT["xai"])
    companion.transport.start()
    try:
        run(companion, read_stdin=not args.no_stdin, poll_interval=cfg.poll_interval_s)
    except KeyboardInterrupt:
        pass
    finally:
        companion.shutdown()
        companion.transport.stop()
    return 0
