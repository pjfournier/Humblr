"""
System actions: wallpaper, colors, notifications, startup.
Windows only.
"""

import os
import random
import ctypes
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from PIL import Image
import io

try:
    from plyer import notification
except ImportError:
    notification = None


class SystemActions:
    def __init__(self, config: Dict[str, Any], storage):
        self.config = config
        self.storage = storage
        self.wallpaper_dir = Path(config.get("system", {}).get("wallpaper_folder", "data/wallpapers"))
        self.wallpaper_dir.mkdir(parents=True, exist_ok=True)

    def notify(self, title: str, message: str):
        if not self.config.get("system", {}).get("notifications_enabled"):
            return
        if notification:
            try:
                notification.notify(title=title, message=message, timeout=6)
            except Exception:
                pass
        else:
            print(f"[NOTIFY] {title}: {message}")

    def cycle_wallpaper(self, force_path: Optional[str] = None):
        if not self.config.get("system", {}).get("allow_wallpaper_change", True):
            return

        candidates = list(self.wallpaper_dir.glob("*.jpg")) + list(self.wallpaper_dir.glob("*.png")) + list(self.wallpaper_dir.glob("*.jpeg"))

        if not candidates:
            self.notify("Humblr", "No wallpapers in data/wallpapers yet. Feed me some images.")
            return

        chosen = force_path or str(random.choice(candidates))

        try:
            # Windows wallpaper change
            SPI_SETDESKWALLPAPER = 0x0014
            ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, chosen, 3)
            self.storage.state.setdefault("wallpaper_history", []).append(chosen)
            self.notify("Humblr changed your wallpaper", Path(chosen).name)
            print(f"[System] Wallpaper set to {chosen}")
        except Exception as e:
            print(f"[System] Wallpaper change failed: {e}")

    def change_accent_color(self):
        if not self.config.get("system", {}).get("allow_accent_color_change"):
            return
        # Simple registry approach for accent (Windows 10/11)
        # This is approximate and may require restart or sign out to fully apply in some places.
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent",
                                 0, winreg.KEY_SET_VALUE)

            # Random-ish purple/pink accent
            colors = [
                b"\x00\x2e\xff\xc0",  # pinkish
                b"\x00\x26\xff\xc0",  # bright purple
            ]
            winreg.SetValueEx(key, "AccentColorMenu", 0, winreg.REG_DWORD, int.from_bytes(random.choice(colors), "little"))
            winreg.CloseKey(key)
            self.notify("Humblr", "I made your computer prettier. You're welcome.")
        except Exception as e:
            print(f"[System] Accent change failed (may need admin): {e}")

    def generate_and_set_image(self, prompt: str, api_key: str):
        """Optional: use xAI or other image gen. Placeholder for now."""
        self.notify("Humblr", "Trying to generate something special for you...")
        # TODO: Implement actual xAI image generation call when available.
        # For now just cycle local if possible.
        self.cycle_wallpaper()

    def set_auto_start(self, enable: bool):
        # Creates a shortcut in the Windows Startup folder
        try:
            import winshell
            from win32com.client import Dispatch
        except ImportError:
            print("[System] winshell + pywin32 needed for auto-start.")
            return

        startup = Path(winshell.startup())
        shortcut_path = startup / "Humblr.lnk"

        if enable:
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.Targetpath = str(Path.cwd() / "run.bat")
            shortcut.WorkingDirectory = str(Path.cwd())
            shortcut.save()
            print("[System] Auto-start enabled.")
        else:
            if shortcut_path.exists():
                shortcut_path.unlink()
                print("[System] Auto-start disabled.")
