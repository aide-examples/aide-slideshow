# Platform Detection

**Module:** `platform_detect.py`

Detecting runtime environment (Raspberry Pi, WSL2, desktop).

## Purpose

The slideshow needs to run on both:
- **Raspberry Pi** (production) - fullscreen kmsdrm mode, real GPIO/CEC
- **Development machines** (WSL2, Linux, macOS, Windows) - windowed mode, simulated hardware

Platform detection enables this by providing information about the current environment.

## API

```python
from platform_detect import is_raspberry_pi, is_wsl2, get_platform_info
```

| Function | Returns | Description |
|----------|---------|-------------|
| `is_raspberry_pi()` | `bool` | True if running on Raspberry Pi |
| `is_wsl2()` | `bool` | True if running in WSL2 |
| `get_platform_info()` | `dict` | Detailed platform information |

## Platform Matrix

| Platform | `is_raspberry_pi()` | `is_wsl2()` | Video Driver | Display Mode |
|----------|---------------------|-------------|--------------|--------------|
| Raspberry Pi | `True` | `False` | `kmsdrm` | Fullscreen |
| WSL2 | `False` | `True` | `wayland`/`x11` | Windowed |
| Linux Desktop | `False` | `False` | `wayland`/`x11` | Windowed |
| macOS | `False` | `False` | `cocoa` | Windowed |
| Windows | `False` | `False` | `windows` | Windowed |

## Implementation

Detection is based on:
- `/proc/device-tree/model` - contains "Raspberry Pi" on Pi hardware
- `/proc/version` - contains "microsoft" on WSL2
- `platform.system()` - OS detection

## Usage in Slideshow

```python
from platform_detect import is_raspberry_pi

if is_raspberry_pi():
    # Use kmsdrm driver, fullscreen
    os.environ['SDL_VIDEODRIVER'] = 'kmsdrm'
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
else:
    # Windowed mode for development
    screen = pygame.display.set_mode((1280, 720))
```

## Performance

The detection adds negligible overhead:
- **Startup:** ~1-2ms one-time cost (reads two small `/proc` files)
- **Memory:** <1KB (cached in global variables)
- **Runtime:** No impact (detection runs once at startup)
