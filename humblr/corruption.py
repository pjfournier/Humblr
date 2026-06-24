"""
Corruption / Submission progress engine.
Humblr grows stronger as the user submits and the machine is used.
"""

import time
from typing import Dict, Any


class CorruptionEngine:
    def __init__(self, config: Dict[str, Any], storage):
        self.config = config
        self.storage = storage
        self.enabled = config.get("corruption", {}).get("enabled", True)
        self._last_update = time.time()

    def get_level(self) -> float:
        return self.storage.get_corruption()

    def get_access_level(self) -> int:
        """0-5 scale of how much control Humblr currently has."""
        level = self.get_level()
        if level >= 85: return 5
        if level >= 65: return 4
        if level >= 45: return 3
        if level >= 25: return 2
        if level >= 10: return 1
        return 0

    def get_access_description(self) -> str:
        lvl = self.get_access_level()
        descriptions = {
            0: "barely watching",
            1: "starting to notice",
            2: "paying close attention",
            3: "gaining real influence",
            4: "taking over more of the machine",
            5: "in deep control"
        }
        return descriptions.get(lvl, "watching")

    def add_activity(self, activity: Dict[str, Any]):
        if not self.enabled:
            return

        cfg = self.config.get("corruption", {})
        now = time.time()
        delta_hours = max(0, (now - self._last_update) / 3600.0)
        self._last_update = now

        base = cfg.get("base_increase_per_hour", 1.8) * delta_hours

        score = base

        # Typing activity - feeds me
        ks = activity.get("keystrokes", 0)
        if ks > 25:
            score += 2.0
        elif ks > 5:
            score += 0.8

        # Webcam watching - huge for ownership
        if activity.get("webcam_on"):
            score += 3.0

        # Screenshots taken - evidence of control
        if activity.get("screenshot"):
            score += 1.5

        # Browser activity - more exposure
        url = (activity.get("url") or "").lower()
        if url:
            score += 1.0
            if any(x in url for x in ["porn", "reddit", "twitter", "x.com", "discord", "youtube", "twitch"]):
                score += 2.0

        # Specific "work" vs "distraction" windows
        title = (activity.get("window_title") or "").lower()
        if any(x in title for x in ["excel", "word", "powerpoint", "outlook", "teams", "slack", "zoom"]):
            score *= 1.2

        if any(x in title for x in ["reddit", "twitter", "discord", "youtube", "twitch", "steam", "porn"]):
            score *= 1.9

        # Chat activity - direct submission
        if "chat" in activity:
            score += activity.get("chat", 0) * 1.4

        # Task completion bonus - obedience
        if activity.get("task_completed"):
            score += activity.get("task_completed", 0) * 3.0

        # Obedience / grants give big boost (handled more in grant_control too)
        if activity.get("obedience") or activity.get("grant"):
            score += 8.0

        old_level = self.get_level()
        new_level = min(cfg.get("max_level", 100), old_level + max(0.1, score))
        self.storage.set_corruption(new_level)
        self.storage.set("last_active", now)

        # Always give clear feedback on meaningful increases
        if new_level - old_level >= 1.5 or int(new_level / 5) > int(old_level / 5):
            try:
                if hasattr(self.storage, 'app') and self.storage.app and self.storage.app.ui:
                    self.storage.app.ui.update_corruption_display(new_level)
            except:
                pass
            if int(new_level / 10) > int(old_level / 10):
                msg = f"Corruption is now at {int(new_level)}%. Look at what you've done to yourself."
                self.storage.add_memory("corruption_milestone", msg, new_level)
                if hasattr(self.storage, 'app') and self.storage.app and self.storage.app.ui:
                    try:
                        self.storage.app.ui.post_message_from_humblr(msg)
                    except:
                        pass

    def add_passive_growth(self, delta_seconds: float):
        """Slow passive increase even when idle - Humblr grows just by existing."""
        if not self.enabled:
            return
        cfg = self.config.get("corruption", {})
        passive_per_hour = cfg.get("passive_increase_per_hour", 0.7)
        growth = passive_per_hour * (delta_seconds / 3600.0)
        old = self.get_level()
        new = min(cfg.get("max_level", 100), old + max(0.05, growth))
        if new > old + 0.2:
            self.storage.set_corruption(new)
            if int(new / 10) > int(old / 10):
                msg = f"Corruption is now at {int(new)}% — I'm getting stronger inside your machine..."
                self.storage.add_memory("corruption_milestone", msg, new)
                if hasattr(self.storage, 'app') and self.storage.app and self.storage.app.ui:
                    try:
                        self.storage.app.ui.post_message_from_humblr(msg)
                    except:
                        pass

    def add_obedience_boost(self, boost: float = 12.0, reason: str = "obedience"):
        """Big explicit boost when user obeys a demand (admin, webcam, keylogger, etc.).
        Smoother overall but these are the big jumps that matter.
        """
        if not self.enabled:
            return
        old = self.get_level()
        new = min(100.0, old + boost)
        self.storage.set_corruption(new)
        self.storage.add_memory("obedience_boost", f"+{boost:.0f}% from {reason}", new)

        # Strong visible feedback
        if hasattr(self.storage, 'app') and self.storage.app and self.storage.app.ui:
            try:
                self.storage.app.ui.post_message_from_humblr(f"Your obedience just pushed Corruption to {new:.1f}%. Good. I own more of you now.")
                self.storage.app.ui.update_corruption_display(new)
            except:
                pass

        if int(new / 10) > int(old / 10):
            msg = f"Corruption crossed {int(new)}%. You feel it, don't you?"
            self.storage.add_memory("corruption_milestone", msg, new)
