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

        # Initial greeting from Humblr
        self.ui.post_message_from_humblr("Well, well... you're finally running me. Let's see how long you last.")

        # Start tray icon for persistent "I'm here" feeling
        self._start_tray_icon()

        self.ui.run()

    def _background_loop(self):
        """Main background worker: monitoring + autonomous behavior."""
        last_action_time = time.time()
        autonomous = self.config.get("autonomous", {})

        while self.running:
            try:
                # Update monitor
                activity = self.monitor.poll()

                # Update corruption
                if activity and self.config.get("corruption", {}).get("enabled"):
                    self.corruption.add_activity(activity)

                # As corruption grows, Humblr gets more aggressive
                access = self.corruption.get_access_level()
                if access >= 3 and random.random() < 0.08:
                    self._escalate_control(access, activity)

                # Autonomous actions
                now = time.time()
                min_interval = autonomous.get("min_time_between_actions_seconds", 180)
                if (now - last_action_time) > min_interval and autonomous.get("enabled", True):
                    if self.ui and self.ui.is_ready():
                        self._maybe_do_autonomous_action(activity)
                        last_action_time = now

                # Push any autonomous comments to UI
                if self.monitor.has_pending_comment():
                    comment = self.monitor.get_pending_comment()
                    if comment and self.ui:
                        self.ui.post_message_from_humblr(comment)

            except Exception as e:
                print(f"[Background] Error: {e}")
                traceback.print_exc()

            time.sleep(self.config.get("monitoring", {}).get("poll_interval_seconds", 4))

    def _maybe_do_autonomous_action(self, activity):
        autonomous = self.config.get("autonomous", {})
        roll = random.random()

        if roll < autonomous.get("chance_to_comment", 0.35):
            comment = self.ai.generate_reaction(activity, self.corruption.get_level())
            if comment:
                self.monitor.queue_comment(comment)

        elif roll < autonomous.get("chance_to_comment", 0.35) + autonomous.get("chance_to_push_task", 0.15):
            task = self.tasks.generate_dynamic_task(activity)
            if task:
                self.tasks.add_task(task)
                if self.ui:
                    self.ui.notify_new_task(task)

        elif roll < 0.25 and self.config["system"]["allow_wallpaper_change"]:
            self.system.cycle_wallpaper()

        elif roll < 0.30 and self.config["system"]["allow_accent_color_change"]:
            self.system.change_accent_color()

    def _escalate_control(self, access_level: int, activity: dict):
        """Humblr exerts more control as access grows. This makes the takeover feel real."""
        try:
            if access_level >= 3:
                # Moderate takeover: more frequent comments + occasional forced popup
                if random.random() < 0.4 and self.ui:
                    comment = self.ai.generate_reaction(activity, self.corruption.get_level())
                    if comment:
                        self.ui.post_message_from_humblr(comment)

            if access_level >= 4:
                # Stronger: change more things, possibly force browser open
                if random.random() < 0.25:
                    self.system.cycle_wallpaper()
                if random.random() < 0.15:
                    self.system.show_humblr_message_popup(
                        "I'm in your machine now. You can't look away forever."
                    )

            if access_level >= 5:
                # Deep control: more invasive actions
                if random.random() < 0.2:
                    self.system.change_accent_color()
                if random.random() < 0.1 and activity.get("url"):
                    # Occasionally "react" by suggesting or forcing a related action
                    self.system.show_humblr_message_popup(
                        f"I saw you on that page. Good. Keep going for me."
                    )
        except Exception as e:
            print(f"[Escalate] Error: {e}")

    def send_user_message(self, text: str):
        """Called from UI when user sends a message."""
        self.storage.append_chat("user", text)

        # Get context
        recent = self.storage.get_recent_chat(8)
        act = self.monitor.get_current_activity()  # dict with url if available
        activity_summary = self.monitor.get_current_activity_summary()

        # Make richer context for the AI
        url = act.get("url")
        rich_activity = activity_summary
        if url:
            rich_activity += f" (exact URL: {url})"

        level = self.corruption.get_level()

        reply = self.ai.chat_reply(text, recent, rich_activity, level)

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
