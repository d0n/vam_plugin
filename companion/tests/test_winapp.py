"""The Windows launcher of the installed AIBody Companion (winapp.py): pure parts, runnable on any OS."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from aibody_companion import winapp

ROOT = Path(__file__).resolve().parents[2]


def make_vam(folder: Path, exe: bool = True) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    if exe:
        (folder / "VaM.exe").write_bytes(b"")
    else:
        (folder / "AddonPackages").mkdir()
        (folder / "Saves").mkdir()
    return folder


class DetectTests(TestCase):
    def test_looks_like_vam(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(winapp.looks_like_vam(make_vam(Path(tmp) / "a")))
            self.assertTrue(winapp.looks_like_vam(make_vam(Path(tmp) / "b", exe=False)))
            (Path(tmp) / "c").mkdir()
            self.assertFalse(winapp.looks_like_vam(Path(tmp) / "c"))
            self.assertFalse(winapp.looks_like_vam(None))
            self.assertFalse(winapp.looks_like_vam(Path(tmp) / "missing"))

    def test_order_remembered_then_inside_then_common(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            vam = make_vam(t / "VaM")
            other = make_vam(t / "Other")
            inside = vam / "Tools" / "AIBody Companion"
            inside.mkdir(parents=True)
            self.assertEqual(winapp.detect_vam_root(inside, str(other), []), (other, "remembered"))
            self.assertEqual(winapp.detect_vam_root(inside, None, [other])[0].resolve(), vam.resolve())
            self.assertEqual(winapp.detect_vam_root(t / "nowhere", None, [t / "x", other]), (other, "found at a common place"))
            self.assertEqual(winapp.detect_vam_root(t / "nowhere", str(t / "gone"), []), (None, "not found"))

    def test_common_candidates_cover_drives_and_home(self):
        paths = winapp.common_candidates([Path("D:/")], env={"USERPROFILE": "/home/u"})
        self.assertIn(Path("D:/") / "VaM", paths)
        self.assertTrue(any(p.name == "Virt-A-Mate" for p in paths))
        self.assertIn(Path("/home/u") / "VaM", paths)


class SettingsTests(TestCase):
    def test_data_dir_is_local_appdata_not_the_install_dir(self):
        self.assertEqual(winapp.data_dir({"LOCALAPPDATA": "C:/Users/x/AppData/Local"}),
                         Path("C:/Users/x/AppData/Local") / "AIBody Companion")

    def test_remember_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "AIBody Companion"
            self.assertEqual(winapp.load_settings(folder), {})
            winapp.save_settings(folder, {"vam_root": "D:\\VaM"})
            self.assertEqual(winapp.load_settings(folder), {"vam_root": "D:\\VaM"})
            (folder / winapp.SETTINGS_FILE).write_text("not json")
            self.assertEqual(winapp.load_settings(folder), {})


class SingleInstanceTests(TestCase):
    def test_second_instance_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = winapp.SingleInstance("test", lock_dir=Path(tmp))
            second = winapp.SingleInstance("test", lock_dir=Path(tmp))
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()


class LauncherSourceTests(TestCase):
    def test_runs_the_companion_without_console_questions(self):
        src = (ROOT / "companion" / "aibody_companion" / "winapp.py").read_text(encoding="utf-8")
        self.assertIn('cli.main(["--vam-root", str(root), "--no-stdin", "--no-setup"])', src)
        self.assertIn("now running in the background", winapp.RUNNING_NOTE)
        self.assertIn("already running", winapp.ALREADY_NOTE)
        self.assertNotIn("api_key", src)

    def test_packaging_files(self):
        iss = (ROOT / "packaging" / "companion" / "AIBodyCompanion.iss").read_text(encoding="utf-8")
        for part in ("PrivilegesRequired=lowest", "{localappdata}\\Programs\\AIBody Companion",
                     "OutputBaseFilename=AIBody Companion Setup", "Name: \"desktopicon\"", "Name: \"autostart\"",
                     "{userstartup}", "postinstall", "Flags: unchecked"):
            self.assertIn(part, iss)
        wf = (ROOT / ".github" / "workflows" / "companion-windows.yml").read_text(encoding="utf-8")
        for part in ("windows-latest", "pyinstaller", "--windowed", "--selftest", "ISCC", "upload-artifact",
                     "scan_tokens.py"):
            self.assertIn(part, wf)
