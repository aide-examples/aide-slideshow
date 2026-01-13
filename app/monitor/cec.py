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

import subprocess

from aide_frame.log import logger
from . import MonitorControlProvider


class CECMonitorControl(MonitorControlProvider):
    """HDMI-CEC based monitor control."""

    def __init__(self, config):
        super().__init__()
        self.device_id = config.get("device_id", "0")

    def turn_on(self) -> bool:
        try:
            subprocess.run(
                ["cec-client", "-s", "-d", "1"],
                input=f"on {self.device_id}".encode(),
                timeout=5,
                capture_output=True
            )
            self._is_on = True
            logger.info("CEC: Monitor turned ON")
            return True
        except Exception as e:
            logger.error(f"CEC error: {e}")
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
            logger.info("CEC: Monitor turned OFF")
            return True
        except Exception as e:
            logger.error(f"CEC error: {e}")
            return False
