# Monitor Control

**Package:** `monitor/`

Controlling display power via CEC, Shelly, GPIO, or Samsung API.

## Problem

We need to turn the display on/off automatically (to save power when nobody is watching) or manually (via remote control).

## Available Providers

| Provider | Config Value | Use Case |
|----------|--------------|----------|
| CEC | `"cec"` | Most TVs via HDMI (default) |
| Shelly | `"shelly"` | Smart plug with HTTP API |
| GPIO Relay | `"gpio_relay"` | Direct relay control |
| Samsung WS | `"samsung_ws"` | Samsung Smart TVs |
| None | `"none"` | Disable monitor control |

---

## CEC (HDMI-CEC)

Uses HDMI-CEC protocol to control the TV.

| Aspect | Details |
|--------|---------|
| **Requirements** | `cec-utils` package, TV with CEC support |
| **Hardware cost** | None (uses HDMI cable) |
| **Advantages** | No extra hardware, proper standby mode |
| **Limitations** | Some TVs have buggy CEC, may not work with HDMI switches |
| **Samsung name** | "Anynet+" - enable in Settings → General → External Device Manager |

```json
"monitor_control": {
    "provider": "cec",
    "cec": {
        "device_id": "0"
    }
}
```

**Test CEC:**
```bash
sudo apt install cec-utils
echo "scan" | cec-client -s -d 1      # Scan for devices
echo "standby 0" | cec-client -s -d 1  # Turn TV off
echo "on 0" | cec-client -s -d 1       # Turn TV on
```

---

## Shelly Smart Plug

Uses a Shelly smart plug to cut power to the display.

| Aspect | Details |
|--------|---------|
| **Requirements** | Shelly Plug/Shelly 1, same network as Pi |
| **Hardware cost** | ~€15-25 |
| **Advantages** | Works with any display, measures power consumption |
| **Limitations** | Hard power cut (not ideal for all displays) |

```json
"monitor_control": {
    "provider": "shelly",
    "shelly": {
        "ip": "192.168.1.100"
    }
}
```

---

## GPIO Relay

Uses a relay module connected to GPIO to switch power.

| Aspect | Details |
|--------|---------|
| **Requirements** | Relay module, wiring |
| **Hardware cost** | ~€2 |
| **Advantages** | Cheapest solution, no network dependency |
| **Limitations** | Requires wiring, hard power cut |

```json
"monitor_control": {
    "provider": "gpio_relay",
    "gpio_relay": {
        "pin": 27,
        "active_low": false
    }
}
```

---

## Samsung WebSocket API

Native Samsung Smart TV control via WebSocket API. **Recommended for Samsung The Frame**.

| Aspect | Details |
|--------|---------|
| **Requirements** | Samsung Smart TV (2016+), `samsungtvws` library |
| **Hardware cost** | None |
| **Advantages** | Most features, proper standby, can send any remote key |
| **Limitations** | Samsung TVs only, requires initial pairing on TV |

**Setup for Samsung The Frame:**
1. On TV: Settings → General → Network → Expert Settings → Power On with Mobile → **On**
2. Find your TV's IP address: Settings → General → Network → Network Status
3. Find TV's MAC address (for Wake-on-LAN): Same screen, or check your router
4. Install library on Pi: `pip install samsungtvws`
5. First connection will show a pairing prompt on TV - **approve it**
6. Token is saved automatically for future connections

```json
"monitor_control": {
    "provider": "samsung_ws",
    "samsung_ws": {
        "ip": "192.168.0.197",
        "port": 8002,
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "token_file": "/home/pi/.samsung_token",
        "name": "RaspberryPiSlideshow",
        "timeout": 5
    }
}
```

| Option | Description |
|--------|-------------|
| `ip` | TV's IP address (required) |
| `port` | 8002 for newer TVs (SSL), 8001 for older |
| `mac_address` | For Wake-on-LAN (optional but recommended) |
| `token_file` | Where to store auth token |
| `name` | Name shown on TV when pairing |
| `timeout` | Connection timeout in seconds |

**Test connection:**
```bash
curl http://192.168.0.197:8001/api/v2/
pip install "samsungtvws[cli]"
samsungtv --host 192.168.0.197 device-info
```

---

## None

Disables monitor control entirely.

```json
"monitor_control": {
    "provider": "none"
}
```

---

## Adding a New Provider

See [Extending](../../development/extending.md) for how to add a new monitor control provider.
