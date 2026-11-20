"""Plugin preset in the package (version 31): Custom/Atom/Person/Plugins/AIBody/Preset_AIBody.vap registers the .cslist."""
from __future__ import annotations

import importlib.util
import json
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_build_var():
    spec = importlib.util.spec_from_file_location("build_var", ROOT / "tools" / "build_var.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginPresetTests(unittest.TestCase):
    def test_preset_lists_exactly_one_plugin_the_package_cslist(self):
        build = load_build_var()
        data = json.loads(build.plugin_preset("d0n", "AIBody", 31, "Custom/Scripts/d0n/AIBody"))
        self.assertEqual(list(data), ["storables"])
        self.assertEqual(len(data["storables"]), 1)
        manager = data["storables"][0]
        self.assertEqual(manager["id"], "PluginManager")
        self.assertEqual(manager["plugins"], {"plugin#0": "d0n.AIBody.31:/Custom/Scripts/d0n/AIBody/AIBody.cslist"})

    def test_preset_is_in_the_package_and_the_content_list(self):
        build = load_build_var()
        loose = ROOT / "dist" / build.LOOSE_SCENE
        kept = loose.read_bytes() if loose.exists() else None
        path = build.build(31)
        self.addCleanup(path.unlink)
        self.addCleanup(lambda: loose.write_bytes(kept) if kept is not None else loose.unlink())
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            self.assertIn(build.PRESET_PATH, names)
            self.assertTrue(build.PRESET_PATH.startswith("Custom/Atom/Person/Plugins/"))
            meta = json.loads(z.read("meta.json"))
            self.assertIn(build.PRESET_PATH, meta["contentList"])
            self.assertEqual(sorted(meta["contentList"]), sorted(n for n in names if n != "meta.json"))
            preset = json.loads(z.read(build.PRESET_PATH))
            self.assertIn(f"d0n.AIBody.31:/Custom/Scripts/d0n/AIBody/AIBody.cslist", json.dumps(preset))
            cslists = [n for n in names if n.endswith(".cslist")]
            self.assertEqual(cslists, ["Custom/Scripts/d0n/AIBody/AIBody.cslist"], "still ONE plugin, ONE .cslist")

    def test_source_marks_the_unverified_part(self):
        self.assertIn("TODO(verify)", (ROOT / "tools" / "build_var.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
