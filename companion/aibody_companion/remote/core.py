"""Actions, validation, the thread-safe queue and the status snapshot shared by the HTTP and OSC servers."""
from __future__ import annotations

import logging
import queue
import threading
from typing import TYPE_CHECKING, Any

from .. import __version__
from ..protocol import LOOK_MAX_SECONDS, LOOK_TARGETS
from ..vamjson import as_bool, as_number

if TYPE_CHECKING:
    from ..orchestrator import Companion

log = logging.getLogger(__name__)

LOOPBACK = "127.0.0.1"  # the only address either server binds
MAX_PENDING = 50  # queued actions; more are refused ("busy")
MAX_TEXT_CHARS = 1000
STATUS_INTERVAL_S = 0.5
PTT_ACTIONS = ("start", "stop", "toggle")

# action name -> what it does (also served by GET /api/status)
ACTIONS: dict[str, str] = {
    "say": "speak exactly this text (text to speech, no language model); params: text, interrupt (false)",
    "ask": "ask the AI as if the user had typed it; params: text",
    "expression": "show an expression; params: name, intensity (1.0), blend (0.4 s), hold (seconds, optional)",
    "gesture": "play a gesture from gestures.json; params: name",
    "pose": "apply a pose; params: name",
    "look": "direct the eyes; params: target (client|camera|forward|away|off|atom), atom (name), seconds (0 = until changed)",
    "stop": "stop speaking and drop the answer being prepared; no params",
    "event": "tell the AI about a scene event (like the plugin's 'Scene event'); params: text",
    "ptt": "push-to-talk; params: action (start|stop|toggle)",
}


class RemoteError(ValueError):
    """A request that cannot be run (bad parameters, unknown name, queue full). The message is shown to the caller."""


def _text(params: dict[str, Any], key: str = "text") -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RemoteError(f"'{key}' must be a non-empty string")
    value = value.strip()
    if len(value) > MAX_TEXT_CHARS:
        raise RemoteError(f"'{key}' is longer than {MAX_TEXT_CHARS} characters")
    return value


def _number(params: dict[str, Any], key: str, default: float | None, lo: float, hi: float) -> float | None:
    if key not in params or params[key] is None:
        return default
    value = as_number(params[key])
    if value is None:
        raise RemoteError(f"'{key}' must be a number")
    if not lo <= value <= hi:
        raise RemoteError(f"'{key}' must be from {lo:g} to {hi:g}")
    return float(value)


def parse_action(name: str, params: Any) -> dict[str, Any]:
    """Checks one action's shape and returns the normalized parameters. Raises RemoteError."""
    if name not in ACTIONS:
        raise RemoteError(f"unknown action {name!r}; known: {', '.join(ACTIONS)}")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise RemoteError("the parameters must be a JSON object")
    if name in ("say", "ask", "event"):
        out: dict[str, Any] = {"text": _text(params)}
        if name == "say":
            flag = as_bool(params.get("interrupt", False))
            if flag is None:
                raise RemoteError("'interrupt' must be true/false")
            out["interrupt"] = flag
        return out
    if name in ("gesture", "pose"):
        return {"name": _text(params, "name")}
    if name == "expression":
        out = {"name": _text(params, "name"),
               "intensity": _number(params, "intensity", 1.0, 0.0, 1.0),
               "blend": _number(params, "blend", 0.4, 0.0, 10.0)}
        hold = _number(params, "hold", None, 0.0, 600.0)
        if hold is not None:
            out["hold"] = hold
        return out
    if name == "look":
        target = str(params.get("target") or "").strip()
        atom = str(params.get("atom") or "").strip()
        if target.lower().startswith("atom:"):  # OSC shorthand "atom:Name"
            target, atom = "atom", target[5:].strip()
        target = target.lower()
        if target not in LOOK_TARGETS:
            raise RemoteError(f"'target' must be one of {', '.join(LOOK_TARGETS)}")
        if target == "atom" and not atom:
            raise RemoteError("target 'atom' needs the atom's name in 'atom'")
        out = {"target": target, "seconds": _number(params, "seconds", 0.0, 0.0, LOOK_MAX_SECONDS)}
        if target == "atom":
            out["atom"] = atom
        return out
    if name == "ptt":
        action = str(params.get("action") or "").strip().lower()
        if action not in PTT_ACTIONS:
            raise RemoteError(f"'action' must be one of {', '.join(PTT_ACTIONS)}")
        return {"action": action}
    return {}  # stop


class RemoteControl:
    """Settings, the action queue and the status snapshot. start() opens the servers, process() (main loop) runs actions."""

    def __init__(self, settings: dict[str, Any]):
        self.enabled = as_bool(settings.get("enabled", False)) is True
        self.http_port = int(as_number(settings.get("http_port", 38438)) or 0)
        self.osc_port = int(as_number(settings.get("osc_port", 0)) or 0)
        self.token = str(settings.get("token") or "").strip()
        self._queue: queue.Queue[tuple[str, dict[str, Any], str]] = queue.Queue(maxsize=MAX_PENDING)
        self._lock = threading.Lock()
        self._status: dict[str, Any] = {"version": __version__, "plugin_connected": False, "actions": dict(ACTIONS)}
        self._known: dict[str, list[str]] = {"expressions": [], "gestures": [], "poses": []}
        self._last_status = -1e9
        self._last_action: dict[str, Any] = {}
        self._http: Any = None
        self._osc: Any = None
        self.errors: list[str] = []  # why a server could not start

    # -- start / stop ------------------------------------------------------------------------------

    def start(self) -> list[str]:
        """Opens the servers (nothing if disabled). Returns human-readable lines for the console."""
        lines: list[str] = []
        if not self.enabled:
            return lines
        from .http_server import HttpServer
        from .osc import OscServer

        if len(self.token) < 16:
            self.errors.append("remote.token is missing or shorter than 16 characters: the HTTP API stays off")
        else:
            self._http = HttpServer(self, self.http_port)
            try:
                self._http.start()
                lines.append(f"Remote control: web page and HTTP API on http://{LOOPBACK}:{self._http.port}/ "
                             "(this computer only; the token is remote.token in config.json)")
            except OSError as e:
                self._http = None
                self.errors.append(f"remote HTTP port {self.http_port} could not be opened ({e}); the HTTP API stays off")
        if self.osc_port > 0:
            self._osc = OscServer(self, self.osc_port)
            try:
                self._osc.start()
                lines.append(f"Remote control: OSC on udp://{LOOPBACK}:{self._osc.port} (this computer only; no token) - "
                             "addresses /aibody/<action>, see docs/REMOTE.md")
            except OSError as e:
                self._osc = None
                self.errors.append(f"remote OSC port {self.osc_port} could not be opened ({e}); OSC stays off")
        return lines

    def stop(self) -> None:
        for server in (self._http, self._osc):
            if server is not None:
                server.stop()
        self._http = self._osc = None

    @property
    def http_bound_port(self) -> int:
        return self._http.port if self._http is not None else 0

    @property
    def osc_bound_port(self) -> int:
        return self._osc.port if self._osc is not None else 0

    # -- from the server threads -------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _canonical(self, kind: str, name: str) -> str:
        """The exact spelling the plugin lists (case-insensitive match); unknown names are refused once the lists are known."""
        names = self._known.get(kind) or []
        if not names:
            return name  # plugin not connected yet: the plugin decides
        for known in names:
            if known == name or known.lower() == name.lower():
                return known
        sample = ", ".join(names[:12]) + (" ..." if len(names) > 12 else "")
        raise RemoteError(f"unknown {kind[:-1]} {name!r}; the character has: {sample}")

    def submit(self, name: str, params: Any, source: str = "http") -> None:
        """Validates an action and queues it for the main loop. Raises RemoteError."""
        clean = parse_action(name, params)
        with self._lock:
            if name == "expression":
                clean["name"] = self._canonical("expressions", clean["name"])
            elif name == "gesture":
                clean["name"] = self._canonical("gestures", clean["name"])
            elif name == "pose":
                clean["name"] = self._canonical("poses", clean["name"])
        try:
            self._queue.put_nowait((name, clean, source))
        except queue.Full:
            raise RemoteError("busy: too many actions waiting") from None

    # -- main loop ---------------------------------------------------------------------------------

    def process(self, app: Companion) -> None:
        """Runs the queued actions and refreshes the status snapshot. Called from Companion.tick()."""
        now = app.clock_now()
        if self.enabled and now - self._last_status >= STATUS_INTERVAL_S:
            self._last_status = now
            self._publish(app)
        while True:
            try:
                name, params, source = self._queue.get_nowait()
            except queue.Empty:
                return
            try:
                self._run(app, name, params)
            except Exception:  # noqa: BLE001 - one bad action must not stop the main loop
                log.exception("Remote action %s (%s) failed", name, source)

    def _publish(self, app: Companion) -> None:
        lists = app.body_lists()
        with self._lock:
            self._known = {"expressions": list(lists.expressions), "gestures": list(lists.gestures),
                           "poses": list(lists.poses)}
            self._status = {
                "version": __version__,
                "plugin_connected": bool(app.transport.connected),
                "link": app.transport.link,
                "mode": app.mode_info(),
                "turn": app.turn_status,
                "mic": app.mic_state(),
                "persona": app.persona_in_use,
                "expressions": list(lists.expressions),
                "gestures": list(lists.gestures),
                "poses": list(lists.poses),
                "gaze": bool(lists.gaze),
                "gaze_atoms": list(lists.gaze_atoms),
                "last_action": dict(self._last_action),
                "actions": dict(ACTIONS),
            }

    def _note(self, name: str, ok: bool, note: str = "") -> None:
        with self._lock:
            self._last_action = {"action": name, "ok": ok, "note": note}
            self._status["last_action"] = dict(self._last_action)
        (log.info if ok else log.warning)("Remote action %s: %s", name, note or ("done" if ok else "failed"))

    def _run(self, app: Companion, name: str, p: dict[str, Any]) -> None:
        note = ""
        ok = True
        if name == "say":
            app.say_text(p["text"], p["interrupt"])
        elif name == "ask":
            app.handle_user_text(p["text"])
        elif name == "event":
            app.handle_scene_event({"text": p["text"]})
        elif name == "stop":
            app.cancel_turns()
            app.stop_speaking()
        elif name == "ptt":
            action = p["action"]
            if app.mic_settings.mode != "ptt":
                ok, note = False, f"push-to-talk needs the microphone mode 'ptt' (it is {app.mic_settings.mode!r})"
            else:
                if action == "toggle":
                    action = "stop" if app.input.ptt_active else "start"
                app.handle_ptt(action == "start")
        elif name == "expression":
            allowed, why = app.tools_allowed()
            if not allowed:
                ok, note = False, why
            else:
                app.emotion.note_ai_expression()  # a chosen face: the words-to-face fallback stays out of this answer
                app.send(app.body_command("expression", name=p["name"], intensity=p["intensity"], blend=p["blend"],
                                          hold=p.get("hold")))
        else:  # gesture / pose / look: the same resolution (and the same switches) as the AI's body tools
            tool = {"gesture": "express", "pose": "pose", "look": "look_at"}[name]
            if name == "gesture":
                args: dict[str, Any] = {"gesture": p["name"]}
            elif name == "pose":
                args = {"name": p["name"]}
            else:
                args = {"target": p.get("atom") if p["target"] == "atom" else p["target"], "seconds": p["seconds"]}
            commands, result = app.tool_commands(tool, args)
            if not commands:
                ok, note = False, str(result.get("error") or "not possible")
            for command in commands:
                app.send(command)
        self._note(name + _brief(p), ok, note)


def _brief(params: dict[str, Any]) -> str:
    shown = {k: (v if not isinstance(v, str) or len(v) <= 40 else v[:37] + "...") for k, v in params.items()}
    return " " + str(shown) if shown else ""
