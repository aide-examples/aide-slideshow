"""
Central path configuration for the slideshow application.

All path constants are defined here to avoid duplication across modules.
Call init() once at application startup before importing other modules.
"""

import os

# Base directories - set by init()
SCRIPT_DIR = None      # app/ directory
PROJECT_DIR = None     # Parent of app/ (repo root)
STATIC_DIR = None      # app/static/
DOCS_DIR = None        # app/docs/
WELCOME_DIR = None     # app/.welcome_cache/
VERSION_FILE = None    # app/VERSION
UPDATE_STATE_DIR = None  # .update/ directory (sibling to app/)

_initialized = False


def init(script_dir=None):
    """
    Initialize all path constants.

    Args:
        script_dir: Path to app/ directory. If None, auto-detects from this file's location.
    """
    global SCRIPT_DIR, PROJECT_DIR, STATIC_DIR, DOCS_DIR, WELCOME_DIR, VERSION_FILE, UPDATE_STATE_DIR, _initialized

    if script_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))

    SCRIPT_DIR = script_dir
    PROJECT_DIR = os.path.dirname(script_dir)
    STATIC_DIR = os.path.join(script_dir, "static")
    DOCS_DIR = os.path.join(script_dir, "docs")
    WELCOME_DIR = os.path.join(script_dir, ".welcome_cache")
    VERSION_FILE = os.path.join(script_dir, "VERSION")
    UPDATE_STATE_DIR = os.path.join(PROJECT_DIR, ".update")

    _initialized = True


def ensure_initialized():
    """Ensure paths are initialized, auto-init if not."""
    if not _initialized:
        init()


# MIME types for static file serving (shared across modules)
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.md': 'text/markdown; charset=utf-8',
}
