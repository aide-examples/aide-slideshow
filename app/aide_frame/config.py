"""
Configuration loading utilities.

Provides JSON configuration loading with deep merge support.
Applications provide their own DEFAULT_CONFIG.

Usage:
    from aide_frame.config import load_config

    # Simple load (no defaults)
    config = load_config("config.json")

    # With application defaults
    MY_DEFAULTS = {"port": 8080, "debug": False}
    config = load_config("config.json", defaults=MY_DEFAULTS)

    # With search paths
    config = load_config("config.json", search_paths=[
        "/etc/myapp/config.json",
        "~/.myapp/config.json",
        "./config.json"
    ])
"""

import json
import os


def deep_merge(base, override):
    """
    Recursively merge override into base.

    Args:
        base: Base dictionary (modified in place)
        override: Dictionary with override values

    Returns:
        The merged base dictionary
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(config_path=None, defaults=None, search_paths=None):
    """
    Load configuration from JSON file, merging with defaults.

    Args:
        config_path: Direct path to config file (takes precedence)
        defaults: Default configuration dictionary
        search_paths: List of paths to search for config file

    Returns:
        Configuration dictionary
    """
    # Start with defaults (deep copy to avoid modifying original)
    if defaults:
        config = json.loads(json.dumps(defaults))
    else:
        config = {}

    # Determine which config file to load
    paths_to_try = []
    if config_path:
        paths_to_try.append(config_path)
    if search_paths:
        paths_to_try.extend(search_paths)

    # Expand user paths (~)
    paths_to_try = [os.path.expanduser(p) for p in paths_to_try]

    # Try each path
    loaded_path = None
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    user_config = json.load(f)
                    deep_merge(config, user_config)
                    loaded_path = path
                    break
            except json.JSONDecodeError as e:
                print(f"Config parse error in {path}: {e}")
            except IOError as e:
                print(f"Config read error in {path}: {e}")

    if not loaded_path and paths_to_try:
        print(f"No config file found, using defaults")

    return config


def save_config(config, config_path, indent=2):
    """
    Save configuration to JSON file.

    Args:
        config: Configuration dictionary
        config_path: Path to save to
        indent: JSON indentation (default 2)

    Returns:
        True on success, False on error
    """
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=indent)
        return True
    except IOError as e:
        print(f"Config save error: {e}")
        return False
