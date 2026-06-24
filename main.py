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
        import random

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

    def send_user_message(self, text: str):
        """Called from UI when user sends a message."""
        self.storage.append_chat("user", text)

        # Get context
        recent = self.storage.get_recent_chat(8)
        activity = self.monitor.get_current_activity_summary()
        level = self.corruption.get_level()

        reply = self.ai.chat_reply(text, recent, activity, level)

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


if __name__ == "__main__":
    app = HumblrApp()
    try:
        app.start()
    except KeyboardInterrupt:
        app.shutdown()
    except Exception:
        traceback.print_exc()
        input("Press Enter to exit...")
