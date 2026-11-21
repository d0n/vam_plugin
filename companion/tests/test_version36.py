"""Version 36 (Leon, 20.11.2026): background color in the plugin (greenscreen), the two independent setup points
(background + color / Scene or Plugin, Abort on the first step), and latency work without any new feature."""
from __future__ import annotations

import argparse
import colorsys
import http.server
import json
import re
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from aibody_companion import __version__, atomicfile, cli, settings_file, wakeup
from aibody_companion import setup as first_start
from aibody_companion.pipeline import http as http_module
from aibody_companion.pipeline.sentences import FIRST_CLAUSE_MIN, SentenceSplitter

from .test_plugin_menu import method_body, source

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"
GREEN = {"h": "0.3333333", "s": "1", "v": "1"}


def plugin_after(config: dict, scene_storable: dict | None) -> tuple[bool, dict]:
    """Python model of AIBodyPlugin: the scene's saved values (or the defaults: OFF, green) and then
    ApplyBackgroundSetup(config.json). The C# side is checked against this model in PluginSetupSourceTests."""
    toggle, color = False, dict(GREEN)
    if scene_storable is not None:
        toggle = scene_storable.get(first_start.TOGGLE_NAME, "false") == "true"
        color = scene_storable.get(first_start.COLOR_NAME, color)
    setup, ui = config.get("setup", {}), config.get("ui", {})
    applied = int(ui.get("background_setup_applied", 0))
    if setup.get("asked") and int(setup.get("revision", 0)) > applied and setup.get("background"):
        color = first_start.hsv_of(setup.get("background_color", "#00FF00"))
        toggle = True
    return toggle, color


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        settings_file.write_defaults_if_missing(settings_file.settings_path(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def answer(self, *answers):
        asked, said = [], []
        replies = list(answers)

        def ask(prompt):
            asked.append(prompt)
            return replies.pop(0)
        result = first_start.run(self.root, ask=ask, say=said.append)
        self.assertEqual(replies, [], "every answer was used")
        return result, asked, said

    def config(self):
        return json.loads(settings_file.settings_path(self.root).read_text(encoding="utf-8"))

    def scene(self):
        return json.loads((self.root / first_start.SCENE_REL).read_text(encoding="utf-8"))

    def aibody_storable(self, scene):
        for atom in scene["atoms"]:
            for st in atom["storables"]:
                if st["id"] == first_start.AIBODY_STORABLE:
                    return atom["id"], st
        self.fail("no AIBody storable in the scene")

    def test_order_background_then_color_then_choice(self):
        _, asked, said = self.answer("yes", "", "scene")
        self.assertEqual(asked, ["Do you want a greenscreen background? [yes/no/abort]: ",
                                 "Set your color for transparency [#00FF00]: ", "Your choice [scene/plugin]: "])
        self.assertTrue(any(s.startswith("Choose what to use:\n  1) Scene") and "2) Plugin" in s for s in said))
        _, asked, _ = self.answer("no", "plugin")
        self.assertEqual(len(asked), 2, "no color question after 'no'")

    def test_1_background_yes_and_scene(self):
        result, _, _ = self.answer("yes", "#8000ff", "scene")
        self.assertEqual(result["choice"], "scene")
        holder, st = self.aibody_storable(self.scene())
        self.assertEqual(holder, "Client")  # version 42 (Leon 18:27): AIBody on the male Client, before on BryanGosling
        self.assertEqual(st[first_start.TOGGLE_NAME], "true")
        self.assertEqual(st[first_start.COLOR_NAME], first_start.hsv_of("#8000FF"))
        toggle, color = plugin_after(self.config(), st)
        self.assertTrue(toggle)
        self.assertEqual(color, first_start.hsv_of("#8000FF"))

    def test_2_background_yes_and_plugin_only_purple(self):
        """Leon's example: purple, background yes, NOT Scene -> background on (toggle ON, purple), no scene."""
        result, _, said = self.answer("y", "#800080", "plugin")
        self.assertFalse((self.root / first_start.SCENE_REL).exists(), "no scene is written")
        self.assertIsNone(result["scene_path"])
        setup = self.config()["setup"]
        self.assertEqual(setup, {"asked": True, "background": True, "background_color": "#800080", "choice": "plugin",
                                 "revision": 1})
        toggle, color = plugin_after(self.config(), None)  # the user's own scene, no AIBody values saved
        self.assertTrue(toggle)
        self.assertEqual(color, first_start.hsv_of("#800080"))
        self.assertTrue(any("Plugins > Add Plugin" in s for s in said))

    def test_3_background_no_and_scene(self):
        """Scene yes + background no -> the scene without background color, the toggle stays OFF."""
        self.answer("no", "scene")
        _, st = self.aibody_storable(self.scene())
        self.assertEqual(st[first_start.TOGGLE_NAME], "false")
        self.assertEqual(plugin_after(self.config(), st)[0], False)

    def test_4_background_no_and_plugin(self):
        self.answer("n", "2")
        self.assertFalse((self.root / first_start.SCENE_REL).exists())
        self.assertEqual(self.config()["setup"]["choice"], "plugin")
        self.assertEqual(plugin_after(self.config(), None), (False, GREEN), "defaults: OFF, green")

    def test_abort_on_the_first_step_changes_nothing(self):
        before = settings_file.settings_path(self.root).read_text(encoding="utf-8")
        result, asked, said = self.answer("abort")
        self.assertTrue(result["aborted"])
        self.assertEqual(len(asked), 1)
        self.assertEqual(settings_file.settings_path(self.root).read_text(encoding="utf-8"), before)
        self.assertFalse((self.root / first_start.SCENE_REL).exists())
        self.assertFalse(first_start.already_asked(self.root), "asked again on the next start")
        self.assertTrue(any("Setup aborted" in s for s in said))

    def test_invalid_answers_ask_again_and_enter_keeps_green(self):
        _, _, said = self.answer("maybe", "yes", "blue", "#12345", "", "later", "s")
        self.assertIn("Please answer yes, no or abort.", said)
        self.assertEqual(sum("Please type a color as #RRGGBB" in s for s in said), 2)
        self.assertIn("Please answer scene or plugin.", said)
        self.assertEqual(self.config()["setup"]["background_color"], "#00FF00")
        self.assertEqual(first_start.hsv_of("#00FF00"), GREEN)

    def test_new_revision_applies_once_and_again_after_a_new_setup(self):
        self.answer("yes", "#FF0000", "plugin")
        cfg = self.config()
        self.assertTrue(plugin_after(cfg, None)[0])
        cfg["ui"]["background_setup_applied"] = cfg["setup"]["revision"]  # what the plugin writes back
        self.assertFalse(plugin_after(cfg, None)[0], "applied once: switching it off later in VaM sticks")
        settings_file.settings_path(self.root).write_text(json.dumps(cfg), encoding="utf-8")
        self.answer("yes", "#0000FF", "plugin")
        cfg = self.config()
        self.assertEqual(cfg["setup"]["revision"], 2)
        self.assertEqual(plugin_after(cfg, None), (True, first_start.hsv_of("#0000FF")))

    def test_answers_validate_and_old_v35_answers_are_no_error(self):
        self.answer("yes", "#00ff00", "scene")
        data, errors = settings_file.load(settings_file.settings_path(self.root))
        self.assertEqual(errors, [])
        self.assertEqual(data["setup"]["background_color"], "#00FF00")
        old = {"setup": {"asked": True, "green_background": True, "example_scene": False}}
        _, errors = settings_file.validate(old)
        self.assertEqual(errors, [])
        _, errors = settings_file.validate({"setup": {"choice": "both"}})
        self.assertTrue(any("setup.choice" in e for e in errors))

    def test_cli_asks_once_in_a_console_and_again_with_setup(self):
        args = argparse.Namespace(setup=False, no_setup=False)
        self.assertFalse(cli.maybe_ask_setup(str(self.root), args, interactive=False))
        self.answer("no", "plugin")
        self.assertFalse(cli.maybe_ask_setup(str(self.root), args, interactive=True), "answered once")
        self.assertFalse(cli.maybe_ask_setup(str(self.root), argparse.Namespace(setup=True, no_setup=True), True))

    def test_existing_scene_is_kept_as_bak(self):
        self.answer("no", "scene")
        self.answer("yes", "", "scene")
        self.assertTrue((self.root / (first_start.SCENE_REL + ".bak")).exists())


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.data = first_start.scene_data(False)

    def atom(self, atom_id):
        return next(a for a in self.data["atoms"] if a["id"] == atom_id)

    def test_only_aibody_of_this_version_no_other_package(self):
        text = json.dumps(self.data)
        for word in ("Sally", "CameraBackgroundColor", "AIBody.35"):
            self.assertNotIn(word, text)
        plugins = [p for a in self.data["atoms"] for st in a["storables"] if st["id"] == "PluginManager"
                   for p in st["plugins"].values()]
        self.assertEqual(plugins, [f"d0n.AIBody.{__version__}:/Custom/Scripts/d0n/AIBody/AIBody.cslist"])

    def test_two_people_female_and_male(self):
        female = self.atom("AI")       # version 42: Leon's scene, the female "AI" and the male "Client"
        male = self.atom("Client")
        self.assertEqual(female["type"], "Person")
        self.assertEqual(male["type"], "Person")
        geom = {st["id"]: st for st in female["storables"]}
        self.assertEqual(geom["geometry"]["character"], "Female 1")
        self.assertEqual(next(st for st in male["storables"] if st["id"] == "geometry")["character"], "Male 4")
        self.assertIn("[CameraRig]", [a["id"] for a in self.data["atoms"]])

    def test_template_default_is_background_on(self):
        st = next(st for a in json.loads(first_start.TEMPLATE.read_text())["atoms"] for st in a["storables"]
                  if st["id"] == first_start.AIBODY_STORABLE)
        self.assertEqual(st[first_start.TOGGLE_NAME], "true")
        self.assertEqual(st[first_start.COLOR_NAME], GREEN)

    def test_hsv_matches_vam_format(self):
        h, s, v = (float(x) for x in first_start.hsv_of("#800080").values())
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        self.assertEqual([round(c * 255) for c in (r, g, b)], [128, 0, 128])
        self.assertIsNone(first_start.parse_color("purple"))
        self.assertEqual(first_start.parse_color(" 00ff00 "), "#00FF00")


class VarTests(unittest.TestCase):
    def test_var_contains_the_scene_and_declares_scene_dependencies(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_var36", ROOT / "tools" / "build_var.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        loose_path = ROOT / "dist" / build.LOOSE_SCENE
        loose_thumb = ROOT / "dist" / build.LOOSE_THUMB
        kept = loose_path.read_bytes() if loose_path.exists() else None
        kept_thumb = loose_thumb.read_bytes() if loose_thumb.exists() else None
        expected_deps = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))["dependencies"]
        out = build.build(version_override=9036)
        try:
            with zipfile.ZipFile(out) as z:
                meta = json.loads(z.read("meta.json"))
                self.assertIn(build.SCENE_PATH, z.namelist())
                self.assertIn(build.SCENE_PATH, meta["contentList"])
                self.assertEqual(meta.get("licenseType"), "FC")
                self.assertEqual(meta.get("dependencies"), expected_deps)
                scene = z.read(build.SCENE_PATH).decode("utf-8")
                self.assertEqual(build.SCENE_PATH, "Saves/scene/AIBody/AI-Buddy.json")
                plugins = [p for a in json.loads(scene)["atoms"] for st in a["storables"]
                           if st["id"] == "PluginManager" for p in st["plugins"].values()]
                self.assertEqual(plugins, ["SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist"])
                self.assertIn(plugins[0][len("SELF:/"):], z.namelist(), "SELF: resolves to the .cslist in the VAR")
                self.assertNotIn("Sally", scene)
                self.assertNotIn("Dollmaster", scene)
                self.assertNotIn("ImprovedPoV", scene)
                self.assertNotIn("AIBody.9036", scene, "no version inside the package scene")
            loose = json.loads((out.parent / build.LOOSE_SCENE).read_text(encoding="utf-8"))
            self.assertIn("d0n.AIBody.9036:/Custom/Scripts/d0n/AIBody/AIBody.cslist", json.dumps(loose))
        finally:
            out.unlink()
            if kept is None:
                loose_path.unlink(missing_ok=True)
            else:
                loose_path.write_bytes(kept)
            if kept_thumb is None:
                loose_thumb.unlink(missing_ok=True)
            else:
                loose_thumb.write_bytes(kept_thumb)


class PluginSetupSourceTests(unittest.TestCase):
    def setUp(self):
        self.ai = source("AIBody.cs")

    def test_toggle_default_off_green_color_and_menu_order(self):
        self.assertIn('BackgroundToggleName = "Set background color"', self.ai)
        self.assertIn('BackgroundHint = "for pass-through transparency"', self.ai)
        self.assertIn("new JSONStorableBool(BackgroundToggleName, false,", self.ai)
        self.assertIn("HSVColorPicker.RGBToHSV(0f, 1f, 0f)", self.ai)
        body = method_body(self.ai, "private void BuildBackgroundSection(")
        self.assertLess(body.index("Toggle(_backgroundJson"), body.index("ColorPicker(_backgroundColorJson"))
        self.assertLess(body.index("ColorPicker(_backgroundColorJson"), body.index("Note(BackgroundHint"))

    def test_pass_through_appears_only_in_the_hint(self):
        hits = [(p.name, line.strip()) for p in SRC.glob("*.cs") for line in p.read_text().splitlines()
                if "pass-through" in line.lower() and not line.strip().startswith("//")]
        self.assertEqual(hits, [("AIBody.cs", 'public const string BackgroundHint = "for pass-through transparency";')])
        self.assertNotIn("pass-through", first_start.QUESTION_BACKGROUND + first_start.QUESTION_COLOR)

    def test_setup_answer_switches_on_once_per_revision_and_no_never_switches_off(self):
        body = method_body(self.ai, "private void ApplyBackgroundSetup(JSONClass file)")
        self.assertIn('Protocol.GetFloat(ui, "background_setup_applied", 0f)', body)
        self.assertIn("if (revision <= _backgroundSetupApplied) return;", body)
        self.assertIn('if (!Protocol.GetBool(setup, "background", false)) return;', body)
        self.assertIn("SetColorParamValue(BackgroundColorName, HSVColorPicker.RGBToHSV(r, g, b));", body)
        self.assertIn("_backgroundJson.val = true;", body)
        self.assertNotIn("_backgroundJson.val = false", self.ai, "the setup never switches the background off")
        self.assertNotIn("choice", body, "the scene choice has no effect on the background")
        self.assertIn('uiState["background_setup_applied"].AsInt = _backgroundSetupApplied;', self.ai)
        self.assertEqual(self.ai.count("ApplyBackgroundSetup(file)"), 2, "start-up check and Reload Config JSON")
        self.assertIn("if (appSeen && !_appWasSeen && _settingsChecked) CheckBackgroundSetup();", self.ai)

    def test_hex_parser_matches_the_wizard(self):
        body = method_body(self.ai, "public static bool ParseHexColor(")
        self.assertIn('"0123456789ABCDEF".IndexOf(char.ToUpperInvariant(t[i]))', body)

    def test_background_uses_only_audited_apis_and_restores(self):
        bg = source("Background.cs")
        for api in ("CameraTarget.centerTarget", ".targetCamera", "CameraClearFlags.SolidColor", ".backgroundColor",
                    "SkyshopLightController.singleton", 'GetBoolJSONParam("showSkybox")'):
            self.assertIn(api, bg)
        self.assertIn("public void Restore()", bg)
        for bad in ("System.Reflection", "UnityEngine.Networking", "this[", "GetComponent"):
            self.assertNotIn(bad, bg)
        self.assertIn("Background.cs", (SRC / "AIBody.cslist").read_text())
        audit = (ROOT / "docs" / "API_AUDIT.md").read_text()
        for key in ("E30", "E31", "E32", "E33"):
            self.assertIn(key, audit)
        stubs = (ROOT / "tools" / "stubs" / "VaMStubs.cs").read_text()
        self.assertIn("public void SetColorParamValue(string n, HSVColor c)", stubs)

    def test_background_is_saved_with_the_scene_not_in_config_json(self):
        self.assertNotIn('"background"', method_body(self.ai, "private void WriteSettings("))


class LatencyCodeTests(unittest.TestCase):
    """Latency work is code only (Leon): no new setting, UI or metric."""

    def test_no_new_latency_setting(self):
        keys = json.dumps(settings_file.DEFAULTS).lower()
        self.assertNotIn("latency", keys)
        self.assertFalse((ROOT / "tools" / "latency_bench.py").exists())

    def test_plugin_status_text_only_while_the_ui_is_visible(self):
        self.assertIn("if (_link != null) _link.UiVisible = visible;", self.ai_source())
        self.assertIn("Describe", source("IdlePoses.cs"))
        self.assertIn("StatusInterval", source("MicConfig.cs"))

    def ai_source(self):
        return source("AIBody.cs")

    def test_speech_starts_when_the_clip_is_ready(self):
        sp = source("SpeechPlayer.cs")
        # since the audio fix after version 40: ready = sourceClip set AND its audio data loaded (E36)
        self.assertIn("u.Clip.sourceClip", sp)
        self.assertIn("AudioDataLoadState.Loaded", sp)
        self.assertIn("RetryInterval = 0.5f", sp)

    def test_socket_queue_swap_without_copy(self):
        self.assertNotIn("_incoming.ToArray()", source("SocketLink.cs"))

    def test_wakeup_returns_at_once(self):
        wakeup.wait(0)
        threading.Timer(0.01, wakeup.notify).start()
        t = time.monotonic()
        self.assertTrue(wakeup.wait(2.0))
        self.assertLess(time.monotonic() - t, 0.5)
        self.assertFalse(wakeup.wait(0.01), "the signal is cleared")

    def test_first_clause_goes_early_but_not_numbers(self):
        s = SentenceSplitter()
        out = s.feed("Oh, that is a really lovely question, ")
        self.assertEqual(out, ["Oh, that is a really lovely question,"])
        self.assertGreaterEqual(len(out[0]), FIRST_CLAUSE_MIN)
        self.assertEqual(s.feed("and here is more, still the same sentence"), [], "only the first piece goes early")
        s = SentenceSplitter()
        self.assertEqual(s.feed("The value is 1,5 and it is quite large indeed"), [])
        self.assertEqual(SentenceSplitter(early_first_clause=False).feed("Oh, that is a really lovely question, "), [])

    def test_speech_files_are_written_without_fsync(self):
        self.assertIn("durable", atomicfile.atomic_write_bytes.__code__.co_varnames)


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        status = 401 if self.path == "/bad" else 200
        reply = json.dumps({"echo": body.decode(), "path": self.path}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


class PooledHttpTests(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.pool = http_module.ConnectionPool()

    def tearDown(self):
        self.pool.close_all()
        self.server.shutdown()
        self.server.server_close()

    def post(self, path, data=b"x"):
        req = urllib.request.Request(self.base + path, data=data, method="POST")
        with http_module.pooled_opener(req, 5.0, self.pool) as resp:
            return json.loads(resp.read())

    def test_connection_is_reused(self):
        for i in range(4):
            self.assertEqual(self.post("/ok", str(i).encode())["echo"], str(i))
        self.assertEqual((self.pool.opened, self.pool.reused), (1, 3))

    def test_http_error_like_urlopen_and_connection_kept(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/bad")
        self.assertEqual(ctx.exception.code, 401)
        self.assertIn(b'"/bad"', ctx.exception.read())
        self.post("/ok")
        self.assertEqual(self.pool.opened, 1)

    def test_stale_connection_is_retried_once(self):
        self.post("/ok")
        key = self.pool.key(self.base)
        conn, _ = self.pool._idle[key][0]
        conn.sock.close()  # the connection dies while idle; the pool still lists it
        conn.sock = __import__("socket").socket()  # unconnected socket: sending fails
        orig = http_module.ConnectionPool._usable
        http_module.ConnectionPool._usable = staticmethod(lambda c: True)
        try:
            self.assertEqual(self.post("/ok", b"again")["echo"], "again")
        finally:
            http_module.ConnectionPool._usable = orig
        self.assertEqual(self.pool.opened, 2)

    def test_default_opener_is_pooled(self):
        self.assertIs(http_module._default_opener, http_module.pooled_opener)


class EyesBelongToVaMTests(unittest.TestCase):
    """Leon (calls 20.11.2026 22:34-22:36): no gaze and no blink control in AIBody any more. Removed: Gaze follows
    speaker, Gaze control, Default gaze (incl. Natural), the AI's look_at tool / command, the remote 'look' action,
    the scene actions Look at client / camera / straight ahead / away / Gaze back to default, Blink control and
    'Blink now'. VaM's own gaze and blinking are untouched. Expressions and gestures stay."""

    GONE_UI = ("Gaze follows speaker", "Gaze control", "Default gaze", "Natural (looks around)", "Blink control",
               "Blink now", "Look at client", "Look at camera", "Look straight ahead", "Look away",
               "Gaze back to default", "Gaze and blinking", "Gaze now", "Blinking now")

    def test_no_gaze_or_blink_code_or_ui_in_the_plugin(self):
        self.assertFalse((SRC / "GazeController.cs").exists())
        self.assertFalse((SRC / "BlinkController.cs").exists())
        cslist = (SRC / "AIBody.cslist").read_text().split()
        self.assertNotIn("GazeController.cs", cslist)
        self.assertNotIn("BlinkController.cs", cslist)
        for path in SRC.glob("*.cs"):
            text = path.read_text(encoding="utf-8")
            for word in self.GONE_UI:
                self.assertNotIn(word, text, f"{word!r} in {path.name}")
            for code in ("GazeController", "BlinkController", "_gaze", "_blink", "gaze_control", "gaze_default",
                         "gaze_atoms", "blink_control", "EyelidControl", "eyeTargetControl"):
                self.assertNotIn(code, text, f"{code!r} in {path.name}")
        tab = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        self.assertNotRegex(tab.lower(), r"gaze|blink|eyes")

    def test_old_look_at_from_an_older_app_is_ignored_not_an_error(self):
        router = source("CommandRouter.cs")
        case = router[router.index("case Protocol.CmdLookAt:"):]
        self.assertIn("return null;", case[:case.index("case Protocol.CmdIdle:")])
        self.assertIn("CmdLookAt", source("Protocol.cs"))

    def test_the_companion_never_offers_or_sends_look_at(self):
        from aibody_companion import body_tools, protocol
        from aibody_companion.remote import RemoteError, parse_action
        self.assertNotIn("look_at", protocol.COMMANDS)
        self.assertNotIn("look_at", protocol.BODY_COMMANDS)
        lists = body_tools.BodyLists.from_body_info({"gaze_control": "true", "gaze_atoms": ["Lamp"]}, ["neutral"], ["nod"])
        self.assertEqual([t["name"] for t in body_tools.tools(lists)], ["express"])
        self.assertNotIn("look_at", body_tools.rules(lists))
        self.assertFalse(body_tools.resolve("look_at", {"target": "client"}, lists, True)[1]["ok"])
        with self.assertRaises(RemoteError):
            parse_action("look", {"target": "client"})
        schema = json.loads((ROOT / "protocol" / "schema" / "command.schema.json").read_text())
        self.assertNotIn("look_at", schema["properties"]["type"]["enum"])

    def test_config_keys_gone_and_old_files_still_load(self):
        for key in ("gaze_follows_speaker", "gaze_control", "gaze_default", "blink_control"):
            self.assertNotIn(key, settings_file.DEFAULTS["body"])
            self.assertNotIn(key, (ROOT / "protocol" / "schema" / "config.schema.json").read_text())
            self.assertNotIn(key, (ROOT / "examples" / "config.json").read_text())
        old = {"body": {"gaze_follows_speaker": True, "gaze_control": "false", "gaze_default": "natural",
                        "blink_control": True, "body_control": True}}
        data, errors = settings_file.validate(old)
        self.assertEqual(errors, [])
        self.assertNotIn("gaze_control", data["body"])

    def test_expressions_and_gestures_stay(self):
        body = source("Body.cs")
        for needle in ("Show expression", "Reset expression", "Reload expressions", "Play gesture", '"Expression: "',
                       '"Gesture: "'):
            self.assertIn(needle, body)
        # the built-in head gestures (examples/gestures.json maps names such as agree/disagree onto them)
        self.assertIn('new[] { "nod", "shake", "tilt" }', body)
        idle = source("IdleController.cs")
        for g in ("nod", "shake", "tilt"):
            self.assertIn(f'"{g}"', idle)


class BodyControlDefaultTests(unittest.TestCase):
    """Leon: Body control is ON for a fresh install, a fresh scene and a missing key; since version 39 nothing in
    AIBody switches it off by itself (the Question and Answer button that did is gone)."""

    def test_every_default_is_on(self):
        body = source("Body.cs")
        self.assertIn('new JSONStorableBool("Body control", true,', body)
        self.assertIn('Protocol.GetBool(body, "body_control", _bodyControlJson.val)', body, "missing key keeps ON")
        self.assertTrue(settings_file.DEFAULTS["body"]["body_control"])
        self.assertTrue(json.loads((ROOT / "examples" / "config.json").read_text())["body"]["body_control"])
        schema = json.loads((ROOT / "protocol" / "schema" / "config.schema.json").read_text())
        self.assertIs(schema["properties"]["body"]["properties"]["body_control"]["default"], True)
        data, _ = settings_file.validate({"body": {}})
        self.assertTrue(data["body"]["body_control"])

    def test_nothing_switches_it_off(self):
        for p in SRC.glob("*.cs"):
            self.assertNotIn("SetBodyControl(", p.read_text())
            self.assertNotIn("_bodyControlJson.val = false", p.read_text())

    def test_scene_preset_and_setup_do_not_store_it_off(self):
        for st in [st for a in first_start.scene_data(True)["atoms"] for st in a["storables"]]:
            self.assertNotIn("Body control", st)
        self.assertNotIn("Body control", (ROOT / "tools" / "build_var.py").read_text())
        self.assertNotIn("body_control", (ROOT / "companion" / "aibody_companion" / "setup.py").read_text())


class VersionTests(unittest.TestCase):
    def test_version_36_everywhere(self):
        """Historical: version 36 sources are gone after the v37 bump; consistency is test_version42."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version36.py").is_file())


class MenuLayoutTests(unittest.TestCase):
    """Leon, 20.11.2026: menus ordered by topic; right column = category headers and controls only;
    left info field = running prose with every control name in bold (rich text evidenced, API_AUDIT E35)."""

    RIGHT = [
        ("AppLink.cs", "public void BuildConnectionSection(UiPage page)"),
        ("AppLink.cs", "public void BuildAiSection(UiPage page)"),
        ("AppLink.cs", "public void BuildVoiceSection(UiPage page)"),
        ("AppLink.cs", "public void BuildClientCharacterTab(UiPage page)"),
        ("AppLink.cs", "public void BuildConfigTab(UiPage page"),
        ("Body.cs", "public void BuildSoundSection(UiPage page)"),
        ("Body.cs", "public void BuildCharacterTab(UiPage page)"),
        ("CharacterWizard.cs", "public void Build(UiPage page)"),
        ("MicConfig.cs", "public void BuildTab(UiPage page, JSONStorableBool bargeIn)"),
    ]

    def order(self, body, parts):
        idx = [body.index(p) for p in parts]
        self.assertEqual(idx, sorted(idx), parts)

    def test_right_column_has_only_headers_and_controls(self):
        # GateQuestion (version 40, Leon: "the wizard shows no question at all") is the label of the Yes / No pair below it
        allowed_labels = {"XaiTokenLabel", "BreathMorphLabel", "NewPoseCommandLabel", "GateQuestion"}
        for file, sig in self.RIGHT:
            body = method_body(source(file), sig)
            self.assertNotRegex(body, r"\bpage\.(Text|Note)\(", f"{file} {sig}")
            for m in re.finditer(r"page\.Header\(([^;]*)\);", body):
                arg = m.group(1)
                ok = arg in allowed_labels or re.fullmatch(r'"<b>[^<"]{1,40}</b>"', arg)
                self.assertTrue(ok, f"{file}: header {arg} is not a short category header or field label")
        show = method_body(source("AIBody.cs"), "private void ShowTab(int index)")
        for m in re.finditer(r"_page\.Header\(([^;]*)\);", show):
            self.assertRegex(m.group(1), r'^"<b>[^<"]{1,40}</b>"$')
        # the one caption Leon asked for in version 36 stays under the color picker
        self.assertEqual(re.findall(r"_page\.Note\((\w+)\)", source("AIBody.cs")), ["BackgroundHint"])
        self.assertIn('HintText = "<b>First start: XAI API Token</b>"', source("AppLink.cs"))

    def test_tabs_are_ordered_by_topic(self):
        show = method_body(source("AIBody.cs"), "private void ShowTab(int index)")
        self.order(show, ['"<b>Companion connection</b>"', "BuildConnectionSection", '"<b>AI</b>"',
                          "BuildAiSection", '"<b>Voice and sound</b>"', "BuildVoiceSection", "BuildSoundSection",
                          "BuildConfigTab", '"<b>Logging</b>"', "_verboseJson", '"<b>Background</b>"', "BuildBackgroundSection"])
        char = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        self.order(char, ["Characters.Build(page)", '"<b>Body control</b>"', "_bodyControlJson", '"<b>Idle poses</b>"', "_idlePosesJson", "_idlePoseMaxJson",
                          '"<b>Idle motion and breathing</b>"', "_idleJson", "_breathingJson", "_breathRateJson", "_breathDepthJson",
                          "page.Header(BreathMorphLabel)", "_breathMorphJson", '"<b>Expression and gesture</b>"', '"<b>Poses</b>"'])
        wizard = method_body(source("CharacterWizard.cs"), "public void Build(UiPage page)")
        self.order(wizard, ['"<b>Characters</b>"', 'page.Button("Yes"', 'page.Button("No"',
                            "page.Popup(_aiGenderJson)", "page.Popup(_userGenderJson)", '"<b>Clothing</b>"'])
        self.assertNotIn("_volumeJson", char)
        self.assertIn("page.Slider(_volumeJson);", method_body(source("Body.cs"), "public void BuildSoundSection(UiPage page)"))
        self.assertIn('BreathMorphLabel = "Breath morph";', source("Body.cs"))   # after version 40: no help text in the label
        self.assertIn('new JSONStorableString("Breath morph", "Breath1"', source("Body.cs"))
        mic = method_body(source("MicConfig.cs"), "public void BuildTab(UiPage page, JSONStorableBool bargeIn)")
        self.order(mic, ['"<b>Microphone</b>"', "Toggle(Enabled)", "Popup(Mode)", "Slider(Gain)", '"<b>Push-to-talk</b>"', "_pttActive",
                         '"<b>Voice detection</b>"', "Popup(VadEngine)", "Slider(MaxUtteranceMs)", '"<b>Echo and barge-in</b>"',
                         "Slider(EchoTail)", "Toggle(bargeIn)"])
        ai = method_body(source("AppLink.cs"), "public void BuildAiSection(UiPage page)")
        self.order(ai, ["_realtimeJson", "_aiModeJson", "_llmJson", "_personaJson", "_memoryJson", "Forget memory", "_proactiveJson"])
        voice = method_body(source("AppLink.cs"), "public void BuildVoiceSection(UiPage page)")
        self.order(voice, ["_voiceJson", "_sttJson", "_ttsJson", "Test tone via companion"])

    def test_left_texts_are_prose_with_bold_labels(self):
        link, body, mic, ai = source("AppLink.cs"), source("Body.cs"), source("MicConfig.cs"), source("AIBody.cs")
        wizard = source("CharacterWizard.cs")
        self.assertIn("<b>Breaths per minute</b> controls how fast", body)
        for label in ("Body control", "Pose command", "Idle head motion", "Breathing", "Idle default pose", "Add Pose", "Reset poses"):
            self.assertIn(f"<b>{label}</b>", body)
        for label in ("Yes", "No", "Configure characters", "AI gender/body", "Your character gender", "Clothing"):
            self.assertIn(f"<b>{label}</b>", wizard)
        for label in ("AI mode", "Use realtime voice", "Proactive talking", "Speech delay timer (s)", "Persona", "Memory",
                      "Forget memory", "Network Active", "Reload Config JSON", "XAI API Token"):
            self.assertIn(f"<b>{label}</b>", link)
        self.assertIn('<b>" + XaiTokenLabel + "</b>', link)
        for label in ("Push-to-talk active", "Mic mode", "VAD engine", "VAD strictness", "VAD threshold", "Echo gate tail (s)"):
            self.assertIn(f"<b>{label}</b>", mic)
        for label in ("Set background color",):
            self.assertIn(f"<b>{label}</b>", ai)
        # no "Label: explanation" boxes left in the explanations
        for old in ("Memory: off", "Persona: none", "Proactive talking: when on", "VAD strictness 0-3:",
                    "Body control off = ", "Breath morph: a name"):
            self.assertNotIn(old, link + body + mic + ai)
        # bold is evidenced for the info text field
        audit = (ROOT / "docs" / "API_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("| E35 |", audit)
        self.assertIn("ManageAnimationsScreen.cs", audit)
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("**Left info field (Leon, 20.11.2026, standing rule):**", spec)
        self.assertIn("**Right column (Leon, 20.11.2026, standing rule):**", spec)

    def test_every_bold_label_names_a_real_control(self):
        cs = "".join(source(f) for f in ("AIBody.cs", "AppLink.cs", "Body.cs", "MicConfig.cs", "CharacterWizard.cs"))
        labels = set(re.findall(r"<b>([^<\"]+)</b>", cs))
        known = set(re.findall(r'new JSONStorable\w+\("([^"]+)"', cs)) | set(re.findall(r'Button\("([^"]+)"', cs))
        known |= {"Breath morph", "Companion inbox poll interval (s)", "XAI API Token",
                  "Background color", "Set background color", "Pose command", "Pose", "Language model", "Speech-to-text", "Text-to-speech", "Voice",
                  "AI gender/body", "Your character gender"}
        headers = {"Companion connection", "AI", "Voice and sound", "Logging", "Background", "Body control", "Idle poses",
                   "Idle motion and breathing", "Expression and gesture", "Poses", "Microphone", "Push-to-talk",
                   "Voice detection", "Echo and barge-in", "Config file", "Connection", "First start: XAI API Token",
                   "Self-test", "Recent events", "Startup log", "Engine status", "Info: ", "Characters", "Clothing", "Reset"}
        unknown = sorted(x for x in labels if x not in known and x not in headers and not x.startswith(("AIBody", "Info")))
        self.assertEqual(unknown, [], "bold text that is neither a control label nor a section title")


if __name__ == "__main__":
    unittest.main()
