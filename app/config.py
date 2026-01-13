"""
Configuration loading and defaults.

Provides default configuration values and loading from JSON files.
"""

import json

DEFAULT_CONFIG = {
    "image_dir": "img/show",
    "upload_dir": "img/upload",
    "display_duration": 35,
    "fade_steps": 5,
    "api_port": 8080,

    # Monitor power control - choose ONE provider
    "monitor_control": {
        "provider": "cec",  # Options: "cec", "shelly", "gpio_relay", "samsung_ws", "none"
        "cec": {
            "device_id": "0"
        },
        "shelly": {
            "ip": None
        },
        "gpio_relay": {
            "pin": 27,
            "active_low": False
        },
        "samsung_ws": {
            "ip": None,
            "port": 8002,
            "mac_address": None,
            "token_file": "/home/pi/.samsung_token",
            "name": "RaspberryPiSlideshow",
            "timeout": 5
        }
    },

    # Motion sensor - choose ONE provider
    "motion_sensor": {
        "provider": "none",  # Options: "gpio_pir", "mqtt", "none"
        "idle_timeout": 300,  # Seconds without motion before turning off monitor
        "gpio_pir": {
            "pin": 17
        },
        "mqtt": {
            "broker": None,
            "topic": "home/motion/livingroom"
        }
    },

    # Remote control input - can enable MULTIPLE
    "remote_control": {
        "http_api": {
            "enabled": True,
            "port": 8080
        },
        "ir_remote": {
            "enabled": False,
            "device": "/dev/input/event0",
            "key_map": {
                "KEY_PLAYPAUSE": "toggle_pause",
                "KEY_PLAY": "resume",
                "KEY_PAUSE": "pause",
                "KEY_NEXT": "skip",
                "KEY_PREVIOUS": "skip",
                "KEY_UP": "speed_down",
                "KEY_DOWN": "speed_up",
                "KEY_POWER": "toggle_monitor",
                "KEY_1": "filter_1",
                "KEY_2": "filter_2",
                "KEY_3": "filter_3",
                "KEY_0": "filter_clear"
            },
            "folder_shortcuts": {
                "filter_1": None,
                "filter_2": None,
                "filter_3": None
            }
        },
        "alexa": {
            "enabled": False,
            "device_name": "Slideshow",
            "port": 12340
        }
    }
}


def load_config(config_path="/home/pi/slideshow/config.json"):
    """Load configuration from JSON file, merging with defaults."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # Deep copy

    def deep_merge(base, override):
        """Recursively merge override into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    try:
        with open(config_path, 'r') as f:
            user_config = json.load(f)
            deep_merge(config, user_config)
    except FileNotFoundError:
        print(f"Config not found at {config_path}, using defaults")
    except json.JSONDecodeError as e:
        print(f"Config parse error: {e}, using defaults")

    return config
