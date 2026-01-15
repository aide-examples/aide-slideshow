"""
Utility functions for the slideshow application.

Contains:
- Welcome image generation
- Image preparation job management
"""

import os
import threading

from aide_frame import paths
from aide_frame.log import logger


# =============================================================================
# WELCOME IMAGE GENERATION
# =============================================================================

def url_to_filename(url):
    """Convert URL to a safe filename."""
    # Remove protocol and replace special chars
    safe = url.replace("://", "_").replace("/", "_").replace(":", "_").replace(".", "_")
    return f"{safe}.png"


def generate_welcome_image(url, output_path, width=1920, height=1080, alexa_device_name=None):
    """Generate a welcome image with QR code pointing to the control UI.

    Args:
        url: URL to the control UI
        output_path: Path to save the image
        width: Image width in pixels
        height: Image height in pixels
        alexa_device_name: If set, show Alexa voice control hint
    """
    from aide_frame import qrcode_utils

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        logger.warning(f"Cannot generate welcome image: {e}")
        logger.info("Install with: pip install pillow")
        return False

    # Generate QR code using framework utility (white on black for dark background)
    qr_img = qrcode_utils.generate_qr_image(url, fill_color="white", back_color="black")
    if qr_img is None:
        logger.warning("Cannot generate welcome image: qrcode library not available")
        return False

    # Create main image (dark background)
    img = Image.new('RGB', (width, height), color=(20, 20, 30))
    draw = ImageDraw.Draw(img)

    # Scale QR code to reasonable size (about 1/3 of height)
    qr_size = min(height // 3, 360)
    qr_img = qrcode_utils.resize_qr_image(qr_img, (qr_size, qr_size))

    # Position QR code (center-left area)
    qr_x = width // 4 - qr_size // 2
    qr_y = height // 2 - qr_size // 2
    img.paste(qr_img, (qr_x, qr_y))

    # Add text - try to use a nice font, fall back to default
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        url_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        text_font = title_font
        url_font = title_font
        small_font = title_font

    # Text position (right side of QR code)
    text_x = width // 2
    text_y = height // 2 - 100

    # Draw text
    draw.text((text_x, text_y), "Control the Slideshow", font=title_font, fill=(255, 255, 255))
    draw.text((text_x, text_y + 70), "Scan the QR code or visit:", font=text_font, fill=(200, 200, 200))
    draw.text((text_x, text_y + 120), url, font=url_font, fill=(100, 180, 255))

    # Add Alexa hint if enabled
    if alexa_device_name:
        alexa_text = f'"Alexa, turn on/off {alexa_device_name}"'
        draw.text((text_x, text_y + 180), "Or use voice control:", font=text_font, fill=(200, 200, 200))
        draw.text((text_x, text_y + 225), alexa_text, font=small_font, fill=(255, 180, 100))

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save image
    img.save(output_path, "PNG")
    logger.info(f"Generated welcome image: {output_path}")
    return True


def get_or_create_welcome_image(url, alexa_device_name=None, force=False):
    """Get path to welcome image, creating it if needed for this URL.

    Args:
        url: URL to the control UI
        alexa_device_name: If set, include Alexa voice control hint
        force: If True, regenerate even if cached image exists
    """
    paths.ensure_initialized()
    if paths.WELCOME_DIR is None:
        return None

    # Include alexa in filename to regenerate if alexa status changes
    suffix = f"_alexa_{alexa_device_name}" if alexa_device_name else ""
    filename = url_to_filename(url + suffix)
    image_path = os.path.join(paths.WELCOME_DIR, filename)

    # Check if image already exists for this URL + alexa config
    if os.path.exists(image_path) and not force:
        # Verify the image is valid (not empty/corrupt)
        try:
            size = os.path.getsize(image_path)
            if size > 1000:  # Valid PNG should be > 1KB
                logger.debug(f"Using cached welcome image: {filename}")
                return image_path
            else:
                logger.warning(f"Cached welcome image too small ({size} bytes), regenerating")
        except OSError:
            pass

    # Clean up old welcome images (different URLs or alexa configs)
    if os.path.exists(paths.WELCOME_DIR):
        for old_file in os.listdir(paths.WELCOME_DIR):
            if old_file.endswith('.png'):
                old_path = os.path.join(paths.WELCOME_DIR, old_file)
                try:
                    os.remove(old_path)
                    logger.debug(f"Removed old welcome image: {old_file}")
                except OSError:
                    pass

    # Generate new image
    if generate_welcome_image(url, image_path, alexa_device_name=alexa_device_name):
        return image_path
    return None


# =============================================================================
# IMAGE PREPARATION JOB
# =============================================================================

# Lazy-loaded module reference
_imgPrepare = None


def get_imgPrepare():
    """Lazy import of imgPrepare module to avoid loading PIL until needed."""
    global _imgPrepare
    if _imgPrepare is None:
        try:
            import imgPrepare as module
            _imgPrepare = module
            logger.debug("imgPrepare module loaded")
        except ImportError as e:
            logger.warning(f"Failed to import imgPrepare: {e}")
            return None
    return _imgPrepare


class ImagePrepareJob:
    """Manages a background image preparation job."""

    def __init__(self):
        self.running = False
        self.cancelled = False
        self.progress = None  # Current PrepareProgress
        self.counts = {"processed": 0, "exists": 0, "error": 0}
        self.error = None
        self._thread = None
        self._lock = threading.Lock()

    def start(self, config):
        """Start processing in background thread."""
        if self.running:
            return False, "Job already running"

        module = get_imgPrepare()
        if module is None:
            return False, "imgPrepare module not available"

        self.running = True
        self.cancelled = False
        self.progress = None
        self.counts = {"processed": 0, "exists": 0, "error": 0}
        self.error = None

        self._thread = threading.Thread(target=self._run, args=(module, config), daemon=True)
        self._thread.start()
        return True, "Job started"

    def _run(self, module, config):
        """Background processing loop."""
        try:
            gen = module.process_folder_iter(config)
            for progress in gen:
                if self.cancelled:
                    break
                with self._lock:
                    self.progress = progress
                    self.counts[progress.status] = self.counts.get(progress.status, 0) + 1
        except Exception as e:
            self.error = str(e)
            logger.error(f"ImagePrepareJob error: {e}")
        finally:
            self.running = False

    def cancel(self):
        """Request cancellation of running job."""
        self.cancelled = True

    def get_status(self):
        """Get current job status."""
        with self._lock:
            if self.progress:
                return {
                    "running": self.running,
                    "cancelled": self.cancelled,
                    "current": self.progress.current,
                    "total": self.progress.total,
                    "percent": round(100 * self.progress.current / self.progress.total, 1) if self.progress.total > 0 else 0,
                    "current_file": self.progress.filepath,
                    "counts": self.counts.copy(),
                    "error": self.error,
                }
            else:
                return {
                    "running": self.running,
                    "cancelled": self.cancelled,
                    "current": 0,
                    "total": 0,
                    "percent": 0,
                    "current_file": None,
                    "counts": self.counts.copy(),
                    "error": self.error,
                }


# Global job instance (only one job at a time)
prepare_job = ImagePrepareJob()


__all__ = [
    'url_to_filename',
    'generate_welcome_image',
    'get_or_create_welcome_image',
    'get_imgPrepare',
    'ImagePrepareJob',
    'prepare_job',
]
