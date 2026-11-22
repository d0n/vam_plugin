#!/usr/bin/env python3
"""Builds the AIBody VaM package: ONE .var with ONE plugin (one .cslist, one MVRScript).

  dist/d0n.AIBody.<N>.var
    meta.json
    Custom/Scripts/d0n/AIBody/AIBody.cslist   (+ the .cs files it lists, same folder)
    Custom/Scripts/d0n/AIBody/AIBodyTest.wav  (test tone for the plugin's "Play test tone")
    Custom/Scripts/d0n/AIBody/AIBodyTest2.wav, AIBodyTest3.wav  (version 44: 2x / 3x louder copies, Speech volume > 1)
    Custom/Atom/Person/Plugins/AIBody/Preset_AIBody.vap  (plugin preset, version 31: adds the plugin to a Person)
    Saves/scene/AIBody/AI-Buddy.json     (the AIBody scene = the "Scene" choice; VaM's scene browser lists
                                                scenes of packages below Saves/scene/; the plugin is referenced as
                                                "SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist" = this package)
    Saves/scene/AIBody/AI-Buddy.jpg      (version 37: preview thumbnail next to the scene, same base name, so
                                                VaM's Load Scene menu can show it)
  dist/AI-Buddy.json                     (optional loose copy for <VaM>/Saves/scene/AIBody/, release asset; it
                                                references "d0n.AIBody.<N>:/..." because SELF: only works in a package)
  dist/AI-Buddy.jpg                      (the same thumbnail next to the loose scene)

meta.json is packaging/meta.json (unchanged, incl. licenseType) with the overrides from
packaging/AIBody.json, which also sets the package version <N>. The script folder is assembled by
tools/assemble_plugins.py (the legacy plugins in legacy/ are never packaged). After writing,
every file inside the .var is scanned with the strict sandbox rules (tools/sandbox_rules.py);
on any match the .var is deleted and the build fails.

Usage: python tools/build_var.py [--version N]
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import math
import struct
import wave
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "build" / "var" / "AIBody"
SCRIPT_FOLDER = "AIBody"
TEST_TONE = "AIBodyTest.wav"  # Body.TestToneFile
PRESET_PATH = "Custom/Atom/Person/Plugins/AIBody/Preset_AIBody.vap"  # VaM's folder for Person plugin presets


SCENE_PATH = "Saves/scene/AIBody/AI-Buddy.json"
SCENE_THUMB_PATH = "Saves/scene/AIBody/AI-Buddy.jpg"
SCENE_TEMPLATE = ROOT / "examples" / "scenes" / "AI-Buddy.json"
SCENE_THUMB = SCENE_TEMPLATE.with_suffix(".jpg")

LOOSE_SCENE = "AI-Buddy.json"
# The one atom of the example scene that carries AIBody: the user's own male "Client" (Leon, 21.11.2026 18:27; it drives
# the female "AI", AIBodyPlugin.FindAiCharacter). Before: "BryanGosling" (17:02), the female "Person".
AIBODY_ATOM = "Client"
AIBODY_STORABLE = "plugin#0_AIBody.AIBodyPlugin"
LOOSE_THUMB = "AI-Buddy.jpg"
# Tab Dollmaster (22.11.2026, Leon): the assets of the ported Dollmaster (VAMDeluxe, MIT) next to the plugin, as in the old
# Dollmaster package: <script_dir>/Dollmaster/dollmaster_config.json and <script_dir>/Dollmaster/Assets/... (personas, sound
# effects, expressions, VAMasutra poses). AIBodyPlugin.DollmasterFolder, DmPlugin.ASSETS_PATH.
DOLLMASTER_ASSETS = ROOT / "assets" / "dollmaster"
DOLLMASTER_FOLDER = "Dollmaster"
# Text files of the package (scanned with the sandbox rules); audio and images are binary and only packed.
TEXT_SUFFIXES = {".cs", ".cslist", ".json", ".vap", ".txt", ".md"}
STORED_SUFFIXES = {".mp3", ".jpg", ".png", ".ogg"}   # already compressed


def check_aibody_atom(data: dict) -> None:
    """AIBody (PluginManager entry and its saved values) on AIBODY_ATOM only; the scene's saved background is on."""
    holders, settings = [], []
    for atom in data.get("atoms", []):
        for st in atom.get("storables", []):
            if st.get("id") == "PluginManager" and st.get("plugins"):
                holders.append(atom.get("id"))
            if st.get("id") == AIBODY_STORABLE:
                settings.append((atom.get("id"), st))
    if holders != [AIBODY_ATOM] or [a for a, _ in settings] != [AIBODY_ATOM]:
        raise SystemExit(f"scene template: AIBody must be on {AIBODY_ATOM} only (plugin on {holders}, "
                         f"settings on {[a for a, _ in settings]})")
    if settings[0][1].get("Set background color") != "true":
        raise SystemExit("scene template: 'Set background color' of AIBody must be on")


def example_scene(creator: str, package: str, version: int, script_dir: str, inside_package: bool = True) -> str:
    """The AI-Buddy scene template (Leon's scene of 21.11.2026 18:27) with AIBody on the male "Client", which drives the female "AI". Third-party clothing, hair and morph packages
    stay in the scene and are declared in packaging/meta.json "dependencies" (VaM format: package id -> licenseType
    when known from a Hub lookup, plus nested dependencies). Loose Custom/ and Saves/ paths stay in the scene too
    (they resolve on the author's PC; VaM skips them elsewhere) and are not packaged. Inside the package the plugin
    is "SELF:/<script_dir>/AIBody.cslist" (VaM's prefix for content of the same package, E34), so the scene never
    points at another version; the loose copy uses "<creator>.<package>.<version>:/...".
    TODO(verify) in VaM: the scene is listed by Open Scene, PluginManager resolves SELF:, and missing dependencies
    are shown."""
    data = json.loads(SCENE_TEMPLATE.read_text(encoding="utf-8"))
    prefix = "SELF" if inside_package else f"{creator}.{package}.{version}"
    cslist = f"{prefix}:/{script_dir}/AIBody.cslist"
    for atom in data.get("atoms", []):
        for st in atom.get("storables", []):
            if st.get("id") == "PluginManager":
                for key, value in list(st.get("plugins", {}).items()):
                    if value.endswith(f"/{script_dir}/AIBody.cslist"):
                        st["plugins"][key] = cslist
                    else:
                        raise SystemExit(f"scene template references another plugin: {value}")
    check_aibody_atom(data)
    return json.dumps(data, indent=3) + "\n"


def plugin_preset(creator: str, package: str, version: int, script_dir: str) -> str:
    """The plugin preset (.vap, JSON): the Person's PluginManager storable with ONE plugin, the package's .cslist.
    Only the plugin list is stored: the plugin keeps all its settings in config.json, so no parameter values are
    written and the preset cannot overwrite anything of the scene. TODO(verify) in VaM: the preset appears in the
    Person's Plugins tab > Load Preset, and the package-qualified path "<creator>.<package>.<version>:/..." is accepted."""
    cslist = f"{creator}.{package}.{version}:/{script_dir}/AIBody.cslist"
    return json.dumps({"storables": [{"id": "PluginManager", "plugins": {"plugin#0": cslist}}]}, indent=3) + "\n"


# Peak of the test tone (fraction of full scale). Leon, 21.11.2026 20:04: 0.35 was very quiet in v42; 0.70 is
# +6 dB, still clear of clipping (<= 0.8). Only the test tone; speech volume is unchanged.
TEST_TONE_PEAK = 0.70


# Version 44 (Leon 21:01/21:16): louder copies for Speech volume above 1 (VaM's head audio stops at 1). Same plain linear
# gain as the companion (pipeline/tts.py gained_sample): no limiter, only cut to the 16-bit range.
LOUD_TEST_TONES = {2: "AIBodyTest2.wav", 3: "AIBodyTest3.wav"}  # gain -> file (Body.TestToneFileFor)


def gained_sample(value: int, gain: float) -> int:
    return max(-32768, min(32767, int(round(value * gain))))


def test_tone_wav(seconds: float = 1.5, rate: int = 22050, gain: float = 1.0) -> bytes:
    """16-bit mono PCM WAV: a two-note chime with 4 "syllables" per second (the jaw moves); gain > 1 = louder copy."""
    frames = bytearray()
    for i in range(int(seconds * rate)):
        t = i / rate
        freq = 440.0 if t < seconds / 2 else 660.0
        fade = min(1.0, t / 0.02, (seconds - t) / 0.05)
        envelope = 0.55 + 0.45 * math.sin(2 * math.pi * 4 * t)
        sample = int(TEST_TONE_PEAK * fade * envelope * math.sin(2 * math.pi * freq * t) * 32767)
        if gain != 1.0:
            sample = gained_sample(sample, gain)
        frames += struct.pack("<h", sample)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def assemble() -> list[str]:
    spec = importlib.util.spec_from_file_location("assemble_plugins", ROOT / "tools" / "assemble_plugins.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.assemble(STAGE)


def scan_var(path: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location("sandbox_rules", ROOT / "tools" / "sandbox_rules.py")
    rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules)
    with zipfile.ZipFile(path) as z:
        items = [(f"{path.name}:{n}", z.read(n).decode("utf-8", "replace")) for n in z.namelist()
                 if Path(n).suffix.lower() in TEXT_SUFFIXES]
    return rules.scan_files(items)


def dollmaster_files() -> list[tuple[Path, str]]:
    """(file, path below <script_dir>/Dollmaster) of every Dollmaster asset, sorted."""
    if not DOLLMASTER_ASSETS.is_dir():
        raise SystemExit(f"missing Dollmaster assets: {DOLLMASTER_ASSETS}")
    files = sorted(p for p in DOLLMASTER_ASSETS.rglob("*") if p.is_file())
    return [(p, p.relative_to(DOLLMASTER_ASSETS).as_posix()) for p in files]


def build(version_override: int | None = None) -> Path:
    meta = json.loads((ROOT / "packaging" / "meta.json").read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / "packaging" / "AIBody.json").read_text(encoding="utf-8"))
    overrides.pop("_comment", None)
    version = version_override or int(overrides.pop("version", 1))
    overrides.pop("version", None)
    for key, value in overrides.items():
        meta[key] = value.replace("<version>", str(version)) if isinstance(value, str) else value
    creator = meta["creatorName"]
    script_dir = f"Custom/Scripts/{creator}/{SCRIPT_FOLDER}"

    files = assemble()
    (STAGE / TEST_TONE).write_bytes(test_tone_wav())
    files.append(TEST_TONE)
    for gain, name in LOUD_TEST_TONES.items():
        (STAGE / name).write_bytes(test_tone_wav(gain=gain))
        files.append(name)
    packaged = [PRESET_PATH, SCENE_PATH]
    if not SCENE_THUMB.is_file():
        raise SystemExit(f"missing scene thumbnail: {SCENE_THUMB}")
    packaged.append(SCENE_THUMB_PATH)
    dollmaster = dollmaster_files()
    meta["contentList"] = ([f"{script_dir}/{f}" for f in files] + packaged
                           + [f"{script_dir}/{DOLLMASTER_FOLDER}/{rel}" for _, rel in dollmaster])
    out = ROOT / "dist" / f"{creator}.{meta['packageName']}.{version}.var"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, indent=2))
        for f in files:
            z.write(STAGE / f, f"{script_dir}/{f}")
        z.writestr(PRESET_PATH, plugin_preset(creator, meta["packageName"], version, script_dir))
        z.writestr(SCENE_PATH, example_scene(creator, meta["packageName"], version, script_dir))
        z.write(SCENE_THUMB, SCENE_THUMB_PATH)
        for src, rel in dollmaster:
            stored = src.suffix.lower() in STORED_SUFFIXES
            z.write(src, f"{script_dir}/{DOLLMASTER_FOLDER}/{rel}", zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
    (out.parent / LOOSE_SCENE).write_text(example_scene(creator, meta["packageName"], version, script_dir, False),
                                          encoding="utf-8")
    (out.parent / LOOSE_THUMB).write_bytes(SCENE_THUMB.read_bytes())
    thumb_problem = check_scene_thumbnail(out)
    if thumb_problem:
        out.unlink()
        raise SystemExit("scene thumbnail (deleted the .var): " + thumb_problem)
    problems = scan_var(out)
    if problems:
        out.unlink()
        raise SystemExit("forbidden APIs inside the .var (deleted):\n" + "\n".join(problems))
    print(f"Wrote {out.relative_to(ROOT)} ({len(files) + 3} files + {len(dollmaster)} Dollmaster assets); strict scan of the .var: 0 forbidden matches")
    return out


def check_scene_thumbnail(var: Path) -> str | None:
    """Version 47 (Leon 22.11.2026 12:17): VaM shows a scene's thumbnail only when a JPG with the SAME base name sits in
    the SAME folder as the scene JSON. Every .var must carry it, byte for byte the one in examples/scenes/."""
    with zipfile.ZipFile(var) as z:
        names = z.namelist()
        scenes = [n for n in names if n.startswith("Saves/scene/") and n.endswith(".json")]
        if not scenes:
            return "no scene JSON below Saves/scene/"
        for scene in scenes:
            thumb = scene[: -len(".json")] + ".jpg"
            if thumb not in names:
                return f"{scene} has no {thumb} next to it"
            data = z.read(thumb)
            if not data.startswith(b"\xff\xd8"):
                return f"{thumb} is not a JPEG"
            if thumb == SCENE_THUMB_PATH and data != SCENE_THUMB.read_bytes():
                return f"{thumb} differs from {SCENE_THUMB.relative_to(ROOT)}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, help="override the package version from packaging/AIBody.json")
    args = parser.parse_args()
    build(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
