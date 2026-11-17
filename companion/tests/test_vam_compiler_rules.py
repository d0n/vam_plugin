"""VaM's C# compiler (old Mono mcs) rejects foreach over Dictionary .Keys/.Values with CS584
(version 13). tools/sandbox_rules.py bans those constructs; this test pins the rule and checks src/."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("sandbox_rules", ROOT / "tools" / "sandbox_rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

BANNED = [
    "foreach (Dictionary<string, float> preset in _presets.Values)",   # the v13 line (CS584 in VaM)
    "foreach (string n in preset.Keys)",
    "foreach (string n in _poseFiles.Keys)",
    'foreach (JSONClass def in a.b["c"].Values)',
    "var first = names.Keys.First();",
    "Dictionary<string, int>.ValueCollection values = d.Values;",
]
ALLOWED = [
    "foreach (KeyValuePair<string, JSONClass> kv in _gestures)",
    "return new List<string>(_presets.Keys);",
    "_layer.ReleaseAllExcept(targets.Keys);",
]


class VamCompilerRuleTests(unittest.TestCase):
    def test_banned_constructs_are_found(self):
        for line in BANNED:
            self.assertTrue(rules.scan_text("x.cs", line), line)

    def test_allowed_constructs_pass(self):
        for line in ALLOWED:
            self.assertEqual(rules.scan_text("x.cs", line), [], line)

    def test_plugin_sources_are_clean(self):
        files = sorted((ROOT / "src").rglob("*.cs"))
        self.assertTrue(files)
        problems = rules.scan_files((str(p), p.read_text(encoding="utf-8")) for p in files)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
