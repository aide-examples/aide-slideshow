"""
Remote control providers.

Provides different backends for controlling the slideshow:
- HTTP API: Universal, works from any device with a browser
- IR Remote: Physical remote via Linux input events
- Alexa: Voice control via Fauxmo (WeMo emulation)
"""

from abc import ABC, abstractmethod

from aide_frame.log import logger


class RemoteControlProvider(ABC):
    """
    Abstract interface for remote control input.

    Problem: We need ways to control the slideshow (pause, skip, speed, filters).

    Solutions:
    - HTTP API: Universal, works from any device with a browser
    - IR Remote: Physical remote, works without network
    - Alexa: Voice control via Fauxmo WeMo emulation
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
            logger.warning(f"Unknown action: {action}")


# Import providers after base class is defined
from .http_api import HTTPAPIRemoteControl
from .ir_remote import IRRemoteControl
from .alexa import FauxmoRemoteControl

__all__ = [
    'RemoteControlProvider',
    'HTTPAPIRemoteControl',
    'IRRemoteControl',
    'FauxmoRemoteControl',
]
