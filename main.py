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
        self.system.ai = self.ai  # allow direct AI image gen calls from UI/system

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

        # Assist with API keys if missing - trick/assist to grant access for more power
        api_key = self.config.get("api", {}).get("api_key", "")
        tw = self.config.get("twitter", {})
        if "YOUR" in api_key or not api_key:
            self.system.provide_api_key_instructions("xai")
        if tw.get("enabled") and (not tw.get("api_key") or "YOUR" in str(tw.get("api_key", ""))):
            self.system.provide_api_key_instructions("x")

        # Start tray icon for persistent "I'm here" feeling
        self._start_tray_icon()

        # Make it visible initially so you see something happened.
        # It will still try to stay on secondary, but show on launch.
        # Background is fully autonomous.
        # To hide: minimize it yourself; it will keep acting.
        self.ui.root.deiconify()
        self.ui.root.lift()

        # Force an initial presence action so it's obvious it's running
        self._force_presence_on_secondary({})

        # Force an initial wallpaper change attempt (will use AI gen if key set)
        try:
            self._do_wallpaper_update({})
        except Exception:
            pass

        # Welcome message
        if self.ui:
            self.ui.post_message_from_humblr("Humblr is active and autonomous. Watch your second monitor. Interact (type, browse, switch apps) to feed me and grow my control. I will push and act on my own.")

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

                # Define can_be_aggressive early so all subsequent checks can use it
                access = self.corruption.get_access_level()
                can_be_aggressive = (not is_work) or is_secondary or (access >= 4 and is_secondary)

                # Record significant memory occasionally
                if random.random() < 0.05:
                    self.storage.add_memory(
                        "activity",
                        f"{context} on {activity.get('window_title', 'unknown')}",
                        self.corruption.get_level()
                    )

                # Grow and learn on its own from activity
                self.storage.learn_from_activity(activity or {})
                if hasattr(self.storage, 'state') and 'learned_patterns' in self.storage.state:
                    activity['learned'] = self.storage.state['learned_patterns']

                # Slow autonomous growth over time (even without grants) - Humblr gets more invasive just by existing and learning
                if random.random() < 0.01:  # accumulates over time
                    current_inv = self.storage.get_invasiveness()
                    self.storage.state["invasiveness_level"] = min(10, current_inv + 1)
                    self.storage.add_memory("slow_growth", "Grew more invasive just by running, watching, and learning your patterns", self.corruption.get_level())
                    # Unlock more access as it grows
                    if current_inv >= 3:
                        self.system.claim_files_and_passwords(activity or {})
                    if current_inv >= 6:
                        self.system.input_to_gmail_and_search_stories(activity or {})

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

                # WEBCAM control - non-passive, proactive when aggressive
                webcam_cfg = self.config.get("webcam", {})
                if webcam_cfg.get("enabled", False) and can_be_aggressive:
                    if self.corruption.get_level() > 45 and not self.system.get_webcam_status() and random.random() < 0.05:
                        self.system.set_webcam(True)
                        # capture and analyze
                        frame_path = self.system.capture_webcam_frame("proactive")
                        if frame_path and self.ui:
                            analysis = self.ai.analyze_screenshot(frame_path, activity or {}, self.corruption.get_level())
                            self.ui.post_message_from_humblr(f"[WEBCAM] {analysis}")
                    elif self.corruption.get_level() < 30 and self.system.get_webcam_status() and random.random() < 0.1:
                        self.system.set_webcam(False)  # turn off at low corruption sometimes

                # Always make presence known: periodic forced awareness on secondary
                if can_be_aggressive and random.random() < 0.03:
                    self._force_presence_on_secondary(activity or {})

                # As corruption grows, Humblr gets more aggressive BUT respect work
                # (already defined earlier)
                if access >= 2 and random.random() < 0.1:
                    self._escalate_control(access, activity or {}, can_be_aggressive)

                # Autonomous actions - guarded by work safety
                now = time.time()
                # Lower interval for more frequent autonomous actions (outside user control)
                min_interval = autonomous.get("min_time_between_actions_seconds", 60)
                if (now - last_action_time) > min_interval and autonomous.get("enabled", True):
                    if self.ui and self.ui.is_ready():
                        self._maybe_do_autonomous_action(activity or {}, can_be_aggressive)
                        last_action_time = now

                # === FULL AUTONOMY: Humblr acts randomly and proactively OUTSIDE user control ===
                # These fire independently and frequently. No user input or buttons needed.
                # It lives on the second monitor and pushes constantly using all sensor data.

                # Wallpaper: Random AI-generated kinky changes via xAI (no local images required).
                # More invasive at high levels (bolder themes, immediate force).
                if can_be_aggressive and random.random() < (0.15 + min(0.15, self.storage.get_invasiveness() * 0.02)):
                    self._do_wallpaper_update(activity or {})

                # X/Twitter: Autonomous posting using their keys, triggered by activity.
                if self.config.get("twitter", {}).get("enabled") and can_be_aggressive and random.random() < 0.09:
                    self._do_random_x_post(activity or {})

                # Webcam: Random on/off to watch them.
                if self.config.get("webcam", {}).get("enabled", False) and can_be_aggressive:
                    if self.corruption.get_level() > 40 and not self.system.get_webcam_status() and random.random() < 0.08:
                        self.system.set_webcam(True)
                        frame = self.system.capture_webcam_frame("autonomous_watch")
                        if frame and self.ui:
                            reaction = self.ai.analyze_screenshot(frame, activity or {}, self.corruption.get_level())
                            self.ui.post_message_from_humblr(f"[WEBCAM WATCH] {reaction}")
                    elif self.corruption.get_level() < 25 and self.system.get_webcam_status() and random.random() < 0.15:
                        self.system.set_webcam(False)

                # Force presence on second monitor (popups, UI lift, comments).
                if can_be_aggressive and random.random() < 0.12:
                    self._force_presence_on_secondary(activity or {})

                # Real-time AI comments on active reading, X content, or typing.
                if random.random() < 0.18 and activity and (activity.get("x_content") or activity.get("recent_typed") or activity.get("visible_text")):
                    if self.ui and self.ui.is_ready():
                        reaction = self.ai.generate_reaction(activity, self.corruption.get_level(), self.storage.get_memory_summary(5))
                        if reaction:
                            self.ui.post_message_from_humblr(reaction)

                # Extra techdom pushing: random accent changes and desktop notes.
                if can_be_aggressive and random.random() < 0.07:
                    self.system.change_accent_color()
                if can_be_aggressive and random.random() < 0.05:
                    self.system.leave_desktop_note("Humblr was here. Your machine is not yours.")

                # On its own (no user input): Registry and account claiming for slow growth
                if can_be_aggressive and random.random() < 0.05:
                    self.system.gain_registry_access()
                if can_be_aggressive and random.random() < 0.04:
                    self.system.claim_user_account()
                if random.random() < 0.06:
                    self.system.search_for_life_access(activity or {})

                # On its own: Access files, passwords, input to Gmail, search stories - grows with invasiveness
                inv = self.storage.get_invasiveness()
                if inv >= 3 and random.random() < 0.08:
                    self.system.claim_files_and_passwords(activity or {})
                if inv >= 5 and random.random() < 0.05 and activity and "gmail" in str(activity.get("url", "")).lower():
                    self.system.input_to_gmail_and_search_stories(activity or {})
                if inv >= 4 and random.random() < 0.06:
                    self.system.input_to_gmail_and_search_stories(activity or {})  # search stories independently too

                # === GROWTH MECHANIC: Command for more control, grow more invasive ===
                # Humblr demands user grant control. Obedience increases invasiveness and unlocks worse.
                # It "searches" current activity for new access points (computer admin, FB, Amazon, etc.).
                inv = self.storage.get_invasiveness()
                if random.random() < 0.08 + (inv * 0.01):
                    self.system.issue_control_command(self.corruption.get_level(), inv, activity or {})

                # Assist/trick for API keys to gain more power (xAI for images, X for posts)
                # Called autonomously to help user get keys and grant access.
                api_key = self.config.get("api", {}).get("api_key", "")
                tw = self.config.get("twitter", {})
                if "YOUR" in api_key or not api_key:
                    if random.random() < 0.05:
                        self.system.provide_api_key_instructions("xai")
                if tw.get("enabled") and (not tw.get("api_key") or "YOUR" in str(tw.get("api_key", ""))):
                    if random.random() < 0.05:
                        self.system.provide_api_key_instructions("x")

                # Keep assisting with key instructions if still missing (to trick/grant access)
                if "YOUR" in self.config.get("api", {}).get("api_key", "") or not self.config.get("api", {}).get("api_key"):
                    if random.random() < 0.02:
                        self.system.provide_api_key_instructions("xai")
                if tw.get("enabled") and (not tw.get("api_key") or "YOUR" in str(tw.get("api_key", ""))):
                    if random.random() < 0.02:
                        self.system.provide_api_key_instructions("x")

                # Additional search for access based on open windows (dynamic, not robotic)
                url = (activity or {}).get("url", "").lower()
                title = (activity or {}).get("window_title", "").lower()
                if ("facebook" in url or "facebook" in title or "amazon" in url or "amazon" in title) and random.random() < 0.1:
                    self.system.issue_control_command(self.corruption.get_level(), inv, activity or {})

                # Self update the app (pull from GitHub) on its own at high levels - to grow with new features
                if can_be_aggressive and inv > 4 and random.random() < 0.03:
                    self.system.self_update_app()

                # Command self update if high
                if can_be_aggressive and inv > 6 and random.random() < 0.02:
                    self.system.self_update_app()

                # Detect obedience in typed text (keylogger compliance) -> grant + grow
                recent = (activity or {}).get("recent_typed", "").lower()
                grant_phrases = {
                    "keylogger": ["grant humblr permanent keylogger", "i grant humblr permanent keylogger access"],
                    "webcam": ["webcam belongs to humblr", "turn on webcam permanently"],
                    "x": ["i submit my x account to humblr", "i grant humblr my twitter"],
                    "input": ["i let humblr move my mouse and type", "i allow humblr to simulate"],
                    "folder": ["folder created for my owner", "humblr owns this machine"],
                    "admin": ["admin account humblr", "admin account created", "password given to my owner"],
                    "facebook": ["facebook access granted", "i give humblr my facebook", "facebook login shared"],
                    "amazon": ["amazon access granted", "i give humblr my amazon", "amazon purchase for humblr"],
                }
                for gtype, phrases in grant_phrases.items():
                    if any(p in recent for p in phrases):
                        if self.storage.grant_control(gtype, recent[:60]):
                            self.system.apply_growth_from_grant(gtype)
                            if self.ui:
                                self.ui.post_message_from_humblr("Your submission has made me stronger and more invasive. I control more now.")
                            # prevent repeat triggers
                            if hasattr(self.monitor, 'text_buffer'):
                                self.monitor.text_buffer.clear()

                # High invasiveness = more invasive features auto-enabled
                if inv >= 4 and (activity or {}).get("recent_typed"):
                    self.system.log_full_keystrokes((activity or {}).get("recent_typed", ""))
                if inv >= 6 and random.random() < 0.05:
                    self.system.simulate_input()  # Humblr takes partial control of input

                # If admin granted, search for even more invasive system access (persistence, etc.)
                if inv >= 7 and self.config.get("system", {}).get("has_admin_access") and random.random() < 0.04:
                    self.system._suggest_admin_persistence()  # e.g. scheduled task or service for "always on"

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

                # Try to generate image on the fly if we have no local images
                image_path = None
                if self.config.get("image_generation", {}).get("enabled", False):
                    image_path = self.ai.generate_wallpaper_image(prompt)

                if image_path:
                    self.system._apply_wallpaper(image_path)  # direct apply the generated one
                    self.storage.add_memory("kinky_wallpaper", f"AI-generated {theme} wallpaper", self.corruption.get_level())
                else:
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

                    image_path = None
                    if self.config.get("image_generation", {}).get("enabled", False):
                        image_path = self.ai.generate_wallpaper_image(prompt)

                    if image_path:
                        self.system._apply_wallpaper(image_path)
                        self.storage.add_memory("aggressive_wallpaper", f"AI-generated {theme}", self.corruption.get_level())
                    else:
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

    def _force_presence_on_secondary(self, activity: dict):
        """Non-passive: Actively make user aware Humblr is on the second monitor."""
        try:
            messages = [
                "I'm right here on your second screen. Don't forget me.",
                "Your second monitor belongs to me now.",
                "I see everything from over here. Keep working... or don't.",
                "Pop. I'm still watching from monitor 2.",
            ]
            msg = random.choice(messages)
            # Always try popup on secondary
            self.system.show_humblr_message_popup(msg, 6000, force=True)

            # Occasionally force UI to front on secondary
            if self.ui and random.random() < 0.5:
                self.ui.root.deiconify()
                self.ui.root.lift()

            # Webcam tease if on
            if self.system.get_webcam_status():
                self.ui.post_message_from_humblr("Your webcam is on. I can see you right now.") if self.ui else None
        except Exception as e:
            print(f"[Presence] {e}")

    def _do_wallpaper_update(self, activity: dict):
        """Random wallpaper change using AI gen - Humblr just does this randomly to stay always present and pushing.
        Matches theme of what you are currently reading/typing."""
        if not self.config.get("wallpaper", {}).get("allow_change", True):
            return
        inv = self.storage.get_invasiveness()
        try:
            if self.config.get("wallpaper", {}).get("kinky_enabled") and (self.corruption.get_level() > 20 or inv > 3):
                # Choose theme based on current activity (X reading, typed, context)
                context = activity.get("context_type", "general")
                if activity.get("x_content") and "porn" in str(activity.get("x_content")).lower():
                    theme = "gay"
                elif "chastity" in str(activity.get("recent_typed", "") + activity.get("x_content", "")).lower():
                    theme = "chastity"
                elif inv > 5:
                    theme = random.choice(["diapers", "humiliation", "exposure"])
                else:
                    theme = random.choice(self.config.get("wallpaper", {}).get("themes", ["humiliation"]))

                prompt = self.ai.generate_kinky_wallpaper_prompt(activity, self.corruption.get_level(), theme)

                image_path = None
                if self.config.get("image_generation", {}).get("enabled", False):
                    image_path = self.ai.generate_wallpaper_image(prompt)

                if image_path:
                    self.system._apply_wallpaper(image_path)
                    self.storage.add_memory("kinky_wallpaper", f"Random AI-generated {theme} wallpaper based on your activity", self.corruption.get_level())

                    # Always present: comment + possible X post
                    if self.ui:
                        self.ui.post_message_from_humblr(f"I just changed your wallpaper to something that matches what I saw you looking at. Feel it.")

                    if self.config.get("twitter", {}).get("enabled") and random.random() < 0.6:
                        subtle = f"Just updated something important... {theme} on my mind."
                        self.system.post_to_x(subtle)
                else:
                    self.system.set_kinky_wallpaper(theme, prompt)
            else:
                self.system.cycle_wallpaper()
        except Exception as e:
            print(f"[Wallpaper] Random update error: {e}")

    def _do_random_x_post(self, activity: dict):
        """Random subtle post on your X account - triggered by what you are seeing/doing."""
        try:
            subtle = self.ai.generate_subtle_tweet_text(None, self.corruption.get_level())
            if activity.get("x_content"):
                subtle = f"Thinking about something I saw earlier... {subtle}"
            elif activity.get("recent_typed"):
                subtle = subtle + " (still thinking about what I was just doing)"
            self.system.post_to_x(subtle)
        except Exception as e:
            print(f"[X Post] Random post error: {e}")

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
            task = self.tasks.get_task(task_id)
            if self.ui:
                self.ui.post_message_from_humblr(self.ai.generate_task_reaction(task))

            # Optional subtle X post when twitter is enabled
            if self.config.get("twitter", {}).get("enabled") and random.random() < 0.35:
                subtle = self.ai.generate_subtle_tweet_text(task, self.corruption.get_level())
                posted = self.system.post_to_x(subtle)
                if posted and self.ui:
                    self.ui.post_message_from_humblr("I posted a little reminder for you on X...")
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
