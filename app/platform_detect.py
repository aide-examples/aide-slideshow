"""
Platform detection and video driver configuration.

Detects the runtime platform (Raspberry Pi, WSL2, Linux desktop, macOS, Windows)
and configures the appropriate SDL video driver.
"""

import os


def detect_platform():
    """
    Detect the runtime platform to configure appropriate drivers.

    Returns:
        str: One of 'raspi', 'wsl2', 'linux_desktop', 'macos', 'windows'
    """
    import platform

    system = platform.system().lower()

    if system == 'darwin':
        return 'macos'
    elif system == 'windows':
        return 'windows'
    elif system == 'linux':
        # Check for WSL2
        try:
            with open('/proc/version', 'r') as f:
                version_info = f.read().lower()
                if 'microsoft' in version_info or 'wsl' in version_info:
                    return 'wsl2'
        except:
            pass

        # Check for Raspberry Pi
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().lower()
                if 'raspberry pi' in model:
                    return 'raspi'
        except:
            pass

        # Check if we have kmsdrm capability (headless server or direct console)
        if os.path.exists('/dev/dri/card0'):
            # Could be raspi-like or a desktop with DRM
            # Check if we're running in a graphical session
            if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
                return 'linux_desktop'
            else:
                # Running on console, might work with kmsdrm
                return 'raspi'

        return 'linux_desktop'

    return 'unknown'


def configure_video_driver(platform_type):
    """
    Configure SDL video driver based on detected platform.

    Args:
        platform_type: Result from detect_platform()

    Returns:
        dict: Configuration options for display initialization
    """
    config = {
        'fullscreen': True,
        'windowed_size': (1280, 720),  # Fallback for windowed mode
    }

    if platform_type == 'raspi':
        # Raspberry Pi: use kmsdrm for direct framebuffer access
        os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
        os.environ["SDL_NOMOUSE"] = "1"
        os.environ["SDL_DRM_DEVICE"] = "/dev/dri/card0"
        config['driver'] = 'kmsdrm'
        print("Platform: Raspberry Pi - using kmsdrm driver")

    elif platform_type == 'wsl2':
        # WSL2: use x11 (requires X server like VcXsrv or WSLg)
        # WSLg provides built-in Wayland/X11 support in Windows 11
        # Disable audio on WSL2 (ALSA errors)
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        if os.environ.get('WAYLAND_DISPLAY'):
            os.environ["SDL_VIDEODRIVER"] = "wayland"
            config['driver'] = 'wayland'
            print("Platform: WSL2 - using Wayland driver (WSLg)")
        else:
            os.environ["SDL_VIDEODRIVER"] = "x11"
            config['driver'] = 'x11'
            print("Platform: WSL2 - using X11 driver")
        # In WSL2, we might want windowed mode for easier testing
        config['fullscreen'] = False

    elif platform_type == 'linux_desktop':
        # Linux desktop: prefer Wayland, fallback to X11
        if os.environ.get('WAYLAND_DISPLAY'):
            os.environ["SDL_VIDEODRIVER"] = "wayland"
            config['driver'] = 'wayland'
            print("Platform: Linux desktop - using Wayland driver")
        else:
            os.environ["SDL_VIDEODRIVER"] = "x11"
            config['driver'] = 'x11'
            print("Platform: Linux desktop - using X11 driver")
        config['fullscreen'] = False

    elif platform_type == 'macos':
        # macOS: use cocoa (default)
        os.environ["SDL_VIDEODRIVER"] = "cocoa"
        config['driver'] = 'cocoa'
        config['fullscreen'] = False
        print("Platform: macOS - using Cocoa driver")

    elif platform_type == 'windows':
        # Windows: use windows driver (default)
        os.environ["SDL_VIDEODRIVER"] = "windows"
        config['driver'] = 'windows'
        config['fullscreen'] = False
        print("Platform: Windows - using Windows driver")

    else:
        # Unknown: let SDL choose
        print(f"Platform: Unknown ({platform_type}) - using SDL default driver")
        config['fullscreen'] = False

    return config


# Detect platform and configure video driver at import time
# This MUST happen before pygame is imported elsewhere
PLATFORM = detect_platform()
VIDEO_CONFIG = configure_video_driver(PLATFORM)
