"""
Motion sensor providers.

Provides different backends for motion detection:
- GPIO PIR: Passive infrared sensor via GPIO
- MQTT: Motion events via MQTT broker
"""

import time
import threading
from abc import ABC, abstractmethod

from aide_frame.log import logger


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
        logger.info("Motion sensor: disabled")

    def stop(self):
        pass


class GPIOPIRMotionSensor(MotionSensorProvider):
    """
    GPIO PIR (Passive Infrared) motion sensor.

    Requirements:
    - PIR sensor module (HC-SR501 or similar, ~2 EUR)
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
            logger.info(f"PIR motion sensor started on GPIO {self.pin}")
        except ImportError:
            logger.warning("RPi.GPIO not available, PIR sensor disabled")
        except Exception as e:
            logger.error(f"PIR setup error: {e}")

    def stop(self):
        self._running = False

    def _monitor_loop(self):
        while self._running:
            try:
                if self.GPIO.input(self.pin):
                    self._last_motion = time.time()
                    if self._was_idle:
                        self._was_idle = False
                        logger.info("PIR: Motion detected")
                        self.on_motion()
                else:
                    idle_time = time.time() - self._last_motion
                    if idle_time > self.idle_timeout and not self._was_idle:
                        self._was_idle = True
                        logger.info(f"PIR: No motion for {self.idle_timeout}s")
                        self.on_idle()
            except Exception as e:
                logger.error(f"PIR error: {e}")

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
            logger.warning("MQTT broker not configured")
            return

        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client()
            self._client.on_message = self._on_message
            self._client.connect(self.broker)
            self._client.subscribe(self.topic)
            self._client.loop_start()
            logger.info(f"MQTT motion sensor subscribed to {self.topic}")
        except ImportError:
            logger.warning("paho-mqtt not installed. Run: pip install paho-mqtt")
        except Exception as e:
            logger.error(f"MQTT error: {e}")

    def stop(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def _on_message(self, client, userdata, message):
        try:
            payload = message.payload.decode()
            # Handle common motion sensor payload formats
            if payload in ("ON", "on", "1", "true", "motion"):
                logger.info(f"MQTT: Motion detected on {message.topic}")
                self.on_motion()
        except Exception as e:
            logger.error(f"MQTT message error: {e}")


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


__all__ = [
    'MotionSensorProvider',
    'NullMotionSensor',
    'GPIOPIRMotionSensor',
    'MQTTMotionSensor',
    'create_motion_sensor',
]
