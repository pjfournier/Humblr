"""
Activity Monitor - tracks active window and typing behavior.
Windows focused.
"""

import time
import threading
from typing import Dict, Optional, Any
from collections import deque

import psutil

try:
    import win32gui
    import win32process
except ImportError:
    win32gui = None
    win32process = None

try:
    from pynput import keyboard
except ImportError:
    keyboard = None


class ActivityMonitor:
    def __init__(self, config: Dict, storage):
        self.config = config
        self.storage = storage
        self.enabled = config.get("monitoring", {}).get("enabled", True)

        self.current_activity = {
            "window_title": "Unknown",
            "process_name": "Unknown",
            "keystrokes_last_window": 0,
        }

        self.keystroke_buffer = deque(maxlen=500)
        self._last_sample_time = time.time()
        self._pending_comment: Optional[str] = None
        self._lock = threading.Lock()

        self.listener = None
        self._start_keyboard_listener()

    def _start_keyboard_listener(self):
        if not self.enabled or keyboard is None:
            return
        try:
            self.listener = keyboard.Listener(on_press=self._on_key_press)
            self.listener.daemon = True
            self.listener.start()
            print("[Monitor] Keyboard listener started.")
        except Exception as e:
            print(f"[Monitor] Could not start keyboard listener: {e}")

    def _on_key_press(self, key):
        with self._lock:
            self.keystroke_buffer.append(time.time())

    def poll(self) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        activity = self._get_active_window()
        keystrokes = self._count_keystrokes_in_window()

        activity["keystrokes"] = keystrokes
        activity["timestamp"] = time.time()

        with self._lock:
            self.current_activity = activity

        # Store some stats
        self.storage.increment("total_keystrokes", keystrokes)

        return activity

    def _get_active_window(self) -> Dict[str, str]:
        if win32gui is None:
            return {"window_title": "N/A (no pywin32)", "process_name": "N/A"}

        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or "No title"

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                name = "unknown.exe"

            return {
                "window_title": title[:120],
                "process_name": name
            }
        except Exception:
            return {"window_title": "Error reading window", "process_name": "unknown"}

    def _count_keystrokes_in_window(self) -> int:
        window_sec = self.config.get("monitoring", {}).get("keystroke_sample_window", 25)
        now = time.time()
        cutoff = now - window_sec

        with self._lock:
            recent = [t for t in self.keystroke_buffer if t > cutoff]
            count = len(recent)
            self.keystroke_buffer.clear()
            # re-add recent to keep buffer somewhat accurate
            for t in recent:
                self.keystroke_buffer.append(t)
            return count

    def get_current_activity_summary(self) -> str:
        act = self.current_activity
        ks = act.get("keystrokes", 0)
        return (f"Active window: \"{act.get('window_title', '?')}\" "
                f"({act.get('process_name', '?')}) — {ks} keys in last window")

    def queue_comment(self, text: str):
        with self._lock:
            self._pending_comment = text

    def has_pending_comment(self) -> bool:
        with self._lock:
            return self._pending_comment is not None

    def get_pending_comment(self) -> Optional[str]:
        with self._lock:
            c = self._pending_comment
            self._pending_comment = None
            return c
