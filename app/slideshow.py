"""
Raspberry Pi Photo Slideshow

A modular slideshow application with plugin architecture for:
- Monitor power control (CEC, Shelly, GPIO relay, Samsung TV API)
- Motion detection (GPIO PIR, MQTT)
- Remote control input (IR remote, HTTP API, Alexa)

Each concern has an abstract interface that can be implemented by different
backends depending on your hardware setup.
"""

import os
import sys
import pygame
import time
import random
import signal
import threading

# Force immediate log output for systemd
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# =============================================================================
# PATH SETUP - Must be done before importing local modules
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# Add app directory to Python path for local imports
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# =============================================================================
# LOCAL MODULE IMPORTS
# =============================================================================

import paths
paths.init(SCRIPT_DIR)  # Initialize central path config first

from log import logger, set_level
from platform_detect import PLATFORM, VIDEO_CONFIG
from config import load_config
from monitor import create_monitor_control
from motion import create_motion_sensor
from remote.http_api import HTTPAPIRemoteControl
from remote.ir_remote import IRRemoteControl
from remote.alexa import FauxmoRemoteControl
from update import UpdateManager, get_local_version
from utils import resolve_safe_path, get_or_create_welcome_image, prepare_job


# =============================================================================
# SLIDESHOW CLASS
# =============================================================================

class Slideshow:
    """Main slideshow application with pygame display."""

    def __init__(self, config):
        self.config = config
        self.running = True
        self.paused = False
        self.display_duration = config["display_duration"]
        self.fade_steps = config["fade_steps"]

        # Resolve paths safely (supports both relative and absolute, blocks '..')
        self.image_dir = resolve_safe_path(config["image_dir"])
        default_upload = "img/upload"  # Relative default
        self.upload_dir = resolve_safe_path(config.get("upload_dir", default_upload))
        self.current_filter = None

        # Alexa control reference (set externally if enabled)
        self.alexa_control = None

        # Initialize monitor control
        self.monitor = create_monitor_control(config.get("monitor_control", {}))

        # Check for connected display on Raspberry Pi (kmsdrm requires a monitor)
        if PLATFORM == 'raspi':
            display_connected = False
            try:
                # Check DRM connector status
                for connector in os.listdir('/sys/class/drm/'):
                    status_file = f'/sys/class/drm/{connector}/status'
                    if os.path.exists(status_file):
                        with open(status_file) as f:
                            if f.read().strip() == 'connected':
                                display_connected = True
                                break
            except Exception:
                pass
            if not display_connected:
                logger.warning("No display connected! The slideshow requires a monitor.")
                logger.warning("Connect a display via HDMI and restart the service.")
                sys.exit(1)

        # Initialize pygame display (disable audio on WSL2 to avoid ALSA errors)
        if PLATFORM == 'wsl2':
            os.environ['SDL_AUDIODRIVER'] = 'dummy'
        pygame.display.init()
        pygame.init()

        info = pygame.display.Info()
        logger.info(f"Driver: {pygame.display.get_driver()}")
        logger.info(f"Detected resolution: {info.current_w}x{info.current_h}")

        # Use platform-specific display configuration
        if VIDEO_CONFIG.get('fullscreen', True):
            # Fullscreen mode for Raspberry Pi
            pygame.mouse.set_visible(False)
            self.screen = pygame.display.set_mode(
                (info.current_w, info.current_h),
                pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE
            )
        else:
            # Windowed mode for desktop/WSL2 testing
            width, height = VIDEO_CONFIG.get('windowed_size', (1280, 720))
            pygame.display.set_caption("Slideshow - Press Q to quit, Space to pause")
            self.screen = pygame.display.set_mode(
                (width, height),
                pygame.DOUBLEBUF | pygame.RESIZABLE
            )
            logger.info(f"Running in windowed mode: {width}x{height}")

        # WSLg/Wayland workaround: force window to render immediately
        # Without this, the window may stay black for ~20 seconds under WSLg
        self.screen.fill((0, 0, 0))
        pygame.display.flip()
        pygame.event.pump()

        self.width, self.height = self.screen.get_size()
        self.clock = pygame.time.Clock()
        self.fade_surface = pygame.Surface((self.width, self.height)).convert()
        self.fade_surface.fill((0, 0, 0))

        self.playlist = []
        self.current_img = None
        self.current_path = None
        self._skip_requested = False

        self.lock = threading.Lock()

        signal.signal(signal.SIGTERM, self.handle_exit_signal)
        signal.signal(signal.SIGINT, self.handle_exit_signal)

    def handle_exit_signal(self, signum, frame):
        logger.info("Shutdown signal received. Stopping slideshow...")
        self.running = False
        pygame.quit()
        sys.exit(0)

    def get_effective_image_dir(self):
        """Get the directory currently being used for images (may be sample_images fallback)."""
        if self._scan_directory(self.image_dir):
            return self.image_dir
        sample_dir = os.path.join(SCRIPT_DIR, "sample_images")
        if os.path.isdir(sample_dir) and self._scan_directory(sample_dir):
            return sample_dir
        return self.image_dir

    def get_images(self):
        """Get images, optionally filtered by folder. Falls back to sample_images if empty."""
        images = self._scan_directory(self.image_dir)

        # Fallback to sample_images if configured directory is empty or missing
        if not images:
            sample_dir = os.path.join(SCRIPT_DIR, "sample_images")
            if os.path.isdir(sample_dir):
                images = self._scan_directory(sample_dir)
                if images and not hasattr(self, '_sample_warning_shown'):
                    logger.info(f"Using sample images from {sample_dir}")
                    logger.info("Configure image_dir in config.json to use your own photos")
                    self._sample_warning_shown = True

        return images

    def _scan_directory(self, directory):
        """Scan a directory recursively for images."""
        images = []
        if not os.path.isdir(directory):
            return images
        for root, _, files in os.walk(directory):
            if self.current_filter and self.current_filter not in root:
                continue
            for f in files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    images.append(os.path.join(root, f))
        return images

    def fade_transition(self, next_img):
        steps = self.fade_steps
        for i in range(steps, -1, -1):
            alpha = int((i / steps) * 255)
            self.screen.blit(next_img, (0, 0))
            self.fade_surface.set_alpha(alpha)
            self.screen.blit(self.fade_surface, (0, 0))
            pygame.display.flip()
            self.clock.tick(30)

    def get_memory_info(self):
        """Get memory usage information."""
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(':')
                        value = int(parts[1])  # in kB
                        meminfo[key] = value

                total = meminfo.get('MemTotal', 0)
                available = meminfo.get('MemAvailable', 0)
                used = total - available
                return {
                    "total_mb": round(total / 1024),
                    "used_mb": round(used / 1024),
                    "available_mb": round(available / 1024),
                    "percent_used": round(used / total * 100) if total > 0 else 0
                }
        except:
            return None

    def get_status(self):
        with self.lock:
            status = {
                "running": self.running,
                "paused": self.paused,
                "monitor_on": self.monitor.is_on,
                "display_duration": self.display_duration,
                "current_image": self.current_path,
                "filter": self.current_filter,
                "playlist_size": len(self.playlist)
            }
            mem = self.get_memory_info()
            if mem:
                status["memory"] = mem
            return status

    def set_duration(self, seconds):
        with self.lock:
            self.display_duration = max(1, min(300, seconds))
            logger.info(f"Display duration set to {self.display_duration}s")

    def set_filter(self, folder_filter):
        with self.lock:
            self.current_filter = folder_filter
            self.playlist = []
            logger.info(f"Filter set to: {folder_filter}")

    def clear_filter(self):
        with self.lock:
            self.current_filter = None
            self.playlist = []
            logger.info("Filter cleared")

    def pause(self):
        with self.lock:
            self.paused = True
            logger.info("Slideshow paused")

    def resume(self):
        with self.lock:
            self.paused = False
            logger.info("Slideshow resumed")

    def skip(self):
        with self.lock:
            self._skip_requested = True
            logger.info("Skipping to next image")

    def _handle_pygame_events(self):
        """Process pygame events (keyboard, window close, resize)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    if self.paused:
                        self.resume()
                    else:
                        self.pause()
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_n:
                    self.skip()
                elif event.key == pygame.K_UP:
                    self.set_duration(self.display_duration + 5)
                elif event.key == pygame.K_DOWN:
                    self.set_duration(self.display_duration - 5)
                elif event.key == pygame.K_f:
                    # Toggle fullscreen in desktop mode
                    if not VIDEO_CONFIG.get('fullscreen', True):
                        pygame.display.toggle_fullscreen()
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize
                self.width, self.height = event.w, event.h
                self.screen = pygame.display.set_mode(
                    (self.width, self.height),
                    pygame.DOUBLEBUF | pygame.RESIZABLE
                )
                self.fade_surface = pygame.Surface((self.width, self.height)).convert()
                self.fade_surface.fill((0, 0, 0))
                # Rescale current image if we have one
                if self.current_img:
                    self.current_img = pygame.transform.scale(
                        self.current_img, (self.width, self.height)
                    ).convert()
                    self.screen.blit(self.current_img, (0, 0))
                    pygame.display.flip()

    def show_welcome_screen(self, url, duration=20):
        """Show welcome screen with QR code for the given duration."""
        # Get Alexa device name if enabled
        alexa_device_name = None
        if self.alexa_control:
            alexa_device_name = self.alexa_control.device_name

        welcome_path = get_or_create_welcome_image(url, alexa_device_name=alexa_device_name)
        if not welcome_path:
            return

        try:
            img = pygame.image.load(welcome_path)
            img = pygame.transform.scale(img, (self.width, self.height)).convert()
        except Exception as e:
            logger.error(f"Error loading welcome image: {e}")
            return

        # Display welcome screen
        self.screen.blit(img, (0, 0))
        pygame.display.flip()
        pygame.event.pump()
        logger.info(f"Showing welcome screen for {duration}s - {url}")

        # Wait for duration, but stay responsive
        elapsed = 0
        while elapsed < duration and self.running:
            self._handle_pygame_events()
            time.sleep(0.1)
            elapsed += 0.1

    def run(self, server_url=None):
        # Show welcome screen first if we have a server URL
        if server_url:
            self.show_welcome_screen(server_url)

        while self.running:
            # Process pygame events (essential for desktop mode)
            self._handle_pygame_events()

            if self.paused:
                time.sleep(0.1)
                continue

            if not self.playlist:
                self.playlist = self.get_images()
                if not self.playlist:
                    logger.warning("No images found, waiting...")
                    time.sleep(5)
                    continue
                random.shuffle(self.playlist)

            path = self.playlist.pop(0)
            self.current_path = path

            try:
                img = pygame.image.load(path)
                img = pygame.transform.scale(img, (self.width, self.height)).convert()
            except Exception as e:
                logger.error(f"Error loading {path}: {e}")
                continue

            if self.current_img is None:
                self.screen.blit(img, (0, 0))
                pygame.display.flip()
                pygame.event.pump()  # WSLg/Wayland: process events to show first image
            else:
                self.fade_transition(img)

            self.current_img = img

            self._skip_requested = False
            elapsed = 0
            while elapsed < self.display_duration and self.running and not self._skip_requested:
                self._handle_pygame_events()  # Keep processing events during display
                if self.paused:
                    time.sleep(0.1)
                    continue
                time.sleep(0.1)
                elapsed += 0.1


# =============================================================================
# MAIN
# =============================================================================

def parse_args():
    """Parse command line arguments for testing/development."""
    import argparse
    parser = argparse.ArgumentParser(description='Photo Slideshow')
    parser.add_argument('--image-dir', '-i', type=str,
                        help='Override image directory')
    parser.add_argument('--config', '-c', type=str,
                        help='Path to config file')
    parser.add_argument('--duration', '-d', type=int,
                        help='Override display duration (seconds)')
    parser.add_argument('--fullscreen', '-f', action='store_true',
                        help='Force fullscreen mode')
    parser.add_argument('--windowed', '-w', action='store_true',
                        help='Force windowed mode')
    parser.add_argument('--size', '-s', type=str, default='1280x720',
                        help='Window size for windowed mode (WIDTHxHEIGHT)')
    parser.add_argument('--log-level', '-l', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Log level (default: INFO)')
    return parser.parse_args()


def main():
    args = parse_args()

    # Set log level first
    set_level(args.log_level)

    # Override VIDEO_CONFIG based on command line args
    global VIDEO_CONFIG
    if args.fullscreen:
        VIDEO_CONFIG['fullscreen'] = True
    elif args.windowed:
        VIDEO_CONFIG['fullscreen'] = False
    if args.size:
        try:
            w, h = args.size.split('x')
            VIDEO_CONFIG['windowed_size'] = (int(w), int(h))
        except:
            pass

    # Load config from multiple possible locations
    config_paths = [
        args.config,  # Command line override first
        os.path.join(PROJECT_DIR, "config.json"),  # Parent of app/ (standard location)
        "/home/pi/aide-slideshow/config.json",
        "/home/pi/config.json",
    ]
    config_paths = [p for p in config_paths if p]  # Remove None

    config = None
    for path in config_paths:
        if os.path.exists(path):
            config = load_config(path)
            logger.info(f"Loaded config from {path}")
            break

    if config is None:
        config = load_config("/nonexistent")  # Will use defaults
        logger.info("Using default configuration")

    # Apply command line overrides
    if args.image_dir:
        config['image_dir'] = args.image_dir
        logger.info(f"Image directory overridden to: {args.image_dir}")
    if args.duration:
        config['display_duration'] = args.duration
        logger.info(f"Display duration overridden to: {args.duration}s")

    # Initialize update manager
    update_config = config.get("update", {})
    update_manager = UpdateManager(update_config)
    logger.info(f"Version: {get_local_version()}")

    # Check if we need to verify a pending update
    if update_manager._state.get("pending_verification"):
        logger.info("Update pending verification - will confirm after 60s stable operation")

        def delayed_confirm():
            time.sleep(60)
            if update_manager._state.get("pending_verification"):
                result = update_manager.confirm_update()
                logger.info(f"Update verification: {result.get('message', 'done')}")

        confirm_thread = threading.Thread(target=delayed_confirm, daemon=True)
        confirm_thread.start()

    # Create slideshow
    app = Slideshow(config)

    # Initialize remote control providers
    remote_controls = []
    rc_config = config.get("remote_control", {})

    # HTTP API
    http_config = rc_config.get("http_api", {})
    server_url = None
    if http_config.get("enabled", True):
        http_api = HTTPAPIRemoteControl(
            http_config, app,
            update_manager=update_manager,
            prepare_job=prepare_job,
            platform=PLATFORM
        )
        http_api.start()
        remote_controls.append(http_api)
        server_url = http_api._get_server_url()

    # IR Remote
    ir_config = rc_config.get("ir_remote", {})
    if ir_config.get("enabled", False):
        ir_remote = IRRemoteControl(ir_config, app)
        ir_remote.start()
        remote_controls.append(ir_remote)

    # Alexa control via Fauxmo (disabled by default, doesn't work in WSL2)
    alexa_config = rc_config.get("alexa", {})
    if alexa_config.get("enabled", False):
        alexa = FauxmoRemoteControl(alexa_config, app)
        alexa.start()
        remote_controls.append(alexa)
        app.alexa_control = alexa  # Make accessible for welcome screen
    else:
        logger.debug("Alexa voice control: disabled")

    # Initialize motion sensor
    motion_config = config.get("motion_sensor", {})
    motion_sensor = create_motion_sensor(
        motion_config,
        on_motion=lambda: app.monitor.turn_on(),
        on_idle=lambda: app.monitor.turn_off()
    )
    motion_sensor.start()

    # Run slideshow (with welcome screen if server URL available)
    try:
        app.run(server_url=server_url)
    finally:
        # Cleanup
        motion_sensor.stop()
        for rc in remote_controls:
            rc.stop()


if __name__ == "__main__":
    main()
