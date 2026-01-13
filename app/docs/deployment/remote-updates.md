# Remote Update System

Downloading and applying updates from GitHub.

## Features

- **Version checking** against GitHub repository
- **Manual download and installation** (user decides when to update)
- **Automatic rollback** on failure (max 2 attempts before disabling updates)
- **Development mode detection** (when local version is ahead of remote)
- **Web UI** at `/update` for easy management

## Deployment Modes

The update system works in both deployment scenarios:

### Simple Installation (without /data partition)

```
/home/pi/aide-slideshow/
├── app/                    ← Updateable files (direct write)
│   ├── slideshow.py
│   ├── VERSION
│   ├── static/
│   └── ...
├── .update/                ← Update state and backups
│   ├── state.json
│   ├── staging/
│   └── backup/
├── img/                    ← Images
└── config.json             ← User config (not updated)
```

Updates are written directly to the `app/` directory. The filesystem must be writable.

### Production Installation (with /data partition and read-only root)

```
/home/pi/aide-slideshow/    ← Read-only (overlayroot)
├── app -> /data/app        ← Symlink to writable partition
├── img -> /data/img        ← Symlink to writable partition
└── config.json

/data/                      ← Writable partition
├── app/                    ← Updateable files
├── img/                    ← Images
└── .update/                ← Update state and backups
```

The symlink makes updates transparent - the code uses relative paths and Python's `os.path.abspath()` follows symlinks automatically.

## Setup Symlinks (for Production)

Run once after initial deployment to the Pi with a `/data` partition:

```bash
#!/bin/bash
SLIDESHOW_DIR="/home/pi/aide-slideshow"

# 1. Copy app/ to /data/app (first time only)
if [ ! -d "/data/app" ]; then
    sudo cp -r "$SLIDESHOW_DIR/app" /data/app
    sudo chown -R pi:pi /data/app
fi

# 2. Replace app/ with symlink
rm -rf "$SLIDESHOW_DIR/app"
ln -s /data/app "$SLIDESHOW_DIR/app"

# 3. Create update state directory
mkdir -p /data/.update/{backup,staging}

# 4. Reload service
sudo systemctl daemon-reload
sudo systemctl restart slideshow
```

## Web UI

Access the update management at `http://raspberrypi:8080/update`

The UI shows:
- Current and available version
- Update status (checking, downloading, staged, etc.)
- Buttons for Check, Download, Install, Rollback
- Re-enable button if updates were disabled due to failures

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/update/status` | GET | Current update status |
| `/api/update/check` | POST | Check GitHub for new version |
| `/api/update/download` | POST | Download and stage update |
| `/api/update/apply` | POST | Apply staged update and restart |
| `/api/update/rollback` | POST | Rollback to backup version |
| `/api/update/enable` | POST | Re-enable updates after failures |

## Configuration

Add to `config.json`:

```json
{
  "update": {
    "enabled": true,
    "source": {
      "repo": "aide-examples/aide-slideshow",
      "branch": "main"
    },
    "auto_check_hours": 24,
    "auto_check": true,
    "auto_download": false,
    "auto_apply": false
  }
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `enabled` | Enable update functionality | `true` |
| `source.repo` | GitHub repository | `aide-examples/aide-slideshow` |
| `source.branch` | Branch to update from | `main` |
| `auto_check` | Periodically check for updates | `true` |
| `auto_download` | Automatically download updates | `false` |
| `auto_apply` | Automatically apply updates | `false` |

## Update Flow

```
1. CHECK     User clicks "Check for Updates"
             → Compares local VERSION with GitHub

2. DOWNLOAD  User clicks "Download Update"
             → Downloads files to .update/staging/
             → Verifies SHA256 checksums (if CHECKSUMS.sha256 exists)

3. APPLY     User clicks "Install Update"
             → Backs up current files to .update/backup/
             → Copies staged files to app/
             → Restarts slideshow service

4. VERIFY    After 60s stable operation
             → Clears pending_verification flag
             → Cleans up staging directory

   ROLLBACK  If service fails to start:
             → Restores from backup
             → After 2 failures: disables updates
```

## Rollback Safety

The system includes automatic rollback protection:

- Before applying, current files are backed up to `.update/backup/`
- After restart, a 60-second timer verifies stable operation
- If the service crashes before verification, it rolls back automatically
- After 2 consecutive failures, updates are disabled (requires manual re-enable)
