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
1. Enable network standby: Settings -> General -> Network -> Expert Settings -> Power On with Mobile
2. First run will prompt for approval on TV screen
3. Token is saved to token_file for future connections
"""

import time

from log import logger
from . import MonitorControlProvider


class SamsungWSMonitorControl(MonitorControlProvider):
    """Samsung Smart TV WebSocket API control."""

    def __init__(self, config):
        super().__init__()
        self.ip = config.get("ip")
        self.token_file = config.get("token_file", "/home/pi/.samsung_token")
        self.mac_address = config.get("mac_address")  # For Wake-on-LAN
        self.port = config.get("port", 8002)  # 8001 for older TVs, 8002 for newer (SSL)
        self.timeout = config.get("timeout", 5)
        self.name = config.get("name", "RaspberryPiSlideshow")
        self._tv = None
        self._tv_class = None

        if not self.ip:
            logger.warning("Samsung TV IP not configured")
            return

        # Import the library
        try:
            from samsungtvws import SamsungTVWS
            self._tv_class = SamsungTVWS
            logger.info(f"Samsung WS: Library loaded, TV at {self.ip}:{self.port}")

            # Test connection and get initial state
            if self._check_tv_available():
                logger.debug("Samsung WS: TV is responding")
                self._is_on = True
            else:
                logger.debug("Samsung WS: TV not responding (may be in standby)")
                self._is_on = False

        except ImportError:
            logger.warning("samsungtvws not installed. Run: pip install samsungtvws")
        except Exception as e:
            logger.error(f"Samsung WS init error: {e}")

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
            logger.error(f"Samsung WS connection error: {e}")
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
            logger.error(f"Samsung WS send_key error: {e}")
            return False

    def _wake_on_lan(self) -> bool:
        """Wake TV via Wake-on-LAN if MAC address is configured."""
        if not self.mac_address:
            logger.debug("Samsung WS: MAC address not configured for Wake-on-LAN")
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

            logger.debug("Samsung WS: Wake-on-LAN packet sent")
            return True
        except Exception as e:
            logger.error(f"Samsung WS Wake-on-LAN error: {e}")
            return False

    def turn_on(self) -> bool:
        """Turn TV on."""
        if self._is_on and self._check_tv_available():
            logger.debug("Samsung WS: TV already on")
            return True

        # Try Wake-on-LAN first (works when TV is in standby)
        if self.mac_address:
            self._wake_on_lan()
            # Wait a moment for TV to wake
            time.sleep(3)

        # Check if TV is now available
        if self._check_tv_available():
            self._is_on = True
            logger.info("Samsung WS: Monitor turned ON")
            return True

        # If WoL didn't work or no MAC, try sending KEY_POWER
        # (only works if TV is in network standby mode)
        if self._send_key("KEY_POWER"):
            self._is_on = True
            logger.info("Samsung WS: Monitor turned ON via KEY_POWER")
            return True

        logger.error("Samsung WS: Failed to turn on TV")
        return False

    def turn_off(self) -> bool:
        """Turn TV off (standby)."""
        if not self._is_on and not self._check_tv_available():
            logger.debug("Samsung WS: TV already off")
            return True

        # Send power key to put TV in standby
        if self._send_key("KEY_POWER"):
            self._is_on = False
            logger.info("Samsung WS: Monitor turned OFF")
            return True

        # Alternative: try KEY_POWEROFF specifically
        if self._send_key("KEY_POWEROFF"):
            self._is_on = False
            logger.info("Samsung WS: Monitor turned OFF via KEY_POWEROFF")
            return True

        logger.error("Samsung WS: Failed to turn off TV")
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

    def get_device_info(self) -> dict:
        """Get TV device information via REST API."""
        import urllib.request
        import json
        try:
            url = f"http://{self.ip}:8001/api/v2/"
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            logger.error(f"Samsung WS device info error: {e}")
            return {}
