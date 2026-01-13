"""
Central logging configuration for the slideshow application.

Provides a simple logging interface with levels:
- DEBUG: Detailed information for debugging
- INFO: General operational messages
- WARNING: Something unexpected but not critical
- ERROR: Something failed

Usage:
    from log import logger
    logger.info("Server started on port 8080")
    logger.warning("Config file not found, using defaults")
    logger.error("Failed to connect to TV")
"""

import logging
import sys

# Create the main logger
logger = logging.getLogger("slideshow")
logger.setLevel(logging.DEBUG)

# Console handler with formatting
_handler = logging.StreamHandler(sys.stdout)
_handler.setLevel(logging.DEBUG)

# Format: "INFO: Message" or "WARNING: Message"
_formatter = logging.Formatter('%(levelname)s: %(message)s')
_handler.setFormatter(_formatter)

logger.addHandler(_handler)

# Prevent propagation to root logger
logger.propagate = False


def set_level(level: str):
    """
    Set the logging level.

    Args:
        level: One of 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    """
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
    }
    logger.setLevel(level_map.get(level.upper(), logging.INFO))
    _handler.setLevel(level_map.get(level.upper(), logging.INFO))


def set_quiet():
    """Only show warnings and errors."""
    set_level('WARNING')


def set_verbose():
    """Show all messages including debug."""
    set_level('DEBUG')


# Convenience aliases
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error


__all__ = [
    'logger',
    'set_level',
    'set_quiet',
    'set_verbose',
    'debug',
    'info',
    'warning',
    'error',
]
