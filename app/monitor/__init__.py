"""
Monitor control providers.

Provides different backends for controlling monitor/TV power:
- CEC: HDMI-CEC protocol
- Shelly: Smart plug control
- GPIO: Relay control via GPIO pins
- Samsung WS: Samsung Smart TV WebSocket API
"""

from abc import ABC, abstractmethod


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

    def __init__(self):
        self._is_on = True

    @abstractmethod
    def turn_on(self) -> bool:
        """Turn monitor on. Returns True on success."""
        pass

    @abstractmethod
    def turn_off(self) -> bool:
        """Turn monitor off. Returns True on success."""
        pass

    @property
    def is_on(self) -> bool:
        """Current monitor state (may be assumed, not always queryable)."""
        return self._is_on


class NullMonitorControl(MonitorControlProvider):
    """No-op implementation when monitor control is disabled."""

    def turn_on(self) -> bool:
        self._is_on = True
        return True

    def turn_off(self) -> bool:
        self._is_on = False
        return True


# Import providers AFTER base class is defined to avoid circular imports
from .cec import CECMonitorControl
from .shelly import ShellyMonitorControl
from .gpio import GPIORelayMonitorControl
from .samsung import SamsungWSMonitorControl


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


__all__ = [
    'MonitorControlProvider',
    'NullMonitorControl',
    'CECMonitorControl',
    'ShellyMonitorControl',
    'GPIORelayMonitorControl',
    'SamsungWSMonitorControl',
    'create_monitor_control',
]
