"""Command line entry point: python -m aibody_companion --help"""
from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time

from .audio import EchoGate
from .config import load_config
from .orchestrator import Companion
from .pipeline import EchoLlm, NullStt, ToneTts
from .transport import FileTransport, HttpTransport

log = logging.getLogger("aibody_companion")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aibody_companion", description="Companion app for the VaM AIBody plugin")
    p.add_argument("--config", help="JSON config file (see config.example.json)")
    p.add_argument("--vam-root", dest="vam_root", help="VaM install folder")
    p.add_argument("--channel", help="plugin channel (default: Person)")
    p.add_argument("--transport", choices=["file", "http"])
    p.add_argument("--port", dest="http_port", type=int)
    p.add_argument("--mode", choices=["text", "voice"], default="text",
                   help="text: type messages on stdin; voice: use the microphone")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def build_stack(cfg):
    if cfg.transport == "http":
        transport = HttpTransport(cfg.channel, cfg.http_host, cfg.http_port)
    else:
        transport = FileTransport(cfg.channel_dir)
    # TODO: select real engines from cfg.stt / cfg.llm / cfg.tts once implemented.
    if (cfg.stt, cfg.llm, cfg.tts) != ("null", "echo", "tone"):
        log.warning("Only the mock engines are implemented so far (stt=null, llm=echo, tts=tone).")
    return Companion(cfg, transport, NullStt(), EchoLlm(), ToneTts(), EchoGate(tail_s=cfg.echo_tail_s))


def run_text_mode(companion: Companion, poll_interval: float) -> None:
    lines: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        for line in sys.stdin:
            lines.put(line.rstrip("\n"))
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    print("Type a message and press Enter (Ctrl+D / Ctrl+Z to quit).")
    while True:
        companion.process_events()
        try:
            line = lines.get(timeout=poll_interval)
        except queue.Empty:
            continue
        if line is None:
            break
        if line.strip():
            companion.handle_user_text(line.strip())


def run_voice_mode(companion: Companion, poll_interval: float) -> None:
    from .audio.capture import MicCapture

    cfg = companion.cfg
    mic = MicCapture(cfg.sample_rate, cfg.frame_ms, cfg.mic_device)
    mic.start()
    print("Listening. Press Ctrl+C to quit.")
    try:
        while True:
            companion.process_events()
            for frame in mic.frames(timeout=poll_interval):
                companion.handle_audio_frame(frame)
    finally:
        mic.stop()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config, {
        "vam_root": args.vam_root, "channel": args.channel,
        "transport": args.transport, "http_port": args.http_port,
    })
    errors = cfg.validate()
    if errors:
        for e in errors:
            log.error(e)
        return 2

    companion = build_stack(cfg)
    companion.transport.start()
    try:
        if args.mode == "voice":
            run_voice_mode(companion, cfg.poll_interval_s)
        else:
            run_text_mode(companion, cfg.poll_interval_s)
    except KeyboardInterrupt:
        pass
    finally:
        companion.transport.stop()
        time.sleep(0.05)
    return 0
