"""
Activity Monitor - tracks active window and typing behavior.
Windows focused.
"""

import time
import threading
from typing import Dict, Optional, Any
from collections import deque

import psutil
import time

try:
    from contextlib import nullcontext
except ImportError:
    # Python < 3.7
    from contextlib import contextmanager
    @contextmanager
    def nullcontext(enter_result=None):
        yield enter_result

try:
    import win32gui
    import win32process
    import win32api
except ImportError:
    win32gui = None
    win32process = None
    win32api = None

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

try:
    import uiautomation as auto
except ImportError:
    auto = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import pyautogui
except ImportError:
    pyautogui = None



class ActivityMonitor:
    def __init__(self, config: Dict, storage):
        self.config = config
        self.storage = storage
        self.enabled = config.get("monitoring", {}).get("enabled", True)

        self.current_activity = {
            "window_title": "Unknown",
            "process_name": "Unknown",
            "url": None,
            "visible_text": "",
            "clipboard": "",
            "keystrokes": 0,
            "recent_typed": "",
            "x_content": "",
        }

        self.keystroke_buffer = deque(maxlen=500)
        self.text_buffer = deque(maxlen=400)  # actual typed chars for keylogger feature
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
            # Capture actual typed text for keylogger / commenting on what user is "saying" or thinking
            try:
                if hasattr(key, 'char') and key.char is not None:
                    self.text_buffer.append(key.char)
                elif key == keyboard.Key.space:
                    self.text_buffer.append(' ')
                elif key == keyboard.Key.enter:
                    self.text_buffer.append('\n')
            except:
                pass

    def poll(self) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        # UIAutomation must be initialized per-thread when used from a background thread.
        # Wrap the UIA-dependent parts (window detection + text extraction) in the required context.
        if auto is not None:
            uia_ctx = auto.UiaAutomationInitializerInThread()
        else:
            uia_ctx = nullcontext()

        with uia_ctx:
            activity = self._get_active_window()
            keystrokes = self._count_keystrokes_in_window()

            # Enrich with deeper context (these may rely on UIA)
            activity["keystrokes"] = keystrokes
            activity["timestamp"] = time.time()
            activity["visible_text"] = self._extract_visible_text_snippet(activity.get("window_title", ""))
            activity["clipboard"] = self._get_clipboard_snippet()

        # Non-UIA parts
        # Work safety and monitor detection
        activity["is_work"] = self._is_work_context(activity)
        activity["is_secondary_monitor"] = self._is_on_secondary_monitor()
        activity["context_type"] = self._classify_context(activity)

        # Special X content awareness
        url = (activity.get("url") or "").lower()
        if 'twitter' in url or 'x.com' in url:
            activity["x_content"] = activity.get("visible_text", "")[:300]

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
                "url": url,
                "visible_text": "",
                "clipboard": ""
            }
        except Exception:
            return {
                "window_title": "Error reading window",
                "process_name": "unknown",
                "url": None,
                "visible_text": "",
                "clipboard": ""
            }

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

    def _extract_visible_text_snippet(self, title_hint: str = "", max_chars: int = 400) -> str:
        """Use UIA to pull some readable text from the active window (headings, text blocks, etc.)."""
        if auto is None or win32gui is None:
            return ""

        try:
            hwnd = win32gui.GetForegroundWindow()
            window = auto.ControlFromHandle(hwnd)
            if not window.Exists(0, 0):
                return ""

            texts = []
            # Collect text from various control types that usually hold content
            for control_type in [auto.TextControl, auto.EditControl, auto.DocumentControl]:
                try:
                    controls = window.FindAll(searchDepth=7, condition=auto.ControlCondition(
                        lambda c, ct=control_type: isinstance(c, ct) and c.IsVisible and c.Name
                    )) or []
                    for c in controls[:8]:
                        name = (c.Name or "").strip()
                        if name and len(name) > 3 and name not in texts:
                            texts.append(name)
                except:
                    continue

            # Also try to get some from the main document area (good for browsers and editors)
            try:
                doc = window.DocumentControl(searchDepth=4)
                if doc and doc.Exists(0, 0):
                    # Get some children text
                    for child in doc.GetChildren()[:6]:
                        if hasattr(child, 'Name') and child.Name:
                            t = child.Name.strip()
                            if len(t) > 5:
                                texts.append(t)
            except:
                pass

            combined = " ".join(texts)
            # Clean and truncate
            combined = " ".join(combined.split())[:max_chars]
            return combined
        except Exception:
            return ""

    def _get_clipboard_snippet(self, max_len: int = 300) -> str:
        """Grab current clipboard text (last thing copied)."""
        if pyperclip is None:
            return ""
        try:
            text = pyperclip.paste()
            if isinstance(text, str) and text.strip():
                cleaned = " ".join(text.strip().split())
                return cleaned[:max_len]
        except Exception:
            pass
        return ""

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
        visible = act.get("visible_text", "")[:150]
        clip = act.get("clipboard", "")[:80]
        recent_typed = act.get("recent_typed", "")[:120]
        x_content = act.get("x_content", "")[:120]
        context = act.get("context_type", "general")
        work_flag = "WORK" if act.get("is_work") else "LEISURE"
        monitor = "SECONDARY" if act.get("is_secondary_monitor") else "PRIMARY"

        base = (f"[{work_flag}/{monitor}/{context}] Active: \"{act.get('window_title', '?')}\" "
                f"({act.get('process_name', '?')}) — {ks} keys")

        if url:
            short_url = url[:65] + "..." if len(url) > 65 else url
            base += f"\nURL: {short_url}"

        if recent_typed:
            base += f"\nRecently typed: {recent_typed}..."

        if x_content:
            base += f"\nOn X reading: {x_content}..."

        if visible:
            base += f"\nVisible on screen: {visible}..."

        if clip:
            base += f"\nClipboard: {clip}..."

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

    def _is_work_context(self, activity: Dict) -> bool:
        """Detect if user is in a work context (should limit aggression)."""
        work_procs = self.config.get("work_safety", {}).get("work_processes", [])
        work_domains = self.config.get("work_safety", {}).get("work_domains", [])

        proc = (activity.get("process_name") or "").lower()
        title = (activity.get("window_title") or "").lower()
        url = (activity.get("url") or "").lower()

        for p in work_procs:
            if p in proc or p in title:
                return True

        for d in work_domains:
            if d in url:
                return True

        # Boss / meeting detection
        if any(x in title for x in ["boss", "manager", "director", "call with", "meeting with", "1:1"]):
            return True

        return False

    def _is_on_secondary_monitor(self) -> bool:
        """Check if the foreground window is primarily on a secondary monitor."""
        if win32gui is None or win32api is None:
            return False
        try:
            hwnd = win32gui.GetForegroundWindow()
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            # Get all monitors
            monitors = win32api.EnumDisplayMonitors(None, None)
            if len(monitors) <= 1:
                return False  # only primary

            # Find which monitor the window center is on
            cx = (left + right) // 2
            cy = (top + bottom) // 2

            primary = monitors[0][2]  # (left, top, right, bottom)
            for i, m in enumerate(monitors):
                ml, mt, mr, mb = m[2]
                if ml <= cx <= mr and mt <= cy <= mb:
                    return i != 0  # not primary
            return False
        except Exception:
            return False

    def _classify_context(self, activity: Dict) -> str:
        title = (activity.get("window_title") or "").lower()
        proc = (activity.get("process_name") or "").lower()
        url = (activity.get("url") or "").lower()

        if any(x in title + proc for x in ["porn", "onlyfans", "chaturbate", "xvideos", "pornhub", "reddit.com/r/"]):
            return "leisure_porn"
        if any(x in url for x in ["reddit", "twitter", "x.com", "instagram", "tiktok", "youtube"]):
            return "leisure_social"
        if any(x in proc for x in ["game", "steam", "discord"]):
            return "gaming"
        if activity.get("is_work"):
            return "work"
        return "general"

    def take_screenshot(self, context: str = "auto") -> Optional[str]:
        """Capture screenshot for analysis or proof. Returns path or None."""
        if pyautogui is None:
            return None
        try:
            screenshots_dir = Path(self.config.get("data_paths", {}).get("screenshots", "data/screenshots"))
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            path = screenshots_dir / f"screenshot_{context}_{timestamp}.png"
            screenshot = pyautogui.screenshot()
            screenshot.save(str(path))
            return str(path)
        except Exception as e:
            print(f"[Monitor] Screenshot failed: {e}")
            return None

