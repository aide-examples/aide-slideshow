# Web Control

**Module:** `remote/http_api.py`

HTTP REST API and web UI for controlling the slideshow.

## Purpose

- Provide a REST API for automation and integration
- Serve a web UI for controlling the slideshow from any device
- Serve documentation and image preparation UI

## Configuration

```json
"remote_control": {
    "http_api": {
        "enabled": true,
        "port": 8080
    }
}
```

## Web UI

Access the control interface at `http://raspberrypi:8080/`

The web UI provides:
- Play/Pause button
- Skip button
- Duration slider
- Folder filter dropdown
- Monitor on/off buttons
- Current status display

## REST API Endpoints

### Slideshow Control

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /status` | GET | Current slideshow status |
| `GET /pause` | GET | Pause slideshow |
| `GET /resume` | GET | Resume slideshow |
| `GET /skip` | GET | Skip to next image |
| `GET /duration?seconds=N` | GET | Set display duration (1-300) |

### Folder Filtering

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /folders` | GET | List available folders |
| `GET /filter?folder=NAME` | GET | Filter by folder |
| `GET /filter/clear` | GET | Clear filter (show all) |

### Monitor Control

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /monitor/on` | GET | Turn monitor on |
| `GET /monitor/off` | GET | Turn monitor off |

### Other Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /` | GET | Main control UI |
| `GET /about` | GET | Documentation viewer |
| `GET /prepare` | GET | Image preparation UI |
| `GET /update` | GET | Update management UI |
| `GET /static/*` | GET | Static files (CSS, JS) |

## API Examples

```bash
# Get current status
curl http://raspberrypi:8080/status
# {"paused": false, "duration": 35, "filter": null, "image": "vacation/beach.jpg"}

# Pause slideshow
curl http://raspberrypi:8080/pause
# {"status": "paused"}

# Set duration to 10 seconds
curl "http://raspberrypi:8080/duration?seconds=10"
# {"duration": 10}

# Filter to vacation folder
curl "http://raspberrypi:8080/filter?folder=vacation"
# {"filter": "vacation"}

# List available folders
curl http://raspberrypi:8080/folders
# {"folders": ["vacation", "family", "nature"]}
```

## Server URL Discovery

On startup, the HTTP server logs its accessible URL:

```
HTTP API listening on http://raspberrypi.local:8080
```

The server determines the best URL to display:
1. FQDN (fully qualified domain name) if available
2. First non-localhost IP address
3. `localhost` as fallback

## Static Files

The web UI files are served from `app/static/`:

| File | Purpose |
|------|---------|
| `index.html` | Main control UI |
| `about.html` | Documentation viewer |
| `prepare.html` | Image preparation UI |
| `update.html` | Update management UI |
| `style.css` | Shared styles |
| `js/marked.min.js` | Markdown rendering |
| `js/mermaid.min.js` | Diagram rendering |

## Security Considerations

- The server listens on all interfaces (`0.0.0.0`)
- No authentication (assumes trusted local network)
- Path traversal is blocked in file-serving endpoints
- Input validation on duration and folder parameters
