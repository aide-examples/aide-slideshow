"""
Central path configuration for applications.

Provides base path management that applications can extend with their own paths.
Call init() once at application startup before importing other modules.

Usage:
    from aide_frame import paths

    # Basic initialization (auto-detects app directory)
    paths.init()

    # Or with explicit directory
    paths.init("/path/to/app")

    # Access paths
    print(paths.APP_DIR)      # app/ directory
    print(paths.PROJECT_DIR)  # Parent of app/

    # Applications can register additional paths
    paths.register("DOCS_DIR", os.path.join(paths.APP_DIR, "docs"))
"""

import os

# Base directories - set by init()
APP_DIR = None         # app/ directory (where the main code lives)
PROJECT_DIR = None     # Parent of app/ (repo root, contains config.json)
STATIC_DIR = None      # app/static/ (common for web apps)
VERSION_FILE = None    # app/VERSION
UPDATE_STATE_DIR = None  # .update/ directory (sibling to app/)

# Application-specific paths (registered via register())
_app_paths = {}

_initialized = False


def init(app_dir=None):
    """
    Initialize all path constants.

    Args:
        app_dir: Path to app/ directory. If None, auto-detects from this file's location.
    """
    global APP_DIR, PROJECT_DIR, STATIC_DIR, VERSION_FILE, UPDATE_STATE_DIR, _initialized

    if app_dir is None:
        # Auto-detect: this file is in app/aide_frame/, so app/ is one level up
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    APP_DIR = app_dir
    PROJECT_DIR = os.path.dirname(app_dir)
    STATIC_DIR = os.path.join(app_dir, "static")
    VERSION_FILE = os.path.join(app_dir, "VERSION")
    UPDATE_STATE_DIR = os.path.join(PROJECT_DIR, ".update")

    _initialized = True


def ensure_initialized():
    """Ensure paths are initialized, auto-init if not."""
    if not _initialized:
        init()


def register(name, path):
    """
    Register an application-specific path.

    Args:
        name: Path name (will be accessible as paths.NAME)
        path: The path value

    Example:
        paths.register("DOCS_DIR", os.path.join(paths.APP_DIR, "docs"))
        print(paths.DOCS_DIR)  # Works after registration
    """
    ensure_initialized()
    _app_paths[name] = path
    # Also set as module attribute for convenience
    globals()[name] = path


def get(name, default=None):
    """
    Get a registered path by name.

    Args:
        name: Path name
        default: Default value if not registered

    Returns:
        Path value or default
    """
    return _app_paths.get(name, globals().get(name, default))


# MIME types for static file serving (shared across modules)
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
    '.md': 'text/markdown; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
    '.xml': 'application/xml',
    '.pdf': 'application/pdf',
}
