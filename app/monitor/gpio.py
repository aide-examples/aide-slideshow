"""
GPIO relay based monitor control.

Requirements:
- Relay module connected to GPIO pin
- RPi.GPIO or gpiozero library

Advantages:
- Cheapest solution (~2 EUR for relay module)
- No network dependency
- Works with any display

Limitations:
- Requires wiring
- Hard power cut
"""

from aide_frame.log import logger
from . import MonitorControlProvider


class GPIORelayMonitorControl(MonitorControlProvider):
    """GPIO relay based monitor control."""

    def __init__(self, config):
        super().__init__()
        self.pin = config.get("pin", 27)
        self.active_low = config.get("active_low", False)
        self._gpio_available = False

        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            GPIO.output(self.pin, GPIO.LOW if self.active_low else GPIO.HIGH)
            self._gpio_available = True
            logger.info(f"GPIO Relay initialized on pin {self.pin}")
        except ImportError:
            logger.warning("RPi.GPIO not available, GPIO relay disabled")
        except Exception as e:
            logger.error(f"GPIO setup error: {e}")

    def turn_on(self) -> bool:
        if not self._gpio_available:
            return False
        try:
            self.GPIO.output(self.pin, self.GPIO.LOW if self.active_low else self.GPIO.HIGH)
            self._is_on = True
            logger.info("GPIO Relay: Monitor turned ON")
            return True
        except Exception as e:
            logger.error(f"GPIO error: {e}")
            return False

    def turn_off(self) -> bool:
        if not self._gpio_available:
            return False
        try:
            self.GPIO.output(self.pin, self.GPIO.HIGH if self.active_low else self.GPIO.LOW)
            self._is_on = False
            logger.info("GPIO Relay: Monitor turned OFF")
            return True
        except Exception as e:
            logger.error(f"GPIO error: {e}")
            return False
