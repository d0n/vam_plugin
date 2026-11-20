"""Remote control (version 31): actions, the HTTP API's protection, OSC, config handling and the run on the main loop."""
from __future__ import annotations

import http.client
import json
import socket
import struct
import tempfile
import unittest
from pathlib import Path

from aibody_companion import settings_file
from aibody_companion.remote import RemoteControl, RemoteError, parse_action
from aibody_companion.remote import http_server as http_module
from aibody_companion.remote import osc as osc_module
from tests.fakes import FakeClock, FakePlugin
from tests.test_e2e_simulation import Sim

TOKEN = "t" * 24


def osc_message(address: str, *args) -> bytes:
    def pad(b: bytes) -> bytes:
        b += b"\x00"
        return b + b"\x00" * (-len(b) % 4)

    tags, body = ",", b""
    for a in args:
        if isinstance(a, bool):
            tags += "T" if a else "F"
        elif isinstance(a, int):
            tags += "i"
            body += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"
            body += struct.pack(">f", a)
        else:
            tags += "s"
            body += pad(str(a).encode())
    return pad(address.encode()) + pad(tags.encode()) + body


class ParseActionTests(unittest.TestCase):
    def test_valid_actions(self):
        self.assertEqual(parse_action("say", {"text": " Hi "}), {"text": "Hi", "interrupt": False})
        self.assertEqual(parse_action("say", {"text": "x", "interrupt": "true"})["interrupt"], True)
        self.assertEqual(parse_action("expression", {"name": "happy"}),
                         {"name": "happy", "intensity": 1.0, "blend": 0.4})
        self.assertEqual(parse_action("expression", {"name": "happy", "hold": 3})["hold"], 3.0)
        self.assertEqual(parse_action("look", {"target": "Client"}), {"target": "client", "seconds": 0.0})
        self.assertEqual(parse_action("look", {"target": "atom:Lamp", "seconds": 5}),
                         {"target": "atom", "seconds": 5.0, "atom": "Lamp"})
        self.assertEqual(parse_action("ptt", {"action": "TOGGLE"}), {"action": "toggle"})
        self.assertEqual(parse_action("stop", None), {})

    def test_invalid_actions_are_refused(self):
        bad = [("unknown", {}), ("say", {}), ("say", {"text": "  "}), ("say", {"text": 5}), ("say", {"text": "x" * 1001}),
               ("say", {"text": "x", "interrupt": "maybe"}), ("say", []), ("expression", {"name": "a", "intensity": 2}),
               ("expression", {"name": "a", "blend": "fast"}), ("look", {"target": "moon"}),
               ("look", {"target": "atom"}), ("look", {"target": "client", "seconds": 999}),
               ("ptt", {"action": "hold"}), ("gesture", {"name": ""})]
        for name, params in bad:
            with self.assertRaises(RemoteError, msg=f"{name} {params}"):
                parse_action(name, params)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.remote = RemoteControl({"enabled": True, "http_port": 0, "osc_port": 0, "token": TOKEN})
        self.lines = self.remote.start()
        self.port = self.remote.http_bound_port
        self.addCleanup(self.remote.stop)
        http_module.WRONG_TOKEN_DELAY_S = 0.0

    def call(self, method, path, body=None, headers=None, host=None, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if headers:
            h.update(headers)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if data is not None and "Content-Type" not in h:
            h["Content-Type"] = "application/json"
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for k, v in h.items():
            conn.putheader(k, v)
        if data is not None:
            conn.putheader("Content-Length", str(len(data)))
        conn.endheaders(data)
        r = conn.getresponse()
        payload = r.read()
        conn.close()
        return r.status, payload, r

    AUTH = {"Authorization": f"Bearer {TOKEN}"}

    def test_binds_loopback_only_and_announces_it(self):
        self.assertTrue(self.port > 0)
        server = self.remote._http._server
        self.assertEqual(server.server_address[0], "127.0.0.1")
        self.assertIn("this computer only", self.lines[0])
        text = Path(http_module.__file__).read_text()
        self.assertNotIn("0.0.0.0", text.replace('"0.0.0.0"', "").replace("never 0.0.0.0", ""))

    def test_page_needs_no_token_and_holds_no_secret(self):
        status, body, r = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"AIBody remote", body)
        self.assertNotIn(TOKEN.encode(), body)
        self.assertIn("default-src 'none'", r.getheader("Content-Security-Policy"))
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))
        self.assertNotIn(b"http://", body.replace(b"http://127.0.0.1:PORT", b""), "no external request in the page")

    def test_api_needs_the_token(self):
        self.assertEqual(self.call("GET", "/api/status")[0], 401)
        self.assertEqual(self.call("GET", "/api/status", headers={"Authorization": "Bearer wrong"})[0], 401)
        self.assertEqual(self.call("GET", f"/api/status?token={TOKEN}")[0], 401, "no token in the address")
        status, body, _ = self.call("GET", "/api/status", headers=self.AUTH)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        status, _, _ = self.call("GET", "/api/status", headers={"X-AIBody-Token": TOKEN})
        self.assertEqual(status, 200)
        self.assertEqual(self.call("POST", "/api/stop", {}, headers={})[0], 401)
        self.assertTrue(self.remote._queue.empty(), "nothing queued without the token")

    def test_dns_rebinding_and_foreign_origins_are_refused(self):
        self.assertEqual(self.call("GET", "/", host="evil.example:80")[0], 403)
        self.assertEqual(self.call("GET", "/api/status", headers=self.AUTH, host="evil.example")[0], 403)
        self.assertEqual(self.call("POST", "/api/stop", {}, headers={**self.AUTH, "Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.call("POST", "/api/stop", {}, headers={**self.AUTH, "Origin": f"http://127.0.0.1:{self.port}"})[0], 200)
        self.assertEqual(self.call("GET", "/", host=f"localhost:{self.port}")[0], 200)

    def test_post_validation(self):
        ok, _, _ = self.call("POST", "/api/say", {"text": "Hello"}, headers=self.AUTH)
        self.assertEqual(ok, 200)
        self.assertEqual(self.remote._queue.get_nowait()[:2], ("say", {"text": "Hello", "interrupt": False}))
        self.assertEqual(self.call("POST", "/api/say", {}, headers=self.AUTH)[0], 400)
        self.assertEqual(self.call("POST", "/api/nope", {}, headers=self.AUTH)[0], 404)
        self.assertEqual(self.call("GET", "/api/say", headers=self.AUTH)[0], 405)
        self.assertEqual(self.call("PUT", "/api/say", {"text": "x"}, headers=self.AUTH)[0], 405)
        self.assertEqual(self.call("OPTIONS", "/api/say", headers=self.AUTH)[0], 405, "no CORS preflight")
        self.assertEqual(self.call("POST", "/api/say", raw=b"{bad", headers=self.AUTH)[0], 400)
        self.assertEqual(self.call("POST", "/api/say", raw=b'{"text":"x"}', headers={**self.AUTH, "Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.call("POST", "/api/say", raw=b"x" * (http_module.MAX_BODY_BYTES + 1), headers=self.AUTH)[0], 413)
        self.assertEqual(self.call("POST", "/api/say", raw=b"[1]", headers=self.AUTH)[0], 400)
        self.assertEqual(self.call("GET", "/etc/passwd", headers=self.AUTH)[0], 404)

    def test_queue_is_bounded(self):
        for _ in range(50):
            self.remote.submit("stop", {})
        with self.assertRaises(RemoteError):
            self.remote.submit("stop", {})
        self.assertEqual(self.call("POST", "/api/stop", {}, headers=self.AUTH)[0], 400)

    def test_port_in_use_keeps_http_off_with_a_message(self):
        other = RemoteControl({"enabled": True, "http_port": self.port, "osc_port": 0, "token": TOKEN})
        other.start()
        self.assertEqual(other.http_bound_port, 0)
        self.assertTrue(any("could not be opened" in e for e in other.errors), other.errors)

    def test_short_token_keeps_http_off(self):
        short = RemoteControl({"enabled": True, "http_port": 0, "token": "abc"})
        self.assertEqual(short.start(), [])
        self.assertEqual(short.http_bound_port, 0)
        self.assertTrue(short.errors)

    def test_disabled_opens_nothing(self):
        off = RemoteControl({"enabled": False, "http_port": 0, "osc_port": 0, "token": TOKEN})
        self.assertEqual(off.start(), [])
        self.assertEqual((off.http_bound_port, off.osc_bound_port), (0, 0))


class OscTests(unittest.TestCase):
    def setUp(self):
        self.remote = RemoteControl({"enabled": True, "http_port": 0, "osc_port": 0, "token": ""})
        self.server = osc_module.OscServer(self.remote, 0)

    def test_messages_become_actions(self):
        cases = [
            (osc_message("/aibody/say", "Hello there", 1), ("say", {"text": "Hello there", "interrupt": True})),
            (osc_message("/aibody/ask", "Why?"), ("ask", {"text": "Why?"})),
            (osc_message("/aibody/expression", "happy", 0.5), ("expression", {"name": "happy", "intensity": 0.5, "blend": 0.4})),
            (osc_message("/aibody/gesture", "wave"), ("gesture", {"name": "wave"})),
            (osc_message("/aibody/look", "atom:Lamp", 4), ("look", {"target": "atom", "atom": "Lamp", "seconds": 4.0})),
            (osc_message("/aibody/ptt", 1), ("ptt", {"action": "start"})),
            (osc_message("/aibody/ptt", "toggle"), ("ptt", {"action": "toggle"})),
            (osc_message("/aibody/stop"), ("stop", {})),
        ]
        for packet, (name, params) in cases:
            self.assertEqual(self.server.handle(packet), 1, name)
            got = self.remote._queue.get_nowait()
            self.assertEqual((got[0], got[1]), (name, params))
            self.assertEqual(got[2], "osc")

    def test_bundle_and_garbage(self):
        a, b = osc_message("/aibody/stop"), osc_message("/aibody/gesture", "wave")
        bundle = b"#bundle\x00" + b"\x00" * 8 + struct.pack(">i", len(a)) + a + struct.pack(">i", len(b)) + b
        self.assertEqual(self.server.handle(bundle), 2)
        for junk in (b"", b"hello", b"\xff\xfe\x00", osc_message("/other/say", "x"), osc_message("/aibody/say"),
                     osc_message("/aibody/say", ""), osc_message("/aibody/unknown", "x"),
                     b"#bundle\x00" + b"\x00" * 8 + struct.pack(">i", 999) + b"x"):
            self.assertEqual(self.server.handle(junk), 0, junk)

    def test_real_socket_loopback_only(self):
        self.server.start()
        self.addCleanup(self.server.stop)
        self.assertEqual(self.server._sock.getsockname()[0], "127.0.0.1")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(osc_message("/aibody/stop"), ("127.0.0.1", self.server.port))
        s.close()
        got = None
        for _ in range(50):
            try:
                got = self.remote._queue.get(timeout=0.1)
                break
            except Exception:  # noqa: BLE001
                pass
        self.assertEqual(got[0] if got else None, "stop")


class SettingsTests(unittest.TestCase):
    def test_defaults_are_off_and_loopback_documented(self):
        d = settings_file.defaults()["remote"]
        self.assertEqual(d, {"enabled": False, "http_port": 38438, "osc_port": 0, "token": ""})
        self.assertIn("remote", settings_file.COMPANION_CATEGORIES)

    def test_ensure_token_generates_once_and_keeps_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"version": 1, "ai": {"mode": "qa"}, "remote": {"enabled": True, "http_port": 40000}}))
            remote = {"enabled": True, "token": ""}
            token = settings_file.ensure_remote_token(path, remote)
            self.assertGreaterEqual(len(token), 16)
            data = json.loads(path.read_text())
            self.assertEqual(data["remote"]["token"], token)
            self.assertEqual(data["remote"]["http_port"], 40000)
            self.assertEqual(data["ai"], {"mode": "qa"})
            self.assertEqual(settings_file.ensure_remote_token(path, {"token": ""}), token, "reused, not regenerated")
            self.assertEqual(settings_file.ensure_remote_token(Path(tmp) / "missing.json", {"token": ""}), "")

    def test_token_is_redacted_in_logs(self):
        from aibody_companion import logsetup

        class Cfg:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{}")
            token = settings_file.ensure_remote_token(path, {"token": ""})
            self.assertNotIn(token, logsetup.redact(f"token is {token}"))

    def test_plugin_keeps_the_remote_section(self):
        text = (Path(__file__).resolve().parents[2] / "src/AIBody/AIBody.cs").read_text(encoding="utf-8")
        self.assertIn('existing["remote"]', text)
        self.assertIn('root["remote"] = remote', text)


class MainLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.sim = Sim(self.tmp.name, self.clock, mode="chain")
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(Path(self.tmp.name), self.clock, mode="chain")
        self.plugin.poses = ["sit"]
        self.plugin.start()
        self.remote = RemoteControl({"enabled": True, "http_port": 0, "osc_port": 0, "token": TOKEN})
        self.app.remote = self.remote  # not started: no sockets, the queue is used directly
        self.sim.run(self.plugin, 3)

    def sent(self, type_):
        return self.sim.sent(self.plugin, type_)

    def test_say_speaks_exactly_this_text_without_the_language_model(self):
        self.remote.submit("say", {"text": "Good evening. How are you?"})
        self.sim.run(self.plugin, 2)
        self.assertEqual([s["text"] for s in self.sent("speak")], ["Good evening.", "How are you?"])
        self.assertEqual(self.sent("speak")[0]["queue"], "append")

    def test_say_with_interrupt_interrupts_with_the_first_sentence_only(self):
        self.remote.submit("say", {"text": "One. Two.", "interrupt": True})
        self.sim.run(self.plugin, 2)
        self.assertEqual([s["queue"] for s in self.sent("speak")], ["interrupt", "append"])

    def test_ask_goes_through_the_answer_path(self):
        self.remote.submit("ask", {"text": "Hello"})
        self.sim.run(self.plugin, 2)
        self.assertTrue(self.sent("speak"), "the echo engine answers")

    def test_body_actions_become_plugin_commands(self):
        self.plugin.poses = ["Sit Down"]
        self.sim.run(self.plugin, 2)
        self.remote.submit("expression", {"name": "HAPPY", "intensity": 0.7, "blend": 1})
        self.remote.submit("pose", {"name": "sit down."})
        self.remote.submit("stop", {})
        self.sim.run(self.plugin, 1)
        expr = [e for e in self.sent("expression") if e["name"] == "happy" and e.get("intensity") == 0.7]
        self.assertEqual(len(expr), 1, "the plugin's own spelling is used")
        self.assertEqual(self.sent("pose")[-1]["json"], '{"pose":"Sit Down"}', "pose commands go through the gate")
        self.assertEqual(self.sent("pose")[-1]["command"], "Sit Down")
        self.assertTrue(self.sent("stop_speaking"))
        self.assertEqual(self.remote.status()["last_action"]["action"].split(" ")[0], "stop")

    def test_unknown_names_are_refused_once_the_lists_are_known(self):
        self.sim.run(self.plugin, 2)
        self.remote.process(self.app)
        with self.assertRaises(RemoteError) as e:
            self.remote.submit("expression", {"name": "furious"})
        self.assertIn("neutral", str(e.exception))
        self.remote.submit("pose", {"name": "please sit down"})  # accepted for the queue, refused by the gate
        self.sim.run(self.plugin, 1)
        self.assertEqual(self.sent("pose"), [])
        self.assertFalse(self.remote.status()["last_action"]["ok"])

    def test_body_control_off_and_gaze_off_are_respected(self):
        self.plugin.body_control = False
        self.sim.run(self.plugin, 3)
        self.remote.submit("expression", {"name": "happy"})
        self.remote.submit("look", {"target": "client"})
        self.sim.run(self.plugin, 1)
        self.assertEqual([e for e in self.sent("expression") if e.get("intensity") == 1.0 and e["name"] == "happy"], [])
        self.assertEqual(self.sent("look_at"), [])
        self.assertFalse(self.remote.status()["last_action"]["ok"])

    def test_status_snapshot(self):
        self.sim.run(self.plugin, 1)
        s = self.remote.status()
        self.assertTrue(s["plugin_connected"])
        self.assertIn("happy", s["expressions"])
        self.assertIn("say", s["actions"])
        self.assertNotIn(TOKEN, json.dumps(s))

    def test_ptt_needs_the_ptt_mode(self):
        self.remote.submit("ptt", {"action": "start"})
        self.sim.run(self.plugin, 1)
        self.assertFalse(self.remote.status()["last_action"]["ok"])

    def test_http_post_reaches_the_plugin_through_the_main_loop(self):
        remote = RemoteControl({"enabled": True, "http_port": 0, "osc_port": 0, "token": TOKEN})
        remote.start()
        self.addCleanup(remote.stop)
        self.app.remote = remote
        conn = http.client.HTTPConnection("127.0.0.1", remote.http_bound_port, timeout=5)
        conn.request("POST", "/api/say", json.dumps({"text": "Over HTTP."}),
                     {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
        self.assertEqual(conn.getresponse().status, 200)
        self.sim.run(self.plugin, 2)
        self.assertEqual([s["text"] for s in self.sent("speak")], ["Over HTTP."])
        conn.request("GET", "/api/status", headers={"Authorization": f"Bearer {TOKEN}"})
        status = json.loads(conn.getresponse().read())
        self.assertTrue(status["plugin_connected"])
        self.assertTrue(status["last_action"]["ok"])

    def test_remote_is_off_by_default_in_the_app(self):
        from aibody_companion.cli import start_remote

        self.assertIsNone(start_remote(self.sim.cfg, self.app))
        self.assertEqual(self.sim.cfg.remote["enabled"], False)


class SourceRuleTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2]

    def test_remote_code_has_no_wildcard_bind_and_no_outgoing_requests(self):
        for path in (self.ROOT / "companion/aibody_companion/remote").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('("", ', text, path.name)
            self.assertNotIn("urlopen", text, path.name)
            self.assertNotIn("import requests", text, path.name)
        core = (self.ROOT / "companion/aibody_companion/remote/core.py").read_text(encoding="utf-8")
        self.assertIn('LOOPBACK = "127.0.0.1"', core)

    def test_plugin_has_no_new_network_code(self):
        for path in (self.ROOT / "src/AIBody").glob("*.cs"):
            if path.name != "SocketLink.cs":
                self.assertNotIn("System.Net", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
