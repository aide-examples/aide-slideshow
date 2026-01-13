# Installation

Setup guide for quick start and full Raspberry Pi installation.

## Quick Start

```bash
# Clone repository
git clone https://github.com/aide-examples/aide-slideshow.git
cd aide-slideshow

# Install required dependency
sudo apt install python3-pygame

# Run
python3 app/slideshow.py

# Access web UI
# http://localhost:8080
```

The slideshow works immediately with the bundled sample images.

## Full Installation (Raspberry Pi)

### 1. Install Dependencies

See [Platform Dependencies](../platform/dependencies.md) for the full list.

```bash
sudo apt update
sudo apt install python3-pygame

# Optional (install as needed)
sudo apt install cec-utils         # For HDMI-CEC
sudo apt install ir-keytable       # For IR remote
pip install Pillow                 # For image preparation
pip install "qrcode[pil]"          # For welcome screen
```

### 2. Deploy Files

```bash
# Clone the repository
cd /home/pi
git clone https://github.com/aide-examples/aide-slideshow.git
cd aide-slideshow

# Create image directories
mkdir -p img/show      # For prepared/displayed images
mkdir -p img/upload    # For raw uploads before preparation
```

### 3. Configure

Edit `config.json` to match your hardware setup:

```json
{
    "image_dir": "img/show",
    "display_duration": 35,
    "monitor_control": {
        "provider": "cec"
    }
}
```

See [Configuration](../implementation/technical/config.md) for all options.

### 4. Test

```bash
# Run in foreground
python3 app/slideshow.py

# Access web UI from another device
# http://raspberrypi:8080
```

### 5. Install as Service

Create `/etc/systemd/system/slideshow.service`:

```ini
[Unit]
Description=Photo Slideshow
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/aide-slideshow
ExecStart=/usr/bin/python3 app/slideshow.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable slideshow
sudo systemctl start slideshow

# Check status
sudo systemctl status slideshow
journalctl -u slideshow -f
```

## Directory Structure

After installation:

```
/home/pi/aide-slideshow/
├── app/
│   ├── slideshow.py      # Main application
│   ├── config.py         # Configuration handling
│   ├── static/           # Web UI files
│   ├── docs/             # Documentation
│   └── sample_images/    # Demo images
├── config.json           # Your configuration
└── img/
    ├── show/             # Images to display
    └── upload/           # Raw uploads
```

## Sample Images

The repository includes sample images in `app/sample_images/` so the slideshow works immediately. When `image_dir` is empty or doesn't exist, the slideshow falls back to these bundled images.

To use your own photos:
1. Configure `image_dir` in `config.json`
2. Add images to that directory (or use the web UI upload)

## Related Documentation

- [Read-Only Filesystem](read-only-fs.md) - Power loss protection
- [Remote Updates](remote-updates.md) - Update system
- [Configuration](../implementation/technical/config.md) - All config options
