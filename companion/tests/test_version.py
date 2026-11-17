"""Version scheme since 12: plugin version = companion version = package number of d0n.AIBody.<n>.var."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from aibody_companion import __version__

ROOT = Path(__file__).resolve().parents[2]


class VersionTests(unittest.TestCase):
    def test_versions_equal_the_package_number(self):
        package = json.loads((ROOT / "packaging" / "AIBody.json").read_text(encoding="utf-8"))["version"]
        plugin_src = (ROOT / "src" / "AIBody" / "AIBody.cs").read_text(encoding="utf-8")
        pyproject_src = (ROOT / "companion" / "pyproject.toml").read_text(encoding="utf-8")
        plugin = re.search(r'PluginVersion = "([^"]+)"', plugin_src)
        pyproject = re.search(r'^version = "([^"]+)"', pyproject_src, re.M)
        self.assertIsInstance(package, int)
        self.assertEqual(plugin.group(1), str(package))
        self.assertEqual(__version__, str(package))
        self.assertEqual(pyproject.group(1), str(package))


if __name__ == "__main__":
    unittest.main()
