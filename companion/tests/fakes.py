"""Test doubles: a fake HTTP server for the cloud engines and a fake AIBody plugin that talks to
the companion over the real file channel, the way src/AIBody/*.cs does (a Python model of the
C# code paths: FileTransport.cs, AppLink.cs, MicConfig.cs, AIBody.cs settings, SpeechPlayer)."""
from __future__ import annotations

import io
import json
import queue
import time
from email.message import Message
from pathlib import Path
from typing import Any


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# ---------------------------------------------------------------------------------- HTTP


class FakeResponse:
    def __init__(self, body: bytes = b"", content_type: str = "application/json", status: int = 200,
                 lines: queue.Queue | None = None):
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self._buf = io.BytesIO(body)
        self._lines = lines  # streaming: lines arrive while the test feeds them (None = end)

    def read(self) -> bytes:
        return self._buf.read()

    def readline(self) -> bytes:
        if self._lines is not None:
            line = self._lines.get(timeout=5)
            return b"" if line is None else line
        return self._buf.readline()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def sse(*events: dict, done: bool = True) -> bytes:
    out = b""
    for e in events:
        out += f"event: {e.get('type', '')}\ndata: {json.dumps(e)}\n\n".encode()
    if done:
        out += b"data: [DONE]\n\n"
    return out


def text_stream(text_parts: list[str], response_id: str = "resp-1") -> bytes:
    events: list[dict] = [{"type": "response.created", "response": {"id": response_id}}]
    events += [{"type": "response.output_text.delta", "delta": p} for p in text_parts]
    events.append({"type": "response.completed", "response": {"id": response_id, "output": []}})
    return sse(*events)


class FakeHttp:
    """Opener for HttpClient: routes by URL substring; records every request."""

    def __init__(self):
        self.requests: list[Any] = []
        self.routes: list[tuple[str, Any]] = []

    def route(self, url_part: str, handler) -> None:
        """handler(request) -> FakeResponse, or an Exception instance to raise."""
        self.routes.insert(0, (url_part, handler))

    def __call__(self, request, timeout):
        self.requests.append(request)
        for part, handler in self.routes:
            if part in request.full_url:
                result = handler(request)
                if isinstance(result, Exception):
                    raise result
                return result
        raise AssertionError(f"unexpected request {request.full_url}")

    def json_body(self, i: int = -1) -> dict:
        return json.loads(self.requests[i].data.decode())


def http_error(url: str, status: int, body: dict):
    import urllib.error

    return urllib.error.HTTPError(url, status, "error", Message(), io.BytesIO(json.dumps(body).encode()))


# ---------------------------------------------------------------------------------- plugin


def vam_json(value: Any) -> Any:
    """What VaM's SimpleJSON writes: every number / boolean becomes a string."""
    if isinstance(value, dict):
        return {k: vam_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [vam_json(v) for v in value]
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return value


class FakePlugin:
    """The plugin side of the file channel. Mirrors the C# logic:
    - FileTransport.Start: create inbox/outbox, delete stale inbox files, keep 20 outbox files
    - outbox file names "<20-digit ticks>_<6-digit seq>.json", written in place, VaM-style JSON
    - AppLink: heartbeat event every 2 s; companion_heartbeat with a new session -> ready + config;
      no companion_heartbeat for 6 s -> GETRENNT (logged once), prune outbox to 20 per heartbeat;
      a session different from the last one -> app restarted -> stop speaking
    - AIBody settings: config.json written from the UI values, the "ai" section kept
    - SpeechPlayer: speak -> speech_started (duration) -> speech_ended after the duration
    """

    HEARTBEAT_INTERVAL = 2.0
    APP_TIMEOUT = 6.0

    def __init__(self, vam_root: Path, clock: FakeClock, channel: str = "default", mode: str = "auto"):
        self.root = Path(vam_root)
        self.clock = clock
        self.channel = channel
        # ai controls of the plugin tabs (AppLink.BuildAiJson): sent in the config event, merged into config.json "ai"
        self.poses: list[str] = []      # Body.AddStatus "poses" (gestures.json poses + preset files)
        self.body_control = True        # Body.AddStatus "body_control"
        # Body.SelfTestJson (in-game checks, sent as "selftest" in ready / heartbeat)
        self.selftest: dict[str, Any] = {"pose_storage": "ok", "pose_files": 0, "poses": 0,
                                         "breath_morph": "Breath1", "breath_morph_found": True,
                                         "expression_morphs_found": 9, "expression_morphs_total": 9,
                                         "expression_morphs_missing": [], "timeline_gestures": 0, "timeline": False}
        self.ai_ui: dict[str, Any] = {"mode": mode, "proactive": {"enabled": True, "idle_seconds": 90.0},
                                      "realtime": {"send_while_speaking": False}}
        self.voice = "eve"  # AI Character tab "Voice" -> ai.realtime.voice + ai.xai.voice
        self.xai_token = ""  # field "XAI API Token" (version 21): in the scene, sent in the config event only
        self.key_files = {"xai": "", "elevenlabs": ""}  # key file paths (from config.json; no menu field since 15)
        self.ui = {
            "connection": {"channel": channel, "active": True,
                           "paths": {"expressions": "Saves/PluginData/AIBody/expressions.json",
                                     "gestures": "Saves/PluginData/AIBody/gestures.json", "audio": ""}},
            "engines": {"stt": "null", "llm": "echo", "tts": "tone"},
            "mic": {"enabled": True, "mode": "vad", "device": "", "vad_threshold": 0.01, "end_silence_ms": 700,
                    "min_utterance_ms": 300, "max_utterance_ms": 20000, "echo_tail_s": 0.4, "gain": 1.0,
                    "ptt_interrupts": True, "level_meter": True},
            "body": {"speech_volume": 1.0, "body_control": True, "idle_motion": True, "idle_intensity": 0.5,
                     "breathing": True,
                     "breaths_per_minute": 14.0, "breath_depth": 0.35, "breath_morph": "Breath1"},
            "advanced": {"file_poll_interval_s": 0.1, "verbose_log": False},
        }
        self.settings_initialized = False  # the registered "Settings initialized" bool
        self.seq = 0
        self.app_session: str | None = None
        self.last_session: str | None = None
        self.app_age = 999.0
        self.app_alive = False
        self.seen_epoch = 0
        self.epoch = 0
        self.hb_timer = 0.0
        self.log: list[str] = []
        self.received: list[dict] = []
        self.playing: list[dict] = []  # speak commands, first = playing
        self.play_started_at = 0.0
        self.speech_events: list[tuple[str, str]] = []
        # folder prefixes VaM cannot load audio from (SpeechPlayer: clip does not start -> error
        # "audio_failed" + speech_ended "failed"); the real plugin reports it after 15 s
        self.unloadable: tuple[str, ...] = ()
        self.turn = ""  # companion_heartbeat "turn" (status box line)
        self.audio_out: dict = {}  # companion_heartbeat "audio_out"

    # -- folders ---------------------------------------------------------------------------

    @property
    def data_root(self) -> Path:
        return self.root / "Saves/PluginData/AIBody"

    @property
    def inbox(self) -> Path:
        return self.data_root / self.channel / "inbox"

    @property
    def outbox(self) -> Path:
        return self.data_root / self.channel / "outbox"

    def start(self) -> None:
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.outbox.mkdir(parents=True, exist_ok=True)
        for f in self.inbox.glob("*.json"):  # ClearStaleInbox
            f.unlink()
        self.prune_outbox(20)
        self.epoch += 1
        self.app_session = None
        self.app_alive = False
        self.app_age = 999.0

    def prune_outbox(self, keep: int) -> None:
        files = sorted(self.outbox.glob("*.json"))
        for f in files[: max(0, len(files) - keep)]:
            f.unlink()

    # -- sending ---------------------------------------------------------------------------

    def send(self, type_: str, **fields: Any) -> None:
        self.seq += 1
        evt = {"v": 3, "type": type_, "id": f"evt-{self.seq}", "ts": self.clock(), **fields}
        ticks = int(time.time() * 1e7)
        (self.outbox / f"{ticks:020d}_{self.seq:06d}.json").write_text(json.dumps(vam_json(evt)), encoding="utf-8")

    def status_fields(self) -> dict:
        return {"atom": "Person", "speaking": bool(self.playing), "speech_queue": len(self.playing),
                "expression": "neutral", "expressions": ["neutral", "happy", "sad", "thinking"],
                "gestures": ["nod", "shake", "tilt", *self.poses], "poses": list(self.poses),
                "body_control": self.body_control, "selftest": dict(self.selftest),
                "channel": self.channel, "plugin_version": PLUGIN_VERSION}

    def send_config(self) -> None:
        self.send("config", mic=dict(self.ui["mic"]), engines=dict(self.ui["engines"]),
                  ai=self.build_ai_json(), keys={"xai": self.xai_token.strip()},
                  advanced={"verbose_log": self.ui["advanced"]["verbose_log"]})

    def set_xai_token(self, value: str) -> None:
        """Voice Mode > field "XAI API Token": the config event goes out (AppLink.AddEngines "keys")."""
        self.xai_token = value
        self.send_config()

    def set_verbose(self, on: bool) -> None:
        """Config > "Verbose log": saved to config.json and sent to the app (config event)."""
        self.ui["advanced"]["verbose_log"] = on
        self.write_settings()
        self.send_config()

    def set_realtime(self, on: bool) -> None:
        """Voice Mode > "Echtzeit (Realtime) verwenden" (AppLink.SetRealtime): on = AI mode auto,
        off = qa; it shows on while the mode is auto or realtime."""
        if on != (self.ai_ui["mode"] in ("auto", "realtime")):
            self.ai_ui["mode"] = "auto" if on else "qa"
        self.write_settings()
        self.send_config()

    def build_ai_json(self) -> dict:
        """AppLink.BuildAiJson: the ai keys the tabs control; key file paths only when set."""
        ai = json.loads(json.dumps(self.ai_ui))
        ai["realtime"]["voice"] = self.voice
        ai["xai"] = {"voice": self.voice}
        if self.key_files["xai"]:
            ai["xai"]["key_file"] = self.key_files["xai"]
        if self.key_files["elevenlabs"]:
            ai["elevenlabs"] = {"key_file": self.key_files["elevenlabs"]}
        return ai

    def request_reconnect(self) -> None:
        """AppLink.ApiReconnect (button "API Reconnect")."""
        self.send("reconnect")

    def simple_qa(self) -> None:
        """Button "Einfacher Q&A-Modus" (Voice Mode tab): AI mode qa, body control off, saved + sent."""
        self.ai_ui["mode"] = "qa"
        self.ui["body"]["body_control"] = False
        self.write_settings()
        self.send_config()

    def request_test_tone(self) -> None:
        """AppLink.RequestTestTone (button "Test-Ton über Companion")."""
        self.send("test_tone")

    def press_ptt(self, active: bool) -> None:
        self.send("ptt", active=active)

    # -- config.json (AIBody.cs UpdateSettings / WriteSettings) ----------------------------

    @property
    def settings_path(self) -> Path:
        return self.data_root / "config.json"

    def seed_from_file(self) -> None:
        """1.5 s after Init: a scene without saved AIBody settings takes the file's values."""
        if not self.settings_initialized and self.settings_path.exists():
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            for cat in self.ui:
                for key, value in (data.get(cat) or {}).items():
                    if key in self.ui[cat]:
                        self.ui[cat][key] = _from_vam(value, self.ui[cat][key])
            ai = data.get("ai") or {}
            if ai.get("mode") in ("qa", "auto", "realtime", "chain"):
                self.ai_ui["mode"] = ai["mode"]
            for section, keys in (("proactive", ("enabled", "idle_seconds")), ("realtime", ("send_while_speaking",))):
                for key in keys:
                    if key in (ai.get(section) or {}):
                        self.ai_ui[section][key] = _from_vam(ai[section][key], self.ai_ui[section][key])
            self.voice = str((ai.get("realtime") or {}).get("voice") or self.voice)
        self.adopt_key_files()
        self.settings_initialized = True

    def adopt_key_files(self) -> None:
        """AppLink.AdoptKeyFiles: the key file paths come from config.json on every start (file wins, version 15)."""
        if not self.settings_path.exists():
            return
        ai = json.loads(self.settings_path.read_text(encoding="utf-8")).get("ai") or {}
        for provider in self.key_files:
            path = str((ai.get(provider) or {}).get("key_file") or "")
            if path:
                self.key_files[provider] = path

    def write_settings(self) -> None:
        root: dict[str, Any] = {"version": 1, "written_by": f"AIBody plugin {PLUGIN_VERSION}",
                                **json.loads(json.dumps(self.ui)), "ai": self.build_ai_json()}
        if not root["connection"]["paths"].get("audio"):
            root["connection"]["paths"].pop("audio", None)  # AppLink writes paths.audio only when set
        if self.settings_path.exists():
            existing = json.loads(self.settings_path.read_text(encoding="utf-8"))
            ai = existing.get("ai")
            if isinstance(ai, dict):
                # AppLink.MergeAi: the UI keys go into the kept "ai" section (as VaM strings)
                ui = self.build_ai_json()
                ai["mode"] = ui["mode"]
                for section in ("proactive", "realtime", "xai", "elevenlabs"):
                    if section not in ui:
                        continue
                    if not isinstance(ai.get(section), dict):
                        ai[section] = {}
                    ai[section].update(vam_json(ui[section]))
                root["ai"] = ai
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(vam_json(root)), encoding="utf-8")

    # -- frame loop ------------------------------------------------------------------------

    def tick(self, dt: float = 0.1) -> None:
        connected = True
        self.app_age += dt
        for f in sorted(self.inbox.glob("*.json")):
            try:
                msg = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            f.unlink()
            self.received.append(msg)
            self.handle(msg)
        if connected and self.epoch != self.seen_epoch:
            self.seen_epoch = self.epoch
            self.send("ready", **self.status_fields())
            self.send_config()  # MicConfig.OnConnected
            self.hb_timer = 0.0
        alive = self.app_session is not None and self.app_age < self.APP_TIMEOUT
        if self.app_alive and not alive:
            self.log.append("Companion app disconnected")
            self.app_session = None
        self.app_alive = alive
        self.hb_timer += dt
        if self.hb_timer >= self.HEARTBEAT_INTERVAL:
            self.hb_timer = 0.0
            self.send("heartbeat", **self.status_fields())
            if not alive:
                self.prune_outbox(20)
        self._play(dt)

    def handle(self, msg: dict) -> None:
        t = msg.get("type")
        if t == "companion_heartbeat":
            self.app_age = 0.0
            self.turn = msg.get("turn", self.turn)
            self.audio_out = msg.get("audio_out", self.audio_out)
            session = msg.get("session")
            if session != self.app_session:
                restarted = self.last_session is not None and session != self.last_session
                self.app_session = session
                self.last_session = session
                self.seen_epoch = -1
                if restarted:
                    self.log.append("app restarted")
                    self.stop_speaking("cancelled")
        elif t == "speak":
            self.playing.append(msg)
            if len(self.playing) == 1:
                self._start_current()
        elif t == "stop_speaking":
            self.stop_speaking("cancelled")

    def _start_current(self) -> None:
        cur = self.playing[0]
        audio = self.root / cur["audio"]
        assert audio.is_file(), f"speak points to a missing file: {cur['audio']}"
        if cur["audio"].startswith(self.unloadable):
            self.playing.pop(0)
            self.send("error", reply_to=cur["id"], code="audio_failed",
                      message="did not start playing within 15 s: " + cur["audio"])
            self.send("speech_ended", utterance_id=cur["id"], reason="failed")
            self.speech_events.append(("failed", cur["id"]))
            if self.playing:
                self._start_current()
            return
        self.play_started_at = self.clock()
        self.send("speech_started", utterance_id=cur["id"], duration=float(cur.get("duration", 1.0)))
        self.speech_events.append(("started", cur["id"]))

    def _play(self, dt: float) -> None:
        if not self.playing:
            return
        cur = self.playing[0]
        if self.clock() - self.play_started_at >= float(cur.get("duration", 1.0)):
            self.playing.pop(0)
            self.send("speech_ended", utterance_id=cur["id"], reason="finished")
            self.speech_events.append(("ended", cur["id"]))
            if self.playing:
                self._start_current()

    def stop_speaking(self, reason: str) -> None:
        if self.playing:
            cur = self.playing[0]
            self.send("speech_ended", utterance_id=cur["id"], reason=reason)
            self.speech_events.append(("ended", cur["id"]))
        self.playing = []

    @property
    def status(self) -> str:
        if self.app_alive:
            return "connected"
        return "DISCONNECTED" if self.last_session else "not seen yet"


PLUGIN_VERSION = "21"  # AIBody.cs PluginVersion


def _from_vam(value: Any, like: Any) -> Any:
    """How the C# accessors read a value back (AsBool / AsFloat / Value)."""
    if isinstance(value, dict):
        return value
    if isinstance(like, bool):
        return str(value).lower() == "true"
    if isinstance(like, int):
        return int(float(value))
    if isinstance(like, float):
        return float(value)
    return str(value)
