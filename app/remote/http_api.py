"""
HTTP REST API for remote control.

Provides a web interface and REST API for controlling the slideshow.

Endpoints:
- GET /status - Current slideshow status
- GET /pause - Pause slideshow
- GET /resume - Resume slideshow
- GET /skip - Skip to next image
- GET /duration?seconds=N - Set display duration
- GET /filter?folder=NAME - Filter by folder
- GET /filter/clear - Clear filter
- GET /orientation?mode=MODE - Set orientation (auto, landscape, portrait_left, portrait_right)
- GET /monitor/on - Turn monitor on
- GET /monitor/off - Turn monitor off
"""

import os
import threading
from http.server import ThreadingHTTPServer

from aide_frame import paths, http_routes, http_server, update_routes
from aide_frame.http_server import get_server_url, restart_server
from aide_frame.log import logger
from . import RemoteControlProvider


# Docs/Help configuration for http_routes
DOCS_CONFIG = http_routes.DocsConfig(
    app_name="AIDE Slideshow",
    back_link="/",
    back_text="Back to Control",
    docs_dir_key="DOCS_DIR",
    framework_dir_key="AIDE_FRAME_DOCS_DIR",
    help_dir_key="HELP_DIR",
    enable_mermaid=True,
)


# Module-level references (set by HTTPAPIRemoteControl)
_controller = None
_prepare_job = None


class SlideshowHandler(http_server.JsonHandler):
    """HTTP handler for slideshow control API."""

    def get(self, path, params):
        # Serve web UI at root
        if path == '/' or path == '/index.html':
            return self.file('slide/slide.html')

        if path == '/status':
            return _controller.slideshow.get_status()

        if path == '/pause':
            _controller.execute_action("pause")
            return {"success": True, "paused": True}

        if path == '/resume':
            _controller.execute_action("resume")
            return {"success": True, "paused": False}

        if path == '/skip':
            _controller.execute_action("skip")
            return {"success": True}

        if path == '/duration':
            if 'seconds' in params:
                seconds = int(params['seconds'])
                _controller.execute_action("set_duration", {"seconds": seconds})
                return {"success": True, "duration": seconds}
            return {"error": "Missing 'seconds' parameter"}, 400

        if path == '/filter':
            if 'folder' in params:
                _controller.execute_action("set_filter", {"folder": params['folder']})
                return {"success": True, "filter": params['folder']}
            return {"error": "Missing 'folder' parameter"}, 400

        if path == '/filter/clear':
            _controller.execute_action("filter_clear")
            return {"success": True, "filter": None}

        if path == '/monitor/on':
            _controller.execute_action("monitor_on")
            return {"success": True, "monitor_on": True}

        if path == '/monitor/off':
            _controller.execute_action("monitor_off")
            return {"success": True, "monitor_on": False}

        if path == '/orientation':
            if 'mode' in params:
                mode = params['mode']
                if mode in ('auto', 'landscape', 'portrait_left', 'portrait_right'):
                    _controller.execute_action("set_orientation", {"mode": mode})
                    return {"success": True, "orientation": mode}
                return {"error": "Invalid mode. Use: auto, landscape, portrait_left, portrait_right"}, 400
            return {"error": "Missing 'mode' parameter"}, 400

        if path == '/restart':
            return restart_server()

        if path == '/folders':
            folders = set()
            effective_dir = _controller.slideshow.get_effective_image_dir()
            for root, dirs, _ in os.walk(effective_dir):
                rel_root = os.path.relpath(root, effective_dir)
                if rel_root != '.':
                    folders.add(rel_root)
                for d in dirs:
                    folders.add(os.path.join(rel_root, d) if rel_root != '.' else d)
            return {"folders": sorted(folders)}

        # Image preparation endpoints
        if path == '/prepare' or path == '/prepare.html':
            return self.file('prepare/prepare.html')

        if path == '/api/prepare/status':
            if _prepare_job:
                return _prepare_job.get_status()
            return {"error": "Prepare job not initialized"}, 500

        if path == '/api/prepare/cancel':
            if _prepare_job:
                _prepare_job.cancel()
                return {"success": True, "message": "Cancellation requested"}
            return {"error": "Prepare job not initialized"}, 500

        if path == '/api/prepare/count':
            return self._handle_prepare_count(params)

        if path == '/api/prepare/defaults':
            return {
                "input_dir": _controller.slideshow.upload_dir,
                "output_dir": _controller.slideshow.image_dir,
                "mode": "hybrid-stretch",
                "target_size": "1920x1080",
                "pad_mode": "average",
                "crop_min": 0.8,
                "stretch_max": 0.2,
                "no_stretch_limit": 0.4,
                "modes": ["pad", "crop", "hybrid", "hybrid-stretch"],
                "pad_modes": ["gray", "white", "black", "average"],
            }

        # Default: show API help
        return {
            "endpoints": [
                "GET /status - Current status",
                "GET /pause - Pause slideshow",
                "GET /resume - Resume slideshow",
                "GET /skip - Skip to next image",
                "GET /duration?seconds=N - Set display duration",
                "GET /filter?folder=NAME - Show only images from folder",
                "GET /filter/clear - Clear folder filter",
                "GET /orientation?mode=MODE - Set orientation (auto, landscape, portrait_left, portrait_right)",
                "GET /folders - List available folders",
                "GET /monitor/on - Turn monitor on",
                "GET /monitor/off - Turn monitor off",
                "GET /prepare - Image preparation UI",
                "GET /api/prepare/status - Preparation job status",
                "POST /api/prepare/start - Start preparation job",
                "GET /api/prepare/cancel - Cancel running job",
                "GET /api/update/status - Update system status",
                "POST /api/update/check - Check for updates on GitHub",
                "POST /api/update/download - Download and stage update",
                "POST /api/update/apply - Apply staged update and restart",
                "POST /api/update/rollback - Rollback to backup version",
                "POST /api/update/enable - Re-enable updates after failures",
            ]
        }

    def post(self, path, data):
        if path == '/api/prepare/start':
            return self._handle_prepare_start(data)

        return {"error": "Unknown endpoint"}, 404

    def _handle_prepare_count(self, params):
        """Handle /api/prepare/count endpoint."""
        from aide_frame.paths import resolve_safe_path, PathSecurityError
        from utils.helpers import get_imgPrepare

        dir_param = params.get('dir', _controller.slideshow.image_dir)
        try:
            directory = resolve_safe_path(dir_param)
        except PathSecurityError as e:
            return {"error": str(e)}, 400

        module = get_imgPrepare()
        if module:
            from pathlib import Path
            count = module.count_image_files(Path(directory))
            return {"count": count, "directory": directory}
        return {"error": "imgPrepare not available"}, 500

    def _handle_prepare_start(self, data):
        """Handle /api/prepare/start endpoint."""
        from aide_frame.paths import resolve_safe_path, PathSecurityError
        from utils.helpers import get_imgPrepare
        from pathlib import Path as PathLib

        module = get_imgPrepare()
        if not module:
            return {"error": "imgPrepare module not available"}, 500

        if not _prepare_job:
            return {"error": "Prepare job not initialized"}, 500

        try:
            input_dir_str = data.get('input_dir', _controller.slideshow.upload_dir)
            output_dir_str = data.get('output_dir', _controller.slideshow.image_dir)

            try:
                input_dir = resolve_safe_path(input_dir_str)
                output_dir = resolve_safe_path(output_dir_str)
            except PathSecurityError as e:
                return {"error": str(e)}, 400

            size_str = data.get('target_size', '1920x1080')
            if isinstance(size_str, str):
                w, h = size_str.lower().split('x')
                target_size = (int(w), int(h))
            else:
                target_size = tuple(size_str)

            config = module.PrepareConfig(
                input_dir=PathLib(input_dir),
                output_dir=PathLib(output_dir),
                mode=data.get('mode', 'hybrid-stretch'),
                target_size=target_size,
                pad_mode=data.get('pad_mode', 'average'),
                crop_min=float(data.get('crop_min', 0.8)),
                stretch_max=float(data.get('stretch_max', 0.2)),
                no_stretch_limit=float(data.get('no_stretch_limit', 0.4)),
                show_text=bool(data.get('show_text', True)),
                skip_existing=bool(data.get('skip_existing', False)),
                dry_run=bool(data.get('dry_run', False)),
                flatten=bool(data.get('flatten', False)),
                quiet=True,
            )

            success, message = _prepare_job.start(config)
            if success:
                return {"success": True, "message": message}
            return {"success": False, "error": message}, 409

        except Exception as e:
            return {"error": str(e)}, 400


class HTTPAPIRemoteControl(RemoteControlProvider):
    """HTTP REST API for remote control."""

    def __init__(self, config, slideshow, update_config=None, prepare_job=None, platform='unknown'):
        global _controller, _prepare_job
        super().__init__(slideshow)
        self.port = config.get("port", 8080)
        self.platform = platform
        self._server = None
        self._thread = None

        # Set module-level references for handler
        _controller = self
        _prepare_job = prepare_job

        # Store update_config for handler class
        self._update_config = update_config

    def get_server_url(self):
        """Public method to get server URL."""
        return get_server_url(self.port, self.platform)

    def start(self):
        # Configure handler with docs and update config
        SlideshowHandler.docs_config = DOCS_CONFIG
        SlideshowHandler.update_config = self._update_config
        SlideshowHandler.static_dir = os.path.join(paths.APP_DIR, 'static')

        # Use ThreadingHTTPServer to handle concurrent requests
        # (prevents blocking when monitor control operations are slow)
        self._server = ThreadingHTTPServer(('0.0.0.0', self.port), SlideshowHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        # Log URL asynchronously (DNS lookup can be slow)
        def log_url():
            url = self.get_server_url()
            logger.info(f"HTTP API server started on port {self.port}")
            logger.info(f"HTTP API server reachable at {url}")
            if self.platform == 'wsl2':
                logger.info("         (For LAN access from mobile, use your Windows IP instead of localhost)")
        threading.Thread(target=log_url, daemon=True).start()

    def stop(self):
        if self._server:
            self._server.shutdown()
