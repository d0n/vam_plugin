"""Menu rules of the plugin (Don, 17.11.2026, version 15), checked on the C# sources:
four self-explanatory tabs, no text fields inside the tabs (help and status go to the ONE big
info field on the left), no removed placeholders (Post tab, Channel field, key file fields,
Delay, the tab title headers)."""
import re
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def method_body(text: str, signature: str) -> str:
    start = text.index(signature)
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise AssertionError(signature)


BUILDERS = [
    ("AIBody.cs", "private void ShowTab(int index)"),
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


class PluginMenuTests(unittest.TestCase):
    def test_tabs(self):
        m = re.search(r"string\[\] Tabs = \{([^}]*)\}", source("AIBody.cs"))
        tabs = re.findall(r'"([^"]+)"', m.group(1))
        self.assertEqual(tabs, ["Voice", "AI Character", "Client Character", "Dollmaster", "Config"])  # v49: Dollmaster tab

    def test_no_small_text_fields_in_tabs(self):
        for file, sig in BUILDERS:
            body = method_body(source(file), sig)
            self.assertNotIn("page.Text(", body, f"{file} {sig}: help/status belongs in the big info field")
            self.assertNotIn("_page.Text(", body, f"{file} {sig}")

    def test_only_labelled_inputs(self):
        # an editable field shows only its value: each one needs a header right above it
        for file, sig in BUILDERS:
            body = method_body(source(file), sig)
            for m in re.finditer(r"TextInput\((\w+)\)", body):
                line_start = body.rfind("\n", 0, m.start())
                before = body[:line_start].rstrip().splitlines()[-1]
                self.assertIn("Header(", before, f"{file}: TextInput({m.group(1)}) without a label")

    def test_removed_placeholders_stay_removed(self):
        all_src = "".join(source(f) for f in ("AIBody.cs", "AppLink.cs", "Body.cs", "MicConfig.cs"))
        self.assertNotIn("PostTabLabel", all_src)
        self.assertNotIn("BuildPostTab", all_src)
        self.assertNotIn("BuildAdvancedTab", all_src)
        self.assertNotIn("_delayJson", all_src)
        self.assertNotIn('"Erweitert"', all_src)
        for file, sig in BUILDERS:
            body = method_body(source(file), sig)
            for field in ("_channelJson", "_xaiKeyFileJson", "_elevenKeyFileJson"):
                self.assertNotIn(field, body, f"{file} {sig}")
        show = method_body(source("AIBody.cs"), "private void ShowTab(int index)")
        self.assertNotIn('_page.Header("<b>" + name', show, "tab title header (a field that only says the tab name)")

    def test_pose_section_is_called_poses(self):
        body = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        self.assertIn('"<b>Poses</b>', body)


class Version16MenuTests(unittest.TestCase):
    """Don, 18.11.2026: mic menu empty in VaM; larger per-tab info field; no empty menus."""

    def test_info_field_is_larger_and_per_tab(self):
        plugin = source("AIBody.cs")
        height = re.search(r"status\.height = (\d+)f;", plugin)
        self.assertGreaterEqual(int(height.group(1)), 1800, "version 17: even taller than 1600")
        refresh = method_body(plugin, "private void RefreshStatus()")
        for moved in ("SelfTest()", "Startup log", "Recent events", "<b>Live</b>"):
            self.assertNotIn(moved, refresh, "only the open tab's info in the field")
        info = method_body(plugin, "private string TabInfo()")
        self.assertIn("SelfTest()", info)
        self.assertIn("Startup log", info)

    def test_no_empty_pose_menu(self):
        body = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        # version 42: the Pose dropdown is gone; the Pose command menu is only built when there is a command
        guard = body.index("_poses.Vocabulary.Count > 0")
        self.assertLess(guard, body.index("page.ScrollablePopup(_poseCommandChoiceJson)"))


class Version17MenuTests(unittest.TestCase):
    """Don, 18.11.2026: larger info field, no hint line around it, clear section labels."""

    def test_no_hint_header_on_the_left(self):
        plugin = source("AIBody.cs")
        self.assertNotIn("needs the companion app running", plugin)
        init = method_body(plugin, "public override void Init()")
        self.assertNotIn("UiHelper.Header(", init, "nothing above or below the info field on the left")
        self.assertEqual(init.count("CreateTextField("), 1, "the info field is the only left element")

    def test_live_text_says_engines_only_once(self):
        link = source("AppLink.cs")
        self.assertNotIn("EngineSummary", link)
        self.assertNotIn('"Folder: "', link)

    def test_env_hint_only_while_a_key_is_missing(self):
        body = method_body(source("AppLink.cs"), "private void UpdateKeyStatus()")
        self.assertIn("KeyConfigured(", body)

    def test_reload_expressions_is_part_of_reload_config_json(self):
        # version 53 (Don 20:57): the separate button is gone; Reload Config JSON reloads expressions.json
        body = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        self.assertNotIn('page.Button("Reload expressions (expressions.json)"', body)
        self.assertIn("_body.ReloadConfigFiles();", method_body(source("AIBody.cs"), "private void ReloadConfigJson()"))


class OneCharacterTests(unittest.TestCase):
    """Don, 19.11.2026: one companion app, one character, one fixed message folder."""

    def test_the_plugin_has_no_channel_setting_and_one_fixed_folder(self):
        link = source("AppLink.cs")
        self.assertNotIn("_channelJson", link)
        self.assertNotIn('"Channel"', link, "no storable: a Channel value left in an old scene is simply not read")
        self.assertIn('public const string Channel = "default";', link)
        self.assertIsNone(re.search(r"\bfigures?\b", link.lower()))

    def test_nothing_in_the_plugin_or_the_app_knows_several_characters(self):
        files = [p for p in (ROOT / "companion" / "aibody_companion").rglob("*.py")] + list((ROOT / "src" / "AIBody").glob("*.cs"))
        for path in files:
            text = path.read_text(encoding="utf-8").lower()
            for word in ("fleet", "linkedgate", "parse_channels", "active_figure"):
                self.assertNotIn(word, text, f"{path.name}: {word}")
        self.assertFalse((ROOT / "companion" / "aibody_companion" / "multi.py").exists())


class Version18MenuTests(unittest.TestCase):
    """Don, 18.11.2026: plugin UI in English; old scenes and old companion texts keep working."""

    def test_problem_turns_red_for_old_and_new_companion_texts(self):
        body = method_body(source("AppLink.cs"), "public static bool IsProblemTurn(string turn)")
        for prefix in ('"Nothing"', '"No "', '"error"'):
            self.assertIn(prefix, body)
        for german in ('"Nichts"', '"Keine"', '"Fehler"'):
            self.assertNotIn(german, body)

    def test_menu_labels_are_english(self):
        body = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        for label in ('"Add Pose"', '"Delete Pose"', '"Reset poses"', '"Reload poses"'):
            self.assertIn(label, body)
        for gone in ('"Show expression"', '"Play gesture"', '"Reset expression"'):   # version 66
            self.assertNotIn(gone, body)
        for german in ("Pose anwenden", "Ausdruck zeigen", "Geste abspielen", "Körper"):
            self.assertNotIn(german, body)


class Version19MenuTests(unittest.TestCase):
    """Don, 18.11.2026: the poll slider is about the companion inbox, not config.json."""

    def test_poll_slider_shows_companion_inbox_label_but_keeps_stored_name(self):
        link = source("AppLink.cs")
        self.assertIn('new JSONStorableFloat("File poll interval (s)"', link, "stored name unchanged")
        self.assertIn('FilePollLabel = "Companion inbox poll interval (s)"', link)
        config_tab = method_body(link, "public void BuildConfigTab(UiPage page, UnityEngine.Events.UnityAction reload)")
        self.assertIn("page.Slider(_filePollJson, FilePollLabel);", config_tab)
        self.assertIn("slider.label = label;", source("UiHelper.cs"))

    def test_config_info_names_the_inbox_and_says_config_json_is_not_reloaded(self):
        hint = method_body(source("AppLink.cs"), "public string FilePollInfoText()")
        for part in ("FilePollLabel", '"/inbox/', "speech, poses and expressions",
                     "does not reload config.json", "<b>Reload Config JSON</b>"):
            self.assertIn(part, hint)
        self.assertIn("FilePollInfoText()", method_body(source("AIBody.cs"), "private string TabInfo()"))


class ProactiveIdleZeroTests(unittest.TestCase):
    """Don, 19.11.2026: "Speech delay timer (s)" (was "Proactive idle (s)") can go down to 0 = proactive speech off."""

    def test_slider_minimum_is_zero_and_the_info_line_says_off(self):
        link = source("AppLink.cs")
        self.assertIn('new JSONStorableFloat("Speech delay timer (s)", 90f, (float v) => MarkConfigDirty(), 0f, 3600f)', link)
        line = method_body(link, "private string ProactiveLine()")
        self.assertIn('"off (speech delay timer "', line)
        self.assertIn('"on - after "', line)
        self.assertIn('" s of silence the AI may speak on its own (speech delay timer, not the answer delay)"', line)
        self.assertIn('"Proactive talking: "', line)
        self.assertIn('new JSONStorableBool("Proactive talking", true,', link)
        self.assertNotIn('JSONStorableBool("Proactive",', link)
        self.assertNotIn("Proactive idle", "".join(source(f.name) for f in sorted(SRC.glob("*.cs")))
                         .replace('was "Proactive idle (s)" up to version 22', ""))
        self.assertIn("idle >= 1f", line)


class SpeechDelayTimerTextTests(unittest.TestCase):
    """Don, 19.11.2026: the timer is the silence before the AI may speak on its own, not the answer latency."""

    def test_voice_tab_help_explains_the_timer(self):
        link = source("AppLink.cs")
        self.assertIn("<b>Speech delay timer (s)</b> is how long it", link)
        self.assertIn("must be quiet first (0 = never), not how long the AI takes to answer.", link)

    def test_startup_and_nudge_log_lines(self):
        import tempfile

        from aibody_companion import cli
        from aibody_companion.config import Config

        with tempfile.TemporaryDirectory() as tmp:
            for enabled, idle, expected in (
                    (True, 90, "Proactive talking: on - after 90 s of silence the AI may speak on its own "
                               "(speech delay timer, not the answer delay)"),
                    (True, 0, "Proactive talking: off (speech delay timer 0 s)"),
                    (False, 90, "Proactive talking: off")):
                cfg = Config(vam_root=tmp, channel="default")
                from aibody_companion import settings_file

                cfg.ai = settings_file.defaults()["ai"]
                cfg.ai["proactive"].update(enabled=enabled, idle_seconds=idle)
                cfg.ai["mode"] = "auto"
                with self.assertLogs("aibody_companion", level="INFO") as logs:
                    cli.build_stack(cfg, use_mic=False)
                self.assertIn(expected, [r.getMessage() for r in logs.records])
        text = (SRC.parents[1] / "companion/aibody_companion/orchestrator.py").read_text(encoding="utf-8")
        self.assertIn("s of silence passed (speech delay timer) - the AI may say something on its own", text)


class PlainEnglishTextTests(unittest.TestCase):
    """Don, 19.11.2026: help and error texts in plain English: what went wrong, where to look, what to do."""

    def test_plugin_audio_errors_say_what_to_check(self):
        player = source("SpeechPlayer.cs")
        for part in ("The audio did not start playing within ", "Check that it is a valid WAV",
                     "Speech volume (%) (tab Voice) is above 0", "the character's head audio is not muted or blocked",
                     "make sure its --vam-root is the VaM folder you start VaM from",
                     "VaM would not load the audio file", "Press 'Play test tone' again",
                     "The character cannot speak yet", "Add AIBody to a Person atom"):
            self.assertIn(part, player)
        for jargon in ("QueueClip returned nothing", "GetClip did not find", "QueueClip failed"):
            self.assertNotIn(jargon, player)
        self.assertIn('"did not start playing within " + StartTimeout.ToString("0") + " s: " + u.Path', player,
                      "the short message sent to the companion keeps its wording")
        router = source("CommandRouter.cs")
        self.assertIn("see the Self-test in tab Config", router)
        self.assertNotIn("SpeechPlayer missing", router)

    def test_plugin_help_texts_are_plain(self):
        link, plugin, mic = source("AppLink.cs"), source("AIBody.cs"), source("MicConfig.cs")
        self.assertIn("with <b>Proactive talking</b> off the character only speaks when you ask it something", link)
        self.assertIn("With <b>Proactive talking</b> on, the AI may start talking by itself after a quiet moment", link)
        self.assertIn("paste your xAI API key (from console.x.ai) into <b>", link)
        self.assertIn("The microphone is always the system default input", mic)
        for gone in ("speech recognition -> Grok -> voice", "Mic device", "Refresh microphones"):
            self.assertNotIn(gone, link + plugin + mic)

    def test_companion_messages_say_where_to_look(self):
        from aibody_companion.audio import capture
        from aibody_companion.pipeline.engines import KEY_HINT

        self.assertIn("console.x.ai", KEY_HINT["xai"])
        self.assertIn("A Grok subscription or a grok.com login does not work.", KEY_HINT["xai"])
        with unittest.mock.patch.object(capture, "_sounddevice", lambda: None):
            error = capture.list_input_devices()[1]
        self.assertIn("pip install sounddevice", error)
        self.assertIn("restart this app", error)
        base = ROOT / "companion/aibody_companion"
        cli_text = (base / "cli.py").read_text(encoding="utf-8")
        self.assertIn("paste the key into the field 'XAI API Token' (tab Voice)", cli_text)
        orch = (base / "orchestrator.py").read_text(encoding="utf-8")
        for part in ("Try speaking louder or closer to the microphone", "'API Reconnect' (tab Voice) tries realtime again",
                     "check your xAI key (tab Voice) and internet connection",
                     "the app runs in text-only mode (--no-mic)"):
            self.assertIn(part, orch)
        transport = (base / "transport/file_transport.py").read_text(encoding="utf-8")
        self.assertIn("is --vam-root the VaM folder you start VaM from", transport)
        self.assertIn("not valid JSON", transport)


class NoMicSelectionTests(unittest.TestCase):
    """Don, 19.11.2026: the microphone device selection is gone, the companion always uses the system default."""

    def test_no_device_menu_button_storable_or_list_protocol_in_the_plugin(self):
        self.assertNotIn("MicDeviceList.cs", source("AIBody.cslist"))
        self.assertFalse((ROOT / "src/AIBody/MicDeviceList.cs").exists())
        plugin = "".join(source(f.name) for f in sorted((ROOT / "src/AIBody").glob("*.cs")))
        for gone in ("Mic device", "Refresh microphones", "Refresh mic devices", "MicDeviceList", "RefreshMicrophones",
                     "HandleDevices", "RequestDevices", "RefillChoices", "OnDevicePopupOpen", "EvtListDevices",
                     "CmdDevices", "list_devices", '"devices"', 'mic["device"]', 'Protocol.Has(mic, "device")'):
            self.assertNotIn(gone, plugin, gone)

    def test_mic_tab_keeps_the_other_controls(self):
        build = method_body(source("MicConfig.cs"), "public void BuildTab(UiPage page, JSONStorableBool bargeIn)")
        for part in ("page.Toggle(Enabled);", "page.Popup(Mode);", "page.Toggle(_pttActive);", "page.Toggle(LevelMeter);",
                     "page.Slider(Threshold);", "page.Slider(Gain);", "page.Slider(EchoTail);"):
            self.assertIn(part, build)
        self.assertNotIn("Device", build)

    def test_companion_not_running_is_a_neutral_status_line_only(self):
        """Version 35 (Don): the note 'Companion App not running, so nothing is heard or spoken. Start it in a console ...'
        is gone from the menu; a neutral one-line status stays, the start command goes to the VaM log once."""
        mic = source("MicConfig.cs")
        update = method_body(mic, "public void Update(float deltaTime, bool connected, bool appRunning, bool linkActive)")
        self.assertIn('"Companion app: not connected"', update)
        self.assertIn('Log.Info("Companion app not connected: " + StartHint + ".");', update)
        plugin = "".join(source(f.name) for f in sorted((ROOT / "src/AIBody").glob("*.cs")))
        self.assertNotIn("nothing is heard or spoken", plugin)
        self.assertNotIn("<color=red>Companion app", plugin)
        self.assertNotIn("Start it in a console", source("AppLink.cs"))
        self.assertIn("_appHint", method_body(mic, "private void RefreshStatus()"))
        self.assertIn("_mic.Update(dt, connected, _appAlive,", source("AppLink.cs"))


if __name__ == "__main__":
    unittest.main()


class Version31LayoutTests(unittest.TestCase):
    """REQUIREMENTS 'Next version' menu-layout points (Don, 18.11.2026), closed in version 31 with a source check:
    character-bound controls (poses, expression, gesture, body, gaze) are in the tab AI Character, Config holds only
    what is not character-bound, and no info text fields are left in the tabs."""

    def test_config_tab_holds_only_what_is_not_character_bound(self):
        config = method_body(source("AppLink.cs"), "public void BuildConfigTab(UiPage page")
        # version 55: the toggle "Mute AI (stop talking and listening)" first
        self.assertEqual(re.findall(r'page\.(\w+)\(', config), ["Toggle", "Header", "Button", "Header", "Toggle", "Slider"])
        self.assertIn('"Reload Config JSON"', config)
        for word in ("pose", "Pose", "xpression", "esture", "Body", "Gaze"):
            self.assertNotIn(word, config)

    def test_poses_expression_gesture_and_body_are_in_the_ai_character_tab(self):
        tab = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        for needed in ("Add Pose", "Reset poses", "Reload poses", "Show expression", "Play gesture", "_bodyControlJson"):
            self.assertIn(needed, tab)

    def test_no_info_text_fields_in_the_right_hand_tabs(self):
        for file, sig in BUILDERS:
            body = method_body(source(file), sig)
            self.assertNotIn(".Text(", body, f"{file} {sig}")
