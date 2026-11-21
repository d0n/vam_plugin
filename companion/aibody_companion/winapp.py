"""Windows launcher of the installed AIBody Companion (Leon, 21.11.2026).

The installer ("AIBody Companion Setup.exe", Inno Setup around a PyInstaller build) puts "AIBody Companion.exe" into
%LOCALAPPDATA%\\Programs\\AIBody Companion with a Start menu entry. Starting it:

1. Single instance: a second start only shows the short note "already running" and ends.
2. Finds the VaM folder: first the remembered folder in launcher.json, which the installer writes from its wizard page
   "Your VaM folder" (Leon, 21.11.2026 17:01: chosen during setup, prefilled by auto-detection, VaM.exe required), so
   the companion never has to sit inside the VaM folder; then a parent folder of the exe and common folders on every
   drive (X:\\VaM, X:\\Virt-A-Mate, X:\\Games\\VaM, ...); VaM has no installer, registry key or Steam entry to read.
   Only as the last fallback (no folder from setup, or VaM moved) it asks once with a folder picker and remembers it.
3. Runs the companion app (cli.main with --no-stdin --no-setup) in the background, shows a small note that closes
   by itself ("AIBody Companion is now running in the background") and puts an icon with Quit in the tray.

No console window (PyInstaller --windowed). Launcher settings and its own log live in %LOCALAPPDATA%\\AIBody Companion;
the companion's config.json and companion.log stay where they always were, under <VaM>\\Saves\\PluginData\\AIBody.
--selftest checks the bundled native parts (PortAudio via sounddevice, webrtcvad, tkinter, the tray) and runs the
companion for a few seconds against a temporary VaM folder; the CI build runs it on windows-latest.
"""
from __future__ import annotations

import argparse
import json
import os
import string
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

APP_NAME = "AIBody Companion"
MUTEX_NAME = "Local\\AIBodyCompanionSingleInstance"
SETTINGS_FILE = "launcher.json"
LAUNCHER_LOG = "launcher.log"
NOTE_SECONDS = 5
RUNNING_NOTE = ("AIBody Companion is now running in the background. The AIBody plugin in VaM connects to it by itself. "
                "Quit it from the tray icon.")
ALREADY_NOTE = "AIBody Companion is already running in the background."
COMMON_SUBFOLDERS = ("VaM", "Virt-A-Mate", "VAM", "Games\\VaM", "Games\\Virt-A-Mate", "Program Files\\VaM",
                     "Program Files\\Virt-A-Mate")


# -- folders ---------------------------------------------------------------------------------------------------------

def data_dir(env: dict[str, str] | None = None) -> Path:
    env = dict(os.environ) if env is None else env
    base = env.get("LOCALAPPDATA") or env.get("APPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / APP_NAME


def looks_like_vam(path: Path | str | None) -> bool:
    if not path:
        return False
    p = Path(path)
    try:
        return (p / "VaM.exe").is_file() or ((p / "AddonPackages").is_dir() and (p / "Saves").is_dir())
    except OSError:
        return False


def parent_search(start: Path) -> Path | None:
    """The exe's own folder or one of its parents, when the companion is installed inside the VaM folder."""
    p = Path(start).resolve()
    for candidate in (p, *p.parents):
        if looks_like_vam(candidate):
            return candidate
    return None


def drive_roots() -> list[Path]:
    if os.name != "nt":
        return []
    return [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]


def common_candidates(roots: Iterable[Path] | None = None, env: dict[str, str] | None = None) -> list[Path]:
    env = dict(os.environ) if env is None else env
    found: list[Path] = []
    for root in (drive_roots() if roots is None else roots):
        for sub in COMMON_SUBFOLDERS:
            found.append(Path(root) / Path(sub.replace("\\", os.sep)))
    home = env.get("USERPROFILE") or str(Path.home())
    for sub in ("VaM", "Desktop\\VaM", "Downloads\\VaM", "Games\\VaM"):
        found.append(Path(home) / Path(sub.replace("\\", os.sep)))
    return found


def load_settings(folder: Path) -> dict[str, Any]:
    try:
        # utf-8-sig: the installer writes launcher.json with a byte order mark (Inno Setup SaveStringsToUTF8File)
        data = json.loads((folder / SETTINGS_FILE).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(folder: Path, data: dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / SETTINGS_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")


def detect_vam_root(exe_dir: Path, saved: str | None, candidates: Iterable[Path]) -> tuple[Path | None, str]:
    """Order: remembered folder, exe inside VaM, common folders. Returns (folder, how it was found)."""
    if saved and looks_like_vam(saved):
        return Path(saved), "remembered"
    inside = parent_search(exe_dir)
    if inside is not None:
        return inside, "the companion sits inside the VaM folder"
    for c in candidates:
        if looks_like_vam(c):
            return c, "found at a common place"
    return None, "not found"


# -- small windows ---------------------------------------------------------------------------------------------------

def show_note(text: str, seconds: int = NOTE_SECONDS) -> None:
    """A small window that closes by itself (tkinter is part of the build)."""
    try:
        import tkinter as tk
    except ImportError:
        return
    try:
        win = tk.Tk()
        win.title(APP_NAME)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        tk.Label(win, text=text, wraplength=360, justify="left", padx=18, pady=14).pack()
        tk.Button(win, text="OK", width=10, command=win.destroy).pack(pady=(0, 12))
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        x = win.winfo_screenwidth() - w - 40
        y = win.winfo_screenheight() - h - 90
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        win.after(seconds * 1000, win.destroy)
        win.mainloop()
    except Exception:  # noqa: BLE001 - a missing display must never stop the companion
        pass


def ask_vam_folder() -> Path | None:
    """Folder picker, asked until a VaM folder is chosen or the user cancels."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        return None
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showinfo(APP_NAME, "Please choose your VaM folder (the folder with VaM.exe). "
                                      "AIBody Companion remembers it.", parent=root)
        while True:
            chosen = filedialog.askdirectory(title="Choose your VaM folder (the folder with VaM.exe)", parent=root)
            if not chosen:
                return None
            if looks_like_vam(chosen):
                return Path(chosen)
            if not messagebox.askretrycancel(APP_NAME, f"{chosen} does not look like a VaM folder (no VaM.exe, no "
                                                       "AddonPackages and Saves). Choose again?", parent=root):
                return None
    finally:
        root.destroy()


# -- single instance -------------------------------------------------------------------------------------------------

class SingleInstance:
    """Windows: a named mutex. Elsewhere (tests): an exclusive lock file."""

    def __init__(self, name: str = MUTEX_NAME, lock_dir: Path | None = None):
        self.name = name
        self._handle: Any = None
        self._lock_path: Path | None = None
        self._lock_dir = lock_dir

    def acquire(self) -> bool:
        if os.name == "nt" and self._lock_dir is None:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            self._handle = kernel32.CreateMutexW(None, False, self.name)
            return bool(self._handle) and kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
        folder = self._lock_dir or Path(tempfile.gettempdir())
        self._lock_path = folder / (self.name.replace("\\", "_") + ".lock")
        try:
            fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True

    def release(self) -> None:
        if self._lock_path is not None:
            try:
                self._lock_path.unlink()
            except OSError:
                pass


# -- tray ------------------------------------------------------------------------------------------------------------

def tray_image() -> Any:
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=(40, 140, 220, 255))
    d.ellipse((22, 14, 42, 34), fill=(255, 255, 255, 255))
    d.rectangle((20, 36, 44, 52), fill=(255, 255, 255, 255))
    return img


def run_tray(on_quit: Callable[[], None], log_folder: Path | None) -> bool:
    """Blocks until Quit. False if the tray is not available (the caller then simply waits)."""
    try:
        import pystray
    except Exception:  # noqa: BLE001
        return False

    def open_logs(icon: Any, item: Any) -> None:
        if log_folder is not None and os.name == "nt":
            os.startfile(str(log_folder))  # type: ignore[attr-defined]

    def quit_app(icon: Any, item: Any) -> None:
        icon.stop()
        on_quit()

    menu = pystray.Menu(pystray.MenuItem(f"{APP_NAME} is running", None, enabled=False),
                        pystray.MenuItem("Open log folder", open_logs),
                        pystray.MenuItem("Quit", quit_app))
    pystray.Icon("AIBodyCompanion", tray_image(), APP_NAME, menu).run()
    return True


# -- self-test -------------------------------------------------------------------------------------------------------

def selftest(out: Path | None, run_seconds: float = 6.0) -> int:
    report: dict[str, Any] = {"frozen": bool(getattr(sys, "frozen", False)), "python": sys.version, "checks": {}}
    checks = report["checks"]

    def check(name: str, fn: Callable[[], Any], required: bool = True) -> None:
        try:
            checks[name] = {"ok": True, "required": required, "detail": str(fn())[:300]}
        except Exception as e:  # noqa: BLE001
            checks[name] = {"ok": False, "required": required, "detail": f"{type(e).__name__}: {e}"[:300]}

    def portaudio() -> str:
        import sounddevice as sd
        return f"sounddevice {sd.__version__}, PortAudio {sd.get_portaudio_version()[1]}, {len(sd.query_devices())} devices"

    def webrtc() -> str:
        import webrtcvad
        vad = webrtcvad.Vad(2)
        return f"speech in silence: {vad.is_speech(bytes(320), 16000)}"

    def tk_check() -> str:
        import tkinter
        return f"Tk {tkinter.TkVersion}"

    def tray() -> str:
        import pystray  # noqa: F401
        return f"tray image {tray_image().size}"

    def companion_run() -> str:
        from . import cli
        # the companion keeps its log open: on Windows the folder cannot be removed while it runs
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / "VaM"
            (root / "AddonPackages").mkdir(parents=True)
            (root / "Saves").mkdir()
            t = threading.Thread(target=cli.main, args=(["--vam-root", str(root), "--no-mic", "--no-stdin",
                                                         "--no-setup"],), daemon=True)
            t.start()
            time.sleep(run_seconds)
            log = root / "Saves" / "PluginData" / "AIBody" / "logs" / "companion.log"
            if not log.is_file():
                raise RuntimeError("companion.log was not written")
            text = log.read_text(encoding="utf-8", errors="replace")
            if " ERROR " in text or "Traceback" in text:
                raise RuntimeError("errors in companion.log: " + text[-400:])
            if not t.is_alive():
                raise RuntimeError("the companion stopped by itself")
            return f"companion ran {run_seconds:.0f} s, {len(text.splitlines())} log lines"

    check("portaudio (sounddevice)", portaudio)
    check("webrtcvad", webrtc)
    check("tkinter", tk_check)
    check("tray (pystray, Pillow)", tray)
    check("companion run", companion_run)
    report["ok"] = all(c["ok"] for c in checks.values() if c["required"])
    text = json.dumps(report, indent=2)
    if out is not None:
        out.write_text(text, encoding="utf-8")
    if sys.stdout is not None:
        print(text, flush=True)
    return 0 if report["ok"] else 1


# -- main ------------------------------------------------------------------------------------------------------------

def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def redirect_output(folder: Path) -> None:
    """A windowed exe has no console: print() and the console log handler write into launcher.log instead."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        stream = open(folder / LAUNCHER_LOG, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    except OSError:
        return
    if sys.stdout is None or getattr(sys, "frozen", False):
        sys.stdout = stream
    if sys.stderr is None or getattr(sys, "frozen", False):
        sys.stderr = stream


def check_vam_root(folder: Path, out: Path | None) -> int:
    """--check-vam-root (CI after a silent install with /VAMDIR=): the folder from launcher.json / detection, no picker."""
    settings = load_settings(folder)
    root, how = detect_vam_root(exe_dir(), settings.get("vam_root"), common_candidates())
    report = {"vam_root": str(root) if root else None, "how": how, "settings_file": str(folder / SETTINGS_FILE),
              "set_by": settings.get("vam_root_set_by")}
    text = json.dumps(report, indent=2)
    if out is not None:
        out.write_text(text, encoding="utf-8")
    if sys.stdout is not None:
        print(text, flush=True)
    return 0 if root else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog=APP_NAME)
    p.add_argument("--selftest", action="store_true", help="check the bundled parts and exit (0 = ok)")
    p.add_argument("--selftest-out", type=Path, help="write the self-test report to this file")
    p.add_argument("--vam-root", dest="vam_root", help="use this VaM folder (and remember it)")
    p.add_argument("--choose-vam-folder", action="store_true", help="ask for the VaM folder again")
    p.add_argument("--check-vam-root", action="store_true",
                   help="print the VaM folder the app would use (no picker, nothing started) and exit (0 = found)")
    args = p.parse_args(argv)
    folder = data_dir()
    if args.selftest:
        code = selftest(args.selftest_out)
        os._exit(code)  # the companion thread of the self-test is still running
    if args.check_vam_root:
        code = check_vam_root(folder, args.selftest_out)
        os._exit(code)
    redirect_output(folder)
    instance = SingleInstance()
    if not instance.acquire():
        show_note(ALREADY_NOTE)
        return 0
    settings = load_settings(folder)
    if args.vam_root and looks_like_vam(args.vam_root):
        root, how = Path(args.vam_root), "given on the command line"
    elif args.choose_vam_folder:
        root, how = None, "asked"
    else:
        root, how = detect_vam_root(exe_dir(), settings.get("vam_root"), common_candidates())
    if root is None:
        root = ask_vam_folder()
        how = "chosen in the folder picker"
    if root is None:
        show_note("AIBody Companion needs your VaM folder (the folder with VaM.exe). Start it again from the Start menu "
                  "and choose the folder.", seconds=15)
        return 1
    settings["vam_root"] = str(root)
    save_settings(folder, settings)
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} VaM folder {root} ({how})", flush=True)

    from . import cli
    result: dict[str, int] = {}

    def run_companion() -> None:
        try:
            result["code"] = cli.main(["--vam-root", str(root), "--no-stdin", "--no-setup"])
        except BaseException as e:  # noqa: BLE001
            print(f"companion stopped: {e!r}", flush=True)
            result["code"] = 1

    worker = threading.Thread(target=run_companion, name="companion", daemon=True)
    worker.start()
    threading.Thread(target=show_note, args=(RUNNING_NOTE,), daemon=True).start() if os.name != "nt" else show_note(
        RUNNING_NOTE)

    def quit_all() -> None:
        instance.release()
        os._exit(0)

    def watch() -> None:
        worker.join()
        show_note(f"AIBody Companion stopped (code {result.get('code')}). See {root}\\Saves\\PluginData\\AIBody\\logs"
                  "\\companion.log.", seconds=15)
        quit_all()

    threading.Thread(target=watch, daemon=True).start()
    if not run_tray(quit_all, root / "Saves" / "PluginData" / "AIBody" / "logs"):
        worker.join()
    quit_all()
    return 0
