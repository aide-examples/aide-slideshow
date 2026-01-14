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
- GET /monitor/on - Turn monitor on
- GET /monitor/off - Turn monitor off
"""

import os
import time
import threading
import socket
from http.server import HTTPServer

from aide_frame import paths, http_routes, http_server
from aide_frame.log import logger
from utils.helpers import load_static_file, load_readme
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
_update_manager = None
_prepare_job = None


class SlideshowHandler(http_server.JsonHandler):
    """HTTP handler for slideshow control API."""

    def get(self, path, params):
        # Serve web UI at root
        if path == '/' or path == '/index.html':
            return self._serve_static('index.html')

        # Serve static files from /static/ path
        if path.startswith('/static/'):
            filename = path[8:]
            if '..' in filename or filename.startswith('/'):
                return {"error": "Forbidden"}, 403
            return self._serve_static(filename)

        # Serve update page
        if path == '/update' or path == '/update.html':
            return self._serve_static('update.html')

        # Serve README.md content as JSON
        if path == '/readme':
            return {"content": load_readme()}

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

        if path == '/restart':
            def delayed_exit():
                time.sleep(0.5)
                os._exit(0)
            threading.Thread(target=delayed_exit, daemon=True).start()
            return {"success": True, "message": "Restarting..."}

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

        # Update API endpoints
        if path == '/api/update/status':
            if _update_manager:
                return _update_manager.get_status()
            return {"error": "Update manager not initialized"}, 500

        # Image preparation endpoints
        if path == '/prepare' or path == '/prepare.html':
            return self._serve_static('prepare.html')

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
        if path == '/api/update/check':
            if _update_manager:
                return _update_manager.check_for_updates()
            return {"error": "Update manager not initialized"}, 500

        if path == '/api/update/download':
            if _update_manager:
                return _update_manager.download_update()
            return {"error": "Update manager not initialized"}, 500

        if path == '/api/update/apply':
            if _update_manager:
                return _update_manager.apply_update()
            return {"error": "Update manager not initialized"}, 500

        if path == '/api/update/rollback':
            if _update_manager:
                return _update_manager.rollback()
            return {"error": "Update manager not initialized"}, 500

        if path == '/api/update/enable':
            if _update_manager:
                return _update_manager.enable_updates()
            return {"error": "Update manager not initialized"}, 500

        if path == '/api/prepare/start':
            return self._handle_prepare_start(data)

        return {"error": "Unknown endpoint"}, 404

    def _serve_static(self, filename):
        """Serve a static file."""
        ext = os.path.splitext(filename)[1].lower()
        is_binary = ext in ('.png', '.jpg', '.jpeg', '.ico')
        content = load_static_file(filename, binary=is_binary)

        if content is None:
            return {"error": f"File not found: {filename}"}, 404

        mime_type = paths.MIME_TYPES.get(ext, 'application/octet-stream')
        if is_binary:
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_text(content, mime_type)
        return None  # Already handled

    def _handle_prepare_count(self, params):
        """Handle /api/prepare/count endpoint."""
        from utils.helpers import resolve_safe_path, PathSecurityError, get_imgPrepare

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
        from utils.helpers import resolve_safe_path, PathSecurityError, get_imgPrepare
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

    def __init__(self, config, slideshow, update_manager=None, prepare_job=None, platform='unknown'):
        global _controller, _update_manager, _prepare_job
        super().__init__(slideshow)
        self.port = config.get("port", 8080)
        self.platform = platform
        self._server = None
        self._thread = None

        # Set module-level references for handler
        _controller = self
        _update_manager = update_manager
        _prepare_job = prepare_job

    def _get_server_url(self):
        """Get the best URL to reach this server."""
        hostname = socket.gethostname()

        if self.platform == 'wsl2':
            return f"http://localhost:{self.port}"

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return f"http://{ip}:{self.port}"
        except:
            pass

        try:
            fqdn = socket.getfqdn()
            if fqdn and fqdn != hostname and '.' in fqdn:
                return f"http://{fqdn}:{self.port}"
        except:
            pass

        return f"http://{hostname}:{self.port}"

    def get_server_url(self):
        """Public method to get server URL."""
        return self._get_server_url()

    def _print_server_url_async(self):
        """Print server URL in background thread."""
        def resolve_and_print():
            url = self._get_server_url()
            logger.info(f"HTTP API server reachable at {url}")
            if self.platform == 'wsl2':
                logger.info("         (For LAN access from mobile, use your Windows IP instead of localhost)")
        threading.Thread(target=resolve_and_print, daemon=True).start()

    def start(self):
        # Configure handler with docs config
        SlideshowHandler.docs_config = DOCS_CONFIG

        self._server = HTTPServer(('0.0.0.0', self.port), SlideshowHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"HTTP API server started on port {self.port}")
        self._print_server_url_async()

    def stop(self):
        if self._server:
            self._server.shutdown()
