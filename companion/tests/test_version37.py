"""Version 37 (Leon, 20.11.2026): new AIBody example scene with a Load Scene preview thumbnail,
the menu rebuild after version 36 (menus by topic, Body control on, gaze/blinking removed),
and the package number 37.
"""
from __future__ import annotations

import importlib.util
import json
import re
import zipfile
from pathlib import Path
from unittest import TestCase

from aibody_companion import __version__
from aibody_companion import setup as first_start

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "AIBody"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


GENITAL_MORPHS = {
    "Labia majora-relaxation", "Labia majora-spread-LLow", "Labia majora-spread-RLow",
    "Labia minora-relaxation", "Labia minora-size", "Labia minora-thickness",
    "Pubic Area Size", "OpenXXL", "Penis Length", "Penis Width",
}


class VersionTests(TestCase):
    def test_version_37_everywhere(self):
        self.assertEqual(__version__, "37")
        self.assertIn('PluginVersion = "37"', source("AIBody.cs"))
        self.assertEqual(json.loads((ROOT / "packaging" / "AIBody.json").read_text())["version"], 37)
        self.assertTrue(re.search(r"d0n\.AIBody\.37:", first_start.TEMPLATE.read_text()))
        self.assertEqual(first_start.TEMPLATE, ROOT / "examples" / "scenes" / "AIBody_Example.json")


class ExampleSceneTests(TestCase):
    def setUp(self):
        self.template = json.loads(first_start.TEMPLATE.read_text(encoding="utf-8"))
        self.text = first_start.TEMPLATE.read_text(encoding="utf-8")

    def test_no_foreign_package_or_loose_asset_refs(self):
        pkgs = re.findall(r"[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+\.\d+:/", self.text)
        self.assertEqual(set(pkgs), {"d0n.AIBody.37:/"})
        self.assertNotIn("Custom/", self.text.replace("Custom/Scripts/d0n/AIBody/AIBody.cslist", ""))
        self.assertNotIn("Saves/", self.text)
        self.assertNotIn("NoStage3", self.text)
        self.assertNotIn("Dollmaster", self.text)
        self.assertNotIn("ImprovedPoV", self.text)

    def test_aibody_only_on_the_female_person(self):
        plugins = []
        for atom in self.template["atoms"]:
            for st in atom.get("storables") or []:
                if st.get("id") == "PluginManager":
                    for value in (st.get("plugins") or {}).values():
                        plugins.append((atom["id"], value))
        self.assertEqual(plugins, [("Person", "d0n.AIBody.37:/Custom/Scripts/d0n/AIBody/AIBody.cslist")])
        female = next(a for a in self.template["atoms"] if a["id"] == "Person")
        male = next(a for a in self.template["atoms"] if a["id"] == "BryanGosling")
        self.assertEqual(next(st for st in female["storables"] if st["id"] == "geometry")["character"], "Female 1")
        self.assertEqual(next(st for st in male["storables"] if st["id"] == "geometry")["character"], "Male 4")

    def test_no_genital_morphs(self):
        names = []
        for atom in self.template["atoms"]:
            for st in atom.get("storables") or []:
                if st.get("id") == "geometry":
                    for morph in st.get("morphs") or []:
                        names.append(morph.get("uid") or morph.get("name"))
        self.assertEqual(set(names) & GENITAL_MORPHS, set())

    def test_figures_have_no_clothing(self):
        for atom_id in ("Person", "BryanGosling"):
            atom = next(a for a in self.template["atoms"] if a["id"] == atom_id)
            geom = next(st for st in atom["storables"] if st["id"] == "geometry")
            self.assertEqual(geom.get("clothing") or [], [])

    def test_preview_thumbnail_exists_and_is_512(self):
        thumb = first_start.TEMPLATE.with_suffix(".jpg")
        self.assertTrue(thumb.is_file())
        self.assertGreater(thumb.stat().st_size, 1000)
        header = thumb.read_bytes()[:4]
        self.assertEqual(header, b"\xff\xd8\xff\xe0")  # JPEG SOI + JFIF-ish; accept any JPEG SOI
        # relax: just SOI
        self.assertTrue(thumb.read_bytes().startswith(b"\xff\xd8\xff"))
        from PIL import Image
        im = Image.open(thumb)
        self.assertEqual(im.size, (512, 512))


class SetupThumbTests(TestCase):
    def test_write_scene_copies_the_thumbnail(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = first_start.write_scene(tmp, False)
            self.assertTrue(path.is_file())
            thumb = Path(tmp) / first_start.THUMB_REL
            self.assertTrue(thumb.is_file())
            self.assertEqual(thumb.read_bytes(), first_start.TEMPLATE.with_suffix(".jpg").read_bytes())


class VarTests(TestCase):
    def test_var_contains_the_scene_thumbnail_and_no_dependency(self):
        spec = importlib.util.spec_from_file_location("build_var37", ROOT / "tools" / "build_var.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        loose_path = ROOT / "dist" / build.LOOSE_SCENE
        loose_thumb = ROOT / "dist" / build.LOOSE_THUMB
        kept = loose_path.read_bytes() if loose_path.exists() else None
        kept_thumb = loose_thumb.read_bytes() if loose_thumb.exists() else None
        out = build.build(version_override=9037)
        try:
            with zipfile.ZipFile(out) as z:
                meta = json.loads(z.read("meta.json"))
                self.assertEqual(meta.get("dependencies", {}), {})
                self.assertEqual(meta.get("licenseType"), "FC")
                self.assertIn(build.SCENE_PATH, z.namelist())
                self.assertIn(build.SCENE_THUMB_PATH, z.namelist())
                self.assertIn(build.SCENE_PATH, meta["contentList"])
                self.assertIn(build.SCENE_THUMB_PATH, meta["contentList"])
                scene = z.read(build.SCENE_PATH).decode("utf-8")
                plugins = [p for a in json.loads(scene)["atoms"] for st in a["storables"]
                           if st["id"] == "PluginManager" for p in st["plugins"].values()]
                self.assertEqual(plugins, ["SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist"])
                self.assertIn(plugins[0][len("SELF:/"):], z.namelist())
                self.assertNotIn("9037", scene)
                self.assertTrue(z.read(build.SCENE_THUMB_PATH).startswith(b"\xff\xd8\xff"))
            loose = (out.parent / build.LOOSE_SCENE).read_text(encoding="utf-8")
            self.assertIn("d0n.AIBody.9037:/Custom/Scripts/d0n/AIBody/AIBody.cslist", loose)
            self.assertEqual((out.parent / build.LOOSE_THUMB).read_bytes(),
                             (ROOT / "examples" / "scenes" / "AIBody_Example.jpg").read_bytes())
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
