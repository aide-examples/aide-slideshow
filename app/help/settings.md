# Settings

Configuration options for the slideshow.

## Display Settings

### Display Duration

How long each image is shown (in seconds). Adjust via:
- Web interface: Click "Duration" and select a value
- Config file: Set `display_duration` in `config.json`

Default: 35 seconds

### Fade Effect

Smooth transitions between images. Configure `fade_steps` in the config file:
- `0` = No fade (instant switch)
- `15` = Smooth fade (default)
- `30` = Very slow fade

## Monitor Control

### Automatic Power Off

The monitor can turn off after a period of inactivity:
- Set `motion_sensor.idle_timeout` in config (seconds)
- Requires motion sensor or manual trigger

### Power Control Methods

| Provider | Description |
|----------|-------------|
| `cec` | HDMI-CEC commands (most TVs) |
| `shelly` | Shelly smart plug |
| `gpio_relay` | GPIO relay module |
| `samsung_ws` | Samsung TV WebSocket API |

## Remote Control

### HTTP API

The web interface runs on port 8080 by default. Change via `remote_control.http_api.port` in config.

### Alexa Voice Control

Enable Alexa integration:
1. Set `remote_control.alexa.enabled` to `true`
2. Configure device name
3. Say "Alexa, turn on Slideshow"

## Configuration File

All settings are in `config.json`. Example:

```json
{
    "display_duration": 35,
    "fade_steps": 15,
    "monitor_control": {
        "provider": "cec"
    }
}
```

Restart the slideshow after changing config:
```bash
sudo systemctl restart slideshow
```
