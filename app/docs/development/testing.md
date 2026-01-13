# Testing

Development on WSL2/desktop, keyboard controls, sample images.

## Platform Detection

| Platform | Video Driver | Display Mode | Hardware Features |
|----------|-------------|--------------|-------------------|
| Raspberry Pi | `kmsdrm` | Fullscreen | GPIO, CEC available |
| WSL2 | `wayland` or `x11` | Windowed | Simulated/disabled |
| Linux Desktop | `wayland` or `x11` | Windowed | Simulated/disabled |
| macOS | `cocoa` | Windowed | Simulated/disabled |
| Windows | `windows` | Windowed | Simulated/disabled |

## Running on WSL2

WSL2 with WSLg (Windows 11) provides built-in graphical support. The slideshow will automatically detect WSL2 and use the appropriate Wayland or X11 driver.

```bash
# Install pygame if needed
pip install pygame

# Run with local test images
python3 app/slideshow.py --image-dir myImages --duration 3

# The HTTP API is still available for testing
curl http://localhost:8080/status
curl http://localhost:8080/pause
curl http://localhost:8080/skip
```

Hardware providers (GPIO, CEC) gracefully fall back to no-op implementations when running on non-Raspberry Pi systems, so the slideshow runs without errors.

## Command Line Options

```bash
python3 slideshow.py --help

# Override image directory (useful for testing with local images)
python3 slideshow.py --image-dir myImages

# Set display duration (seconds per image)
python3 slideshow.py --duration 5

# Force windowed or fullscreen mode
python3 slideshow.py --windowed
python3 slideshow.py --fullscreen

# Set window size (WIDTHxHEIGHT)
python3 slideshow.py --size 1920x1080

# Use a specific config file
python3 slideshow.py --config ./my-config.json

# Set log level (DEBUG, INFO, WARNING, ERROR)
python3 slideshow.py --log-level DEBUG

# Combined example for WSL2 testing
python3 slideshow.py -i myImages -d 3 -s 1280x720 -l DEBUG
```

## Keyboard Controls (Windowed Mode)

| Key | Action |
|-----|--------|
| **Q** / **Escape** | Quit |
| **Space** | Toggle pause/play |
| **Right** / **N** | Skip to next image |
| **Up** | Increase duration (+5s) |
| **Down** | Decrease duration (-5s) |
| **F** | Toggle fullscreen |

## Sample Images

The repository includes sample images in `app/sample_images/` so the slideshow works immediately after cloning:

```
sample_images/
├── landscapes/
│   ├── mountain_lake.jpg
│   └── ocean_sunset.jpg
├── animals/
│   ├── fox.jpg
│   └── deer.jpg
└── LICENSE
```

The web control UI shows the subdirectories (landscapes, animals) as filter options.

## Testing the HTTP API

```bash
# Get status
curl http://localhost:8080/status

# Control playback
curl http://localhost:8080/pause
curl http://localhost:8080/resume
curl http://localhost:8080/skip

# Set duration
curl "http://localhost:8080/duration?seconds=10"

# Filter by folder
curl http://localhost:8080/folders
curl "http://localhost:8080/filter?folder=landscapes"
curl http://localhost:8080/filter/clear
```

## Performance Note

The platform detection adds negligible overhead on the Raspberry Pi:
- **Startup:** ~1-2ms one-time cost (reads two small `/proc` files)
- **Memory:** <1KB (two small global variables)
- **Runtime:** The `pygame.event.get()` call processes the event queue, which is recommended practice and has no measurable impact in fullscreen kmsdrm mode
