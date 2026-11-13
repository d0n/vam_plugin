"""Command line entry point: python -m aibody_companion --help"""
from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time

from .audio import EchoGate, MicController
from .config import Config, load_config
from .orchestrator import Companion
from .pipeline import EchoLlm, NullStt, ToneTts
from .transport import AutoTransport, FileTransport, HttpTransport, Transport

log = logging.getLogger("aibody_companion")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aibody_companion", description="Companion app for the VaM AIBody plugin")
    p.add_argument("--config", help="JSON config file (see config.example.json)")
    p.add_argument("--vam-root", dest="vam_root", help="VaM install folder (needed for the file transport)")
    p.add_argument("--channel", help="plugin channel (default: Person)")
    p.add_argument("--transport", choices=["auto", "http", "file"])
    p.add_argument("--host", dest="http_host", help="HTTP bind address (default 127.0.0.1)")
    p.add_argument("--port", dest="http_port", type=int, help="HTTP port (default 8765)")
    p.add_argument("--no-mic", action="store_true", help="never open the microphone (text input only)")
    p.add_argument("--no-stdin", action="store_true", help="do not read typed messages from stdin")
    p.add_argument("--list-devices", action="store_true", help="print input devices and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def build_transport(cfg: Config) -> Transport:
    file = FileTransport(cfg.channel_dir) if cfg.has_vam_root else None
    if cfg.transport == "file":
        assert file is not None
        return file
    http = HttpTransport(cfg.channel, cfg.http_host, cfg.http_port, audio_dir=cfg.audio_dir)
    if cfg.transport == "http":
        return http
    if file is None:
        log.warning("vam_root not set: file fallback disabled, using HTTP only")
    return AutoTransport(http, file)


def build_stack(cfg: Config, use_mic: bool = True) -> Companion:
    # TODO: select real engines from cfg.stt / cfg.llm / cfg.tts once implemented.
    if (cfg.stt, cfg.llm, cfg.tts) != ("null", "echo", "tone"):
        log.warning("Only the mock engines are implemented so far (stt=null, llm=echo, tts=tone).")
    cfg.audio_dir.mkdir(parents=True, exist_ok=True)
    mic = MicController(cfg.sample_rate, cfg.frame_ms) if use_mic else None
    return Companion(cfg, build_transport(cfg), NullStt(), EchoLlm(), ToneTts(), EchoGate(), mic=mic)


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
        "vam_root": args.vam_root, "channel": args.channel, "transport": args.transport,
        "http_host": args.http_host, "http_port": args.http_port,
    })
    errors = cfg.validate()
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
