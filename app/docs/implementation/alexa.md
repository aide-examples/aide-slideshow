# Alexa Voice Control

**Module:** `remote/alexa.py`

Controlling the slideshow with Amazon Alexa.

## How It Works

The slideshow uses **Fauxmo** to emulate a Belkin WeMo smart plug. Alexa discovers it as a native device - no skill, no cloud account, no Alexa app setup needed. Everything runs locally on your network.

## Requirements

| Component | Details |
|-----------|---------|
| **Software** | `fauxmo` library |
| **Network** | Alexa device on same network/VLAN as Pi |
| **Ports** | UDP 1900 (SSDP discovery), TCP 12340 (device control) |

```bash
pip install fauxmo
```

## Configuration

```json
"remote_control": {
    "alexa": {
        "enabled": true,
        "device_name": "Slideshow",
        "port": 12340
    }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `false` | Enable/disable Alexa control |
| `device_name` | `"Slideshow"` | Name Alexa uses (e.g., "turn on *Slideshow*") |
| `port` | `12340` | TCP port for device control |

## Setup

1. Install fauxmo on the Raspberry Pi:
   ```bash
   pip install fauxmo
   ```

2. Enable in `config.json`:
   ```json
   "remote_control": {
       "alexa": {
           "enabled": true,
           "device_name": "Slideshow",
           "port": 12340
       }
   }
   ```

3. Restart the slideshow service:
   ```bash
   sudo systemctl restart slideshow
   ```

4. Say **"Alexa, discover devices"** - Alexa will find "Slideshow"

5. Use voice commands:
   - **"Alexa, turn on Slideshow"** → Resume playback + Monitor on
   - **"Alexa, turn off Slideshow"** → Pause + Monitor off

## Startup Log

When enabled, you'll see:
```
Alexa voice control enabled: 'Slideshow' on port 12340
  → Say 'Alexa, discover devices' to find it
  → Then use 'Alexa, turn on/off Slideshow'
  Alexa: Using IP address 192.168.0.106
  Alexa: UDP socket created for SSDP
  Alexa: SSDP listener started (UDP multicast 239.255.255.250:1900)
  Alexa: TCP server started on 192.168.0.106:12340
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Alexa doesn't find device | Check if Pi and Alexa are on same network/VLAN |
| "Device not responding" | Verify port 12340 is not blocked by firewall |
| fauxmo import error | Install with `pip install fauxmo` |

**Test SSDP discovery manually:**
```bash
# On the Pi - check if ports are listening
netstat -tulpn | grep -E "1900|12340"

# From another machine - test device description
curl http://192.168.0.106:12340/setup.xml
```

## Limitations

- **On/Off only** - WeMo protocol limitation, no dimming or custom commands
- **Local network only** - No remote/cloud access
- **Not supported in WSL2** - UDP multicast issues with Windows networking

## Future Improvements

- **Hue Emulation**: Philips Hue bridge emulation for brightness control via Alexa ("Alexa, set Slideshow to 50%"). Would enable software-based image brightness adjustment. Requires port 80 (root or setcap). Could replace fauxmo.
- **Custom Alexa Skill**: For folder selection and more commands
