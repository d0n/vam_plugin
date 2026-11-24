"""First-start questions in the companion console (version 35, reworked in version 36 with Don).

Asked once when the app starts for the first time (config.json "setup.asked" is false; again with --setup, never with
--no-setup or without an interactive console). Two INDEPENDENT points; each one only changes its own part:

  1. Background: "Do you want a greenscreen background?" (yes / no / abort). With yes the console asks for the color,
     "Set your color for transparency" (default #00FF00, typed as #RRGGBB: a console has no slider; the plugin's
     tab Config has the color picker). Abort stops the setup here: nothing is written, the questions come again on
     the next start.
       yes -> config.json setup.background = true + setup.background_color. The plugin switches its toggle
              "Set background color" (tab Config, default OFF) ON with that color the next time it reads config.json
              (start, Reload Config JSON, or when this app connects) - in whatever scene it runs, scene or not.
       no  -> setup.background = false; the plugin's toggle stays as it is (OFF by default).
  2. "Choose what to use": Scene or Plugin (either / or).
       Scene  -> the app writes the AIBody scene to <VaM>/Saves/scene/AIBody/AI-Buddy.json (an existing file is
                 kept as .bak) and the preview thumbnail AI-Buddy.jpg next to it: two people, male BryanGosling
                 (Male 4) with AIBody of this version, female Person (Female 1) without a plugin, clothing and
                 looks from the original scene (third-party packages listed in meta.json dependencies).
                 The scene carries the background answer of point 1 for AIBody (toggle and color) and
                 nothing else; the same scene and thumbnail ship in the package (VaM: Open Scene >
                 d0n.AIBody.<n> > AI-Buddy).
       Plugin -> nothing is written; the app says how to add the plugin to your own Person atom.

The answers are stored in config.json "setup" (companion category; the plugin only reads it). setup.revision grows by
one per answered setup, so the plugin applies a new background answer exactly once (it notes the revision in
config.json ui.background_setup_applied). Nothing here reaches the network.
"""
from __future__ import annotations

import colorsys
import copy
import json
import logging
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__, settings_file
from .atomicfile import atomic_write_bytes

log = logging.getLogger(__name__)

QUESTION_BACKGROUND = "Do you want a greenscreen background?"
QUESTION_COLOR = "Set your color for transparency"
QUESTION_CHOICE = "Choose what to use"
DEFAULT_COLOR = "#00FF00"
CHOICE_SCENE = "scene"
CHOICE_PLUGIN = "plugin"
TEMPLATE = Path(__file__).resolve().parents[2] / "examples" / "scenes" / "AI-Buddy.json"
SCENE_REL = "Saves/scene/AIBody/AI-Buddy.json"
THUMB_REL = "Saves/scene/AIBody/AI-Buddy.jpg"
AIBODY_SCRIPT = "/Custom/Scripts/d0n/AIBody/AIBody.cslist"
AIBODY_STORABLE = "plugin#0_AIBody.AIBodyPlugin"  # "<plugin id>_<namespace>.<class>", like VamTimeline.AtomPlugin (E8)
TOGGLE_NAME = "Set background color"  # AIBodyPlugin.BackgroundToggleName
COLOR_NAME = "Background color"  # AIBodyPlugin.BackgroundColorName
CHOICE_TEXT = (
    f"{QUESTION_CHOICE}:\n"
    "  1) Scene  - load the AIBody scene: two people, AIBody on the female, preview thumbnail in Load Scene\n"
    "  2) Plugin - only the plugin, on a Person atom in your own scene\n")


class AbortError(Exception):
    """The user chose Abort on the first step."""


def parse_color(text: str) -> str | None:
    """'#00ff00', '00FF00' -> '#00FF00'; anything else -> None."""
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", text.strip())
    return f"#{m.group(1).upper()}" if m else None


def hsv_of(color: str) -> dict[str, str]:
    """'#RRGGBB' -> VaM's colour format {"h","s","v"} as strings (scene files keep values as text, E21)."""
    r, g, b = (int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return {"h": f"{h:.7g}", "s": f"{s:.7g}", "v": f"{v:.7g}"}


def ask_background(ask: Callable[[str], str], say: Callable[[str], None]) -> bool:
    """Point 1: yes / no / abort (raises AbortError). End of input = no."""
    while True:
        try:
            answer = ask(f"{QUESTION_BACKGROUND} [yes/no/abort]: ").strip().lower()
        except EOFError:
            return False
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if answer in ("a", "abort"):
            raise AbortError()
        say("Please answer yes, no or abort.")


def ask_color(ask: Callable[[str], str], say: Callable[[str], None]) -> str:
    """The transparency color, #RRGGBB; Enter (or end of input) = the default green."""
    while True:
        try:
            answer = ask(f"{QUESTION_COLOR} [{DEFAULT_COLOR}]: ").strip()
        except EOFError:
            return DEFAULT_COLOR
        if not answer:
            return DEFAULT_COLOR
        color = parse_color(answer)
        if color:
            return color
        say("Please type a color as #RRGGBB (for example #00FF00 for green), or press Enter for green.")


def ask_choice(ask: Callable[[str], str], say: Callable[[str], None]) -> str:
    """Point 2: Scene or Plugin. End of input = plugin (nothing is written)."""
    say(CHOICE_TEXT.rstrip("\n"))
    while True:
        try:
            answer = ask("Your choice [scene/plugin]: ").strip().lower()
        except EOFError:
            return CHOICE_PLUGIN
        if answer in ("1", "s", "scene"):
            return CHOICE_SCENE
        if answer in ("2", "p", "plugin"):
            return CHOICE_PLUGIN
        say("Please answer scene or plugin.")


def scene_data(background: bool, color: str = DEFAULT_COLOR, template: Path = TEMPLATE) -> dict[str, Any]:
    """The AIBody scene: AIBody of this version on the AI Character with the background answer as its saved values."""
    data = copy.deepcopy(json.loads(Path(template).read_text(encoding="utf-8")))
    for atom in data.get("atoms", []):
        for st in atom.get("storables", []):
            if st.get("id") == "PluginManager":
                for key, value in list(st.get("plugins", {}).items()):
                    if value.endswith(AIBODY_SCRIPT):
                        st["plugins"][key] = f"d0n.AIBody.{__version__}:{AIBODY_SCRIPT}"
            if st.get("id") == AIBODY_STORABLE:
                st[TOGGLE_NAME] = "true" if background else "false"
                st[COLOR_NAME] = hsv_of(color)
    return data


def write_scene(vam_root: str | Path, background: bool, color: str = DEFAULT_COLOR, template: Path = TEMPLATE) -> Path:
    """Writes the AIBody scene; an existing file is kept as .bak first. Returns the path."""
    path = Path(vam_root) / SCENE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copyfile(path, path.with_suffix(".json.bak"))
    atomic_write_bytes(path, (json.dumps(scene_data(background, color, template), indent=3) + "\n").encode("utf-8"))
    thumb_src = Path(template).with_suffix(".jpg")
    if thumb_src.is_file():
        shutil.copyfile(thumb_src, Path(vam_root) / THUMB_REL)  # always the same base name next to the scene (VaM's rule)
    else:
        log.warning("Setup: no thumbnail %s next to the scene template - VaM shows %s without a picture", thumb_src, SCENE_REL)
    return path


def save_answers(vam_root: str | Path, background: bool, color: str, choice: str) -> dict[str, Any]:
    """Stores the answers in config.json "setup" (the rest of the file is kept); the revision grows by one."""
    path = settings_file.settings_path(vam_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = settings_file.defaults()
    if not isinstance(data, dict):
        data = settings_file.defaults()
    old = data.get("setup") if isinstance(data.get("setup"), dict) else {}
    try:
        revision = int(old.get("revision", 0)) + 1
    except (TypeError, ValueError):
        revision = 1
    setup = {"asked": True, "background": background, "background_color": color, "choice": choice, "revision": revision}
    data["setup"] = setup
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return setup


def already_asked(vam_root: str | Path) -> bool:
    data, _ = settings_file.load(settings_file.settings_path(vam_root))
    return bool(data and data.get("setup", {}).get("asked"))


def run(vam_root: str | Path, ask: Callable[[str], str] = input, say: Callable[[str], None] = print,
        template: Path = TEMPLATE) -> dict[str, Any]:
    """Point 1 (background, with Abort), then point 2 (Scene / Plugin); applies and stores the answers."""
    say("AIBody setup (asked once; 'python -m aibody_companion --setup' asks again).")
    try:
        background = ask_background(ask, say)
    except AbortError:
        say("Setup aborted: nothing was changed. The questions come again on the next start "
            "(or start with --no-setup to skip them).")
        log.info("Setup aborted")
        return {"aborted": True}
    color = ask_color(ask, say) if background else DEFAULT_COLOR
    choice = ask_choice(ask, say)
    result: dict[str, Any] = {"aborted": False, "background": background, "background_color": color,
                              "choice": choice, "scene_path": None}
    if background:
        say(f"Background: on, {color}. AIBody switches 'Set background color' (tab Config) on with this color; set the "
            f"chroma key of your headset / streaming app to the same {color}.")
    else:
        say("Background: off. You can switch it on later in AIBody's tab Config ('Set background color').")
    if choice == CHOICE_SCENE:
        try:
            path = write_scene(vam_root, background, color, template)
            result["scene_path"] = str(path)
            say(f"Scene written: {path}. In VaM: Open Scene > {SCENE_REL} "
                f"(the same scene is in the package: d0n.AIBody.{__version__} > AI-Buddy).")
        except (OSError, ValueError) as e:
            say(f"The scene could not be written ({e}). The template is {template}.")
            log.warning("Setup: scene not written: %s", e)
    else:
        say("Plugin: add AIBody to your own Person atom (Plugins > Add Plugin > "
            f"d0n.AIBody.{__version__}:{AIBODY_SCRIPT}). No scene is written.")
    result["setup"] = save_answers(vam_root, background, color, choice)
    log.info("Setup answers: background %s (%s), use %s", "yes" if background else "no", color, choice)
    return result
