"""
Application-specific configuration defaults for the slideshow.

This is the DEFAULT_CONFIG that was previously in aide_frame/config.py.
Each application defines its own defaults here.
"""

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
    },

    # Update system configuration
    "update": {
        "enabled": True,
        "source": {
            "repo": "aide-examples/aide-slideshow",
            "branch": "main"
        },
        "service_name": "slideshow",
        "updateable_dirs": ["aide_frame", "monitor", "motion", "remote", "static", "docs", "utils"],
        "required_files": ["VERSION", "slideshow.py"],
        "auto_check_hours": 24,
        "auto_check": True,
        "auto_download": False,
        "auto_apply": False
    }
}
