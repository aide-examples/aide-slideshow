"""
Raspberry Pi Photo Slideshow

A modular slideshow application with plugin architecture for:
- Monitor power control (CEC, Shelly, GPIO relay, Samsung TV API)
- Motion detection (GPIO PIR, MQTT, Alexa)
- Remote control input (IR remote, HTTP API)

Each concern has an abstract interface that can be implemented by different
backends depending on your hardware setup.
"""

import os
import sys
import json
import pygame
import time
import random
import signal
import threading
import selectors
from abc import ABC, abstractmethod
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import subprocess

# Force immediate log output for systemd
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)


# =============================================================================
# PLATFORM DETECTION
# =============================================================================

def detect_platform():
    """
    Detect the runtime platform to configure appropriate drivers.

    Returns:
        str: One of 'raspi', 'wsl2', 'linux_desktop', 'macos', 'windows'
    """
    import platform

    system = platform.system().lower()

    if system == 'darwin':
        return 'macos'
    elif system == 'windows':
        return 'windows'
    elif system == 'linux':
        # Check for WSL2
        try:
            with open('/proc/version', 'r') as f:
                version_info = f.read().lower()
                if 'microsoft' in version_info or 'wsl' in version_info:
                    return 'wsl2'
        except:
            pass

        # Check for Raspberry Pi
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().lower()
                if 'raspberry pi' in model:
                    return 'raspi'
        except:
            pass

        # Check if we have kmsdrm capability (headless server or direct console)
        if os.path.exists('/dev/dri/card0'):
            # Could be raspi-like or a desktop with DRM
            # Check if we're running in a graphical session
            if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
                return 'linux_desktop'
            else:
                # Running on console, might work with kmsdrm
                return 'raspi'

        return 'linux_desktop'

    return 'unknown'


def configure_video_driver(platform_type):
    """
    Configure SDL video driver based on detected platform.

    Args:
        platform_type: Result from detect_platform()

    Returns:
        dict: Configuration options for display initialization
    """
    config = {
        'fullscreen': True,
        'windowed_size': (1280, 720),  # Fallback for windowed mode
    }

    if platform_type == 'raspi':
        # Raspberry Pi: use kmsdrm for direct framebuffer access
        os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
        os.environ["SDL_NOMOUSE"] = "1"
        os.environ["SDL_DRM_DEVICE"] = "/dev/dri/card0"
        config['driver'] = 'kmsdrm'
        print("Platform: Raspberry Pi - using kmsdrm driver")

    elif platform_type == 'wsl2':
        # WSL2: use x11 (requires X server like VcXsrv or WSLg)
        # WSLg provides built-in Wayland/X11 support in Windows 11
        if os.environ.get('WAYLAND_DISPLAY'):
            os.environ["SDL_VIDEODRIVER"] = "wayland"
            config['driver'] = 'wayland'
            print("Platform: WSL2 - using Wayland driver (WSLg)")
        else:
            os.environ["SDL_VIDEODRIVER"] = "x11"
            config['driver'] = 'x11'
            print("Platform: WSL2 - using X11 driver")
        # In WSL2, we might want windowed mode for easier testing
        config['fullscreen'] = False

    elif platform_type == 'linux_desktop':
        # Linux desktop: prefer Wayland, fallback to X11
        if os.environ.get('WAYLAND_DISPLAY'):
            os.environ["SDL_VIDEODRIVER"] = "wayland"
            config['driver'] = 'wayland'
            print("Platform: Linux desktop - using Wayland driver")
        else:
            os.environ["SDL_VIDEODRIVER"] = "x11"
            config['driver'] = 'x11'
            print("Platform: Linux desktop - using X11 driver")
        config['fullscreen'] = False

    elif platform_type == 'macos':
        # macOS: use cocoa (default)
        os.environ["SDL_VIDEODRIVER"] = "cocoa"
        config['driver'] = 'cocoa'
        config['fullscreen'] = False
        print("Platform: macOS - using Cocoa driver")

    elif platform_type == 'windows':
        # Windows: use windows driver (default)
        os.environ["SDL_VIDEODRIVER"] = "windows"
        config['driver'] = 'windows'
        config['fullscreen'] = False
        print("Platform: Windows - using Windows driver")

    else:
        # Unknown: let SDL choose
        print(f"Platform: Unknown ({platform_type}) - using SDL default driver")
        config['fullscreen'] = False

    return config


# Detect platform and configure video driver BEFORE pygame import side effects
PLATFORM = detect_platform()
VIDEO_CONFIG = configure_video_driver(PLATFORM)


# =============================================================================
# CONFIGURATION
# =============================================================================

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
        }
    }
}


def load_config(config_path="/home/pi/slideshow/config.json"):
    """Load configuration from JSON file, merging with defaults"""
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # Deep copy

    def deep_merge(base, override):
        """Recursively merge override into base"""
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


# =============================================================================
# MONITOR CONTROL - Abstract Interface and Implementations
# =============================================================================

class MonitorControlProvider(ABC):
    """
    Abstract interface for monitor power control.

    Problem: We need to turn the display on/off to save power when no one is watching.

    Solutions:
    - CEC: HDMI-CEC protocol, works with most TVs, no extra hardware
    - Shelly: Smart plug, cuts power completely, works with any display
    - GPIO Relay: Direct relay control, cheapest hardware solution
    - Samsung WebSocket: Samsung Smart TV API, most features but Samsung-only
    """

    @abstractmethod
    def turn_on(self) -> bool:
        """Turn monitor on. Returns True on success."""
        pass

    @abstractmethod
    def turn_off(self) -> bool:
        """Turn monitor off. Returns True on success."""
        pass

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """Current monitor state (may be assumed, not always queryable)."""
        pass


class NullMonitorControl(MonitorControlProvider):
    """No-op implementation when monitor control is disabled."""

    def __init__(self):
        self._is_on = True

    def turn_on(self) -> bool:
        self._is_on = True
        return True

    def turn_off(self) -> bool:
        self._is_on = False
        return True

    @property
    def is_on(self) -> bool:
        return self._is_on


class CECMonitorControl(MonitorControlProvider):
    """
    HDMI-CEC based monitor control.

    Requirements:
    - cec-utils package: sudo apt install cec-utils
    - TV with CEC support (Samsung calls it "Anynet+")
    - HDMI cable that supports CEC (most do)

    Limitations:
    - Some TVs have buggy CEC implementations
    - May not work reliably with all HDMI switches
    """

    def __init__(self, config):
        self.device_id = config.get("device_id", "0")
        self._is_on = True

    def turn_on(self) -> bool:
        try:
            subprocess.run(
                ["cec-client", "-s", "-d", "1"],
                input=f"on {self.device_id}".encode(),
                timeout=5,
                capture_output=True
            )
            self._is_on = True
            print("CEC: Monitor turned ON")
            return True
        except Exception as e:
            print(f"CEC error: {e}")
            return False

    def turn_off(self) -> bool:
        try:
            subprocess.run(
                ["cec-client", "-s", "-d", "1"],
                input=f"standby {self.device_id}".encode(),
                timeout=5,
                capture_output=True
            )
            self._is_on = False
            print("CEC: Monitor turned OFF")
            return True
        except Exception as e:
            print(f"CEC error: {e}")
            return False

    @property
    def is_on(self) -> bool:
        return self._is_on


class ShellyMonitorControl(MonitorControlProvider):
    """
    Shelly smart plug based monitor control.

    Requirements:
    - Shelly Plug or Shelly 1 relay
    - Shelly device on same network

    Advantages:
    - Works with any display (cuts power completely)
    - Can measure power consumption
    - Works even if TV CEC is broken

    Limitations:
    - Requires additional hardware (~€15-25)
    - Hard power cut may not be ideal for all displays
    """

    def __init__(self, config):
        self.ip = config.get("ip")
        self._is_on = True

        if not self.ip:
            print("WARNING: Shelly IP not configured")

    def _request(self, action):
        """Send request to Shelly device"""
        import urllib.request
        try:
            url = f"http://{self.ip}/relay/0?turn={action}"
            urllib.request.urlopen(url, timeout=5)
            return True
        except Exception as e:
            print(f"Shelly error: {e}")
            return False

    def turn_on(self) -> bool:
        if not self.ip:
            return False
        if self._request("on"):
            self._is_on = True
            print("Shelly: Monitor turned ON")
            return True
        return False

    def turn_off(self) -> bool:
        if not self.ip:
            return False
        if self._request("off"):
            self._is_on = False
            print("Shelly: Monitor turned OFF")
            return True
        return False

    @property
    def is_on(self) -> bool:
        return self._is_on


class GPIORelayMonitorControl(MonitorControlProvider):
    """
    GPIO relay based monitor control.

    Requirements:
    - Relay module connected to GPIO pin
    - RPi.GPIO or gpiozero library

    Advantages:
    - Cheapest solution (~€2 for relay module)
    - No network dependency
    - Works with any display

    Limitations:
    - Requires wiring
    - Hard power cut
    """

    def __init__(self, config):
        self.pin = config.get("pin", 27)
        self.active_low = config.get("active_low", False)
        self._is_on = True
        self._gpio_available = False

        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            GPIO.output(self.pin, GPIO.LOW if self.active_low else GPIO.HIGH)
            self._gpio_available = True
            print(f"GPIO Relay initialized on pin {self.pin}")
        except ImportError:
            print("WARNING: RPi.GPIO not available, GPIO relay disabled")
        except Exception as e:
            print(f"GPIO setup error: {e}")

    def turn_on(self) -> bool:
        if not self._gpio_available:
            return False
        try:
            self.GPIO.output(self.pin, self.GPIO.LOW if self.active_low else self.GPIO.HIGH)
            self._is_on = True
            print("GPIO Relay: Monitor turned ON")
            return True
        except Exception as e:
            print(f"GPIO error: {e}")
            return False

    def turn_off(self) -> bool:
        if not self._gpio_available:
            return False
        try:
            self.GPIO.output(self.pin, self.GPIO.HIGH if self.active_low else self.GPIO.LOW)
            self._is_on = False
            print("GPIO Relay: Monitor turned OFF")
            return True
        except Exception as e:
            print(f"GPIO error: {e}")
            return False

    @property
    def is_on(self) -> bool:
        return self._is_on


class SamsungWSMonitorControl(MonitorControlProvider):
    """
    Samsung Smart TV WebSocket API control.

    Requirements:
    - Samsung Smart TV (2016 or newer, including The Frame)
    - samsungtvws library: pip install samsungtvws
    - TV and Pi on same network
    - First connection requires approval on TV screen

    Advantages:
    - Native TV control, most reliable for Samsung
    - Can send any remote key command
    - Proper standby (not hard power cut)
    - Wake-on-LAN support for turning on from standby
    - For The Frame: Can also control Art Mode

    Limitations:
    - Samsung TVs only
    - Requires pairing on first use (approve on TV)
    - TV must have network standby enabled for wake-on-LAN

    Setup for Samsung The Frame:
    1. Enable network standby: Settings → General → Network → Expert Settings → Power On with Mobile
    2. First run will prompt for approval on TV screen
    3. Token is saved to token_file for future connections
    """

    def __init__(self, config):
        self.ip = config.get("ip")
        self.token_file = config.get("token_file", "/home/pi/.samsung_token")
        self.mac_address = config.get("mac_address")  # For Wake-on-LAN
        self.port = config.get("port", 8002)  # 8001 for older TVs, 8002 for newer (SSL)
        self.timeout = config.get("timeout", 5)
        self.name = config.get("name", "RaspberryPiSlideshow")
        self._is_on = True
        self._tv = None
        self._tv_class = None

        if not self.ip:
            print("WARNING: Samsung TV IP not configured")
            return

        # Import the library
        try:
            from samsungtvws import SamsungTVWS
            self._tv_class = SamsungTVWS
            print(f"Samsung WS: Library loaded, TV at {self.ip}:{self.port}")

            # Test connection and get initial state
            if self._check_tv_available():
                print("Samsung WS: TV is responding")
                self._is_on = True
            else:
                print("Samsung WS: TV not responding (may be in standby)")
                self._is_on = False

        except ImportError:
            print("WARNING: samsungtvws not installed. Run: pip install samsungtvws")
        except Exception as e:
            print(f"Samsung WS init error: {e}")

    def _get_connection(self):
        """Create a new TV connection (connections should be short-lived)."""
        if not self._tv_class:
            return None
        try:
            return self._tv_class(
                host=self.ip,
                port=self.port,
                token_file=self.token_file,
                timeout=self.timeout,
                name=self.name
            )
        except Exception as e:
            print(f"Samsung WS connection error: {e}")
            return None

    def _check_tv_available(self) -> bool:
        """Check if TV is reachable via REST API (works even without WebSocket)."""
        import urllib.request
        import urllib.error
        try:
            # Samsung TVs expose device info via REST
            url = f"http://{self.ip}:8001/api/v2/"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def _send_key(self, key):
        """Send a key command to the TV."""
        tv = self._get_connection()
        if not tv:
            return False
        try:
            tv.send_key(key)
            return True
        except Exception as e:
            print(f"Samsung WS send_key error: {e}")
            return False

    def _wake_on_lan(self) -> bool:
        """Wake TV via Wake-on-LAN if MAC address is configured."""
        if not self.mac_address:
            print("Samsung WS: MAC address not configured for Wake-on-LAN")
            return False

        try:
            # Build magic packet
            mac_bytes = bytes.fromhex(self.mac_address.replace(':', '').replace('-', ''))
            magic_packet = b'\xff' * 6 + mac_bytes * 16

            # Send via UDP broadcast
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, ('255.255.255.255', 9))
            sock.close()

            print("Samsung WS: Wake-on-LAN packet sent")
            return True
        except Exception as e:
            print(f"Samsung WS Wake-on-LAN error: {e}")
            return False

    def turn_on(self) -> bool:
        """Turn TV on."""
        if self._is_on and self._check_tv_available():
            print("Samsung WS: TV already on")
            return True

        # Try Wake-on-LAN first (works when TV is in standby)
        if self.mac_address:
            self._wake_on_lan()
            # Wait a moment for TV to wake
            time.sleep(3)

        # Check if TV is now available
        if self._check_tv_available():
            self._is_on = True
            print("Samsung WS: Monitor turned ON")
            return True

        # If WoL didn't work or no MAC, try sending KEY_POWER
        # (only works if TV is in network standby mode)
        if self._send_key("KEY_POWER"):
            self._is_on = True
            print("Samsung WS: Monitor turned ON via KEY_POWER")
            return True

        print("Samsung WS: Failed to turn on TV")
        return False

    def turn_off(self) -> bool:
        """Turn TV off (standby)."""
        if not self._is_on and not self._check_tv_available():
            print("Samsung WS: TV already off")
            return True

        # Send power key to put TV in standby
        if self._send_key("KEY_POWER"):
            self._is_on = False
            print("Samsung WS: Monitor turned OFF")
            return True

        # Alternative: try KEY_POWEROFF specifically
        if self._send_key("KEY_POWEROFF"):
            self._is_on = False
            print("Samsung WS: Monitor turned OFF via KEY_POWEROFF")
            return True

        print("Samsung WS: Failed to turn off TV")
        return False

    def send_key(self, key):
        """
        Send any remote key to the TV.

        Common keys:
        - KEY_POWER, KEY_POWEROFF, KEY_POWERON
        - KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER
        - KEY_RETURN, KEY_HOME, KEY_MENU
        - KEY_VOLUP, KEY_VOLDOWN, KEY_MUTE
        - KEY_CHUP, KEY_CHDOWN
        - KEY_SOURCE, KEY_HDMI (cycle inputs)
        - KEY_0 through KEY_9
        - KEY_PLAY, KEY_PAUSE, KEY_STOP, KEY_FF, KEY_REWIND
        """
        return self._send_key(key)

    @property
    def is_on(self) -> bool:
        # Optionally refresh state
        # self._is_on = self._check_tv_available()
        return self._is_on

    def get_device_info(self) -> dict:
        """Get TV device information via REST API."""
        import urllib.request
        import json
        try:
            url = f"http://{self.ip}:8001/api/v2/"
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Samsung WS device info error: {e}")
            return {}


def create_monitor_control(config) -> MonitorControlProvider:
    """Factory function to create the configured monitor control provider."""
    provider = config.get("provider", "none")

    if provider == "cec":
        return CECMonitorControl(config.get("cec", {}))
    elif provider == "shelly":
        return ShellyMonitorControl(config.get("shelly", {}))
    elif provider == "gpio_relay":
        return GPIORelayMonitorControl(config.get("gpio_relay", {}))
    elif provider == "samsung_ws":
        return SamsungWSMonitorControl(config.get("samsung_ws", {}))
    else:
        return NullMonitorControl()


# =============================================================================
# MOTION SENSOR - Abstract Interface and Implementations
# =============================================================================

class MotionSensorProvider(ABC):
    """
    Abstract interface for motion detection.

    Problem: We want to turn off the display when no one is watching to save power.

    Solutions:
    - GPIO PIR: Simple passive infrared sensor, cheap and reliable
    - MQTT: Subscribe to motion events from external sensors (Zigbee, Alexa, etc.)
    - (Future) Alexa: Use Alexa motion sensor via Smart Home API
    """

    def __init__(self, on_motion_callback, on_idle_callback):
        """
        Initialize with callbacks.

        Args:
            on_motion_callback: Called when motion is detected
            on_idle_callback: Called after idle timeout with no motion
        """
        self.on_motion = on_motion_callback
        self.on_idle = on_idle_callback

    @abstractmethod
    def start(self):
        """Start monitoring for motion."""
        pass

    @abstractmethod
    def stop(self):
        """Stop monitoring."""
        pass


class NullMotionSensor(MotionSensorProvider):
    """No-op implementation when motion sensing is disabled."""

    def start(self):
        print("Motion sensor: disabled")

    def stop(self):
        pass


class GPIOPIRMotionSensor(MotionSensorProvider):
    """
    GPIO PIR (Passive Infrared) motion sensor.

    Requirements:
    - PIR sensor module (HC-SR501 or similar, ~€2)
    - Connected to GPIO pin

    Wiring:
    - VCC -> 5V (Pin 2)
    - GND -> GND (Pin 6)
    - OUT -> GPIO pin (e.g., Pin 11 = GPIO 17)

    Advantages:
    - Very cheap and simple
    - No network/cloud dependency
    - Low latency

    Limitations:
    - Requires line of sight
    - Can be triggered by pets
    """

    def __init__(self, config, on_motion_callback, on_idle_callback):
        super().__init__(on_motion_callback, on_idle_callback)
        self.pin = config.get("pin", 17)
        self.idle_timeout = config.get("idle_timeout", 300)
        self._running = False
        self._thread = None
        self._last_motion = time.time()
        self._gpio_available = False
        self._was_idle = False

    def start(self):
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.IN)
            self._gpio_available = True
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            print(f"PIR motion sensor started on GPIO {self.pin}")
        except ImportError:
            print("WARNING: RPi.GPIO not available, PIR sensor disabled")
        except Exception as e:
            print(f"PIR setup error: {e}")

    def stop(self):
        self._running = False

    def _monitor_loop(self):
        while self._running:
            try:
                if self.GPIO.input(self.pin):
                    self._last_motion = time.time()
                    if self._was_idle:
                        self._was_idle = False
                        print("PIR: Motion detected")
                        self.on_motion()
                else:
                    idle_time = time.time() - self._last_motion
                    if idle_time > self.idle_timeout and not self._was_idle:
                        self._was_idle = True
                        print(f"PIR: No motion for {self.idle_timeout}s")
                        self.on_idle()
            except Exception as e:
                print(f"PIR error: {e}")

            time.sleep(0.5)


class MQTTMotionSensor(MotionSensorProvider):
    """
    MQTT-based motion sensor.

    Requirements:
    - MQTT broker (e.g., Mosquitto)
    - paho-mqtt library: pip install paho-mqtt
    - Motion sensor publishing to MQTT (Zigbee2MQTT, Alexa via bridge, etc.)

    Advantages:
    - Works with any sensor that can publish to MQTT
    - Can aggregate multiple sensors
    - Works with Zigbee sensors via Zigbee2MQTT

    Limitations:
    - Requires MQTT broker setup
    - Additional latency

    Note: This is a placeholder - full implementation requires paho-mqtt.
    """

    def __init__(self, config, on_motion_callback, on_idle_callback):
        super().__init__(on_motion_callback, on_idle_callback)
        self.broker = config.get("broker")
        self.topic = config.get("topic", "home/motion/#")
        self.idle_timeout = config.get("idle_timeout", 300)
        self._client = None

    def start(self):
        if not self.broker:
            print("WARNING: MQTT broker not configured")
            return

        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client()
            self._client.on_message = self._on_message
            self._client.connect(self.broker)
            self._client.subscribe(self.topic)
            self._client.loop_start()
            print(f"MQTT motion sensor subscribed to {self.topic}")
        except ImportError:
            print("WARNING: paho-mqtt not installed. Run: pip install paho-mqtt")
        except Exception as e:
            print(f"MQTT error: {e}")

    def stop(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def _on_message(self, client, userdata, message):
        try:
            payload = message.payload.decode()
            # Handle common motion sensor payload formats
            if payload in ("ON", "on", "1", "true", "motion"):
                print(f"MQTT: Motion detected on {message.topic}")
                self.on_motion()
        except Exception as e:
            print(f"MQTT message error: {e}")


def create_motion_sensor(config, on_motion, on_idle) -> MotionSensorProvider:
    """Factory function to create the configured motion sensor provider."""
    provider = config.get("provider", "none")
    idle_timeout = config.get("idle_timeout", 300)

    if provider == "gpio_pir":
        sensor_config = config.get("gpio_pir", {})
        sensor_config["idle_timeout"] = idle_timeout
        return GPIOPIRMotionSensor(sensor_config, on_motion, on_idle)
    elif provider == "mqtt":
        sensor_config = config.get("mqtt", {})
        sensor_config["idle_timeout"] = idle_timeout
        return MQTTMotionSensor(sensor_config, on_motion, on_idle)
    else:
        return NullMotionSensor(on_motion, on_idle)


# =============================================================================
# REMOTE CONTROL INPUT - Abstract Interface and Implementations
# =============================================================================

class RemoteControlProvider(ABC):
    """
    Abstract interface for remote control input.

    Problem: We need ways to control the slideshow (pause, skip, speed, filters).

    Solutions:
    - HTTP API: Universal, works from any device with a browser
    - IR Remote: Physical remote, works without network
    - (Future) Alexa: Voice control via Smart Home skill
    """

    def __init__(self, slideshow):
        self.slideshow = slideshow

    @abstractmethod
    def start(self):
        """Start listening for control input."""
        pass

    @abstractmethod
    def stop(self):
        """Stop listening."""
        pass

    def execute_action(self, action, params=None):
        """Execute a slideshow control action."""
        params = params or {}

        if action == "toggle_pause":
            if self.slideshow.paused:
                self.slideshow.resume()
            else:
                self.slideshow.pause()

        elif action == "pause":
            self.slideshow.pause()

        elif action == "resume":
            self.slideshow.resume()

        elif action == "skip":
            self.slideshow.skip()

        elif action == "speed_up":
            new_duration = max(5, self.slideshow.display_duration - 5)
            self.slideshow.set_duration(new_duration)

        elif action == "speed_down":
            new_duration = min(120, self.slideshow.display_duration + 5)
            self.slideshow.set_duration(new_duration)

        elif action == "set_duration":
            seconds = params.get("seconds", 35)
            self.slideshow.set_duration(seconds)

        elif action == "toggle_monitor":
            if self.slideshow.monitor.is_on:
                self.slideshow.monitor.turn_off()
            else:
                self.slideshow.monitor.turn_on()

        elif action == "monitor_on":
            self.slideshow.monitor.turn_on()

        elif action == "monitor_off":
            self.slideshow.monitor.turn_off()

        elif action == "filter_clear":
            self.slideshow.clear_filter()

        elif action == "set_filter":
            folder = params.get("folder")
            if folder:
                self.slideshow.set_filter(folder)

        elif action.startswith("filter_"):
            # Handle numbered filter shortcuts
            folder = params.get(action)
            if folder:
                self.slideshow.set_filter(folder)

        else:
            print(f"Unknown action: {action}")


# =============================================================================
# UPDATE MANAGER - Remote update system
# =============================================================================

# Path to static files directory (relative to script location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # app/
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                 # parent of app/
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")
VERSION_FILE = os.path.join(SCRIPT_DIR, "VERSION")
UPDATE_STATE_DIR = os.path.join(PROJECT_DIR, ".update")


def get_local_version():
    """Read the local version from VERSION file."""
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


def compare_versions(local, remote):
    """
    Compare two version strings.

    Returns:
        1 if remote > local (update available)
        0 if remote == local (up to date)
        -1 if remote < local (local is ahead, development mode)
    """
    def parse_version(v):
        # Handle versions like "1.2.3" or "1.2.3-dev"
        base = v.split('-')[0]
        parts = base.split('.')
        return tuple(int(p) for p in parts if p.isdigit())

    try:
        local_parts = parse_version(local)
        remote_parts = parse_version(remote)

        if remote_parts > local_parts:
            return 1
        elif remote_parts < local_parts:
            return -1
        else:
            return 0
    except (ValueError, AttributeError):
        return 0  # Can't compare, assume equal


class UpdateManager:
    """
    Manages remote updates for the slideshow application.

    Features:
    - Version checking against GitHub
    - Manual download and staging
    - Automatic rollback on failure (max 2 attempts)
    - Detection when local version is ahead of remote
    """

    DEFAULT_CONFIG = {
        "enabled": True,
        "source": {
            "repo": "aide-examples/aide-slideshow",
            "branch": "main"
        },
        "auto_check_hours": 24,
        "auto_check": True,
        "auto_download": False,
        "auto_apply": False
    }

    def __init__(self, config=None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.state_dir = UPDATE_STATE_DIR
        self.state_file = os.path.join(self.state_dir, "state.json")
        self._ensure_state_dir()
        self._state = self._load_state()

    def _ensure_state_dir(self):
        """Create state directory if it doesn't exist."""
        if not os.path.exists(self.state_dir):
            try:
                os.makedirs(self.state_dir, exist_ok=True)
            except OSError:
                pass  # May fail on read-only filesystem, that's ok

    def _load_state(self):
        """Load update state from file."""
        default_state = {
            "current_version": get_local_version(),
            "available_version": None,
            "update_state": "idle",  # idle, checking, downloading, staged, verifying
            "pending_verification": False,
            "consecutive_failures": 0,
            "updates_disabled": False,
            "backup_version": None,
            "last_check": None,
            "last_update": None
        }

        try:
            with open(self.state_file, 'r') as f:
                saved_state = json.load(f)
                # Merge with defaults to handle new fields
                return {**default_state, **saved_state}
        except (FileNotFoundError, json.JSONDecodeError):
            return default_state

    def _save_state(self):
        """Save update state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self._state, f, indent=2)
        except OSError:
            pass  # May fail on read-only filesystem

    def get_status(self):
        """Get current update status for API response."""
        local_version = get_local_version()
        available = self._state.get("available_version")

        # Determine update availability
        update_available = False
        version_comparison = "unknown"
        if available:
            cmp = compare_versions(local_version, available)
            if cmp == 1:
                update_available = True
                version_comparison = "update_available"
            elif cmp == -1:
                version_comparison = "local_ahead"
            else:
                version_comparison = "up_to_date"

        return {
            "current_version": local_version,
            "available_version": available,
            "update_available": update_available,
            "version_comparison": version_comparison,
            "update_state": self._state.get("update_state", "idle"),
            "pending_verification": self._state.get("pending_verification", False),
            "consecutive_failures": self._state.get("consecutive_failures", 0),
            "updates_disabled": self._state.get("updates_disabled", False),
            "updates_enabled": self.config.get("enabled", True),
            "backup_version": self._state.get("backup_version"),
            "can_rollback": self._state.get("backup_version") is not None,
            "last_check": self._state.get("last_check"),
            "last_update": self._state.get("last_update"),
            "source": self.config.get("source", {})
        }

    def check_for_updates(self):
        """
        Check GitHub for a newer version.

        Returns:
            dict with check results including available_version and comparison
        """
        import urllib.request
        import datetime

        if not self.config.get("enabled", True):
            return {"success": False, "error": "Updates are disabled in config"}

        if self._state.get("updates_disabled", False):
            return {"success": False, "error": "Updates disabled due to repeated failures"}

        source = self.config.get("source", {})
        repo = source.get("repo", "aide-examples/aide-slideshow")
        branch = source.get("branch", "main")

        # Build URL for raw VERSION file
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/app/VERSION"

        self._state["update_state"] = "checking"
        self._save_state()

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AIDE-Slideshow-Updater"})
            with urllib.request.urlopen(req, timeout=10) as response:
                remote_version = response.read().decode('utf-8').strip()

            local_version = get_local_version()
            cmp = compare_versions(local_version, remote_version)

            # Update state
            self._state["available_version"] = remote_version
            self._state["last_check"] = datetime.datetime.now().isoformat()
            self._state["update_state"] = "idle"
            self._save_state()

            # Determine result
            if cmp == 1:
                return {
                    "success": True,
                    "update_available": True,
                    "current_version": local_version,
                    "available_version": remote_version,
                    "message": f"Update available: {local_version} → {remote_version}"
                }
            elif cmp == -1:
                return {
                    "success": True,
                    "update_available": False,
                    "current_version": local_version,
                    "available_version": remote_version,
                    "message": f"Local version ({local_version}) is ahead of remote ({remote_version})"
                }
            else:
                return {
                    "success": True,
                    "update_available": False,
                    "current_version": local_version,
                    "available_version": remote_version,
                    "message": f"Already up to date ({local_version})"
                }

        except urllib.error.URLError as e:
            self._state["update_state"] = "idle"
            self._save_state()
            return {"success": False, "error": f"Network error: {e.reason}"}
        except Exception as e:
            self._state["update_state"] = "idle"
            self._save_state()
            return {"success": False, "error": str(e)}

    def download_update(self):
        """
        Download update files from GitHub and stage them.

        Downloads all updateable files to .update/staging/ directory
        and verifies checksums if available.

        Returns:
            dict with download results
        """
        import urllib.request
        import urllib.error
        import hashlib
        import shutil

        if not self.config.get("enabled", True):
            return {"success": False, "error": "Updates are disabled in config"}

        if self._state.get("updates_disabled", False):
            return {"success": False, "error": "Updates disabled due to repeated failures"}

        # Check if update is available
        available = self._state.get("available_version")
        local = get_local_version()
        if not available or compare_versions(local, available) != 1:
            return {"success": False, "error": "No update available to download"}

        source = self.config.get("source", {})
        repo = source.get("repo", "aide-examples/aide-slideshow")
        branch = source.get("branch", "main")
        base_url = f"https://raw.githubusercontent.com/{repo}/{branch}/app"

        # Build list of files to update dynamically from local app/ directory
        # This way, new files are automatically included in updates
        files_to_update = []
        for item in os.listdir(SCRIPT_DIR):
            item_path = os.path.join(SCRIPT_DIR, item)
            if os.path.isfile(item_path):
                # Include Python files, VERSION, README, and other text files
                if item.endswith(('.py', '.md', '.txt', '.json')) or item == 'VERSION':
                    files_to_update.append(item)
            elif os.path.isdir(item_path) and item == 'static':
                # Include static files (html, css, js)
                for static_item in os.listdir(item_path):
                    if static_item.endswith(('.html', '.css', '.js')):
                        files_to_update.append(f"static/{static_item}")

        # Ensure essential files are in the list
        for essential in ['VERSION', 'slideshow.py']:
            if essential not in files_to_update:
                files_to_update.append(essential)

        # Prepare staging directory
        staging_dir = os.path.join(self.state_dir, "staging")
        try:
            if os.path.exists(staging_dir):
                shutil.rmtree(staging_dir)
            os.makedirs(staging_dir, exist_ok=True)
            # Create subdirectories as needed
            subdirs = set(os.path.dirname(f) for f in files_to_update if '/' in f)
            for subdir in subdirs:
                os.makedirs(os.path.join(staging_dir, subdir), exist_ok=True)
        except OSError as e:
            return {"success": False, "error": f"Cannot create staging directory: {e}"}

        self._state["update_state"] = "downloading"
        self._save_state()

        downloaded = []
        errors = []
        checksums = {}

        # First, try to download CHECKSUMS.sha256 if it exists
        checksums_url = f"{base_url}/CHECKSUMS.sha256"
        try:
            req = urllib.request.Request(checksums_url, headers={"User-Agent": "AIDE-Slideshow-Updater"})
            with urllib.request.urlopen(req, timeout=10) as response:
                checksums_content = response.read().decode('utf-8')
                for line in checksums_content.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            checksums[parts[1]] = parts[0]
        except urllib.error.HTTPError:
            pass  # Checksums file is optional
        except Exception:
            pass

        # Download each file
        for filepath in files_to_update:
            url = f"{base_url}/{filepath}"
            staging_path = os.path.join(staging_dir, filepath)

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AIDE-Slideshow-Updater"})
                with urllib.request.urlopen(req, timeout=30) as response:
                    content = response.read()

                # Verify checksum if available
                if filepath in checksums:
                    actual_hash = hashlib.sha256(content).hexdigest()
                    if actual_hash != checksums[filepath]:
                        errors.append(f"{filepath}: checksum mismatch")
                        continue

                # Write to staging
                with open(staging_path, 'wb') as f:
                    f.write(content)
                downloaded.append(filepath)

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # File doesn't exist in remote, skip it
                    pass
                else:
                    errors.append(f"{filepath}: HTTP {e.code}")
            except Exception as e:
                errors.append(f"{filepath}: {str(e)}")

        # Check if we got the essential files
        if "VERSION" not in downloaded or "slideshow.py" not in downloaded:
            self._state["update_state"] = "idle"
            self._save_state()
            return {
                "success": False,
                "error": "Failed to download essential files",
                "downloaded": downloaded,
                "errors": errors
            }

        # Update state
        self._state["update_state"] = "staged"
        self._state["staged_version"] = available
        self._save_state()

        return {
            "success": True,
            "message": f"Update {available} staged successfully",
            "staged_version": available,
            "downloaded": downloaded,
            "errors": errors if errors else None
        }

    def apply_update(self):
        """
        Apply a staged update.

        1. Backs up current app/ files to .update/backup/
        2. Copies staged files to app/
        3. Sets pending_verification flag
        4. Triggers service restart

        Returns:
            dict with apply results
        """
        import shutil

        if self._state.get("update_state") != "staged":
            return {"success": False, "error": "No staged update to apply"}

        staged_version = self._state.get("staged_version")
        if not staged_version:
            return {"success": False, "error": "Staged version unknown"}

        staging_dir = os.path.join(self.state_dir, "staging")
        backup_dir = os.path.join(self.state_dir, "backup")

        if not os.path.exists(staging_dir):
            return {"success": False, "error": "Staging directory not found"}

        # Create backup of current files
        try:
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            os.makedirs(backup_dir, exist_ok=True)
            os.makedirs(os.path.join(backup_dir, "static"), exist_ok=True)

            # Backup current files
            current_version = get_local_version()
            for item in os.listdir(staging_dir):
                src = os.path.join(SCRIPT_DIR, item)
                dst = os.path.join(backup_dir, item)
                if os.path.exists(src):
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)

            self._state["backup_version"] = current_version

        except OSError as e:
            return {"success": False, "error": f"Backup failed: {e}"}

        # Apply staged files
        self._state["update_state"] = "applying"
        self._save_state()

        try:
            for item in os.listdir(staging_dir):
                src = os.path.join(staging_dir, item)
                dst = os.path.join(SCRIPT_DIR, item)

                if os.path.isdir(src):
                    # For directories (like static/), copy contents
                    if os.path.exists(dst):
                        # Copy individual files to preserve any extra files
                        for subitem in os.listdir(src):
                            shutil.copy2(
                                os.path.join(src, subitem),
                                os.path.join(dst, subitem)
                            )
                    else:
                        shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

        except OSError as e:
            # Try to rollback
            self._state["update_state"] = "idle"
            self._save_state()
            return {"success": False, "error": f"Apply failed: {e}"}

        # Update state for verification
        self._state["update_state"] = "verifying"
        self._state["pending_verification"] = True
        self._state["current_version"] = staged_version
        self._save_state()

        # Trigger restart (non-blocking)
        restart_result = self._trigger_restart()

        return {
            "success": True,
            "message": f"Update {staged_version} applied, restarting service",
            "applied_version": staged_version,
            "backup_version": self._state.get("backup_version"),
            "restart": restart_result
        }

    def _trigger_restart(self):
        """Trigger service restart via systemctl."""
        try:
            # Use systemctl to restart ourselves
            # This is safe because systemd will wait for the current request to complete
            result = subprocess.Popen(
                ["sudo", "systemctl", "restart", "slideshow"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {"triggered": True}
        except Exception as e:
            return {"triggered": False, "error": str(e)}

    def rollback(self):
        """
        Rollback to the backup version.

        Returns:
            dict with rollback results
        """
        import shutil

        backup_dir = os.path.join(self.state_dir, "backup")
        backup_version = self._state.get("backup_version")

        if not backup_version:
            return {"success": False, "error": "No backup version available"}

        if not os.path.exists(backup_dir):
            return {"success": False, "error": "Backup directory not found"}

        # Restore backup files
        try:
            for item in os.listdir(backup_dir):
                src = os.path.join(backup_dir, item)
                dst = os.path.join(SCRIPT_DIR, item)

                if os.path.isdir(src):
                    if os.path.exists(dst):
                        for subitem in os.listdir(src):
                            shutil.copy2(
                                os.path.join(src, subitem),
                                os.path.join(dst, subitem)
                            )
                    else:
                        shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

        except OSError as e:
            return {"success": False, "error": f"Rollback failed: {e}"}

        # Update state
        self._state["current_version"] = backup_version
        self._state["update_state"] = "idle"
        self._state["pending_verification"] = False
        self._state["consecutive_failures"] = self._state.get("consecutive_failures", 0) + 1

        # Disable updates after too many failures
        if self._state["consecutive_failures"] >= 2:
            self._state["updates_disabled"] = True

        self._save_state()

        # Trigger restart
        restart_result = self._trigger_restart()

        return {
            "success": True,
            "message": f"Rolled back to version {backup_version}",
            "restored_version": backup_version,
            "consecutive_failures": self._state["consecutive_failures"],
            "updates_disabled": self._state.get("updates_disabled", False),
            "restart": restart_result
        }

    def confirm_update(self):
        """
        Confirm that the update is working (called after successful startup).

        Clears the pending_verification flag and resets failure counter.
        """
        if not self._state.get("pending_verification"):
            return {"success": False, "error": "No pending verification"}

        self._state["pending_verification"] = False
        self._state["consecutive_failures"] = 0
        self._state["update_state"] = "idle"
        import datetime
        self._state["last_update"] = datetime.datetime.now().isoformat()
        self._save_state()

        # Clean up staging directory
        staging_dir = os.path.join(self.state_dir, "staging")
        if os.path.exists(staging_dir):
            import shutil
            try:
                shutil.rmtree(staging_dir)
            except OSError:
                pass

        return {
            "success": True,
            "message": "Update verified and confirmed",
            "version": self._state.get("current_version")
        }

    def enable_updates(self):
        """Re-enable updates after they were disabled due to failures."""
        self._state["updates_disabled"] = False
        self._state["consecutive_failures"] = 0
        self._save_state()

        return {
            "success": True,
            "message": "Updates re-enabled"
        }


# Global update manager instance (initialized in main)
update_manager = None


# =============================================================================
# WEB UI - Load from static file
# =============================================================================


class PathSecurityError(ValueError):
    """Raised when a path contains unsafe traversal sequences."""
    pass


def resolve_safe_path(path_str, base_dir=None):
    """
    Resolve a path safely, rejecting path traversal attempts.

    Args:
        path_str: Path from config (relative or absolute)
        base_dir: Base directory for relative paths (defaults to PROJECT_DIR)

    Returns:
        Absolute path string

    Raises:
        PathSecurityError: If path contains '..' traversal sequences
    """
    if base_dir is None:
        base_dir = PROJECT_DIR

    # Block path traversal sequences
    if '..' in path_str:
        raise PathSecurityError(f"Path traversal '..' not allowed in path: {path_str}")

    # Resolve relative paths against base_dir
    if os.path.isabs(path_str):
        resolved = os.path.normpath(path_str)
    else:
        resolved = os.path.normpath(os.path.join(base_dir, path_str))

    # Double-check the resolved path doesn't escape (belt and suspenders)
    # This catches edge cases like paths with encoded sequences
    if '..' in resolved:
        raise PathSecurityError(f"Resolved path contains traversal: {resolved}")

    return resolved


# MIME types for static file serving
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.md': 'text/markdown; charset=utf-8',
}


def load_static_file(filename, binary=False):
    """Load a file from the static directory."""
    filepath = os.path.join(STATIC_DIR, filename)
    try:
        mode = 'rb' if binary else 'r'
        encoding = None if binary else 'utf-8'
        with open(filepath, mode, encoding=encoding) as f:
            return f.read()
    except FileNotFoundError:
        return None


def load_readme():
    """Load README.md from the project root."""
    readme_path = os.path.join(SCRIPT_DIR, "README.md")
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "# README not found\n\nThe README.md file was not found in the project directory."


# =============================================================================
# IMAGE PREPARATION - Lazy import and job management
# =============================================================================

# Lazy-loaded module reference
_imgPrepare = None


def get_imgPrepare():
    """Lazy import of imgPrepare module to avoid loading PIL until needed."""
    global _imgPrepare
    if _imgPrepare is None:
        try:
            import imgPrepare as module
            _imgPrepare = module
            print("imgPrepare module loaded")
        except ImportError as e:
            print(f"Failed to import imgPrepare: {e}")
            return None
    return _imgPrepare


class ImagePrepareJob:
    """Manages a background image preparation job."""

    def __init__(self):
        self.running = False
        self.cancelled = False
        self.progress = None  # Current PrepareProgress
        self.counts = {"processed": 0, "exists": 0, "error": 0}
        self.error = None
        self._thread = None
        self._lock = threading.Lock()

    def start(self, config):
        """Start processing in background thread."""
        if self.running:
            return False, "Job already running"

        module = get_imgPrepare()
        if module is None:
            return False, "imgPrepare module not available"

        self.running = True
        self.cancelled = False
        self.progress = None
        self.counts = {"processed": 0, "exists": 0, "error": 0}
        self.error = None

        self._thread = threading.Thread(target=self._run, args=(module, config), daemon=True)
        self._thread.start()
        return True, "Job started"

    def _run(self, module, config):
        """Background processing loop."""
        try:
            gen = module.process_folder_iter(config)
            for progress in gen:
                if self.cancelled:
                    break
                with self._lock:
                    self.progress = progress
                    self.counts[progress.status] = self.counts.get(progress.status, 0) + 1
        except Exception as e:
            self.error = str(e)
            print(f"ImagePrepareJob error: {e}")
        finally:
            self.running = False

    def cancel(self):
        """Request cancellation of running job."""
        self.cancelled = True

    def get_status(self):
        """Get current job status."""
        with self._lock:
            if self.progress:
                return {
                    "running": self.running,
                    "cancelled": self.cancelled,
                    "current": self.progress.current,
                    "total": self.progress.total,
                    "percent": round(100 * self.progress.current / self.progress.total, 1) if self.progress.total > 0 else 0,
                    "current_file": self.progress.filepath,
                    "counts": self.counts.copy(),
                    "error": self.error,
                }
            else:
                return {
                    "running": self.running,
                    "cancelled": self.cancelled,
                    "current": 0,
                    "total": 0,
                    "percent": 0,
                    "current_file": None,
                    "counts": self.counts.copy(),
                    "error": self.error,
                }


# Global job instance (only one job at a time)
_prepare_job = ImagePrepareJob()


class HTTPAPIRemoteControl(RemoteControlProvider):
    """
    HTTP REST API for remote control.

    Advantages:
    - Works from any device (phone, computer, smart home system)
    - Easy to integrate with automation tools
    - No additional hardware

    Endpoints:
    - GET /status - Current slideshow status
    - GET /pause - Pause slideshow
    - GET /resume - Resume slideshow
    - GET /skip - Skip to next image
    - GET /duration?seconds=N - Set display duration
    - GET /filter?folder=NAME - Filter by folder
    - GET /filter/clear - Clear filter
    - GET /monitor/on - Turn monitor on
    - GET /monitor/off - Turn monitor off
    """

    def __init__(self, config, slideshow):
        super().__init__(slideshow)
        self.port = config.get("port", 8080)
        self._server = None
        self._thread = None

    def _get_server_url(self):
        """Get the best URL to reach this server (may be slow due to DNS)."""
        import socket

        # Under WSL2, use localhost (FQDN like corno.localdomain doesn't resolve)
        if PLATFORM == 'wsl2':
            return f"http://localhost:{self.port}"

        hostname = socket.gethostname()
        try:
            # Try to get FQDN (fully qualified domain name)
            fqdn = socket.getfqdn()
            if fqdn and fqdn != hostname and '.' in fqdn:
                return f"http://{fqdn}:{self.port}"
        except:
            pass
        try:
            # Fall back to IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return f"http://{ip}:{self.port}"
        except:
            pass
        return f"http://{hostname}:{self.port}"

    def _print_server_url_async(self):
        """Print server URL in background thread to avoid blocking startup."""
        def resolve_and_print():
            url = self._get_server_url()
            print(f"HTTP API server reachable at {url}")
        thread = threading.Thread(target=resolve_and_print, daemon=True)
        thread.start()

    def start(self):
        handler = self._create_handler()
        self._server = HTTPServer(('0.0.0.0', self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"HTTP API server started on port {self.port}")
        # Resolve URL asynchronously to avoid blocking (getfqdn can be slow under WSL)
        self._print_server_url_async()

    def stop(self):
        if self._server:
            self._server.shutdown()

    def _create_handler(self):
        """Create request handler with reference to this controller."""
        controller = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                print(f"API: {args[0]}")

            def send_json(self, data, status=200):
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def send_html(self, html):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode())

            def send_static_file(self, filename):
                """Serve a static file with appropriate MIME type."""
                ext = os.path.splitext(filename)[1].lower()
                mime_type = MIME_TYPES.get(ext, 'application/octet-stream')
                is_binary = ext in ('.png', '.jpg', '.jpeg', '.ico')

                content = load_static_file(filename, binary=is_binary)
                if content is None:
                    self.send_error(404, f"File not found: {filename}")
                    return

                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.end_headers()
                if is_binary:
                    self.wfile.write(content)
                else:
                    self.wfile.write(content.encode())

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                params = parse_qs(parsed.query)

                # Serve web UI at root
                if path == '/' or path == '/index.html':
                    self.send_static_file('index.html')
                    return

                # Serve static files from /static/ path
                if path.startswith('/static/'):
                    filename = path[8:]  # Remove '/static/' prefix
                    # Security: prevent directory traversal
                    if '..' in filename or filename.startswith('/'):
                        self.send_error(403, "Forbidden")
                        return
                    self.send_static_file(filename)
                    return

                # Serve about page
                if path == '/about' or path == '/about.html':
                    self.send_static_file('about.html')
                    return

                # Serve update page
                if path == '/update' or path == '/update.html':
                    self.send_static_file('update.html')
                    return

                # Serve README.md content as JSON (for the about page)
                if path == '/readme':
                    self.send_json({"content": load_readme()})
                    return

                if path == '/status':
                    self.send_json(controller.slideshow.get_status())

                elif path == '/pause':
                    controller.execute_action("pause")
                    self.send_json({"success": True, "paused": True})

                elif path == '/resume':
                    controller.execute_action("resume")
                    self.send_json({"success": True, "paused": False})

                elif path == '/skip':
                    controller.execute_action("skip")
                    self.send_json({"success": True})

                elif path == '/duration':
                    if 'seconds' in params:
                        seconds = int(params['seconds'][0])
                        controller.execute_action("set_duration", {"seconds": seconds})
                        self.send_json({"success": True, "duration": seconds})
                    else:
                        self.send_json({"error": "Missing 'seconds' parameter"}, 400)

                elif path == '/filter':
                    if 'folder' in params:
                        controller.execute_action("set_filter", {"folder": params['folder'][0]})
                        self.send_json({"success": True, "filter": params['folder'][0]})
                    else:
                        self.send_json({"error": "Missing 'folder' parameter"}, 400)

                elif path == '/filter/clear':
                    controller.execute_action("filter_clear")
                    self.send_json({"success": True, "filter": None})

                elif path == '/monitor/on':
                    controller.execute_action("monitor_on")
                    self.send_json({"success": True, "monitor_on": True})

                elif path == '/monitor/off':
                    controller.execute_action("monitor_off")
                    self.send_json({"success": True, "monitor_on": False})

                elif path == '/folders':
                    folders = set()
                    effective_dir = controller.slideshow.get_effective_image_dir()
                    for root, dirs, _ in os.walk(effective_dir):
                        rel_root = os.path.relpath(root, effective_dir)
                        if rel_root != '.':
                            folders.add(rel_root)
                        for d in dirs:
                            folders.add(os.path.join(rel_root, d) if rel_root != '.' else d)
                    self.send_json({"folders": sorted(folders)})

                # Update API endpoints
                elif path == '/api/update/status':
                    if update_manager:
                        self.send_json(update_manager.get_status())
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                # Image preparation endpoints
                elif path == '/prepare' or path == '/prepare.html':
                    self.send_static_file('prepare.html')

                elif path == '/api/prepare/status':
                    self.send_json(_prepare_job.get_status())

                elif path == '/api/prepare/cancel':
                    _prepare_job.cancel()
                    self.send_json({"success": True, "message": "Cancellation requested"})

                elif path == '/api/prepare/count':
                    # Count images in a directory (for preview)
                    dir_param = params.get('dir', [controller.slideshow.image_dir])[0]
                    try:
                        directory = resolve_safe_path(dir_param)
                    except PathSecurityError as e:
                        self.send_json({"error": str(e)}, 400)
                        return
                    module = get_imgPrepare()
                    if module:
                        from pathlib import Path
                        count = module.count_image_files(Path(directory))
                        self.send_json({"count": count, "directory": directory})
                    else:
                        self.send_json({"error": "imgPrepare not available"}, 500)

                elif path == '/api/prepare/defaults':
                    # Return default configuration and paths
                    self.send_json({
                        "input_dir": controller.slideshow.upload_dir,
                        "output_dir": controller.slideshow.image_dir,
                        "mode": "hybrid-stretch",
                        "target_size": "1920x1080",
                        "pad_mode": "average",
                        "crop_min": 0.8,
                        "stretch_max": 0.2,
                        "no_stretch_limit": 0.4,
                        "modes": ["pad", "crop", "hybrid", "hybrid-stretch"],
                        "pad_modes": ["gray", "white", "black", "average"],
                    })

                else:
                    self.send_json({
                        "endpoints": [
                            "GET /status - Current status",
                            "GET /pause - Pause slideshow",
                            "GET /resume - Resume slideshow",
                            "GET /skip - Skip to next image",
                            "GET /duration?seconds=N - Set display duration",
                            "GET /filter?folder=NAME - Show only images from folder",
                            "GET /filter/clear - Clear folder filter",
                            "GET /folders - List available folders",
                            "GET /monitor/on - Turn monitor on",
                            "GET /monitor/off - Turn monitor off",
                            "GET /prepare - Image preparation UI",
                            "GET /api/prepare/status - Preparation job status",
                            "POST /api/prepare/start - Start preparation job",
                            "GET /api/prepare/cancel - Cancel running job",
                            "GET /api/update/status - Update system status",
                            "POST /api/update/check - Check for updates on GitHub",
                            "POST /api/update/download - Download and stage update",
                            "POST /api/update/apply - Apply staged update and restart",
                            "POST /api/update/rollback - Rollback to backup version",
                            "POST /api/update/enable - Re-enable updates after failures",
                        ]
                    })

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path

                # Read POST body
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

                try:
                    data = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    self.send_json({"error": "Invalid JSON"}, 400)
                    return

                if path == '/api/update/check':
                    if update_manager:
                        result = update_manager.check_for_updates()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/update/download':
                    if update_manager:
                        result = update_manager.download_update()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/update/apply':
                    if update_manager:
                        result = update_manager.apply_update()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/update/rollback':
                    if update_manager:
                        result = update_manager.rollback()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/update/enable':
                    if update_manager:
                        result = update_manager.enable_updates()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/prepare/start':
                    module = get_imgPrepare()
                    if not module:
                        self.send_json({"error": "imgPrepare module not available"}, 500)
                        return

                    # Parse configuration from POST data
                    from pathlib import Path as PathLib
                    try:
                        # Validate and resolve paths safely
                        input_dir_str = data.get('input_dir', controller.slideshow.upload_dir)
                        output_dir_str = data.get('output_dir', controller.slideshow.image_dir)

                        try:
                            input_dir = resolve_safe_path(input_dir_str)
                            output_dir = resolve_safe_path(output_dir_str)
                        except PathSecurityError as e:
                            self.send_json({"error": str(e)}, 400)
                            return

                        # Parse target size
                        size_str = data.get('target_size', '1920x1080')
                        if isinstance(size_str, str):
                            w, h = size_str.lower().split('x')
                            target_size = (int(w), int(h))
                        else:
                            target_size = tuple(size_str)

                        config = module.PrepareConfig(
                            input_dir=PathLib(input_dir),
                            output_dir=PathLib(output_dir),
                            mode=data.get('mode', 'hybrid-stretch'),
                            target_size=target_size,
                            pad_mode=data.get('pad_mode', 'average'),
                            crop_min=float(data.get('crop_min', 0.8)),
                            stretch_max=float(data.get('stretch_max', 0.2)),
                            no_stretch_limit=float(data.get('no_stretch_limit', 0.4)),
                            show_text=bool(data.get('show_text', True)),
                            skip_existing=bool(data.get('skip_existing', False)),
                            dry_run=bool(data.get('dry_run', False)),
                            flatten=bool(data.get('flatten', False)),
                            quiet=True,  # Don't spam console from web jobs
                        )

                        success, message = _prepare_job.start(config)
                        if success:
                            self.send_json({"success": True, "message": message})
                        else:
                            self.send_json({"success": False, "error": message}, 409)

                    except Exception as e:
                        self.send_json({"error": str(e)}, 400)

                else:
                    self.send_json({"error": "Unknown endpoint"}, 404)

        return Handler


class IRRemoteControl(RemoteControlProvider):
    """
    IR Remote control using Linux input subsystem (ir-keytable).

    Requirements:
    - IR receiver module (VS1838B or similar, ~€2)
    - ir-keytable configured
    - Any IR remote

    Setup:
    1. Add to /boot/config.txt: dtoverlay=gpio-ir,gpio_pin=18
    2. Find device: ir-keytable -t -d /dev/input/event0
    3. Configure key_map in config.json

    Advantages:
    - Works without network
    - Repurpose any old remote
    - Very responsive

    Limitations:
    - Requires line of sight to receiver
    - Need to learn remote codes
    """

    # Linux input event structure constants
    EV_KEY = 0x01
    KEY_PRESS = 1

    # Common IR remote key codes (from linux/input-event-codes.h)
    KEY_CODES = {
        "KEY_POWER": 116, "KEY_PLAY": 207, "KEY_PAUSE": 119,
        "KEY_PLAYPAUSE": 164, "KEY_STOP": 128, "KEY_NEXT": 163,
        "KEY_PREVIOUS": 165, "KEY_UP": 103, "KEY_DOWN": 108,
        "KEY_LEFT": 105, "KEY_RIGHT": 106, "KEY_OK": 352,
        "KEY_ENTER": 28, "KEY_0": 11, "KEY_1": 2, "KEY_2": 3,
        "KEY_3": 4, "KEY_4": 5, "KEY_5": 6, "KEY_6": 7,
        "KEY_7": 8, "KEY_8": 9, "KEY_9": 10, "KEY_VOLUMEUP": 115,
        "KEY_VOLUMEDOWN": 114, "KEY_MUTE": 113, "KEY_MENU": 139,
        "KEY_BACK": 158, "KEY_HOME": 172, "KEY_INFO": 358,
        "KEY_RED": 398, "KEY_GREEN": 399, "KEY_YELLOW": 400,
        "KEY_BLUE": 401,
    }

    def __init__(self, config, slideshow):
        super().__init__(slideshow)
        self.device_path = config.get("device", "/dev/input/event0")
        self.key_map = config.get("key_map", {})
        self.folder_shortcuts = config.get("folder_shortcuts", {})
        self._running = False
        self._thread = None
        self._device_fd = None

    def start(self):
        try:
            self._device_fd = open(self.device_path, 'rb')
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            print(f"IR remote listening on {self.device_path}")
        except FileNotFoundError:
            print(f"IR device not found: {self.device_path}")
            print("Make sure ir-keytable is configured and the IR receiver is connected")
        except PermissionError:
            print(f"Permission denied for {self.device_path}")
            print("Add user to 'input' group: sudo usermod -aG input pi")

    def stop(self):
        self._running = False
        if self._device_fd:
            self._device_fd.close()

    def _code_to_name(self, code):
        """Convert key code to key name."""
        for name, c in self.KEY_CODES.items():
            if c == code:
                return name
        return None

    def _listen_loop(self):
        """Main loop reading input events."""
        import struct

        EVENT_SIZE = 24
        EVENT_FORMAT = 'llHHI'

        sel = selectors.DefaultSelector()
        sel.register(self._device_fd, selectors.EVENT_READ)

        while self._running:
            events = sel.select(timeout=1.0)
            if not events:
                continue

            try:
                data = self._device_fd.read(EVENT_SIZE)
                if not data or len(data) < EVENT_SIZE:
                    continue

                _, _, ev_type, ev_code, ev_value = struct.unpack(EVENT_FORMAT, data)

                if ev_type == self.EV_KEY and ev_value == self.KEY_PRESS:
                    key_name = self._code_to_name(ev_code)
                    if key_name:
                        self._handle_key(key_name)
                    else:
                        print(f"IR: Unknown key code {ev_code}")

            except Exception as e:
                if self._running:
                    print(f"IR read error: {e}")

        sel.close()

    def _handle_key(self, key_name):
        """Handle a key press."""
        action = self.key_map.get(key_name)
        if not action:
            print(f"IR: No action mapped for {key_name}")
            return

        print(f"IR: {key_name} -> {action}")

        # Pass folder shortcuts as params for filter actions
        if action.startswith("filter_") and action != "filter_clear":
            folder = self.folder_shortcuts.get(action)
            if folder:
                self.execute_action("set_filter", {"folder": folder})
            else:
                print(f"IR: No folder configured for {action}")
        else:
            self.execute_action(action)


# =============================================================================
# SLIDESHOW CORE
# =============================================================================

class Slideshow:
    """Core slideshow engine with plugin support."""

    def __init__(self, config):
        self.config = config
        self.running = True
        self.paused = False
        self.display_duration = config["display_duration"]
        self.fade_steps = config["fade_steps"]

        # Resolve paths safely (supports both relative and absolute, blocks '..')
        self.image_dir = resolve_safe_path(config["image_dir"])
        default_upload = "img/upload"  # Relative default
        self.upload_dir = resolve_safe_path(config.get("upload_dir", default_upload))
        self.current_filter = None

        # Initialize monitor control
        self.monitor = create_monitor_control(config.get("monitor_control", {}))

        # Initialize pygame display (disable audio to avoid ALSA errors)
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        pygame.display.init()
        pygame.init()

        info = pygame.display.Info()
        print(f"Driver: {pygame.display.get_driver()}")
        print(f"Detected resolution: {info.current_w}x{info.current_h}")

        # Use platform-specific display configuration
        if VIDEO_CONFIG.get('fullscreen', True):
            # Fullscreen mode for Raspberry Pi
            pygame.mouse.set_visible(False)
            self.screen = pygame.display.set_mode(
                (info.current_w, info.current_h),
                pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE
            )
        else:
            # Windowed mode for desktop/WSL2 testing
            width, height = VIDEO_CONFIG.get('windowed_size', (1280, 720))
            pygame.display.set_caption("Slideshow - Press Q to quit, Space to pause")
            self.screen = pygame.display.set_mode(
                (width, height),
                pygame.DOUBLEBUF | pygame.RESIZABLE
            )
            print(f"Running in windowed mode: {width}x{height}")

        # WSLg/Wayland workaround: force window to render immediately
        # Without this, the window may stay black for ~20 seconds under WSLg
        self.screen.fill((0, 0, 0))
        pygame.display.flip()
        pygame.event.pump()

        self.width, self.height = self.screen.get_size()
        self.clock = pygame.time.Clock()
        self.fade_surface = pygame.Surface((self.width, self.height)).convert()
        self.fade_surface.fill((0, 0, 0))

        self.playlist = []
        self.current_img = None
        self.current_path = None
        self._skip_requested = False

        self.lock = threading.Lock()

        signal.signal(signal.SIGTERM, self.handle_exit_signal)
        signal.signal(signal.SIGINT, self.handle_exit_signal)

    def handle_exit_signal(self, signum, frame):
        print("Shutdown signal received. Stopping slideshow...")
        self.running = False
        pygame.quit()
        sys.exit(0)

    def get_effective_image_dir(self):
        """Get the directory currently being used for images (may be sample_images fallback)."""
        if self._scan_directory(self.image_dir):
            return self.image_dir
        sample_dir = os.path.join(SCRIPT_DIR, "sample_images")
        if os.path.isdir(sample_dir) and self._scan_directory(sample_dir):
            return sample_dir
        return self.image_dir

    def get_images(self):
        """Get images, optionally filtered by folder. Falls back to sample_images if empty."""
        images = self._scan_directory(self.image_dir)

        # Fallback to sample_images if configured directory is empty or missing
        if not images:
            sample_dir = os.path.join(SCRIPT_DIR, "sample_images")
            if os.path.isdir(sample_dir):
                images = self._scan_directory(sample_dir)
                if images and not hasattr(self, '_sample_warning_shown'):
                    print(f"Using sample images from {sample_dir}")
                    print("Configure image_dir in config.json to use your own photos")
                    self._sample_warning_shown = True

        return images

    def _scan_directory(self, directory):
        """Scan a directory recursively for images."""
        images = []
        if not os.path.isdir(directory):
            return images
        for root, _, files in os.walk(directory):
            if self.current_filter and self.current_filter not in root:
                continue
            for f in files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    images.append(os.path.join(root, f))
        return images

    def fade_transition(self, next_img):
        steps = self.fade_steps
        for i in range(steps, -1, -1):
            alpha = int((i / steps) * 255)
            self.screen.blit(next_img, (0, 0))
            self.fade_surface.set_alpha(alpha)
            self.screen.blit(self.fade_surface, (0, 0))
            pygame.display.flip()
            self.clock.tick(30)

    def get_status(self):
        with self.lock:
            return {
                "running": self.running,
                "paused": self.paused,
                "monitor_on": self.monitor.is_on,
                "display_duration": self.display_duration,
                "current_image": self.current_path,
                "filter": self.current_filter,
                "playlist_size": len(self.playlist)
            }

    def set_duration(self, seconds):
        with self.lock:
            self.display_duration = max(1, min(300, seconds))
            print(f"Display duration set to {self.display_duration}s")

    def set_filter(self, folder_filter):
        with self.lock:
            self.current_filter = folder_filter
            self.playlist = []
            print(f"Filter set to: {folder_filter}")

    def clear_filter(self):
        with self.lock:
            self.current_filter = None
            self.playlist = []
            print("Filter cleared")

    def pause(self):
        with self.lock:
            self.paused = True
            print("Slideshow paused")

    def resume(self):
        with self.lock:
            self.paused = False
            print("Slideshow resumed")

    def skip(self):
        with self.lock:
            self._skip_requested = True
            print("Skipping to next image")

    def _handle_pygame_events(self):
        """Process pygame events (keyboard, window close, resize)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    if self.paused:
                        self.resume()
                    else:
                        self.pause()
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_n:
                    self.skip()
                elif event.key == pygame.K_UP:
                    self.set_duration(self.display_duration + 5)
                elif event.key == pygame.K_DOWN:
                    self.set_duration(self.display_duration - 5)
                elif event.key == pygame.K_f:
                    # Toggle fullscreen in desktop mode
                    if not VIDEO_CONFIG.get('fullscreen', True):
                        pygame.display.toggle_fullscreen()
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize
                self.width, self.height = event.w, event.h
                self.screen = pygame.display.set_mode(
                    (self.width, self.height),
                    pygame.DOUBLEBUF | pygame.RESIZABLE
                )
                self.fade_surface = pygame.Surface((self.width, self.height)).convert()
                self.fade_surface.fill((0, 0, 0))
                # Rescale current image if we have one
                if self.current_img:
                    self.current_img = pygame.transform.scale(
                        self.current_img, (self.width, self.height)
                    ).convert()
                    self.screen.blit(self.current_img, (0, 0))
                    pygame.display.flip()

    def run(self):
        while self.running:
            # Process pygame events (essential for desktop mode)
            self._handle_pygame_events()

            if self.paused:
                time.sleep(0.1)
                continue

            if not self.playlist:
                self.playlist = self.get_images()
                if not self.playlist:
                    print("No images found, waiting...")
                    time.sleep(5)
                    continue
                random.shuffle(self.playlist)

            path = self.playlist.pop(0)
            self.current_path = path

            try:
                img = pygame.image.load(path)
                img = pygame.transform.scale(img, (self.width, self.height)).convert()
            except Exception as e:
                print(f"Error loading {path}: {e}")
                continue

            if self.current_img is None:
                self.screen.blit(img, (0, 0))
                pygame.display.flip()
                pygame.event.pump()  # WSLg/Wayland: process events to show first image
            else:
                self.fade_transition(img)

            self.current_img = img

            self._skip_requested = False
            elapsed = 0
            while elapsed < self.display_duration and self.running and not self._skip_requested:
                self._handle_pygame_events()  # Keep processing events during display
                if self.paused:
                    time.sleep(0.1)
                    continue
                time.sleep(0.1)
                elapsed += 0.1


# =============================================================================
# MAIN
# =============================================================================

def parse_args():
    """Parse command line arguments for testing/development."""
    import argparse
    parser = argparse.ArgumentParser(description='Photo Slideshow')
    parser.add_argument('--image-dir', '-i', type=str,
                        help='Override image directory')
    parser.add_argument('--config', '-c', type=str,
                        help='Path to config file')
    parser.add_argument('--duration', '-d', type=int,
                        help='Override display duration (seconds)')
    parser.add_argument('--fullscreen', '-f', action='store_true',
                        help='Force fullscreen mode')
    parser.add_argument('--windowed', '-w', action='store_true',
                        help='Force windowed mode')
    parser.add_argument('--size', '-s', type=str, default='1280x720',
                        help='Window size for windowed mode (WIDTHxHEIGHT)')
    return parser.parse_args()


def main():
    args = parse_args()

    # Override VIDEO_CONFIG based on command line args
    global VIDEO_CONFIG
    if args.fullscreen:
        VIDEO_CONFIG['fullscreen'] = True
    elif args.windowed:
        VIDEO_CONFIG['fullscreen'] = False
    if args.size:
        try:
            w, h = args.size.split('x')
            VIDEO_CONFIG['windowed_size'] = (int(w), int(h))
        except:
            pass

    # Load config from multiple possible locations
    config_paths = [
        args.config,  # Command line override first
        os.path.join(PROJECT_DIR, "config.json"),  # Parent of app/ (standard location)
        "/home/pi/aide-slideshow/config.json",
        "/home/pi/config.json",
    ]
    config_paths = [p for p in config_paths if p]  # Remove None

    config = None
    for path in config_paths:
        if os.path.exists(path):
            config = load_config(path)
            print(f"Loaded config from {path}")
            break

    if config is None:
        config = load_config("/nonexistent")  # Will use defaults
        print("Using default configuration")

    # Apply command line overrides
    if args.image_dir:
        config['image_dir'] = args.image_dir
        print(f"Image directory overridden to: {args.image_dir}")
    if args.duration:
        config['display_duration'] = args.duration
        print(f"Display duration overridden to: {args.duration}s")

    # Initialize update manager
    global update_manager
    update_config = config.get("update", {})
    update_manager = UpdateManager(update_config)
    print(f"Version: {get_local_version()}")

    # Check if we need to verify a pending update
    if update_manager._state.get("pending_verification"):
        print("Update pending verification - will confirm after 60s stable operation")

        def delayed_confirm():
            time.sleep(60)
            if update_manager._state.get("pending_verification"):
                result = update_manager.confirm_update()
                print(f"Update verification: {result.get('message', 'done')}")

        confirm_thread = threading.Thread(target=delayed_confirm, daemon=True)
        confirm_thread.start()

    # Create slideshow
    app = Slideshow(config)

    # Initialize remote control providers
    remote_controls = []
    rc_config = config.get("remote_control", {})

    # HTTP API
    http_config = rc_config.get("http_api", {})
    if http_config.get("enabled", True):
        http_api = HTTPAPIRemoteControl(http_config, app)
        http_api.start()
        remote_controls.append(http_api)

    # IR Remote
    ir_config = rc_config.get("ir_remote", {})
    if ir_config.get("enabled", False):
        ir_remote = IRRemoteControl(ir_config, app)
        ir_remote.start()
        remote_controls.append(ir_remote)

    # Initialize motion sensor
    motion_config = config.get("motion_sensor", {})
    motion_sensor = create_motion_sensor(
        motion_config,
        on_motion=lambda: app.monitor.turn_on(),
        on_idle=lambda: app.monitor.turn_off()
    )
    motion_sensor.start()

    # Run slideshow
    try:
        app.run()
    finally:
        # Cleanup
        motion_sensor.stop()
        for rc in remote_controls:
            rc.stop()


if __name__ == "__main__":
    main()
