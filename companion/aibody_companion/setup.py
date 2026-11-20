"""First-start questions (version 35, Leon 20.11.2026).

The project had no interactive setup before (the plugin's only first-run element is the one-line note about the xAI
token in its UI), so these are the smallest sensible setup: two yes/no questions in the companion app's console, asked
once when the app starts for the first time (config.json "setup.asked" is false) and again with --setup. Order:

  1. "Do you want a green background to use pass-through?"
  2. "Do you want to use the standard scene as an example?"

What the answers do:

  - standard scene yes: the app writes the prepared scene examples/scenes/AIBody_GreenScreen.json (AI Character with
    AIBody of this version, Client Character, two invisible lights) to <VaM>/Saves/scene/AIBody/AIBody_Example.json.
    With green background yes it keeps the green #00FF00 background (Camera Background Color plugin by Sally on the
    Client Character, a Hub package the user installs); with no the scene has no background plugin, so it needs no
    third-party package at all.
  - standard scene no (plugin only): nothing is written. With green background yes the app explains where the green
    background is set: the Camera Background Color plugin (Sally) as a Scene plugin or on any atom of the user's own
    scene, Color #00FF00, Show Skybox off, and the same color as the chroma key in the headset.

The answers are stored in config.json "setup" (companion category; the plugin keeps it unchanged). Nothing here reaches
the network. A console that is not interactive (no TTY) skips the questions and logs how to ask them later.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable

from . import __version__, settings_file
from .atomicfile import atomic_write_bytes

log = logging.getLogger(__name__)

QUESTION_GREEN = "Do you want a green background to use pass-through?"
QUESTION_SCENE = "Do you want to use the standard scene as an example?"
TEMPLATE = Path(__file__).resolve().parents[2] / "examples" / "scenes" / "AIBody_GreenScreen.json"
SCENE_REL = "Saves/scene/AIBody/AIBody_Example.json"
AIBODY_SCRIPT = "/Custom/Scripts/d0n/AIBody/AIBody.cslist"
BACKGROUND_PLUGIN = "CameraBackgroundColor"
GREEN_HELP = (
    "Green background without the example scene: add the plugin 'Camera Background Color' by Sally "
    "(Hub package Sally.CameraBackgroundColor.7) to your own scene as a Scene plugin or on any atom, set Color to "
    "#00FF00 (R 0, G 255, B 0) and Show Skybox off, and set the chroma key of your headset / streaming app "
    "(e.g. Quest 3 with Virtual Desktop) to the same #00FF00. VaM itself only shows the green; the headset makes it "
    "transparent. Details: docs/SCENE_GREENSCREEN.md")


def ask_yes_no(question: str, ask: Callable[[str], str], say: Callable[[str], None]) -> bool:
    """Asks until the answer is yes or no (y / n, any case). End of input = no."""
    while True:
        try:
            answer = ask(f"{question} [yes/no]: ").strip().lower()
        except EOFError:
            return False
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        say("Please answer yes or no.")


def scene_data(green: bool, template: Path = TEMPLATE) -> dict[str, Any]:
    """The standard scene: AIBody of this version on the AI Character; without green the background plugin is removed."""
    data = json.loads(Path(template).read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    for atom in data.get("atoms", []):
        storables = atom.get("storables", [])
        for st in storables:
            if st.get("id") != "PluginManager":
                continue
            plugins = st.get("plugins", {})
            for key, value in list(plugins.items()):
                if value.endswith(AIBODY_SCRIPT):
                    plugins[key] = f"d0n.AIBody.{__version__}:{AIBODY_SCRIPT}"
                elif BACKGROUND_PLUGIN in value and not green:
                    del plugins[key]
        if not green:
            atom["storables"] = [st for st in storables if not str(st.get("id", "")).endswith("_" + BACKGROUND_PLUGIN)]
    return data


def write_scene(vam_root: str | Path, green: bool, template: Path = TEMPLATE) -> Path:
    """Writes the standard scene; an existing file is kept as .bak first. Returns the path."""
    path = Path(vam_root) / SCENE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copyfile(path, path.with_suffix(".json.bak"))
    atomic_write_bytes(path, (json.dumps(scene_data(green, template), indent=3) + "\n").encode("utf-8"))
    return path


def save_answers(vam_root: str | Path, green: bool, scene: bool) -> None:
    """Stores the answers in config.json "setup" (the rest of the file is kept)."""
    path = settings_file.settings_path(vam_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = settings_file.defaults()
    if not isinstance(data, dict):
        return
    data["setup"] = {"asked": True, "green_background": green, "example_scene": scene}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def already_asked(vam_root: str | Path) -> bool:
    data, _ = settings_file.load(settings_file.settings_path(vam_root))
    return bool(data and data.get("setup", {}).get("asked"))


def run(vam_root: str | Path, ask: Callable[[str], str] = input, say: Callable[[str], None] = print,
        template: Path = TEMPLATE) -> dict[str, Any]:
    """Asks both questions (green background first, then the standard scene), applies and stores the answers."""
    say("AIBody setup (asked once; 'python -m aibody_companion --setup' asks again).")
    green = ask_yes_no(QUESTION_GREEN, ask, say)
    scene = ask_yes_no(QUESTION_SCENE, ask, say)
    result: dict[str, Any] = {"green_background": green, "example_scene": scene, "scene_path": None}
    if scene:
        try:
            path = write_scene(vam_root, green, template)
            result["scene_path"] = str(path)
            say(f"Standard scene written: {path}. In VaM: Open Scene > {SCENE_REL}."
                + (" It has the green #00FF00 background: set your headset's chroma key to #00FF00 and install the Hub "
                   "package Sally.CameraBackgroundColor.7." if green else " It has no green background and needs no other package."))
        except (OSError, ValueError) as e:
            say(f"The standard scene could not be written ({e}). The template is {template}.")
            log.warning("Setup: standard scene not written: %s", e)
    else:
        say("Plugin only: add AIBody to your own Person atom (Plugins > Add Plugin > "
            f"d0n.AIBody.{__version__}:{AIBODY_SCRIPT}).")
        if green:
            say(GREEN_HELP)
    save_answers(vam_root, green, scene)
    log.info("Setup answers: green background %s, standard scene %s", "yes" if green else "no", "yes" if scene else "no")
    return result
