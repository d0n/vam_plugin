"""Command line entry point: python -m aibody_companion --help"""
from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
from pathlib import Path

from . import __version__, logsetup, settings_file
from . import setup as first_start
from . import personas as personas_module
from . import wakeup
from .audio import EchoGate, MicController
from .config import PLUGIN_DATA_SUBDIR, Config, load_config
from .orchestrator import Companion
from .remote import RemoteControl
from .pipeline.engines import KEY_HINT, EngineSet
from .transport import FileTransport, HybridTransport, SocketTransport, Transport

FIXED_CHANNEL = "default"
log = logging.getLogger("aibody_companion")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aibody_companion", description="Companion app for the VaM AIBody plugin")
    p.add_argument("--config", help="JSON config file (see config.example.json)")
    p.add_argument("--vam-root", dest="vam_root", help='VaM install folder (required), e.g. "D:\\VaM"')
    p.add_argument(
        "--channel",
        help="ignored (one character, one fixed folder); accepted so old start scripts keep working",
    )
    p.add_argument("--no-mic", action="store_true", help="never open the microphone (text input only)")
    p.add_argument("--no-stdin", action="store_true", help="do not read typed messages from stdin")
    p.add_argument("--list-devices", action="store_true", help="print input devices and exit")
    p.add_argument("--setup", action="store_true",
                   help="ask the first-start questions again (background color, Scene / Plugin)")
    p.add_argument("--no-setup", action="store_true", help="never ask the first-start questions")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="DEBUG output of all modules plus the turn trace (else: config.json advanced.verbose_log)")
    return p


def build_transport(cfg: Config) -> Transport:
    """The link to the plugin: JSON files in <vam_root>/Saves/PluginData/AIBody/default/, plus (version 30) a loopback
    UDP listener the plugin's option 'Network Active' connects to. The files stay the fallback."""
    files = FileTransport(cfg.channel_dir)
    if cfg.network_port <= 0:
        return files
    return HybridTransport(files, SocketTransport(cfg.network_port))


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
    if not p.enabled:
        log.info("Proactive talking: off")
    elif not p.active:
        log.info("Proactive talking: off (speech delay timer %.0f s)", p.idle_seconds)
    elif p.enabled and companion.speech_only:
        log.info("Proactive talking: paused in Question and Answer mode (the AI only speaks when asked)")
    else:
        log.info("Proactive talking: on - after %.0f s of silence the AI may speak on its own "
                 "(speech delay timer, not the answer delay)", p.idle_seconds)
    return companion


def start_remote(cfg: Config, companion: Companion) -> RemoteControl | None:
    """Remote control (version 31): off unless config.json remote.enabled is true. Returns the running object or None."""
    remote = RemoteControl(cfg.remote)
    if not remote.enabled:
        return None
    remote.token = settings_file.ensure_remote_token(settings_file.settings_path(cfg.vam_root), cfg.remote)
    companion.remote = remote
    for line in remote.start():
        log.info(line)
    for problem in remote.errors:
        log.warning("Remote control: %s", problem)
    return remote


def start_stdin_reader() -> queue.Queue[str | None]:
    lines: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        for line in sys.stdin:
            lines.put(line.rstrip("\n"))
            wakeup.notify()
        lines.put(None)
        wakeup.notify()

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
        wakeup.wait(poll_interval)  # version 36: returns at once when a thread has work for the tick


def maybe_ask_setup(vam_root: str, args: argparse.Namespace, interactive: bool | None = None) -> bool:
    """The first-start questions (setup.py): once, or again with --setup; only in an interactive console. True if asked."""
    if args.no_setup:
        return False
    if not args.setup and first_start.already_asked(vam_root):
        return False
    if interactive is None:
        interactive = sys.stdin is not None and sys.stdin.isatty()
    if not interactive:
        log.info("Setup questions skipped (no interactive console); start once with --setup in a console to answer them")
        return False
    first_start.run(vam_root)
    return True


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

    cfg = load_config(args.config, {"vam_root": args.vam_root})
    cfg.channel = FIXED_CHANNEL  # one character, one fixed folder
    if args.channel and args.channel != FIXED_CHANNEL:
        log.warning("--channel %s is ignored: the app serves one character in the folder Saves/PluginData/AIBody/%s",
                    args.channel, FIXED_CHANNEL)
    errors = cfg.validate()
    if errors:
        for e in errors:
            log.error(e)
        return 2
    log_path = logsetup.setup(cfg.vam_root, debug=args.verbose)
    log.info("AIBody companion %s, log file: %s", __version__, log_path or "none (folder not writable)")
    for problem in settings_file.apply_to_config(cfg):
        log.warning("config.json: %s", problem)
    logsetup.set_verbose(cfg.verbose_log)
    maybe_ask_setup(cfg.vam_root, args)
    seeded = personas_module.seed_starter_personas(
        Path(cfg.vam_root) / PLUGIN_DATA_SUBDIR / personas_module.PERSONAS_SUBDIR)
    if seeded:
        log.info("Starter personas written for the Persona menu: %s", ", ".join(seeded))
    errors = cfg.validate()  # re-check after config.json (engines)
    if errors:
        for e in errors:
            log.error(e)
        return 2

    companion = build_stack(cfg, use_mic=not args.no_mic)
    if not companion.engine_set.key("xai"):
        log.warning("No xAI API key yet, so only the test engines run (they repeat what you type and play a tone) - "
                    "no real conversation. %s To fix it: paste the key into the field 'XAI API Token' (tab Voice) in "
                    "VaM - it reaches this app as soon as the plugin connects - or set the XAI_API_KEY environment "
                    "variable, or a key file in config.json (ai.xai.key_file).", KEY_HINT["xai"])
    companion.transport.start()
    remote = start_remote(cfg, companion)
    try:
        run(companion, read_stdin=not args.no_stdin, poll_interval=cfg.poll_interval_s)
    except KeyboardInterrupt:
        pass
    finally:
        if remote is not None:
            remote.stop()
        companion.shutdown()
        companion.transport.stop()
    return 0
