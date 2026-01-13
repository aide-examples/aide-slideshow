# Remote Updates

GitHub-based remote update system with rollback support.

## Overview

The `UpdateManager` provides:
- Version checking against GitHub repository
- Staged downloads with checksum verification
- Automatic backup before applying updates
- Rollback on failure (max 2 attempts before disabling)
- Configurable file types and directories

## Update Flow

1. **CHECK** - Compare local VERSION with GitHub
2. **DOWNLOAD** - Download files to `.update/staging/`, verify checksums
3. **APPLY** - Backup current files, copy staging to app/, restart service
4. **VERIFY** - After 60s stable operation, confirm update; on failure, rollback

## Usage

```python
from aide_frame.update import UpdateManager, get_local_version

# Configure for your application
config = {
    "enabled": True,
    "source": {
        "repo": "username/repo-name",
        "branch": "main"
    },
    "service_name": "myapp",
    "updateable_dirs": ["src", "static", "templates"],
    "required_files": ["main.py", "VERSION"]
}

manager = UpdateManager(config)

# Check for updates
result = manager.check_for_updates()
if result["update_available"]:
    print(f"Update available: {result['available_version']}")

# Download and stage
result = manager.download_update()

# Apply update (triggers restart)
result = manager.apply_update()

# After successful startup, confirm
manager.confirm_update()

# Or rollback if something went wrong
manager.rollback()
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `True` | Enable/disable updates |
| `source.repo` | str | - | GitHub repo (e.g., "user/repo") |
| `source.branch` | str | `"main"` | Branch to update from |
| `service_name` | str | - | Systemd service name for restart |
| `updateable_dirs` | list | `[]` | Directories where files can be deleted |
| `required_files` | list | `["VERSION"]` | Files that must be downloaded |
| `file_extensions` | list | `.py`, `.md`, etc. | File types to include |
| `auto_check` | bool | `True` | Periodically check for updates |
| `auto_check_hours` | int | `24` | Hours between auto-checks |

## Safety Features

- **Backup before apply**: All current files backed up to `.update/backup/`
- **Rollback on failure**: Automatic restore if update fails
- **Failure limit**: Updates disabled after 2 consecutive failures
- **Re-enable**: Call `manager.enable_updates()` to reset

## API Endpoints

When integrated with HTTP API:

| Endpoint | Description |
|----------|-------------|
| `GET /api/update/status` | Current update status |
| `POST /api/update/check` | Check for updates |
| `POST /api/update/download` | Download and stage |
| `POST /api/update/apply` | Apply staged update |
| `POST /api/update/rollback` | Rollback to backup |
