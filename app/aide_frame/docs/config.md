# Configuration

**Module:** `config.py`

Loading and managing application configuration.

## Purpose

- Load configuration from JSON file
- Provide sensible defaults
- Merge user config with defaults

## API

```python
from config import load_config, DEFAULT_CONFIG

# Load config (merges with defaults)
config = load_config("/path/to/config.json")

# Access settings
duration = config.get("display_duration", 35)
monitor_provider = config.get("monitor_control", {}).get("provider", "none")
```

## Config File Location

The config file is searched in this order:
1. Path specified via `--config` command line argument
2. `config.json` in the project root directory

## Default Configuration

```python
DEFAULT_CONFIG = {
    "image_dir": "img/show",
    "upload_dir": "img/upload",
    "display_duration": 35,
    "fade_steps": 5,
    "monitor_control": {
        "provider": "none"
    },
    "motion_sensor": {
        "provider": "none",
        "idle_timeout": 300
    },
    "remote_control": {
        "http_api": {"enabled": True, "port": 8080}
    }
}
```

## Path Handling

Paths can be:
- **Relative** - Resolved against the script directory (recommended)
- **Absolute** - Used as-is

```json
{
    "image_dir": "img/show",           // Relative (recommended)
    "image_dir": "/home/pi/photos"     // Absolute
}
```

**Security:** Path traversal (`..`) is blocked to prevent accessing files outside the intended directories.

## Full Configuration Reference

### Core Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `image_dir` | string | `"img/show"` | Path to images (scanned recursively) |
| `upload_dir` | string | `"img/upload"` | Path for raw uploads |
| `display_duration` | int | `35` | Seconds per image |
| `fade_steps` | int | `5` | Transition smoothness (1-30) |

### Monitor Control

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `monitor_control.provider` | string | `"none"` | Provider: `none`, `cec`, `shelly`, `gpio_relay`, `samsung_ws` |

See [Monitor Control](../slideshow/monitor-control.md) for provider-specific settings.

### Motion Sensor

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `motion_sensor.provider` | string | `"none"` | Provider: `none`, `gpio_pir`, `mqtt` |
| `motion_sensor.idle_timeout` | int | `300` | Seconds of no motion before standby |

See [Motion Detection](../slideshow/motion-detection.md) for provider-specific settings.

### Remote Control

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `remote_control.http_api.enabled` | bool | `true` | Enable HTTP API |
| `remote_control.http_api.port` | int | `8080` | HTTP server port |
| `remote_control.ir_remote.enabled` | bool | `false` | Enable IR remote |
| `remote_control.alexa.enabled` | bool | `false` | Enable Alexa voice control |

See [Web Control](../slideshow/web-control.md), [IR Remote](../slideshow/ir-remote.md), and [Alexa](../slideshow/alexa.md) for details.

## Example Configuration

```json
{
    "image_dir": "img/show",
    "upload_dir": "img/upload",
    "display_duration": 35,
    "fade_steps": 5,

    "monitor_control": {
        "provider": "cec",
        "cec": { "device_id": "0" }
    },

    "motion_sensor": {
        "provider": "gpio_pir",
        "idle_timeout": 300,
        "gpio_pir": { "pin": 17 }
    },

    "remote_control": {
        "http_api": { "enabled": true, "port": 8080 },
        "ir_remote": { "enabled": false },
        "alexa": { "enabled": false }
    }
}
```
