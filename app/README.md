# AIDE - Slideshow

A modular fullscreen photo slideshow with a plugin architecture for different hardware setups.

Designed to run on a dedicated device connected to a wall mounted display as a digital photo frame.

This project is part of [AIDE examples](https://github.com/aide-examples) - a series of applications built almost completely with agentic coding.

## Quick Start

```bash
# Install dependencies
sudo apt install python3-pygame

# Run slideshow
python3 app/slideshow.py

# Access web UI
# http://localhost:8080
```

## Features

- **Slideshow:** Random/filtered image display with fade transitions
- **Web Control:** Pause, skip, filter, adjust speed from any device
- **Monitor Control:** CEC, Shelly, GPIO Relay, Samsung TV support
- **Motion Detection:** GPIO PIR sensor or MQTT
- **Voice Control:** Alexa integration via Fauxmo
- **Image Preparation:** Resize and optimize images via web UI
- **Remote Updates:** GitHub-based update system

## Documentation

The full documentation is available in the `docs/` directory and via the web UI at `/about`.

| Document | Description |
|----------|-------------|
| [Overview](docs/index.md) | Platform, requirements, feature list |
| [Architecture](docs/architecture.md) | Code structure, module dependencies, diagrams |
| [Installation](docs/installation.md) | System setup and configuration reference |
| [Development](docs/development.md) | Testing, extending, troubleshooting |
| [Image Preparation](docs/image-preparation.md) | Image organization and preparation |

### Hardware Providers

| Document | Description |
|----------|-------------|
| [Monitor Control](docs/hardware/monitor-control.md) | CEC, Shelly, GPIO Relay, Samsung |
| [Motion Detection](docs/hardware/motion-detection.md) | GPIO PIR, MQTT |
| [Remote Control](docs/hardware/remote-control.md) | HTTP API, IR Remote, Alexa |

### Deployment

| Document | Description |
|----------|-------------|
| [Read-Only Filesystem](docs/deployment/read-only-fs.md) | Power loss protection |
| [Remote Updates](docs/deployment/remote-updates.md) | GitHub update system |

## License

MIT License
