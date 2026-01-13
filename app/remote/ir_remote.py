"""
IR Remote control using Linux input subsystem (ir-keytable).

Requirements:
- IR receiver module (VS1838B or similar, ~2 EUR)
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

import threading
import selectors

from aide_frame.log import logger
from . import RemoteControlProvider


class IRRemoteControl(RemoteControlProvider):
    """IR Remote control using Linux input subsystem."""

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
            logger.info(f"IR remote listening on {self.device_path}")
        except FileNotFoundError:
            logger.error(f"IR device not found: {self.device_path}")
            logger.info("Make sure ir-keytable is configured and the IR receiver is connected")
        except PermissionError:
            logger.error(f"Permission denied for {self.device_path}")
            logger.info("Add user to 'input' group: sudo usermod -aG input pi")

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
                        logger.debug(f"IR: Unknown key code {ev_code}")

            except Exception as e:
                if self._running:
                    logger.error(f"IR read error: {e}")

        sel.close()

    def _handle_key(self, key_name):
        """Handle a key press."""
        action = self.key_map.get(key_name)
        if not action:
            logger.debug(f"IR: No action mapped for {key_name}")
            return

        logger.info(f"IR: {key_name} -> {action}")

        # Pass folder shortcuts as params for filter actions
        if action.startswith("filter_") and action != "filter_clear":
            folder = self.folder_shortcuts.get(action)
            if folder:
                self.execute_action("set_filter", {"folder": folder})
            else:
                logger.warning(f"IR: No folder configured for {action}")
        else:
            self.execute_action(action)
