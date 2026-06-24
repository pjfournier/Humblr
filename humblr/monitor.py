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

try:
    import uiautomation as auto
except ImportError:
    auto = None



class ActivityMonitor:
    def __init__(self, config: Dict, storage):
        self.config = config
        self.storage = storage
        self.enabled = config.get("monitoring", {}).get("enabled", True)

        self.current_activity = {
            "window_title": "Unknown",
            "process_name": "Unknown",
            "url": None,
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
            return {"window_title": "N/A (no pywin32)", "process_name": "N/A", "url": None}

        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or "No title"

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                name = proc.name().lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                name = "unknown.exe"

            url = None
            if auto is not None and any(b in name for b in ['chrome', 'msedge', 'firefox', 'brave', 'opera']):
                url = self._try_get_browser_url(hwnd, name)

            return {
                "window_title": title[:120],
                "process_name": name,
                "url": url
            }
        except Exception:
            return {"window_title": "Error reading window", "process_name": "unknown", "url": None}

    def _try_get_browser_url(self, hwnd, process_name: str) -> Optional[str]:
        """Attempt to read the current URL from the browser's address bar using UI Automation."""
        if auto is None:
            return None

        try:
            # Get the window control from handle
            window = auto.ControlFromHandle(hwnd)
            if not window.Exists(0, 0):
                return None

            # Common strategies for Chromium-based browsers (Chrome, Edge, Brave, Opera)
            if any(b in process_name for b in ['chrome', 'msedge', 'brave', 'opera']):
                # Strategy 1: Look for the omnibox / address bar edit control
                address = window.EditControl(ClassName='Chrome_OmniboxView')
                if address.Exists(0.2, 0):
                    value = address.GetValuePattern().Value
                    if value and (value.startswith('http') or value.startswith('chrome') or value.startswith('edge')):
                        return value.strip()

                # Strategy 2: Search more broadly in the toolbar area
                try:
                    toolbar = window.ToolbarControl(searchDepth=5)
                    if toolbar.Exists(0.2, 0):
                        edit = toolbar.EditControl()
                        if edit.Exists(0.1, 0):
                            val = edit.GetValuePattern().Value
                            if val and val.startswith(('http', 'https', 'www.')):
                                return val.strip()
                except Exception:
                    pass

                # Strategy 3: Find by AutomationId or Name containing "address"
                try:
                    addr = window.FindFirst(searchDepth=8,
                                            condition=auto.ControlCondition(
                                                lambda c: 'address' in (c.Name or '').lower() or
                                                          'omnibox' in (c.ClassName or '').lower() or
                                                          c.LocalizedControlType == 'edit'
                                            ))
                    if addr and addr.Exists(0.1, 0):
                        val = addr.GetValuePattern().Value if addr.IsValuePatternAvailable() else None
                        if val and val.startswith('http'):
                            return val.strip()
                except Exception:
                    pass

            # Firefox
            if 'firefox' in process_name:
                try:
                    # Firefox uses different class names
                    url_bar = window.EditControl(Name='Search with Google or enter address')
                    if not url_bar.Exists(0.2, 0):
                        url_bar = window.EditControl(AutomationId='urlbar-input')
                    if url_bar.Exists(0.2, 0):
                        val = url_bar.GetValuePattern().Value
                        if val and val.startswith('http'):
                            return val.strip()
                except Exception:
                    pass

            # Last resort: try to find any visible Edit control that looks like a URL in the top part of the window
            try:
                edits = window.FindAll(searchDepth=6, condition=auto.ControlCondition(
                    lambda c: c.LocalizedControlType in ('edit', 'text') and c.IsVisible
                ))
                for edit in edits[:5]:
                    try:
                        val = edit.GetValuePattern().Value
                        if val and val.startswith(('http://', 'https://')):
                            return val.strip()
                    except:
                        continue
            except Exception:
                pass

        except Exception as e:
            # Silent fail - UIA can be fragile
            pass

        return None


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
        url = act.get("url")
        base = (f"Active window: \"{act.get('window_title', '?')}\" "
                f"({act.get('process_name', '?')}) — {ks} keys in last window")
        if url:
            # Show a clean version of the URL
            short_url = url[:70] + "..." if len(url) > 70 else url
            base += f" | URL: {short_url}"
        return base


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

    def get_current_activity(self) -> Dict[str, Any]:
        """Return a copy of the latest activity dict (includes url when available)."""
        with self._lock:
            return self.current_activity.copy()

