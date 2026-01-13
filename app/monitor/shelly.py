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
- Requires additional hardware (~15-25 EUR)
- Hard power cut may not be ideal for all displays
"""

from log import logger
from . import MonitorControlProvider


class ShellyMonitorControl(MonitorControlProvider):
    """Shelly smart plug based monitor control."""

    def __init__(self, config):
        super().__init__()
        self.ip = config.get("ip")

        if not self.ip:
            logger.warning("Shelly IP not configured")

    def _request(self, action):
        """Send request to Shelly device."""
        import urllib.request
        try:
            url = f"http://{self.ip}/relay/0?turn={action}"
            urllib.request.urlopen(url, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Shelly error: {e}")
            return False

    def turn_on(self) -> bool:
        if not self.ip:
            return False
        if self._request("on"):
            self._is_on = True
            logger.info("Shelly: Monitor turned ON")
            return True
        return False

    def turn_off(self) -> bool:
        if not self.ip:
            return False
        if self._request("off"):
            self._is_on = False
            logger.info("Shelly: Monitor turned OFF")
            return True
        return False
