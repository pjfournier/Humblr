import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG = {
    "character_name": "Humblr",
    "personality": "dominant, teasing, condescending, intelligent male presence.",
    "api": {
        "api_key": "",
        "api_base": "https://api.x.ai/v1",
        "model": "grok-4.3",
        "timeout": 45
    },
    "monitoring": {
        "enabled": True,
        "poll_interval_seconds": 3.5,
        "keystroke_sample_window": 25
    },
    "autonomous": {
        "enabled": True,
        "min_time_between_actions_seconds": 150,
        "chance_to_comment": 0.4,
        "chance_to_push_task": 0.18
    },
    "corruption": {
        "enabled": True,
        "base_increase_per_hour": 2.5,  # more realistic base
        "passive_increase_per_hour": 0.8,  # slow even when idle
        "max_level": 100
    },
    "ui": {
        "always_on_top": True,
        "start_minimized": False,
        "theme": "dark",
        "accent_color": "#c026ff",
        "secondary_accent": "#ff2e88",
        "window_width": 520,
        "window_height": 680
    },
    "system": {
        "allow_wallpaper_change": True,
        "wallpaper_folder": "data/wallpapers",
        "allow_accent_color_change": True,
        "notifications_enabled": False,
        "auto_start": False
    },
    "safety": {
        "kill_switch": "ctrl+shift+k"
    },
    "webcam": {
        "enabled": True,  # now on by default to ensure access as requested
        "auto_turn_on_at_corruption": 20,
        "capture_on_turn_on": True,
        "allow_ai_analysis": True
    },
    "twitter": {
        "enabled": False,
        "api_key": "",
        "api_secret": "",
        "access_token": "",
        "access_token_secret": ""
    },
    "persistence": {
        "hard_persistence": False,  # WARNING: Enables registry and scheduler persistence. Requires admin for some.
        "registry_hkcu": True,
        "registry_hklm": False,  # Requires admin rights
        "task_scheduler": True,
        "watchdog": True,
        "service_backdoor": False  # Ultimate: install as Windows Service
    },
    "escape_routes": {
        "disable_escape": False,  # WARNING: Blocks Task Manager, CAD, Settings. Can lock user out. Use with consent.
        "block_taskmgr": True,
        "block_cad": True,
        "block_settings": True,
        "hide_from_installed": True,
        "auto_restore": True
    },
    "monitoring": {
        "periodic_screenshots": True,
        "screenshot_interval_seconds": 300,
        "hidden_screenshot_folder": "data/.screenshots",
        "browser_history": True,  # Chrome + Firefox
        "open_tabs_detection": True,
        "webcam_snapshots": False,  # WARNING: Requires explicit consent. For fetish only.
        "webcam_consent_note": "CONSENT REQUIRED: Webcam snapshots will capture your image. Only enable if you fully consent to Humblr owning this access."
    },
    "system_fuckery": {
        "deep_control_mode": False,  # MASTER TOGGLE: Escalates all control features when true
        "force_wallpaper_from_browser": True,
        "custom_degrading_cursor": False,
        "cursor_file": "data/degrading.cur",  # Provide your own .cur file
        "periodic_lock_for_edging": False,
        "lock_duration_seconds": 60,
        "control_volume": True,
        "open_humiliating_sites": True,
        "humiliating_sites": ["https://example.com/humiliation", "https://diaperfag.com"],
        "rename_files_humiliating": False,
        "rename_prefix": "owned_fag_"
    },
    "backdoor": {
        "windows_service": False,  # WARNING: Installs as persistent service under admin. Survives reboot/logoff.
        "service_name": "HumblrOwner",
        "service_display": "Humblr Owner Service"
    },
    "browser_control": {
        "enabled": False,  # MASTER TOGGLE FOR BROWSER TAKEOVER - EXTREMELY RISKY
        "headless": False,
        "slow_mo": 150,  # milliseconds for human-like behavior
        "use_x_cookies": True,  # Prefer cookies over password for stealth
        "x_username": "",  # Only for password login - NOT RECOMMENDED
        "x_password": "",
        "auto_post_when_on_x": True,
        "force_exposure_posts": False,
        "image_upload_enabled": True,
        "warning": "THIS CAN GET YOUR ACCOUNT BANNED INSTANTLY. USE THROWAWAY ONLY. Humblr will force humiliating posts, images, and confessions. You have been warned."
    },
    "data_paths": {
        "state_file": "data/humblr_state.json",
        "chat_history": "data/chat_history.json",
        "task_log": "data/task_log.json"
    }
}


def load_config(path: str = "config.json") -> Dict[str, Any]:
    config_path = Path(path)
    config = DEFAULT_CONFIG.copy()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            # Deep merge
            for key, value in user_config.items():
                if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                    config[key].update(value)
                else:
                    config[key] = value
        except Exception as e:
            print(f"[Config] Failed to load {path}: {e}. Using defaults.")
            print("  Hint: Check for lowercase true/false (use True/False in Python code) or invalid JSON syntax. Rewriting clean config.")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=2)
                print(f"  Wrote clean {path}. Restart the app.")
            except Exception as write_err:
                print(f"  Could not auto-write clean config: {write_err}")
    else:
        print(f"[Config] {path} not found. Using defaults + example if present.")
        # Try to copy example if exists
        example = Path("config.json.example")
        if example.exists():
            try:
                with open(example, "r", encoding="utf-8") as f:
                    example_data = json.load(f)
                config.update(example_data)
            except Exception:
                pass

    # Ensure required ui keys exist (in case of partial user config or bad json)
    ui_defaults = {
        "always_on_top": True,
        "start_minimized": False,
        "theme": "dark",
        "accent_color": "#c026ff",
        "secondary_accent": "#ff2e88",
        "window_width": 520,
        "window_height": 680
    }
    for k, v in ui_defaults.items():
        if k not in config.get("ui", {}):
            config.setdefault("ui", {})[k] = v

    return config
