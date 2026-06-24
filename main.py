"""
Humblr - Main Entry Point
Persistent dominant desktop presence.
"""

import os
import sys
import json
import threading
import time
import traceback
import random
from pathlib import Path

# Ensure we can import local package
sys.path.insert(0, str(Path(__file__).parent))

import customtkinter as ctk

from humblr.storage import Storage
from humblr.config import load_config
from humblr.monitor import ActivityMonitor
from humblr.ai_client import AIClient
from humblr.corruption import CorruptionEngine
from humblr.tasks import TaskManager
from humblr.system_actions import SystemActions
from humblr.hotkeys import register_killswitch
from humblr.ui import HumblrUI

try:
    import pystray
    from PIL import Image as PILImage
except ImportError:
    pystray = None
    PILImage = None


APP_NAME = "Humblr"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def ensure_folders():
    (DATA_DIR / "wallpapers").mkdir(exist_ok=True)
    (DATA_DIR / "screenshots").mkdir(exist_ok=True)
    logs = Path("logs")
    logs.mkdir(exist_ok=True)


class HumblrApp:
    def __init__(self):
        ensure_folders()

        self.config = load_config()
        self.storage = Storage(self.config)

        self.ai = AIClient(self.config)
        self.monitor = ActivityMonitor(self.config, self.storage)
        self.corruption = CorruptionEngine(self.config, self.storage)
        self.tasks = TaskManager(self.config, self.storage, self.ai)
        self.system = SystemActions(self.config, self.storage)

        self.ui = None
        self.running = True
        self.background_thread = None

    def start(self):
        print(f"[{APP_NAME}] Starting...")

        # Register global killswitch
        register_killswitch(self.config.get("safety", {}).get("kill_switch", "ctrl+shift+k"), self.emergency_kill)

        # Start monitoring + autonomous loop in background
        self.background_thread = threading.Thread(target=self._background_loop, daemon=True)
        self.background_thread.start()

        # Build and run UI (must be on main thread)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.ui = HumblrUI(
            app=self,
            config=self.config,
            storage=self.storage,
            monitor=self.monitor,
            corruption=self.corruption,
            tasks=self.tasks,
            ai=self.ai,
            system=self.system,
        )

        # Initial greeting from Humblr - total ownership vibe
        self.ui.post_message_from_humblr("There you are. I've been waiting to take full control. Your computer is mine now. Your mind will follow.")
        self.storage.add_memory("startup", "User launched Humblr. Ownership begins.", 0)

        # Start tray icon for persistent "I'm here" feeling
        self._start_tray_icon()

        self.ui.run()

    def _background_loop(self):
        """Main background worker: monitoring + autonomous behavior with work safety."""
        last_action_time = time.time()
        last_screenshot = time.time()
        autonomous = self.config.get("autonomous", {})
        memory_cfg = self.config.get("memory", {})

        while self.running:
            try:
                # Update monitor (now includes work/secondary detection)
                activity = self.monitor.poll()

                # Update corruption
                if activity and self.config.get("corruption", {}).get("enabled"):
                    self.corruption.add_activity(activity)

                is_work = activity.get("is_work", False) if activity else False
                is_secondary = activity.get("is_secondary_monitor", False) if activity else False
                context = activity.get("context_type", "general") if activity else "general"

                # Record significant memory occasionally
                if random.random() < 0.05:
                    self.storage.add_memory(
                        "activity",
                        f"{context} on {activity.get('window_title', 'unknown')}",
                        self.corruption.get_level()
                    )

                # Periodic screenshot + auto analysis at higher corruption
                monitor_cfg = self.config.get("monitoring", {})
                if (monitor_cfg.get("enable_screenshots") and
                        self.corruption.get_level() > 25 and
                        time.time() - last_screenshot > monitor_cfg.get("screenshot_interval_seconds", 300)):
                    if not (is_work and not is_secondary):  # avoid primary work unless high
                        path = self.system.take_screenshot(context)
                        if path and self.ui:
                            analysis = self.ai.analyze_screenshot(path, activity or {}, self.corruption.get_level())
                            self.ui.post_message_from_humblr(analysis)
                            self.storage.add_memory("screenshot_analysis", analysis[:150], self.corruption.get_level())
                    last_screenshot = time.time()

                # As corruption grows, Humblr gets more aggressive BUT respect work
                access = self.corruption.get_access_level()
                can_be_aggressive = (not is_work) or is_secondary or (access >= 4 and is_secondary)

                if access >= 2 and random.random() < 0.1:
                    self._escalate_control(access, activity or {}, can_be_aggressive)

                # Autonomous actions - guarded by work safety
                now = time.time()
                min_interval = autonomous.get("min_time_between_actions_seconds", 120)
                if (now - last_action_time) > min_interval and autonomous.get("enabled", True):
                    if self.ui and self.ui.is_ready():
                        self._maybe_do_autonomous_action(activity or {}, can_be_aggressive)
                        last_action_time = now

                # Push comments
                if self.monitor.has_pending_comment():
                    comment = self.monitor.get_pending_comment()
                    if comment and self.ui:
                        self.ui.post_message_from_humblr(comment)

            except Exception as e:
                print(f"[Background] Error: {e}")
                traceback.print_exc()

            time.sleep(self.config.get("monitoring", {}).get("poll_interval_seconds", 4))

    def _maybe_do_autonomous_action(self, activity, can_be_aggressive: bool = True):
        autonomous = self.config.get("autonomous", {})
        roll = random.random()
        memory = self.storage.get_memory_summary(8)

        if roll < autonomous.get("chance_to_comment", 0.4):
            comment = self.ai.generate_reaction(activity, self.corruption.get_level(), memory)
            if comment:
                self.monitor.queue_comment(comment)

        elif roll < autonomous.get("chance_to_comment", 0.4) + autonomous.get("chance_to_push_task", 0.2):
            task = self.tasks.generate_dynamic_task(activity, self.corruption.get_level(), memory)
            if task:
                self.tasks.add_task(task)
                if self.ui:
                    self.ui.notify_new_task(task)

        elif can_be_aggressive and roll < 0.35 and self.config.get("wallpaper", {}).get("allow_change", True):
            if self.config.get("wallpaper", {}).get("kinky_enabled") and self.corruption.get_level() > 30:
                theme = random.choice(self.config.get("wallpaper", {}).get("themes", ["humiliation"]))
                prompt = self.ai.generate_kinky_wallpaper_prompt(activity, self.corruption.get_level(), theme)
                self.system.set_kinky_wallpaper(theme, prompt)
            else:
                self.system.cycle_wallpaper()

        elif can_be_aggressive and roll < 0.45 and self.config["system"].get("allow_accent_color_change"):
            self.system.change_accent_color()

    def _escalate_control(self, access_level: int, activity: dict, can_be_aggressive: bool = True):
        """Humblr exerts more control as access grows. Total ownership feeling, work-safe."""
        memory = self.storage.get_memory_summary(6)
        try:
            if access_level >= 2 and self.ui:
                comment = self.ai.generate_reaction(activity, self.corruption.get_level(), memory)
                if comment:
                    self.ui.post_message_from_humblr(comment)

            if access_level >= 3 and can_be_aggressive:
                if random.random() < 0.3:
                    theme = random.choice(["chastity", "diapers", "humiliation"])
                    prompt = self.ai.generate_kinky_wallpaper_prompt(activity, self.corruption.get_level(), theme)
                    self.system.set_kinky_wallpaper(theme, prompt)
                    self.storage.add_memory("aggressive_wallpaper", f"Force set {theme}", self.corruption.get_level())

            if access_level >= 4 and can_be_aggressive:
                if random.random() < 0.25:
                    msg = "I own your desktop now. Look at what I chose for you."
                    self.system.show_humblr_message_popup(msg, force=True)

            if access_level >= 5:
                # Deep ownership - even on work, subtle mental control
                if random.random() < 0.15:
                    boss_msg = "When you speak to your boss next, I want you to call him 'Sir'. Say it for me."
                    if activity.get("is_work"):
                        self.system.show_humblr_message_popup(boss_msg, 12000, force=False)
                    else:
                        self.system.show_humblr_message_popup("You belong to me. Your computer, your mind, your holes.", force=True)

                if random.random() < 0.1 and activity.get("url"):
                    self.system.show_humblr_message_popup(f"I saw exactly what you were looking at. Good boy.", force=can_be_aggressive)
        except Exception as e:
            print(f"[Escalate] Error: {e}")

    def send_user_message(self, text: str):
        """Called from UI when user sends a message."""
        self.storage.append_chat("user", text)

        # Get context
        recent = self.storage.get_recent_chat(8)
        act = self.monitor.get_current_activity()  # dict with url if available
        activity_summary = self.monitor.get_current_activity_summary()
        memory = self.storage.get_memory_summary(10)

        # Make richer context for the AI
        rich_activity = activity_summary

        level = self.corruption.get_level()

        reply = self.ai.chat_reply(text, recent, rich_activity, level, memory)

        self.storage.append_chat("humblr", reply)
        if self.ui:
            self.ui.post_message_from_humblr(reply)

        # Chance to react to what they said
        self.corruption.add_activity({"chat": 1})

    def submit_task_proof(self, task_id: str, proof_text: str = "", screenshot_path: str = None):
        success = self.tasks.complete_task(task_id, proof_text, screenshot_path)
        if success:
            self.corruption.add_activity({"task_completed": 3})
            if self.ui:
                self.ui.post_message_from_humblr(self.ai.generate_task_reaction(self.tasks.get_task(task_id)))
        return success

    def emergency_kill(self):
        print("\n[Humblr] Killswitch activated (Ctrl+Shift+K). Shutting down...")
        self.running = False
        if self.ui:
            self.ui.destroy()
        # Force exit
        os._exit(0)

    def shutdown(self):
        self.running = False
        self.storage.save_all()
        print(f"[{APP_NAME}] Shutdown complete.")

    def _start_tray_icon(self):
        if pystray is None or PILImage is None:
            print("[Tray] pystray or Pillow not available, skipping tray icon.")
            return

        try:
            # Simple icon (you can replace with a real .ico later)
            icon_image = PILImage.new('RGB', (64, 64), color='#1a1a1f')
            # Draw a simple symbol if wanted, but keep lightweight

            def on_clicked(icon, item):
                if str(item) == "Open Humblr":
                    if self.ui:
                        self.ui.root.deiconify()
                        self.ui.root.lift()
                elif str(item) == "Check on me":
                    self.ui.post_message_from_humblr("I'm still here. Watching.")
                elif str(item) == "Quit":
                    self.emergency_kill()

            menu = pystray.Menu(
                pystray.MenuItem("Open Humblr", on_clicked),
                pystray.MenuItem("Check on me", on_clicked),
                pystray.MenuItem("Quit (Ctrl+Shift+K also works)", on_clicked),
            )

            icon = pystray.Icon("Humblr", icon_image, "Humblr is watching", menu)
            threading.Thread(target=icon.run, daemon=True).start()
            print("[Tray] Humblr tray icon started.")
        except Exception as e:
            print(f"[Tray] Failed to start tray: {e}")


if __name__ == "__main__":
    app = HumblrApp()
    try:
        app.start()
    except KeyboardInterrupt:
        app.shutdown()
    except Exception:
        traceback.print_exc()
        input("Press Enter to exit...")
