"""
Global hotkeys.
"""

import threading

try:
    import keyboard
except ImportError:
    keyboard = None


_kill_registered = False


def register_killswitch(hotkey: str, callback):
    global _kill_registered
    if _kill_registered or keyboard is None:
        return

    def handler():
        print(f"[Hotkey] {hotkey} pressed — killing Humblr")
        callback()

    try:
        keyboard.add_hotkey(hotkey, handler, suppress=False)
        _kill_registered = True
        print(f"[Hotkeys] Killswitch registered: {hotkey}")
    except Exception as e:
        print(f"[Hotkeys] Failed to register hotkey: {e}")
