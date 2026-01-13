"""
Utility functions for the slideshow application.

Contains:
- Path security functions
- File loading utilities
- Welcome image generation
- Image preparation job management
"""

import os
import threading

from aide_frame import paths
from aide_frame.log import logger


# =============================================================================
# PATH SECURITY
# =============================================================================

class PathSecurityError(ValueError):
    """Raised when a path contains unsafe traversal sequences."""
    pass


def resolve_safe_path(path_str, base_dir=None):
    """
    Resolve a path safely, rejecting path traversal attempts.

    Args:
        path_str: Path from config (relative or absolute)
        base_dir: Base directory for relative paths (defaults to PROJECT_DIR)

    Returns:
        Absolute path string

    Raises:
        PathSecurityError: If path contains '..' traversal sequences
    """
    paths.ensure_initialized()
    if base_dir is None:
        base_dir = paths.PROJECT_DIR

    # Block path traversal sequences
    if '..' in path_str:
        raise PathSecurityError(f"Path traversal '..' not allowed in path: {path_str}")

    # Resolve relative paths against base_dir
    if os.path.isabs(path_str):
        resolved = os.path.normpath(path_str)
    else:
        resolved = os.path.normpath(os.path.join(base_dir, path_str))

    # Double-check the resolved path doesn't escape (belt and suspenders)
    # This catches edge cases like paths with encoded sequences
    if '..' in resolved:
        raise PathSecurityError(f"Resolved path contains traversal: {resolved}")

    return resolved


# =============================================================================
# FILE LOADING
# =============================================================================

def load_static_file(filename, binary=False):
    """Load a file from the static directory."""
    paths.ensure_initialized()
    if paths.STATIC_DIR is None:
        return None
    filepath = os.path.join(paths.STATIC_DIR, filename)
    try:
        mode = 'rb' if binary else 'r'
        encoding = None if binary else 'utf-8'
        with open(filepath, mode, encoding=encoding) as f:
            return f.read()
    except FileNotFoundError:
        return None


def load_readme():
    """Load README.md from the app directory."""
    paths.ensure_initialized()
    if paths.APP_DIR is None:
        return "# README not found"
    readme_path = os.path.join(paths.APP_DIR, "README.md")
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "# README not found\n\nThe README.md file was not found in the project directory."


# =============================================================================
# DOCUMENTATION
# =============================================================================

def list_docs():
    """List all markdown files in docs/ directory recursively.

    Returns:
        List of relative paths like ["index.md", "hardware/monitor-control.md", ...]
    """
    paths.ensure_initialized()
    if paths.DOCS_DIR is None or not os.path.isdir(paths.DOCS_DIR):
        return []

    docs = []
    for root, _, files in os.walk(paths.DOCS_DIR):
        for f in files:
            if f.endswith('.md'):
                rel_path = os.path.relpath(os.path.join(root, f), paths.DOCS_DIR)
                docs.append(rel_path)
    return sorted(docs)


def load_doc(filename, framework=False):
    """Load a specific markdown file from docs/ or aide_frame/docs/.

    Args:
        filename: Relative path within docs/, e.g. "hardware/monitor-control.md"
        framework: If True, load from aide_frame/docs/ instead of docs/

    Returns:
        File content as string, or None if not found or invalid path
    """
    paths.ensure_initialized()

    # Choose base directory
    if framework:
        base_dir = paths.get("AIDE_FRAME_DOCS_DIR")
    else:
        base_dir = paths.DOCS_DIR

    if base_dir is None:
        return None

    # Security: block path traversal
    if '..' in filename:
        logger.warning(f"Path traversal attempt blocked: {filename}")
        return None

    filepath = os.path.join(base_dir, filename)

    # Verify the resolved path is still within base_dir
    real_path = os.path.realpath(filepath)
    real_base = os.path.realpath(base_dir)
    if not real_path.startswith(real_base + os.sep) and real_path != real_base:
        logger.warning(f"Path escape attempt blocked: {filename}")
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_title_and_description(filepath):
    """Extract the first H1 heading and first sentence from a markdown file.

    Args:
        filepath: Full path to the markdown file

    Returns:
        Tuple of (title, description). Description is the first sentence
        after the H1 heading, or None if not found.
    """
    title = None
    description = None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            found_title = False
            collecting_desc = False
            desc_lines = []

            for line in f:
                # Find title (first H1)
                if not found_title and line.startswith('# '):
                    title = line[2:].strip()
                    found_title = True
                    collecting_desc = True
                    continue

                # Collect description after title
                if collecting_desc:
                    stripped = line.strip()

                    # Skip empty lines right after title
                    if not stripped and not desc_lines:
                        continue

                    # Stop at next heading, code block, or horizontal rule
                    if stripped.startswith('#') or stripped.startswith('```') or stripped.startswith('---'):
                        break

                    # Skip certain markdown elements
                    if stripped.startswith('|') or stripped.startswith('-') or stripped.startswith('*'):
                        if not desc_lines:  # Skip if we haven't started collecting
                            continue
                        break  # Stop if we hit a list/table after text

                    if stripped:
                        desc_lines.append(stripped)

                    # Check if we have a complete sentence
                    combined = ' '.join(desc_lines)
                    # Find first sentence ending with . ! or ?
                    for i, char in enumerate(combined):
                        if char in '.!?' and i > 10:  # Minimum sentence length
                            # Make sure it's not an abbreviation (e.g., "e.g.")
                            if i + 1 >= len(combined) or combined[i + 1] in ' \n':
                                description = combined[:i + 1]
                                break
                    if description:
                        break

    except (FileNotFoundError, IOError):
        pass

    # Fallback for title: filename without extension, formatted
    if not title:
        basename = os.path.basename(filepath).replace('.md', '')
        title = basename.replace('-', ' ').replace('_', ' ').title()

    return title, description


def extract_title(filepath):
    """Extract the first H1 heading from a markdown file.

    Args:
        filepath: Full path to the markdown file

    Returns:
        Title string (from first H1 or fallback to filename)
    """
    title, _ = extract_title_and_description(filepath)
    return title


def get_docs_structure():
    """Get documentation structure with sections, titles, and descriptions.

    Returns a structured list of sections, each containing documents with
    their paths, titles (from H1), and descriptions (first sentence after H1).

    Sections are organized in two groups:
    1. AIDE Frame (from aide_frame/docs/): Framework documentation
    2. Application docs (from docs/): Slideshow-specific documentation

    Within each section, index.md comes first, rest alphabetically sorted.

    Returns:
        dict with "sections" list, each doc has: path, title, description (optional)
              Framework docs have "framework": true flag
    """
    paths.ensure_initialized()
    sections = []

    # Helper to build AIDE Frame section
    def build_framework_section():
        frame_docs_dir = paths.get("AIDE_FRAME_DOCS_DIR")
        if not frame_docs_dir or not os.path.isdir(frame_docs_dir):
            return None
        docs = []
        for f in os.listdir(frame_docs_dir):
            if f.endswith('.md'):
                filepath = os.path.join(frame_docs_dir, f)
                if os.path.isfile(filepath):
                    title, desc = extract_title_and_description(filepath)
                    doc_entry = {"path": f, "title": title, "framework": True}
                    if desc:
                        doc_entry["description"] = desc
                    docs.append(doc_entry)
        if docs:
            docs.sort(key=lambda d: (0 if d["path"].endswith("index.md") else 1, d["path"]))
            return {"name": "AIDE Frame", "docs": docs, "framework": True}
        return None

    # ==========================================================================
    # Application documentation (docs/)
    # ==========================================================================
    if paths.DOCS_DIR is None or not os.path.isdir(paths.DOCS_DIR):
        frame_section = build_framework_section()
        if frame_section:
            sections.append(frame_section)
        return {"sections": sections}

    # Define section order and their paths
    # Tuple: (section_path, section_name, extra_files_path)
    # Use "AIDE_FRAME" as marker for where to insert framework docs
    section_defs = [
        (None, "Overview", None),
        ("requirements", "Requirements", None),
        ("platform", "Platform", None),
        ("implementation", "Implementation", None),
        ("implementation/slideshow", "Application Components", None),
        ("AIDE_FRAME", None, None),  # Marker for AIDE Frame section
        ("deployment", "Deployment", None),
        ("development", "Development", None),
    ]

    for section_path, section_name, extra_path in section_defs:
        # Handle AIDE Frame marker
        if section_path == "AIDE_FRAME":
            frame_section = build_framework_section()
            if frame_section:
                sections.append(frame_section)
            continue

        docs = []

        if section_path is None:
            # Root level: only .md files directly in docs/
            scan_dir = paths.DOCS_DIR
            for f in os.listdir(scan_dir):
                if f.endswith('.md'):
                    filepath = os.path.join(scan_dir, f)
                    if os.path.isfile(filepath):
                        title, desc = extract_title_and_description(filepath)
                        doc_entry = {"path": f, "title": title}
                        if desc:
                            doc_entry["description"] = desc
                        docs.append(doc_entry)
        else:
            # Include extra index.md from parent directory if specified
            if extra_path:
                extra_index = os.path.join(paths.DOCS_DIR, extra_path, "index.md")
                if os.path.isfile(extra_index):
                    title, desc = extract_title_and_description(extra_index)
                    rel_path = extra_path + "/index.md"
                    doc_entry = {"path": rel_path, "title": title}
                    if desc:
                        doc_entry["description"] = desc
                    docs.append(doc_entry)

            # Subdirectory
            scan_dir = os.path.join(paths.DOCS_DIR, section_path)
            if os.path.isdir(scan_dir):
                for f in os.listdir(scan_dir):
                    if f.endswith('.md'):
                        filepath = os.path.join(scan_dir, f)
                        if os.path.isfile(filepath):
                            title, desc = extract_title_and_description(filepath)
                            rel_path = os.path.join(section_path, f).replace(os.sep, '/')
                            doc_entry = {"path": rel_path, "title": title}
                            if desc:
                                doc_entry["description"] = desc
                            docs.append(doc_entry)

        if docs:
            # Sort: index.md first, then alphabetically by path
            docs.sort(key=lambda d: (0 if d["path"].endswith("index.md") else 1, d["path"]))
            sections.append({"name": section_name, "docs": docs})

    return {"sections": sections}


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

    Only imports qrcode library when actually needed (lazy loading).

    Args:
        url: URL to the control UI
        output_path: Path to save the image
        width: Image width in pixels
        height: Image height in pixels
        alexa_device_name: If set, show Alexa voice control hint
    """
    try:
        # Lazy import - only load when needed
        import qrcode
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        logger.warning(f"Cannot generate welcome image: {e}")
        logger.info("Install with: pip install qrcode[pil]")
        return False

    # Create QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="white", back_color="black")

    # Create main image (dark background)
    img = Image.new('RGB', (width, height), color=(20, 20, 30))
    draw = ImageDraw.Draw(img)

    # Scale QR code to reasonable size (about 1/3 of height)
    qr_size = min(height // 3, 360)
    # Use NEAREST for older Pillow versions (Resampling added in 9.1.0)
    try:
        resample = Image.Resampling.NEAREST
    except AttributeError:
        resample = Image.NEAREST
    qr_img = qr_img.resize((qr_size, qr_size), resample)

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
    except:
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
                except:
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
    'PathSecurityError',
    'resolve_safe_path',
    'load_static_file',
    'load_readme',
    'list_docs',
    'load_doc',
    'extract_title',
    'extract_title_and_description',
    'get_docs_structure',
    'url_to_filename',
    'generate_welcome_image',
    'get_or_create_welcome_image',
    'get_imgPrepare',
    'ImagePrepareJob',
    'prepare_job',
]
