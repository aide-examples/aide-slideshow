# Extending

Adding new monitor, motion, or remote control providers.

## Adding a New Provider

Each concern (monitor control, motion detection, remote control) uses a plugin architecture. You can add new providers by implementing the appropriate abstract base class.

### Steps

1. **Create provider class** implementing the appropriate abstract base class
2. **Import and export** in the package's `__init__.py`
3. **Add to factory function**
4. **Add configuration** in `DEFAULT_CONFIG` in `app/config.py`
5. **Document** in the appropriate docs file

## Example: Adding a Monitor Provider

### 1. Create Provider Class

```python
# app/monitor/tasmota.py
import requests
from log import logger
from . import MonitorControlProvider

class TasmotaMonitorControl(MonitorControlProvider):
    """Control monitor via Tasmota smart plug."""

    def __init__(self, config):
        super().__init__()
        self.ip = config.get("ip")
        if not self.ip:
            raise ValueError("Tasmota IP address required")

    def turn_on(self) -> bool:
        try:
            requests.get(f"http://{self.ip}/cm?cmnd=Power%20On", timeout=5)
            self._is_on = True
            logger.info("Tasmota: Monitor ON")
            return True
        except Exception as e:
            logger.error(f"Tasmota: Failed to turn on: {e}")
            return False

    def turn_off(self) -> bool:
        try:
            requests.get(f"http://{self.ip}/cm?cmnd=Power%20Off", timeout=5)
            self._is_on = False
            logger.info("Tasmota: Monitor OFF")
            return True
        except Exception as e:
            logger.error(f"Tasmota: Failed to turn off: {e}")
            return False
```

### 2. Add to Factory

```python
# app/monitor/__init__.py
from .tasmota import TasmotaMonitorControl

def create_monitor_control(config):
    provider = config.get("monitor_control", {}).get("provider", "none")

    # ... existing providers ...

    elif provider == "tasmota":
        return TasmotaMonitorControl(config.get("monitor_control", {}).get("tasmota", {}))

    else:
        return NullMonitorControl()
```

### 3. Add Configuration

```python
# app/config.py - add to DEFAULT_CONFIG
DEFAULT_CONFIG = {
    # ...
    "monitor_control": {
        "provider": "none",
        # ... existing providers ...
        "tasmota": {
            "ip": None
        }
    }
}
```

### 4. Document

Add documentation to `docs/implementation/monitor-control.md`.

## Provider Base Classes

### MonitorControlProvider

```python
# app/monitor/__init__.py
class MonitorControlProvider(ABC):
    def __init__(self):
        self._is_on = True

    @property
    def is_on(self) -> bool:
        return self._is_on

    @abstractmethod
    def turn_on(self) -> bool:
        """Turn monitor on. Returns True on success."""
        pass

    @abstractmethod
    def turn_off(self) -> bool:
        """Turn monitor off. Returns True on success."""
        pass
```

### MotionSensorProvider

```python
# app/motion/__init__.py
class MotionSensorProvider(ABC):
    def __init__(self, on_motion=None, on_idle=None):
        self.on_motion = on_motion  # Callback for motion detected
        self.on_idle = on_idle      # Callback for idle timeout

    @abstractmethod
    def start(self):
        """Start monitoring for motion."""
        pass

    @abstractmethod
    def stop(self):
        """Stop monitoring."""
        pass
```

### RemoteControlProvider

```python
# app/remote/__init__.py
class RemoteControlProvider(ABC):
    def __init__(self, slideshow):
        self.slideshow = slideshow

    @abstractmethod
    def start(self):
        """Start listening for commands."""
        pass

    @abstractmethod
    def stop(self):
        """Stop listening."""
        pass

    def execute_action(self, action):
        """Execute a slideshow action by name."""
        # ... implementation ...
```

## File Locations

| Provider Type | Base Class Location | Factory Function |
|---------------|---------------------|------------------|
| Monitor Control | `app/monitor/__init__.py` | `create_monitor_control()` |
| Motion Sensor | `app/motion/__init__.py` | `create_motion_sensor()` |
| Remote Control | `app/remote/__init__.py` | Instantiated in `main()` |

## Testing Your Provider

1. Create a minimal config that uses your provider
2. Run with debug logging: `python3 slideshow.py --log-level DEBUG`
3. Test all methods manually via the HTTP API or keyboard
4. Check error handling (disconnect device, invalid config, etc.)
