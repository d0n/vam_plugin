"""Version 61: the Grok Bot bridge (optional driver next to the direct method, opt-in installer step), own emotion
keywords and gestures from yes / no, and the scene-load guard of the IdlePoser attach (crash review of v60)."""
from __future__ import annotations

import http.client
import io
import json
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path

from aibody_companion import bridge, emotion, grok_bot_setup, settings_file
from aibody_companion.remote import RemoteControl
from aibody_companion.remote import http_server as http_module
from tests.fakes import FakeClock, FakePlugin
from tests.test_e2e_simulation import Sim

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
TOKEN = "b" * 24


class BridgeQueueTests(unittest.TestCase):
    def test_driver_names(self):
        self.assertEqual(bridge.normalize_driver("grok_bot"), "grok_bot")
        self.assertEqual(bridge.normalize_driver("Grok-Bot"), "grok_bot")
        for value in ("", None, "direct", "anything"):
            self.assertEqual(bridge.normalize_driver(value), "direct")

    def test_ids_since_and_limit(self):
        q = bridge.BridgeQueue(clock=lambda: 5.0, max_events=3)
        for i in range(5):
            q.push("user_said", text=f"t{i}")
        self.assertEqual(q.last_id, 5)
        self.assertEqual([e["id"] for e in q.since(0)], [3, 4, 5], "old events dropped, the gap shows in the ids")
        self.assertEqual([e["text"] for e in q.since(4)], ["t4"])
        self.assertEqual(q.since(5), [])
        with self.assertRaises(ValueError):
            q.push("bogus")

    def test_long_poll_wakes_up_on_a_new_event(self):
        q = bridge.BridgeQueue()
        threading.Timer(0.1, lambda: q.push("scene_event", text="door")).start()
        t = time.monotonic()
        events = q.since(0, wait_s=3)
        self.assertEqual([e["text"] for e in events], ["door"])
        self.assertLess(time.monotonic() - t, 2.5)
        self.assertEqual(q.since(1, wait_s=0.05), [])


class DriverTests(unittest.TestCase):
    """ai.driver: direct by default; grok_bot hands what the user says to the bridge instead of the language model."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.sim = Sim(self.tmp.name, self.clock, mode="chain")
        self.app = self.sim.start_app()
        self.plugin = FakePlugin(Path(self.tmp.name), self.clock, mode="chain")
        self.plugin.start()
        self.sim.run(self.plugin, 3)
        http_module.WRONG_TOKEN_DELAY_S = 0.0

    def open_remote(self):
        remote = RemoteControl({"enabled": True, "http_port": 0, "osc_port": 0, "token": TOKEN})
        remote.start()
        self.addCleanup(remote.stop)
        remote.bridge = self.app.bridge
        self.app.remote = remote
        return remote

    def test_default_is_the_direct_method(self):
        self.assertEqual(settings_file.DEFAULTS["ai"]["driver"], "direct")
        self.assertEqual(self.app.driver, "direct")
        self.app.handle_user_text("Hello")
        self.sim.run(self.plugin, 2)
        self.assertTrue(self.sim.sent(self.plugin, "speak"), "the app's own AI (echo) answers")
        self.assertEqual(self.app.bridge.last_id, 0)

    def test_grok_bot_without_the_remote_falls_back_to_direct(self):
        self.app.engine_set.ai["driver"] = "grok_bot"
        info = self.app.driver_info()
        self.assertEqual((info["requested"], info["active"]), ("grok_bot", "direct"))
        self.assertIn("remote.enabled", info["note"])
        self.app.handle_user_text("Hello")
        self.sim.run(self.plugin, 2)
        self.assertTrue(self.sim.sent(self.plugin, "speak"), "never without an AI")

    def test_grok_bot_gets_the_words_and_answers_over_http(self):
        self.app.engine_set.ai["driver"] = "grok_bot"
        remote = self.open_remote()
        self.assertEqual(self.app.driver, "grok_bot")
        ok, why = self.app._want_realtime()
        self.assertFalse(ok)
        self.assertIn("Grok Bot", why)
        self.app.handle_user_text("How are you?")
        self.app.handle_scene_event({"text": "the door opens"})
        self.sim.run(self.plugin, 2)
        self.assertEqual(self.sim.sent(self.plugin, "speak"), [], "no answer of the app's own AI")
        conn = http.client.HTTPConnection("127.0.0.1", remote.http_bound_port, timeout=5)
        conn.request("GET", "/api/bridge/events?after=0", headers={"Authorization": f"Bearer {TOKEN}"})
        data = json.loads(conn.getresponse().read())
        self.assertTrue(data["ok"])
        self.assertEqual([(e["type"], e["text"]) for e in data["events"]],
                         [("user_said", "How are you?"), ("scene_event", "the door opens")])
        self.assertEqual(data["events"][0]["source"], "typed")
        self.assertEqual(data["driver"]["active"], "grok_bot")
        conn.request("GET", f"/api/bridge/events?after={data['last_id']}", headers={"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(json.loads(conn.getresponse().read())["events"], [])
        conn.request("POST", "/api/say", json.dumps({"text": "Fine, thanks."}),
                     {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
        self.assertEqual(conn.getresponse().status, 200)
        self.sim.run(self.plugin, 2)
        self.assertEqual([s["text"] for s in self.sim.sent(self.plugin, "speak")], ["Fine, thanks."])
        conn.request("GET", "/api/status", headers={"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(json.loads(conn.getresponse().read())["driver"]["active"], "grok_bot")

    def test_bridge_route_needs_the_token_and_valid_numbers(self):
        remote = self.open_remote()
        conn = http.client.HTTPConnection("127.0.0.1", remote.http_bound_port, timeout=5)
        conn.request("GET", "/api/bridge/events")
        self.assertEqual(conn.getresponse().status, 401)
        for query in ("after=x", "wait=-1", "wait=nan"):
            conn.request("GET", f"/api/bridge/events?{query}", headers={"Authorization": f"Bearer {TOKEN}"})
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 400, query)

    def test_mute_words_still_work_locally_with_grok_bot(self):
        self.app.engine_set.ai["driver"] = "grok_bot"
        self.open_remote()
        self.app.handle_user_text("shut up")
        self.sim.run(self.plugin, 1)
        self.assertTrue(self.app.muted)
        self.assertEqual(self.app.bridge.last_id, 0, "a mute word never reaches Grok Bot")

    def test_no_proactive_nudges_with_grok_bot(self):
        self.app.engine_set.ai["driver"] = "grok_bot"
        self.open_remote()
        self.assertFalse(self.app._can_nudge_engine())

    def test_config_choice_is_validated(self):
        _, errors = settings_file.validate({"ai": {"driver": "grok_bot"}})
        self.assertEqual(errors, [])
        cfg, errors = settings_file.validate({"ai": {"driver": "skynet"}})
        self.assertEqual(cfg["ai"]["driver"], "direct")
        self.assertTrue(any("ai.driver" in e for e in errors))


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class GrokBotSetupTests(unittest.TestCase):
    FEED = json.dumps({"version": "1.2.3",
                       "downloadUrl": "https://downloads.cursor.com/grokbot/stable/win32-x64/1.2.3/Grok_Bot_1.2.3_Setup.exe"})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.urls: list[str] = []
        self.runs: list[list[str]] = []

    def opener(self, request, timeout):
        self.urls.append(request.full_url)
        return _Response(self.FEED.encode() if "api2.cursor.sh" in request.full_url else b"MZ-installer")

    def run_cmd(self, args, timeout, check):
        self.runs.append(args)

        class R:
            returncode = 0
        return R()

    def test_feed_and_url_check(self):
        self.assertEqual(grok_bot_setup.windows_platform("AMD64"), "win32-x64-user")
        self.assertEqual(grok_bot_setup.windows_platform("ARM64"), "win32-arm64-user")
        url, version = grok_bot_setup.installer_url(self.FEED.encode())
        self.assertEqual(version, "1.2.3")
        for bad in ('{"downloadUrl": "http://downloads.cursor.com/x.exe"}', '{"downloadUrl": "https://evil.example/x.exe"}',
                    '{"downloadUrl": "https://downloads.cursor.com/x.msi"}', "not json", "[]"):
            with self.assertRaises(grok_bot_setup.SetupError, msg=bad):
                grok_bot_setup.installer_url(bad.encode())

    def test_local_installs_silently_and_switches_to_the_bridge(self):
        path = settings_file.settings_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"ai": {"mode": "auto", "driver": "direct"}, "body": {"breathing": "true"}}))
        code = grok_bot_setup.run_setup("local", self.root, opener=self.opener, run=self.run_cmd, machine="AMD64",
                                        temp_dir=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(self.urls[0], "https://api2.cursor.sh/updates/api/download/stable/win32-x64-user/sand")
        self.assertEqual(self.runs, [[str(self.root / "Grok_Bot_1.2.3_Setup.exe"), "/S"]])
        data = json.loads(path.read_text())
        self.assertEqual(data["ai"], {"mode": "auto", "driver": "grok_bot"})
        self.assertTrue(data["remote"]["enabled"])
        self.assertEqual(data["body"], {"breathing": "true"}, "the rest stays")
        log = (self.root / "Saves/PluginData/AIBody/logs/grok_bot_setup.log").read_text()
        self.assertIn("sign in with your Cursor account", log)

    def test_failures_never_raise_and_keep_the_direct_method(self):
        def broken(request, timeout):
            raise OSError("offline")
        self.assertEqual(grok_bot_setup.run_setup("local", self.root, opener=broken, run=self.run_cmd), 1)
        self.assertFalse(settings_file.settings_path(self.root).exists())
        self.assertIn("keeps the direct method", (self.root / "Saves/PluginData/AIBody/logs/grok_bot_setup.log").read_text())
        self.assertEqual(grok_bot_setup.run_setup("cloud", self.root), 0)
        self.assertEqual(self.runs, [], "cloud installs nothing")
        self.assertFalse(settings_file.settings_path(self.root).exists())

    def test_installer_task_is_opt_in(self):
        iss = (ROOT / "packaging/companion/AIBodyCompanion.iss").read_text(encoding="utf-8")
        line = next(l for l in iss.splitlines() if l.startswith('Name: "grokbot";'))
        self.assertIn("Flags: unchecked", line)
        self.assertIn("Tasks: grokbot\\local", iss)
        self.assertIn("--setup-grok-bot local", iss)
        self.assertIn("--setup-grok-bot cloud", iss)
        self.assertIn('choices=("local", "cloud")', (ROOT / "companion/aibody_companion/winapp.py").read_text())


class EmotionV61Tests(unittest.TestCase):
    def test_own_keywords_add_to_the_rules(self):
        rules = emotion.own_rules({"happy": "juhu, mega*", "sad": "", "bogus": "x"})
        self.assertEqual(set(rules), {"happy"})
        self.assertIsNone(emotion.classify("Juhu, megastark!"))
        self.assertEqual(emotion.classify("Juhu, megastark!", rules), "happy")
        self.assertEqual(emotion.parse_keywords(" A , b* ,, " + "x" * 50), (("b",), ("a",)))

    def test_yes_and_no_at_the_start(self):
        for text, kind in (("Yes, of course.", "yes"), ("Ja klar!", "yes"), ("Nein, das nicht.", "no"),
                           ("Nope.", "no"), ("No problem!", None), ("Nobody knows.", None), ("I think so.", None),
                           ("Klarer Fall.", None)):
            self.assertEqual(emotion.classify_answer(text), kind, text)

    def test_gesture_once_per_answer_only_when_on_and_the_ai_chose_none(self):
        d = emotion.EmotionDirector({}, clock=lambda: 0.0)
        d.begin_answer()
        self.assertIsNone(d.gesture_for_speech("Yes.", ["nod", "shake"]), "off by default")
        d.configure({"gestures": True})
        d.begin_answer()
        self.assertEqual(d.gesture_for_speech("Yes, sure.", ["Nod", "shake"]), "Nod")
        self.assertIsNone(d.gesture_for_speech("Yes again.", ["nod"]), "first sentence only")
        d.begin_answer()
        d.note_ai_gesture()
        self.assertIsNone(d.gesture_for_speech("No.", ["shake"]), "the AI's own gesture wins")
        d.begin_answer()
        self.assertIsNone(d.gesture_for_speech("No.", ["nod"]), "only gestures the plugin has")


class IdlePoserLoadGuardTests(unittest.TestCase):
    """Crash review of v60: IdlePoser is never looked for or added while VaM loads a scene."""

    def test_find_waits_for_the_scene_load(self):
        link = (SRC / "IdlePoserLink.cs").read_text(encoding="utf-8")
        self.assertIn("public void Find(float dt, bool add, bool loading)", link)
        self.assertIn("if (loading) { _sinceLoad = 0f; return; }", link)
        self.assertIn("public const float LoadGraceSeconds = 3f;", link)
        body = (SRC / "Body.cs").read_text(encoding="utf-8")
        i, j = body.index("bool loading = SuperController.singleton"), body.index("_poser.Find(dt,")
        self.assertLess(i, j, "loading is known before Find runs")
        self.assertIn("_poser.Find(dt, _idleMove.Enabled && BodyControl, loading)", body)

    def test_duplicate_instances_are_switched_off(self):
        link = (SRC / "IdlePoserLink.cs").read_text(encoding="utf-8")
        search = link[link.index("private JSONStorable Search()"):link.index("private static void Switch(")]
        self.assertIn("Switch(s, false);", search)
        self.assertTrue(re.search(r"if \(found == null\) \{ found = s; continue; \}", search))
