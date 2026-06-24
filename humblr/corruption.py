"""
Corruption / Submission progress engine.
"""

import time
from typing import Dict, Any


class CorruptionEngine:
    def __init__(self, config: Dict[str, Any], storage):
        self.config = config
        self.storage = storage
        self.enabled = config.get("corruption", {}).get("enabled", True)

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
        base = cfg.get("base_increase_per_hour", 1.2) / 3600.0 * 4   # rough per poll

        score = base

        # Typing activity
        ks = activity.get("keystrokes", 0)
        if ks > 30:
            score += 0.8
        elif ks > 8:
            score += 0.35

        # Specific "work" vs "distraction" windows
        title = (activity.get("window_title") or "").lower()
        if any(x in title for x in ["excel", "word", "powerpoint", "outlook", "teams", "slack", "zoom"]):
            score *= 1.4   # working = more "corruption" opportunity

        if any(x in title for x in ["reddit", "twitter", "discord", "youtube", "twitch", "steam"]):
            score *= 1.6

        # Chat activity
        if "chat" in activity:
            score += activity.get("chat", 0) * 0.6

        # Task completion bonus
        if activity.get("task_completed"):
            score += activity["task_completed"]

        old_level = self.get_level()
        new_level = self.get_level() + score
        max_level = cfg.get("max_level", 100)
        self.storage.set_corruption(min(new_level, max_level))
        self.storage.set("last_active", time.time())

        if int(new_level / 10) > int(old_level / 10):
            self.storage.add_memory("corruption_milestone", f"Corruption reached {int(new_level)}", new_level)
