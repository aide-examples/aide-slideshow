# Path Management

Managing application paths with extensible registration.

## Overview

The `paths` module provides centralized path management with:
- Automatic detection of application directory
- Base paths (APP_DIR, PROJECT_DIR, STATIC_DIR, etc.)
- Registration system for app-specific paths
- MIME type mapping for static file serving

## Usage

```python
from aide_frame import paths
import os

# Initialize (auto-detects app directory)
paths.init()

# Or with explicit directory
paths.init("/path/to/app")

# Access base paths
print(paths.APP_DIR)       # /path/to/app
print(paths.PROJECT_DIR)   # /path/to (parent)
print(paths.STATIC_DIR)    # /path/to/app/static
print(paths.VERSION_FILE)  # /path/to/app/VERSION

# Register app-specific paths
paths.register("DOCS_DIR", os.path.join(paths.APP_DIR, "docs"))
paths.register("CACHE_DIR", os.path.join(paths.APP_DIR, ".cache"))

# Access registered paths
print(paths.DOCS_DIR)      # /path/to/app/docs
print(paths.get("CACHE_DIR"))  # Alternative access
```

## Base Paths

| Path | Description |
|------|-------------|
| `APP_DIR` | Application directory (where main code lives) |
| `PROJECT_DIR` | Parent of APP_DIR (repo root, contains config.json) |
| `STATIC_DIR` | Static files directory (APP_DIR/static) |
| `VERSION_FILE` | Version file path (APP_DIR/VERSION) |
| `UPDATE_STATE_DIR` | Update state directory (PROJECT_DIR/.update) |

## MIME Types

The module includes a `MIME_TYPES` dictionary for static file serving:

```python
from aide_frame.paths import MIME_TYPES

ext = '.html'
content_type = MIME_TYPES.get(ext, 'application/octet-stream')
```

Supported types: `.html`, `.css`, `.js`, `.json`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.ico`, `.webp`, `.md`, `.txt`, `.xml`, `.pdf`
