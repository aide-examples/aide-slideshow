# IR Remote Control

**Module:** `remote/ir_remote.py`

Physical infrared remote control support.

## Purpose

Control the slideshow with a standard IR remote - no network or app required.

## Requirements

| Component | Details |
|-----------|---------|
| **Hardware** | IR receiver (VS1838B or similar), any IR remote |
| **Software** | `ir-keytable` package |
| **Cost** | ~€2 |

## Hardware Setup

**Wiring:**
| VS1838B | Raspberry Pi |
|---------|--------------|
| VCC | 3.3V (Pin 1) |
| GND | GND (Pin 6) |
| OUT | GPIO 18 (Pin 12) |

**Kernel overlay:**

Add to `/boot/config.txt`:
```
dtoverlay=gpio-ir,gpio_pin=18
```

Reboot after making this change.

## Configuration

```json
"remote_control": {
    "ir_remote": {
        "enabled": true,
        "device": "/dev/input/event0",
        "key_map": {
            "KEY_PLAYPAUSE": "toggle_pause",
            "KEY_NEXT": "skip",
            "KEY_UP": "speed_down",
            "KEY_DOWN": "speed_up",
            "KEY_POWER": "toggle_monitor",
            "KEY_1": "filter_1",
            "KEY_0": "filter_clear"
        },
        "folder_shortcuts": {
            "filter_1": "vacation",
            "filter_2": "family",
            "filter_3": "nature"
        }
    }
}
```

## Available Actions

| Action | Description |
|--------|-------------|
| `toggle_pause` | Pause or resume slideshow |
| `pause` | Pause slideshow |
| `resume` | Resume slideshow |
| `skip` | Skip to next image |
| `speed_up` | Decrease display duration by 5s |
| `speed_down` | Increase display duration by 5s |
| `toggle_monitor` | Turn monitor on/off |
| `monitor_on` | Turn monitor on |
| `monitor_off` | Turn monitor off |
| `filter_clear` | Show all images |
| `filter_1/2/3` | Apply folder shortcut |

## Finding Your Input Device

```bash
# List input devices
cat /proc/bus/input/devices | grep -A 5 "ir"

# Or list all event devices
ls -la /dev/input/event*
```

## Testing Key Codes

Use `ir-keytable` to see which key codes your remote sends:

```bash
# Test remote (press buttons and see key codes)
ir-keytable -t -d /dev/input/event0
```

Output example:
```
Testing events. Please, press CTRL-C to abort.
1234567890.123456: event type EV_KEY(0x01): key_down: KEY_PLAYPAUSE (0x00a4)
1234567890.234567: event type EV_KEY(0x01): key_up: KEY_PLAYPAUSE (0x00a4)
```

Use the key names (e.g., `KEY_PLAYPAUSE`) in your `key_map` configuration.

## Common Key Names

| Key Name | Typical Button |
|----------|----------------|
| `KEY_PLAYPAUSE` | Play/Pause |
| `KEY_PLAY` | Play |
| `KEY_PAUSE` | Pause |
| `KEY_NEXT` | Next/Skip |
| `KEY_PREVIOUS` | Previous |
| `KEY_UP` | Up arrow |
| `KEY_DOWN` | Down arrow |
| `KEY_POWER` | Power |
| `KEY_0` - `KEY_9` | Number buttons |
| `KEY_VOLUMEUP` | Volume Up |
| `KEY_VOLUMEDOWN` | Volume Down |

## Troubleshooting

**No events when pressing buttons:**
- Check wiring (VCC to 3.3V, not 5V for most receivers)
- Verify kernel overlay is loaded: `dmesg | grep gpio_ir`
- Check permissions: `sudo usermod -aG input pi` and re-login

**Wrong key codes:**
- Your remote may use a different protocol
- Try `ir-keytable -p all` to enable all protocols
- Map the actual key codes your remote sends

**Device not found:**
- Check if the overlay is enabled in `/boot/config.txt`
- Reboot after making changes
- Try different event device numbers
