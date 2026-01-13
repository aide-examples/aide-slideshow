# Motion Detection

**Package:** `motion/`

Detecting presence via GPIO PIR sensor or MQTT.

## Problem

We want to automatically turn off the display when nobody is watching, and turn it back on when someone enters the room.

## Available Providers

| Provider | Config Value | Use Case |
|----------|--------------|----------|
| GPIO PIR | `"gpio_pir"` | Direct PIR sensor on GPIO |
| MQTT | `"mqtt"` | Any MQTT-publishing sensor |
| None | `"none"` | Disable motion detection (default) |

---

## GPIO PIR Sensor

Uses a passive infrared motion sensor connected to GPIO.

| Aspect | Details |
|--------|---------|
| **Requirements** | PIR sensor module (HC-SR501), wiring |
| **Hardware cost** | ~€2 |
| **Advantages** | Simple, cheap, no network/cloud dependency |
| **Limitations** | Requires line of sight, may trigger on pets |

**Wiring:**
| PIR Module | Raspberry Pi |
|------------|--------------|
| VCC | 5V (Pin 2) |
| GND | GND (Pin 6) |
| OUT | GPIO 17 (Pin 11) |

```json
"motion_sensor": {
    "provider": "gpio_pir",
    "idle_timeout": 300,
    "gpio_pir": {
        "pin": 17
    }
}
```

---

## MQTT

Subscribes to motion events from an MQTT broker.

| Aspect | Details |
|--------|---------|
| **Requirements** | MQTT broker, `paho-mqtt` library |
| **Hardware cost** | Depends on sensor |
| **Advantages** | Works with any MQTT-publishing sensor (Zigbee2MQTT, etc.) |
| **Limitations** | Requires MQTT broker setup, additional latency |

```json
"motion_sensor": {
    "provider": "mqtt",
    "idle_timeout": 300,
    "mqtt": {
        "broker": "192.168.1.10",
        "topic": "zigbee2mqtt/motion_sensor"
    }
}
```

```bash
pip install paho-mqtt
```

---

## None (Default)

Disables motion detection.

```json
"motion_sensor": {
    "provider": "none"
}
```

---

## Common Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `idle_timeout` | int | `300` | Seconds of no motion before turning off display |

## Behavior

1. **Motion detected** → Turn on display, resume slideshow
2. **Idle timeout reached** → Turn off display, pause slideshow

The motion sensor calls the configured callbacks:
- `on_motion` - Called when motion is detected
- `on_idle` - Called when idle timeout is reached

---

## Future Providers (Not Yet Implemented)

- **Alexa Motion Sensor**: Via Alexa Smart Home API or MQTT bridge
- **Camera-based**: Motion detection via Pi camera

---

## Adding a New Provider

See [Extending](../../development/extending.md) for how to add a new motion sensor provider.
