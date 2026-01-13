"""
Alexa voice control using Fauxmo (WeMo emulation).

Alexa sees the slideshow as a smart plug/switch:
- "Alexa, turn on Slideshow" -> Resume + Monitor on
- "Alexa, turn off Slideshow" -> Pause + Monitor off

Requirements:
- pip install fauxmo
- Alexa device on same network
- UDP port 1900 (SSDP) and TCP port (default 12340) accessible

Setup:
1. Enable in config.json: "alexa": {"enabled": true}
2. Restart slideshow
3. Say "Alexa, discover devices"
4. Alexa will find "Slideshow" device

Limitations:
- Only on/off control (WeMo protocol limitation)
- Requires local network (no cloud)
- Does not work in WSL2 (UDP multicast issues)
"""

import threading

from aide_frame.log import logger
from . import RemoteControlProvider


class FauxmoRemoteControl(RemoteControlProvider):
    """Alexa voice control using Fauxmo (WeMo emulation)."""

    def __init__(self, config, slideshow):
        super().__init__(slideshow)
        self.config = config
        self.device_name = config.get("device_name", "Slideshow")
        self.port = config.get("port", 12340)
        self._fauxmo = None
        self._thread = None
        self.discovered = False  # Set to True when Alexa discovers the device

    def start(self):
        try:
            from fauxmo.protocols import Fauxmo
            from fauxmo.utils import make_udp_sock, get_local_ip
            import asyncio
            import logging
            # Reduce fauxmo logging to WARNING (suppress INFO polling messages)
            logging.getLogger("fauxmo").setLevel(logging.WARNING)
        except ImportError:
            logger.error("Alexa voice control: FAILED - fauxmo not installed (pip install fauxmo)")
            return

        slideshow = self.slideshow
        device_name = self.device_name
        port = self.port

        class SimpleFauxmoDevice:
            """Simple Fauxmo device handler for slideshow control."""

            def __init__(self, name: str, port: int):
                self.name = name
                self.port = port
                self.state = "off"

            def on(self) -> bool:
                self.state = "on"
                # Run slideshow control in background to not block Alexa response
                def do_on():
                    slideshow.paused = False
                    slideshow.monitor.turn_on()
                    logger.info("Alexa: Slideshow ON")
                threading.Thread(target=do_on, daemon=True).start()
                return True

            def off(self) -> bool:
                self.state = "off"
                # Run slideshow control in background to not block Alexa response
                def do_off():
                    slideshow.paused = True
                    slideshow.monitor.turn_off()
                    logger.info("Alexa: Slideshow OFF")
                threading.Thread(target=do_off, daemon=True).start()
                return True

            def get_state(self) -> str:
                return "on" if not slideshow.paused else "off"

        def run_fauxmo():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            plugin = SimpleFauxmoDevice(name=device_name, port=port)

            try:
                # Get local IP address for SSDP responses
                ip_address = get_local_ip()
                logger.debug(f"  Alexa: Using IP address {ip_address}")

                # Create UDP socket for SSDP discovery
                udp_sock = make_udp_sock()
                logger.debug(f"  Alexa: UDP socket created for SSDP")

                # Create SSDP responder for device discovery
                from fauxmo.protocols import SSDPServer
                ssdp = SSDPServer(devices=[
                    {"name": device_name, "port": port, "ip_address": ip_address}
                ])
                listen = loop.create_datagram_endpoint(
                    lambda: ssdp,
                    sock=udp_sock
                )
                loop.run_until_complete(listen)
                logger.debug(f"  Alexa: SSDP listener started (UDP multicast 239.255.255.250:1900)")

                # Wrapper to detect when Alexa discovers the device
                alexa_control = self
                class DiscoveryTrackingFauxmo(Fauxmo):
                    def data_received(self, data: bytes) -> None:
                        # Check if this is a setup.xml request (discovery)
                        if b"GET /setup.xml" in data and not alexa_control.discovered:
                            alexa_control.discovered = True
                            logger.info("Alexa: Device discovered by Echo!")
                        super().data_received(data)

                # Create TCP server for device control - bind to specific IP
                coro = loop.create_server(
                    lambda: DiscoveryTrackingFauxmo(name=device_name, plugin=plugin),
                    host=ip_address,
                    port=port
                )
                server = loop.run_until_complete(coro)
                logger.debug(f"  Alexa: TCP server started on {ip_address}:{port}")

                loop.run_forever()
            except Exception as e:
                logger.error(f"Alexa control error: {e}")
                import traceback
                traceback.print_exc()

        # Start in background thread
        self._thread = threading.Thread(target=run_fauxmo, daemon=True)
        self._thread.start()
        logger.info(f"Alexa voice control enabled: '{self.device_name}' on port {self.port}")
        logger.info(f"  -> Say 'Alexa, discover devices' to find it")
        logger.info(f"  -> Then use 'Alexa, turn on/off {self.device_name}'")

    def stop(self):
        # Fauxmo runs in daemon thread, will stop with main process
        pass
