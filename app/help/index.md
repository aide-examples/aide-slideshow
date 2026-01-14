# Slideshow - User Guide

Welcome to the Raspberry Pi Photo Slideshow. This guide explains how to use the web interface to control your slideshow.

## Quick Start

1. Open `http://raspberrypi:8080` in your browser
2. The slideshow starts automatically with your images
3. Use the control panel to pause, skip, or adjust settings

## Web Interface

### Main Controls

| Button | Action |
|--------|--------|
| Pause/Resume | Toggle slideshow playback |
| Skip | Jump to next image |
| Duration | Adjust display time per image |

### Folder Filter

You can filter images by folder:
1. Click on "Filter by Folder"
2. Select a subfolder name
3. Only images from that folder will be shown
4. Click "Clear Filter" to show all images again

## Adding Images

Copy your images to the `img/show/` directory on the Raspberry Pi:

```bash
scp photo.jpg pi@raspberrypi:~/img/show/
```

Supported formats: JPG, PNG, GIF, WEBP

## Monitor Control

The slideshow can control your TV/monitor:
- Automatic power off after idle timeout
- Motion sensor wake-up (if configured)
- Manual on/off buttons in the web interface

## Troubleshooting

### Images not appearing
- Check that images are in `img/show/`
- Verify file permissions
- Check the log output for errors

### Web interface not loading
- Verify the Pi is running: `systemctl status slideshow`
- Check the IP address: `hostname -I`
- Default port is 8080
