# Logging

**Module:** `log.py`

Centralized logging for all modules.

## Purpose

Consistent logging across all modules with configurable log levels.

## API

```python
from log import logger

logger.debug("Detailed info for debugging")
logger.info("Normal operation info")
logger.warning("Something unexpected but not fatal")
logger.error("Something went wrong")
```

## Log Levels

| Level | When to Use |
|-------|-------------|
| `DEBUG` | Detailed information for debugging |
| `INFO` | Normal operation (default) |
| `WARNING` | Something unexpected happened |
| `ERROR` | Operation failed |

## Configuration

Set via command line:

```bash
python3 slideshow.py --log-level DEBUG
```

Or in code:

```python
import logging
from log import logger
logger.setLevel(logging.DEBUG)
```

## Output Format

```
2024-01-15 10:30:45 INFO     Slideshow started
2024-01-15 10:30:45 INFO     HTTP API listening on port 8080
2024-01-15 10:30:46 DEBUG    Loading image: vacation/beach.jpg
```

## Design Decisions

- **Single logger instance** - All modules import the same logger
- **No external dependencies** - Uses Python's built-in `logging` module
- **Foundation module** - Has no local dependencies, can be imported by any module
