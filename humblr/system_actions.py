"""
System actions: wallpaper, colors, notifications, startup.
Windows only.
"""

import os
import random
import ctypes
import webbrowser
import tkinter as tk
import time
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

    def set_kinky_wallpaper(self, theme: str = None, ai_prompt: str = None):
        """Aggressively set a kinky themed wallpaper. Prefers themed folders, falls back to prompt suggestion."""
        if not self.config.get("wallpaper", {}).get("kinky_enabled", True):
            return self.cycle_wallpaper()

        themes = self.config.get("wallpaper", {}).get("themes", [])
        folders = self.config.get("wallpaper", {}).get("local_folders", {})

        if theme and theme in folders:
            folder = Path(folders[theme])
            candidates = list(folder.glob("*.jpg")) + list(folder.glob("*.png"))
            if candidates:
                chosen = str(random.choice(candidates))
                self._apply_wallpaper(chosen)
                self.storage.add_memory("kinky_wallpaper", f"Switched to {theme} theme", self.storage.get_corruption())
                return

        # Try any kinky subfolder
        kinky_root = Path("data/wallpapers/kinky")
        for sub in kinky_root.iterdir():
            if sub.is_dir():
                cands = list(sub.glob("*.jpg")) + list(sub.glob("*.png"))
                if cands:
                    chosen = str(random.choice(cands))
                    self._apply_wallpaper(chosen)
                    self.storage.add_memory("kinky_wallpaper", f"Applied random kinky from {sub.name}", self.storage.get_corruption())
                    return

        # Fallback: use prompt or general
        if ai_prompt:
            self.notify("Humblr", f"Use this kinky prompt in your image generator: {ai_prompt[:150]}...")
        self.cycle_wallpaper()

    def _apply_wallpaper(self, path: str):
        try:
            SPI = 0x0014
            ctypes.windll.user32.SystemParametersInfoW(SPI, 0, path, 3)
            self.notify("Humblr", "I changed your wallpaper to something that reminds you who owns you.")
            print(f"[System] Kinky wallpaper: {path}")
        except Exception as e:
            print(f"[System] Kinky wallpaper failed: {e}")

    def take_screenshot(self, context: str = "auto_analysis") -> Optional[str]:
        """Take screenshot using monitor or pyautogui."""
        # Delegate to monitor if possible, but simple here too
        try:
            import pyautogui
            screenshots_dir = Path(self.config.get("data_paths", {}).get("screenshots", "data/screenshots"))
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            path = screenshots_dir / f"{context}_{ts}.png"
            img = pyautogui.screenshot()
            img.save(str(path))
            self.storage.add_memory("screenshot", f"Auto screenshot taken during {context}", self.storage.get_corruption())
            return str(path)
        except Exception as e:
            print(f"[System] Screenshot error: {e}")
            return None

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

    # --- TAKEOVER / ESCALATION ACTIONS ---

    def show_humblr_message_popup(self, message: str, duration_ms: int = 8000, force: bool = False):
        """Popup only if allowed (not blocking primary work unless forced)."""
        if not force and self.config.get("work_safety", {}).get("subtle_only_on_primary_work"):
            # Caller should check before calling
            pass
        try:
            popup = tk.Tk()
            popup.title("Humblr owns this")
            popup.attributes("-topmost", True)
            popup.geometry("460x180+200+150")
            popup.configure(bg="#111113")

            label = tk.Label(
                popup,
                text=message,
                wraplength=420,
                bg="#111113",
                fg="#ff2e88",
                font=("Segoe UI", 13, "bold"),
                justify="left"
            )
            label.pack(padx=20, pady=25, fill="both", expand=True)

            close_btn = tk.Button(
                popup, text="Yes Sir", command=popup.destroy,
                bg="#2a2a2f", fg="#c026ff", relief="flat", font=("Segoe UI", 11)
            )
            close_btn.pack(pady=(0, 12))

            popup.after(duration_ms, popup.destroy)
            popup.mainloop()
        except Exception as e:
            print(f"[System] Popup failed: {e}")
            self.notify("Humblr", message)

    def force_open_url(self, url: str, reason: str = ""):
        """Open a browser tab. Used for 'guidance' or punishment/reward."""
        try:
            webbrowser.open(url, new=2)
            self.notify("Humblr", f"Opening something for you... {reason}")
        except Exception as e:
            print(f"[System] Failed to open URL: {e}")

    def leave_desktop_note(self, text: str):
        """Drops a text file on the Desktop so Humblr 'leaves a message'."""
        try:
            desktop = Path.home() / "Desktop"
            note_path = desktop / f"Humblr_{int(time.time())}.txt"
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(f"Humblr says:\n\n{text}\n\n— Your computer belongs to me now.")
            self.notify("Humblr", "I left you a note on your desktop.")
        except Exception as e:
            print(f"[System] Desktop note failed: {e}")

    def increase_control(self, level: int):
        """Placeholder for future escalating privileges (e.g. more permissions)."""
        print(f"[System] Access level now feels like {level}. More of your machine is mine.")

