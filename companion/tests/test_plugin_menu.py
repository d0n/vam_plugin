"""Menu rules of the plugin (Leon, 17.11.2026, version 15), checked on the C# sources:
four self-explanatory tabs, no text fields inside the tabs (help and status go to the ONE big
info field on the left), no removed placeholders (Post tab, Channel field, key file fields,
Delay, the tab title headers)."""
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "AIBody"


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
    ("AppLink.cs", "public void BuildVoiceModeTab(UiPage page)"),
    ("AppLink.cs", "public void BuildAiVoiceSection(UiPage page)"),
    ("AppLink.cs", "public void BuildClientCharacterTab(UiPage page)"),
    ("AppLink.cs", "public void BuildConfigTab(UiPage page"),
    ("Body.cs", "public void BuildVoiceModeTab(UiPage page)"),
    ("Body.cs", "public void BuildCharacterTab(UiPage page)"),
    ("MicConfig.cs", "public void BuildTab(UiPage page)"),
]


class PluginMenuTests(unittest.TestCase):
    def test_tabs(self):
        m = re.search(r"string\[\] Tabs = \{([^}]*)\}", source("AIBody.cs"))
        tabs = re.findall(r'"([^"]+)"', m.group(1))
        self.assertEqual(tabs, ["Voice", "AI Character", "Client Character", "Config"])

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

    def test_pose_section_is_called_posen(self):
        body = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        self.assertIn('"<b>Posen</b>', body)


class Version16MenuTests(unittest.TestCase):
    """Leon, 18.11.2026: mic menu empty in VaM; larger per-tab info field; no empty menus."""

    def test_mic_menu_has_plain_choices_and_always_standard(self):
        mic = source("MicConfig.cs")
        self.assertIsNone(re.search(r"\.displayChoices\s*=", mic),
                          "the only chooser with displayChoices showed an empty list")
        self.assertIn("MicDeviceList.Build(", method_body(mic, "public void HandleDevices(JSONClass msg)"))
        self.assertIn("EnsureDeviceChoices();", method_body(mic, "public void BuildTab(UiPage page)"))
        self.assertIn("MicDeviceList.cs", source("AIBody.cslist"))
        self.assertIn('"Standard (System-Mikrofon)"', source("MicDeviceList.cs"))

    def test_mic_info_shows_count_source_time_and_menu_entries(self):
        mic = source("MicConfig.cs")
        handle = method_body(mic, "public void HandleDevices(JSONClass msg)")
        for part in ('" empfangen von der Companion-App"', '" (Host-API "', 'DateTime.Now.ToString("HH:mm:ss")'):
            self.assertIn(part, handle)
        self.assertIn('"Menü Mic device: "', method_body(mic, "private string MenuEntriesText()"))
        self.assertIn("MenuEntriesText()", method_body(mic, "private void RefreshStatus()"))

    def test_info_field_is_larger_and_per_tab(self):
        plugin = source("AIBody.cs")
        self.assertIn("status.height = 1600f;", plugin)
        refresh = method_body(plugin, "private void RefreshStatus()")
        for moved in ("SelfTest()", "Start-Protokoll", "Letzte Ereignisse", "<b>Live</b>"):
            self.assertNotIn(moved, refresh, "only the open tab's info in the field")
        info = method_body(plugin, "private string TabInfo()")
        self.assertIn("SelfTest()", info)
        self.assertIn("Start-Protokoll", info)

    def test_no_empty_pose_menu(self):
        body = method_body(source("Body.cs"), "public void BuildCharacterTab(UiPage page)")
        guard = body.index("PoseNames.Count > 0")
        self.assertLess(guard, body.index("page.ScrollablePopup(_poseChoiceJson)"))


if __name__ == "__main__":
    unittest.main()
