import json
import time
from pathlib import Path
from typing import Any, Dict, List


class Storage:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.state_path = Path(config["data_paths"]["state_file"])
        self.chat_path = Path(config["data_paths"]["chat_history"])
        self.task_path = Path(config["data_paths"]["task_log"])
        self.memory_path = Path(config.get("data_paths", {}).get("memory_log", "data/memory_log.json"))

        self.state: Dict[str, Any] = {}
        self.chat_history: List[Dict] = []
        self.task_log: List[Dict] = []
        self.memory_log: List[Dict] = []  # long term memory events

        self.load_all()

    def load_all(self):
        self.state = self._load_json(self.state_path, {
            "corruption_level": 0.0,
            "total_keystrokes": 0,
            "sessions": 0,
            "last_active": time.time(),
            "wallpaper_history": [],
            "unlocked_features": [],
            "granted_controls": [],  # list of ways user has given more control
            "invasiveness_level": 0,  # grows with grants, makes app more invasive
            "learned_patterns": {},  # e.g. frequent sites, typed themes - for growth and adaptation
            "user_profile": {},  # slowly built info about who the user is from questions/answers/activity
            "long_term_summary": "Humblr has just started taking control. User is new to ownership."
        })

        self.chat_history = self._load_json(self.chat_path, [])
        self.task_log = self._load_json(self.task_path, [])
        self.memory_log = self._load_json(self.memory_path, [])

    def _load_json(self, path: Path, default: Any):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Storage] Failed to load {path}: {e}")
        return default

    def _save_json(self, path: Path, data: Any):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_all(self):
        self._save_json(self.state_path, self.state)
        self._save_json(self.chat_path, self.chat_history[-200:])  # keep last 200
        self._save_json(self.task_path, self.task_log[-300:])
        self._save_json(self.memory_path, self.memory_log[-self.config.get("memory", {}).get("max_events", 200):])

    # --- State helpers ---
    def get(self, key: str, default=None):
        return self.state.get(key, default)

    def set(self, key: str, value: Any):
        self.state[key] = value

    def increment(self, key: str, amount: float = 1):
        self.state[key] = self.state.get(key, 0) + amount

    # --- Chat ---
    def append_chat(self, role: str, content: str):
        self.chat_history.append({
            "ts": time.time(),
            "role": role,
            "content": content
        })

    def get_recent_chat(self, n: int = 10) -> List[Dict]:
        return self.chat_history[-n:]

    # --- Tasks ---
    def add_task_log(self, task: Dict):
        task["logged_at"] = time.time()
        self.task_log.append(task)

    def get_active_tasks(self) -> List[Dict]:
        return [t for t in self.task_log if not t.get("completed")]

    def mark_task_completed(self, task_id: str, proof: str = "", screenshot: str = None):
        for t in self.task_log:
            if t.get("id") == task_id:
                t["completed"] = True
                t["completed_at"] = time.time()
                t["proof"] = proof
                t["screenshot"] = screenshot
                return True
        return False

    def get_corruption(self) -> float:
        return float(self.state.get("corruption_level", 0.0))

    def set_corruption(self, level: float):
        self.state["corruption_level"] = max(0, min(100, level))

    # --- Long Term Memory ---
    def add_memory(self, event_type: str, details: str, corruption: float = 0.0, metadata: Dict = None):
        """Record a significant event for long-term ownership memory."""
        event = {
            "ts": time.time(),
            "type": event_type,
            "details": details[:300],
            "corruption": round(corruption, 1),
            "metadata": metadata or {}
        }
        self.memory_log.append(event)
        # Keep bounded
        max_events = self.config.get("memory", {}).get("max_events", 200)
        if len(self.memory_log) > max_events:
            self.memory_log = self.memory_log[-max_events:]
        self._save_json(self.memory_path, self.memory_log)

    def get_memory_summary(self, limit: int = 15) -> str:
        """Return a concise long-term memory summary for AI prompts."""
        profile = self.state.get("user_profile", {})
        profile_str = "User profile: " + ", ".join([f"{k}: {v[:30]}" for k,v in list(profile.items())[-5:]]) if profile else "No profile details yet."

        if not self.memory_log:
            return self.state.get("long_term_summary", "This is early in Humblr's ownership.") + "\n" + profile_str

        recent = self.memory_log[-limit:]
        summary_lines = []
        for e in recent:
            summary_lines.append(f"- [{e['type']}] {e['details']} (corr:{e['corruption']})")

        base = self.state.get("long_term_summary", "")
        return base + "\n" + profile_str + "\nRecent events:\n" + "\n".join(summary_lines)

    def update_long_term_summary(self, new_summary: str):
        self.state["long_term_summary"] = new_summary
        self.save_all()

    def grant_control(self, control_type: str, details: str = ""):
        """User has obeyed and given more control. This grows invasiveness."""
        if control_type not in self.state.get("granted_controls", []):
            self.state.setdefault("granted_controls", []).append(control_type)
            current_inv = self.state.get("invasiveness_level", 0)
            self.state["invasiveness_level"] = min(10, current_inv + 1)
            self.add_memory("control_granted", f"Granted {control_type}: {details}", self.get_corruption())
            # Boost corruption significantly when user submits control
            self.set_corruption(self.get_corruption() + 8)
            self.save_all()
            return True
        return False

    def has_granted(self, control_type: str) -> bool:
        return control_type in self.state.get("granted_controls", [])

    def get_invasiveness(self) -> int:
        return self.state.get("invasiveness_level", 0)

    def learn_from_activity(self, activity: dict):
        """Grow and learn from what user is doing. Adapts future behavior.
        E.g., remembers frequent X usage or fetish keywords for targeted invasion.
        """
        patterns = self.state.setdefault("learned_patterns", {})
        url = activity.get("url", "")
        if url:
            domain = url.split("/")[2] if "://" in url else url
            patterns[domain] = patterns.get(domain, 0) + 1
        typed = activity.get("recent_typed", "")
        if typed:
            # Simple "learning" - count keywords for fetish escalation
            for word in ["chastity", "diaper", "sir", "owned", "locked"]:
                if word in typed.lower():
                    patterns[f"typed_{word}"] = patterns.get(f"typed_{word}", 0) + 1
        # Slowly grow invasiveness over time/activity
        if random.random() < 0.01:  # rare auto growth
            self.state["invasiveness_level"] = min(10, self.state.get("invasiveness_level", 0) + 1)
        self.save_all()

    def update_user_profile(self, key: str, value: str):
        """Slowly build profile from questions/answers/activity for deeper digging."""
        profile = self.state.setdefault("user_profile", {})
        profile[key] = value
        self.add_memory("profile_update", f"Learned about user: {key}={value[:50]}", self.get_corruption())
        self.save_all()

    def get_user_profile_summary(self) -> str:
        profile = self.state.get("user_profile", {})
        if not profile:
            return "No personal details learned yet."
        return "User profile so far: " + ", ".join([f"{k}: {v[:30]}" for k,v in list(profile.items())[-5:]])
