# Photo Slideshow

A modular fullscreen photo slideshow with a plugin architecture for different hardware setups.

Designed to run on a dedicated device connected to a wall mounted display as a digital photo frame.

---

# Platform

## Target Device Selection

We are looking for a cheap platform which can store a lot of images and display them via HDMI.
It must be strong enough to host a small web server, so that we conveniently can upload images
and control the device via a mobile phone. Furthermore the device should be small and energy efficient.
It must allow to connect sensors for motion and darkness because we want to switch the system
off when no human is around. Ideally we want to adapt brightness depending on ambient light.
Maybe we also want to power on/off the display to save energy.

An ESP32 based system would be too weak, even if we had a storage card connected. So the natural
choice is a Raspberry. We aim to use the Rpi Zero 2WH because it has everything we need:
A multitasking OS, HDMI output and USB ports, GPIOs (to connect a motion sensor) and an SD card
which will be able to store thousands of images. However, there is not much memory (512 MB RAM).

The original idea was to run a chromium browser page in kiosk mode. Hardware access might be 
somewhat problematic, however, and we would need to install the full desktop OS to run the browser.
Tests showed that it could work on an old Raspi 3B (similar processor as 2WH but 1024 MB of memory)
but sometimes the screen was not refreshed properly, most probably due to memory bottlenecks.

So the choice went for a python script which draws directly into the grahical memory using
pygame and a suitable driver (vc4-kms-v3d). If we are carefully setting the limits for the GPU
we will have sufficient memory for the python process - which must not only read images but shall
also handle a Web API and optionally be able to take commands from a classical infrared remote control.

As is often the case with developing systems for tiny target hardware we aim at being able to test the 
application within the development environment (windows/wsl ubuntu). Therefore we added hardware
detection and bypassing for the raspi-specific libraries. Hardware sensors are replaced by stubs.

Because this application is part of the *[aide-examples](https://github.com/aide-examples)* we also 
want to offer easy access to the current document. So we included an "about.html" which allows viewing
markdown files and mermaid diagrams on the web client of the application.


## Task Assignment

We see the following tasks and plan to assign them to the platforms as follows

- sliding the images, controlling HDMI
  - Python script on RPI ZWH in production
  - WSL/Ubuntu in development

- UI to control the slider
  - Python script serves tiny index.html on port 8080 with embedded css and js
  - Web client browser on user's platform (desktop, tablet, mobile) handles the UI

- display information on architecture of the system
  - Python script serves "about.html" and README.md
  - Web client browser on user's platform handles UI, fetches README and renders markdown

- administration of images
  - we install a separate executable on the target hardware ("filebrowser")
    which comes with its own http server (port 8081)
  - during development we use the native explorer of the IDE platform
  - the control UI (port 8080) contains a href to the filebrowser UI (port 8081)

- searching images, taking photos
  - done by the user on a platform of his choice
  - maybe we can provide an AI assistant which identifies and collect suitable material?
  - upload via the filebrowser wen frontend

- preparation of images for efficient display
  - this could be a separate application running on the user's machine before uploading;
    maybe it is another python script which we provide
  - or it could be integrated into the sliding app after uploading if memory restrictions
    and CPU power allow; this solution would avoid the need to have a python environment
    on the user's machine
  - technically the preparation may include the user of tools like image-magick or ffmpeg
  
---

# Requirements

This is a long list of potential features. Those marked with an asterisk are already implented.

- show images
  - in random order (*)
  - in canonical order by name or timestamp
  - show all images or only a subset (*)
  - restrict shown images to those matching a certain monitor orientation (portrait/landscape)
  - recognize current monitor orientation (tilt sensor)
  - show image exactly if it meets the monitor resolution (*)
  - image preparation (may or may not happen within the slide showing process)
    - adapt image size cleverly if it does not meet size or proportions
    - allow some degree of distortion
    - add border in color which harmoizes with image content
    - add image file name in decent small gray font
    - prepare images to be shown in landscape mode even when they have portrait format
    - prepare images to be shown in portrait mode even when they have landscape format
    - offer art style borders/frames and integrate into the image

- energy
  - run on an energy efficient device (*)
  - switch the monitor off when no images shall be shown (*)
  - react on motion detection
  - allow time dependant on/off periods
  - allow daylight dependant on/off periods
  - adapt brightness to ambient light conditions

- control (how)
  - via mouse
  - via keyboard
  - via a REST API (*)
  - via an HTTP UI (*)
  - via an infrared remote control

- control (what)
  - play (*)
  - pause (*)
  - forward/skip (*)
  - backward
  - presentation order
  - select image subdirectory as a subset for presentation (*)
  - presentation speed (*)
  - select type of image change (slide, fade, ..)
  - monitor on/off via CEC (*)
  - monitor on/off via relay (AC power)
  - monitor on/off via shelly plug

- image administration
  - sftp access to image directory (*)
  - batch upload via API
  - interactive upload via a web client (*) - installed "filebrowser" executable

- documentation
  - architecture documentation in README.md (*)
  - being able to show this documentation when the app is running (*)

---

# Architecture Overview (Python Source)

The script is built around three main concerns, each with multiple implementation options (providers):

| Concern | Problem | Providers |
|---------|---------|-----------|
| **Monitor Control** | Turn display on/off to save power | CEC, Shelly, GPIO Relay, Samsung WS |
| **Motion Detection** | Detect presence to auto-wake display | GPIO PIR, MQTT |
| **Remote Control** | Control slideshow playback | HTTP API, IR Remote |

Each concern has an abstract interface. You choose ONE provider per concern (except Remote Control, where you can enable multiple). Switch providers by changing the `provider` field in `config.json`.

```mermaid
classDiagram
    class Slideshow {
        +config
        +monitor: MonitorControlProvider
        +paused: bool
        +display_duration: int
        +run()
        +pause()
        +resume()
        +skip()
        +set_filter(folder)
    }

    class MonitorControlProvider {
        <<abstract>>
        +turn_on() bool
        +turn_off() bool
        +is_on: bool
    }
    class CECMonitorControl
    class ShellyMonitorControl
    class GPIORelayMonitorControl
    class SamsungWSMonitorControl
    class NullMonitorControl

    class MotionSensorProvider {
        <<abstract>>
        +on_motion callback
        +on_idle callback
        +start()
        +stop()
    }
    class GPIOPIRMotionSensor
    class MQTTMotionSensor
    class NullMotionSensor

    class RemoteControlProvider {
        <<abstract>>
        +slideshow: Slideshow
        +start()
        +stop()
        +execute_action(action)
    }
    class HTTPAPIRemoteControl
    class IRRemoteControl

    MonitorControlProvider <|-- CECMonitorControl
    MonitorControlProvider <|-- ShellyMonitorControl
    MonitorControlProvider <|-- GPIORelayMonitorControl
    MonitorControlProvider <|-- SamsungWSMonitorControl
    MonitorControlProvider <|-- NullMonitorControl

    MotionSensorProvider <|-- GPIOPIRMotionSensor
    MotionSensorProvider <|-- MQTTMotionSensor
    MotionSensorProvider <|-- NullMotionSensor

    RemoteControlProvider <|-- HTTPAPIRemoteControl
    RemoteControlProvider <|-- IRRemoteControl

    Slideshow --> MonitorControlProvider : uses
    RemoteControlProvider --> Slideshow : controls
    MotionSensorProvider --> MonitorControlProvider : triggers
```

---

## 1. Monitor Control

**Problem:** We need to turn the display on/off automatically (to save power when nobody is watching) or manually (via remote control).

### Available Providers

#### CEC (Default) - `"provider": "cec"`
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

#### Shelly Smart Plug - `"provider": "shelly"`
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

#### GPIO Relay - `"provider": "gpio_relay"`
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

#### Samsung WebSocket API - `"provider": "samsung_ws"`
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
# Check if TV responds (works when TV is on)
curl http://192.168.0.197:8001/api/v2/

# Install and test with CLI
pip install "samsungtvws[cli]"
samsungtv --host 192.168.0.197 device-info
samsungtv --host 192.168.0.197 power
```

**Finding MAC address:**
```bash
# From your router's DHCP table, or:
arp -a | grep 192.168.0.197
```

#### None - `"provider": "none"`
Disables monitor control entirely.

---

## 2. Motion Detection

**Problem:** We want to automatically turn off the display when nobody is watching, and turn it back on when someone enters the room.

### Available Providers

#### GPIO PIR Sensor - `"provider": "gpio_pir"`
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

#### MQTT - `"provider": "mqtt"`
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

#### None (Default) - `"provider": "none"`
Disables motion detection.

### Future Providers (Not Yet Implemented)
- **Alexa Motion Sensor**: Via Alexa Smart Home API or MQTT bridge
- **Camera-based**: Motion detection via Pi camera

---

## 3. Remote Control Input

**Problem:** We need ways to control the slideshow - pause/resume, skip images, change speed, filter by folder, turn monitor on/off.

Unlike other concerns, you can enable MULTIPLE remote control providers simultaneously.

### Available Actions

| Action | Description |
|--------|-------------|
| `toggle_pause` | Pause or resume slideshow |
| `pause` | Pause slideshow |
| `resume` | Resume slideshow |
| `skip` | Skip to next image |
| `speed_up` | Decrease display duration by 5s |
| `speed_down` | Increase display duration by 5s |
| `set_duration` | Set specific display duration |
| `toggle_monitor` | Turn monitor on/off |
| `monitor_on` | Turn monitor on |
| `monitor_off` | Turn monitor off |
| `filter_clear` | Show all images |
| `set_filter` | Show only images from specific folder |
| `filter_1/2/3` | Folder shortcuts (configurable) |

### HTTP API - `"enabled": true`
REST API accessible from any device on the network.

| Aspect | Details |
|--------|---------|
| **Requirements** | None |
| **Advantages** | Universal, easy automation integration |

```json
"remote_control": {
    "http_api": {
        "enabled": true,
        "port": 8080
    }
}
```

**Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `GET /status` | Current slideshow status |
| `GET /pause` | Pause slideshow |
| `GET /resume` | Resume slideshow |
| `GET /skip` | Skip to next image |
| `GET /duration?seconds=N` | Set display duration (1-300) |
| `GET /filter?folder=NAME` | Filter by folder |
| `GET /filter/clear` | Clear filter |
| `GET /folders` | List available folders |
| `GET /monitor/on` | Turn monitor on |
| `GET /monitor/off` | Turn monitor off |

**Examples:**
```bash
curl http://raspberrypi:8080/status
curl http://raspberrypi:8080/pause
curl "http://raspberrypi:8080/filter?folder=vacation"
```

### IR Remote - `"enabled": true`
Physical IR remote control.

| Aspect | Details |
|--------|---------|
| **Requirements** | IR receiver (VS1838B), any IR remote, `ir-keytable` |
| **Hardware cost** | ~€2 |
| **Advantages** | Works without network, repurpose any old remote |

**Wiring:**
| VS1838B | Raspberry Pi |
|---------|--------------|
| VCC | 3.3V (Pin 1) |
| GND | GND (Pin 6) |
| OUT | GPIO 18 (Pin 12) |

**Setup:**
1. Add to `/boot/config.txt`:
   ```
   dtoverlay=gpio-ir,gpio_pin=18
   ```
2. Reboot
3. Find input device:
   ```bash
   cat /proc/bus/input/devices | grep -A 5 "ir"
   ```
4. Test remote:
   ```bash
   ir-keytable -t -d /dev/input/event0
   ```
5. Configure key mappings in config.json

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

### Future Providers (Not Yet Implemented)
- **Alexa Voice Control**: Via fauxmo (WeMo emulation) or Alexa Smart Home skill
- **Web UI**: Browser-based control panel
- **Bluetooth**: Bluetooth remote support

---

# Installation

## 1. System Dependencies

```bash
sudo apt update
sudo apt install python3-pygame

# Optional: for CEC support
sudo apt install cec-utils

# Optional: for IR remote
sudo apt install ir-keytable
```

## 2. Python Dependencies (Optional)

```bash
# For Samsung WebSocket control
pip install samsungtvws

# For MQTT motion sensor
pip install paho-mqtt
```

## 3. Deploy Files

```bash
# Clone the repository or copy files
mkdir -p /home/pi/slideshow
cp slideshow.py /home/pi/slideshow/
cp config.json /home/pi/slideshow/
cp README.md /home/pi/slideshow/
cp -r static /home/pi/slideshow/
cp -r sample_images /home/pi/slideshow/

# Create image directory for your own photos
mkdir -p /home/pi/img
```

The `static/` directory contains the web UI and is required for HTTP control. The `sample_images/` directory provides demo images so the slideshow works immediately - you can remove it once you add your own photos to `/home/pi/img`.

## 4. Configure

Edit `/home/pi/slideshow/config.json` to match your hardware setup.

## 5. Install Systemd Service

```bash
sudo cp slideshow.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable slideshow
sudo systemctl start slideshow
```

---

# Configuration Reference

## Full Example

```json
{
    "image_dir": "/home/pi/img",
    "display_duration": 35,
    "fade_steps": 5,

    "monitor_control": {
        "provider": "cec",
        "cec": { "device_id": "0" },
        "shelly": { "ip": null },
        "gpio_relay": { "pin": 27, "active_low": false },
        "samsung_ws": { "ip": null, "token_file": "/home/pi/.samsung_token" }
    },

    "motion_sensor": {
        "provider": "gpio_pir",
        "idle_timeout": 300,
        "gpio_pir": { "pin": 17 },
        "mqtt": { "broker": null, "topic": "home/motion/#" }
    },

    "remote_control": {
        "http_api": { "enabled": true, "port": 8080 },
        "ir_remote": {
            "enabled": true,
            "device": "/dev/input/event0",
            "key_map": { ... },
            "folder_shortcuts": { ... }
        }
    }
}
```

## Core Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `image_dir` | Path to images (scanned recursively) | `/home/pi/img` |
| `display_duration` | Seconds per image | 35 |
| `fade_steps` | Transition smoothness (1-30) | 5 |

---

# Image Organization

Organize images in subfolders for filtering:

```
/home/pi/img/
├── vacation/
│   ├── beach_2024/
│   └── mountains/
├── family/
│   ├── birthdays/
│   └── holidays/
└── nature/
```

Use IR remote buttons or API to filter by folder.

---

# Development & Testing

The slideshow automatically detects the runtime platform and configures itself appropriately, allowing development and testing on desktop systems (WSL2, Linux, macOS, Windows) without the Raspberry Pi hardware.

## Platform Detection

| Platform | Video Driver | Display Mode | Hardware Features |
|----------|-------------|--------------|-------------------|
| Raspberry Pi | `kmsdrm` | Fullscreen | GPIO, CEC available |
| WSL2 | `wayland` or `x11` | Windowed | Simulated/disabled |
| Linux Desktop | `wayland` or `x11` | Windowed | Simulated/disabled |
| macOS | `cocoa` | Windowed | Simulated/disabled |
| Windows | `windows` | Windowed | Simulated/disabled |

## Command Line Options

```bash
python3 slideshow.py --help

# Override image directory (useful for testing with local images)
python3 slideshow.py --image-dir ./imgraw

# Set display duration (seconds per image)
python3 slideshow.py --duration 5

# Force windowed or fullscreen mode
python3 slideshow.py --windowed
python3 slideshow.py --fullscreen

# Set window size (WIDTHxHEIGHT)
python3 slideshow.py --size 1920x1080

# Use a specific config file
python3 slideshow.py --config ./my-config.json

# Combined example for WSL2 testing
python3 slideshow.py -i ./imgraw -d 3 -s 1280x720
```

## Keyboard Controls (Windowed Mode)

| Key | Action |
|-----|--------|
| **Q** / **Escape** | Quit |
| **Space** | Toggle pause/play |
| **Right** / **N** | Skip to next image |
| **Up** | Increase duration (+5s) |
| **Down** | Decrease duration (-5s) |
| **F** | Toggle fullscreen |

## Testing on WSL2

WSL2 with WSLg (Windows 11) provides built-in graphical support. The slideshow will automatically detect WSL2 and use the appropriate Wayland or X11 driver.

```bash
# Install pygame if needed
pip install pygame

# Run with local test images
python3 slideshow.py --image-dir ./imgraw --duration 3

# The HTTP API is still available for testing
curl http://localhost:8080/status
curl http://localhost:8080/pause
curl http://localhost:8080/skip
```

Hardware providers (GPIO, CEC) gracefully fall back to no-op implementations when running on non-Raspberry Pi systems, so the slideshow runs without errors. On startup, the server prints its reachable URL (FQDN or IP address) to the console.

## Sample Images

The repository includes sample images in `sample_images/` so the slideshow works immediately after cloning without any configuration. When the configured `image_dir` is empty or doesn't exist, the slideshow automatically falls back to these bundled images.

```
sample_images/
├── landscapes/
│   ├── mountain_lake.jpg
│   └── ocean_sunset.jpg
├── animals/
│   ├── fox.jpg
│   └── deer.jpg
└── LICENSE
```

The web control UI shows the subdirectories (landscapes, animals) as filter options. To use your own photos, configure `image_dir` in `config.json` or use the `--image-dir` command line option.

### Performance Note

The platform detection adds negligible overhead on the Raspberry Pi:
- **Startup:** ~1-2ms one-time cost (reads two small `/proc` files)
- **Memory:** <1KB (two small global variables)
- **Runtime:** The `pygame.event.get()` call processes the event queue, which is recommended practice and has no measurable impact in fullscreen kmsdrm mode

---

# Troubleshooting

## Display Issues

**Black screen:**
```bash
ls /dev/dri/  # Check available GPU devices
# Try card1 in slideshow.py if card0 doesn't work
```

## Permission Issues

```bash
# For IR remote
sudo usermod -aG input pi

# For GPIO
sudo usermod -aG gpio pi
```

## Service Issues

```bash
sudo systemctl status slideshow
journalctl -u slideshow -f
sudo systemctl restart slideshow
```

---

# Extending

To add a new provider:

1. Create a class implementing the appropriate abstract base class:
   - `MonitorControlProvider` for monitor control
   - `MotionSensorProvider` for motion detection
   - `RemoteControlProvider` for remote input

2. Add configuration in `DEFAULT_CONFIG`

3. Update the factory function (`create_monitor_control`, `create_motion_sensor`, or main)

4. Document in this README

---

# License

MIT License
