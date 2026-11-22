"""Version 37 (Leon, 20.11.2026): new example scene with a Load Scene preview thumbnail,
the menu rebuild after version 36 (menus by topic, Body control on, gaze/blinking removed),
and the package number 37.

After version 37 (21.11.2026, no version bump): the example is Leon's original two-character
scene, named AI-Buddy, with clothing and looks kept, Dollmaster / Improved PoV and explicit
genital morphs removed, AIBody on the female with Set background color on, and third-party
packages declared in meta.json dependencies.
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

SCENE_PACKAGES = {
    "Ark1F1.Olivia_McAllister.1",
    "EuLinRabei.ProCourt_Outfit.3",
    "Molmark.Police_uniform.2",
    "NoStage3.Hair_Long_Backswept_Pony.1",
    "Wolverine333.LAUREN_4.1",
    "mopedlampe.Morwyn.1",
    "paledriver.Nico.2",
    "particle pinnacle.missing_morphs.1",
    "KdollMASTA.KDoll_Mk10.1",   # Leon's scene of 21.11.2026 18:27: the Breath1 morph (AIBody's default breath morph)
}
HUB_LICENSES = {
    "EuLinRabei.ProCourt_Outfit.3": "CC BY-SA",
    "Molmark.Police_uniform.2": "CC BY",
    "NoStage3.Hair_Long_Backswept_Pony.1": "CC BY",
    "Wolverine333.LAUREN_4.1": "CC BY",
    "mopedlampe.Morwyn.1": "CC BY",
    "paledriver.Nico.2": "CC BY-NC-ND",
}
# Looked up on the Hub 21.11.2026 (getResourceDetail, no download); these packages were not on the Hub
# (KDoll_Mk10: version 42, Leon's scene of 18:27).
HUB_LICENSE_UNKNOWN = {
    "Ark1F1.Olivia_McAllister.1",
    "particle pinnacle.missing_morphs.1",
    "KdollMASTA.KDoll_Mk10.1",
}
GENITAL_MORPHS = {
    "Labia majora-relaxation", "Labia majora-spread-LLow", "Labia majora-spread-RLow",
    "Labia minora-relaxation", "Labia minora-size", "Labia minora-thickness",
    "Pubic Area Size", "OpenXXL", "Penis Length", "Penis Width",
}
REMOVED_ATOMS = {"Doll SFX Person", "Thrust AP Person", "AnimationStep", "AnimationStep#2"}
LOOSE_LOCAL_CONTENT = {
    "Custom/Atom/Person/Morphs/female/AUTO/FHMGiselle.vmi",
    "Custom/Atom/Person/Morphs/female/AUTO/FHMShaneka.vmi",
    "Custom/Atom/Person/Morphs/female/AUTO/PHMGiselleEyelashes.vmi",
    "Custom/Atom/Person/Morphs/female/CTRLFitness.vmi",
    "Custom/Atom/Person/Morphs/female/Claire 0401 Alt-cc2d3570.vmi",
    "Custom/Atom/Person/Morphs/male/AUTO/RG InOut.vmi",
    "Custom/Atom/Person/Morphs/male/AUTO/RG Side2Side.vmi",
    "Custom/Atom/Person/Morphs/male/Bryan Gosling.vmi",
    "Custom/Atom/Person/Textures/N3DX/0329/0329_face v5.jpg",
    "Custom/Atom/Person/Textures/N3DX/0329/0329_limbs.jpg",
    "Custom/Atom/Person/Textures/N3DX/0329/0329_torso.jpg",
    "Custom/Atom/Person/Textures/Tan Lines (Decals)/Base Female/6%/String Bikini (select)/genitalsDecal.png",
    "Custom/Atom/Person/Textures/Tan Lines (Decals)/Base Female/6%/String Bikini (select)/torsoDecal.png",
    "Custom/Clothing/Male/PositiveResult/HoodieMale/HoodieMale_Down.vam",
    "Custom/Hair/Female/scamp/Samples/THEV.vam",
    "Saves/scene/Tiseb29/RetroGlide/RetroSlinger_RyanG/BryanGoslingFace.jpg",
}


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def scene_packages(text: str) -> set[str]:
    pkgs = re.findall(r"([A-Za-z0-9_ .-]+\.[A-Za-z0-9_ .-]+\.\d+):/", text)
    return {p for p in pkgs if not p.startswith("d0n.AIBody.")}


class VersionTests(TestCase):
    def test_version_37_everywhere(self):
        """Historical: version 37 sources are gone after the v38 bump; consistency is test_version47."""
        self.assertTrue((ROOT / "companion" / "tests" / "test_version37.py").is_file())
        self.assertEqual(first_start.TEMPLATE, ROOT / "examples" / "scenes" / "AI-Buddy.json")
        self.assertEqual(first_start.SCENE_REL, "Saves/scene/AIBody/AI-Buddy.json")
        self.assertEqual(first_start.THUMB_REL, "Saves/scene/AIBody/AI-Buddy.jpg")
        self.assertIn(" > AI-Buddy ", source("AIBody.cs"))
        self.assertNotIn("AIBody_Example", source("AIBody.cs"))


class ExampleSceneTests(TestCase):
    def setUp(self):
        self.template = json.loads(first_start.TEMPLATE.read_text(encoding="utf-8"))
        self.text = first_start.TEMPLATE.read_text(encoding="utf-8")

    def test_package_refs_match_meta_dependencies(self):
        self.assertEqual(scene_packages(self.text), SCENE_PACKAGES)
        meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta.get("licenseType"), "FC")
        deps = meta.get("dependencies") or {}
        self.assertEqual(set(deps), SCENE_PACKAGES)
        for name, license_type in HUB_LICENSES.items():
            self.assertEqual(deps[name].get("licenseType"), license_type)
            self.assertEqual(deps[name].get("dependencies"), {})
        for name in HUB_LICENSE_UNKNOWN:
            self.assertNotIn("licenseType", deps[name], "license was not on the Hub; do not invent one")
            self.assertEqual(deps[name].get("dependencies"), {})
        self.assertNotIn("WeebU.Amy_Demon_futa_scenes.2", deps)
        self.assertNotIn("JoyBoy.Andi_Collection.2", deps)

    def test_conflicting_plugins_and_dollmaster_parts_are_gone(self):
        self.assertNotIn("Dollmaster", self.text)
        self.assertNotIn("ImprovedPoV", self.text)
        self.assertNotIn("betterPOV", self.text)
        self.assertNotIn("WeebU.", self.text)
        self.assertNotIn("JoyBoy.", self.text)
        ids = {a["id"] for a in self.template["atoms"]}
        self.assertTrue(REMOVED_ATOMS.isdisjoint(ids))
        self.assertEqual(
            {a["id"] for a in self.template["atoms"]},
            {"WindowCamera", "PlayerNavigationPanel", "CoreControl", "[CameraRig]", "AI", "Client"},   # version 42: Leon's names,
        )
        core = next(a for a in self.template["atoms"] if a["id"] == "CoreControl")
        clips = next((st for st in core["storables"] if st["id"] == "URLAudioClipManager"), {}).get("clips") or []
        self.assertEqual(clips, [])

    def test_aibody_only_on_one_person_with_background_on(self):
        """Version 42 (Leon 18:27): AIBody is on the male Client and drives the female AI; before on BryanGosling / Person."""
        plugins = []
        for atom in self.template["atoms"]:
            for st in atom.get("storables") or []:
                if st.get("id") == "PluginManager":
                    for value in (st.get("plugins") or {}).values():
                        plugins.append((atom["id"], value))
        self.assertEqual(plugins, [("Client", f"d0n.AIBody.{__version__}:/Custom/Scripts/d0n/AIBody/AIBody.cslist")])
        female = next(a for a in self.template["atoms"] if a["id"] == "AI")
        male = next(a for a in self.template["atoms"] if a["id"] == "Client")
        self.assertEqual(next(st for st in female["storables"] if st["id"] == "geometry")["character"], "Female 1")
        self.assertEqual(next(st for st in male["storables"] if st["id"] == "geometry")["character"], "Male 4")
        self.assertFalse(any(s["id"] == first_start.AIBODY_STORABLE for s in female["storables"]))
        st = next(s for s in male["storables"] if s["id"] == first_start.AIBODY_STORABLE)
        self.assertEqual(st["Set background color"], "true")
        self.assertEqual(st["Background color"], {"h": "0.3333333", "s": "1", "v": "1"})

    def test_clothing_hair_and_normal_morphs_kept(self):
        female = next(a for a in self.template["atoms"] if a["id"] == "AI")
        male = next(a for a in self.template["atoms"] if a["id"] == "Client")
        fgeom = next(st for st in female["storables"] if st["id"] == "geometry")
        mgeom = next(st for st in male["storables"] if st["id"] == "geometry")
        self.assertEqual(
            [c["id"] for c in fgeom.get("clothing") or []],
            [
                "EuLinRabei.ProCourt_Outfit.3:"
                "/Custom/Clothing/Female/EuLinRabei/Pro Court Short F/Pro Court Short F.vam",
                "paledriver.Nico.2:/Custom/Clothing/Female/paledriver/Nico/Nico Tanktop.vam",
            ],
        )
        self.assertEqual(
            [c["id"] for c in mgeom.get("clothing") or []],
            [
                "Molmark.Police_uniform.2:/Custom/Clothing/Male/Molmark/Police uniform/police_male_pants.vam",
                "Custom/Clothing/Male/PositiveResult/HoodieMale/HoodieMale_Down.vam",
            ],
        )
        self.assertIn(
            "NoStage3.Hair_Long_Backswept_Pony.1:/Custom/Hair/Female/NoStage3/Long Backswept Pony/Long Backswept.vam",
            [h["id"] for h in fgeom.get("hair") or []],
        )
        names = []
        for atom in (female, male):
            for st in atom.get("storables") or []:
                if st.get("id") == "geometry":
                    for morph in st.get("morphs") or []:
                        names.append(morph.get("uid") or morph.get("name"))
        self.assertEqual(set(names) & GENITAL_MORPHS, set())
        self.assertFalse(any("AG2_M_OpenXXL" in (n or "") for n in names))
        self.assertTrue(any("Bryan Gosling.vmi" in (n or "") for n in names))

    def test_loose_custom_paths_are_kept_and_documented(self):
        for path in LOOSE_LOCAL_CONTENT:
            self.assertIn(path, self.text)
        guide = (ROOT / "docs" / "SCENE_GREENSCREEN.md").read_text(encoding="utf-8")
        spec = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("needs local content", guide)
        self.assertIn("needs local content", spec)
        for path in LOOSE_LOCAL_CONTENT:
            self.assertIn(path, guide)

    def test_preview_thumbnail_exists_and_is_512(self):
        thumb = first_start.TEMPLATE.with_suffix(".jpg")
        self.assertTrue(thumb.is_file())
        self.assertGreater(thumb.stat().st_size, 1000)
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
            self.assertEqual(path, Path(tmp) / "Saves/scene/AIBody/AI-Buddy.json")
            thumb = Path(tmp) / first_start.THUMB_REL
            self.assertTrue(thumb.is_file())
            self.assertEqual(thumb.read_bytes(), first_start.TEMPLATE.with_suffix(".jpg").read_bytes())
            st = next(s for a in json.loads(path.read_text())["atoms"] for s in a["storables"]
                      if s["id"] == first_start.AIBODY_STORABLE)
            self.assertEqual(st["Set background color"], "false")


class VarTests(TestCase):
    def test_var_contains_ai_buddy_and_declared_dependencies(self):
        spec = importlib.util.spec_from_file_location("build_var37", ROOT / "tools" / "build_var.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        loose_path = ROOT / "dist" / build.LOOSE_SCENE
        loose_thumb = ROOT / "dist" / build.LOOSE_THUMB
        kept = loose_path.read_bytes() if loose_path.exists() else None
        kept_thumb = loose_thumb.read_bytes() if loose_thumb.exists() else None
        expected_deps = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))["dependencies"]
        out = build.build(version_override=9037)
        try:
            with zipfile.ZipFile(out) as z:
                meta = json.loads(z.read("meta.json"))
                self.assertEqual(meta.get("dependencies"), expected_deps)
                self.assertEqual(meta.get("licenseType"), "FC")
                self.assertEqual(build.SCENE_PATH, "Saves/scene/AIBody/AI-Buddy.json")
                self.assertEqual(build.SCENE_THUMB_PATH, "Saves/scene/AIBody/AI-Buddy.jpg")
                self.assertIn(build.SCENE_PATH, z.namelist())
                self.assertIn(build.SCENE_THUMB_PATH, z.namelist())
                self.assertIn(build.SCENE_PATH, meta["contentList"])
                self.assertIn(build.SCENE_THUMB_PATH, meta["contentList"])
                self.assertTrue(all("AIBody_Example" not in n for n in z.namelist()))
                scene = z.read(build.SCENE_PATH).decode("utf-8")
                plugins = [p for a in json.loads(scene)["atoms"] for st in a["storables"]
                           if st["id"] == "PluginManager" for p in st["plugins"].values()]
                self.assertEqual(plugins, ["SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist"])
                self.assertIn(plugins[0][len("SELF:/"):], z.namelist())
                self.assertNotIn("9037", scene)
                self.assertNotIn("Dollmaster", scene)
                self.assertNotIn("ImprovedPoV", scene)
                self.assertIn('"Set background color": "true"', scene)
                self.assertTrue(z.read(build.SCENE_THUMB_PATH).startswith(b"\xff\xd8\xff"))
            loose = (out.parent / build.LOOSE_SCENE).read_text(encoding="utf-8")
            self.assertIn("d0n.AIBody.9037:/Custom/Scripts/d0n/AIBody/AIBody.cslist", loose)
            self.assertEqual((out.parent / build.LOOSE_THUMB).read_bytes(),
                             (ROOT / "examples" / "scenes" / "AI-Buddy.jpg").read_bytes())
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
