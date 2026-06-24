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
        "base_increase_per_hour": 1.2,
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
    "twitter": {
        "enabled": False,
        "api_key": "",
        "api_secret": "",
        "access_token": "",
        "access_token_secret": ""
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
            print("  Hint: Your config.json is invalid JSON (bad quotes, commas, etc at or near line 27). I'll write a fresh one now.")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=2)
                print(f"  Wrote clean {path}. Restart or grant key to load it.")
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
