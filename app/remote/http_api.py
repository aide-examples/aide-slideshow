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
import json
import socket
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import paths
from log import logger
from . import RemoteControlProvider
from utils import load_static_file, load_readme, list_docs, load_doc, get_docs_structure


class HTTPAPIRemoteControl(RemoteControlProvider):
    """
    HTTP REST API for remote control.

    Advantages:
    - Works from any device (phone, computer, smart home system)
    - Easy to integrate with automation tools
    - No additional hardware
    """

    def __init__(self, config, slideshow, update_manager=None, prepare_job=None, platform='unknown'):
        super().__init__(slideshow)
        self.port = config.get("port", 8080)
        self.update_manager = update_manager
        self.prepare_job = prepare_job
        self.platform = platform
        self._server = None
        self._thread = None

    def _get_server_url(self):
        """Get the best URL to reach this server (may be slow due to DNS)."""
        import socket

        hostname = socket.gethostname()

        # Under WSL2, localhost works only on same machine
        if self.platform == 'wsl2':
            return f"http://localhost:{self.port}"

        # Try to get IP address first (works for LAN access from mobile devices)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return f"http://{ip}:{self.port}"
        except:
            pass

        try:
            # Try to get FQDN (fully qualified domain name)
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
        """Print server URL in background thread to avoid blocking startup."""
        def resolve_and_print():
            url = self._get_server_url()
            logger.info(f"HTTP API server reachable at {url}")
            if self.platform == 'wsl2':
                logger.info("         (For LAN access from mobile, use your Windows IP instead of localhost)")
        thread = threading.Thread(target=resolve_and_print, daemon=True)
        thread.start()

    def start(self):
        handler = self._create_handler()
        self._server = HTTPServer(('0.0.0.0', self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"HTTP API server started on port {self.port}")
        # Resolve URL asynchronously to avoid blocking
        self._print_server_url_async()

    def stop(self):
        if self._server:
            self._server.shutdown()

    def _create_handler(self):
        """Create request handler with reference to this controller."""
        controller = self
        update_manager = self.update_manager
        prepare_job = self.prepare_job

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                logger.debug(f"API: {args[0]}")

            def send_json(self, data, status=200):
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def send_html(self, html):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode())

            def send_static_file(self, filename):
                """Serve a static file with appropriate MIME type."""
                ext = os.path.splitext(filename)[1].lower()
                mime_type = paths.MIME_TYPES.get(ext, 'application/octet-stream')
                is_binary = ext in ('.png', '.jpg', '.jpeg', '.ico')

                content = load_static_file(filename, binary=is_binary)
                if content is None:
                    self.send_error(404, f"File not found: {filename}")
                    return

                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.end_headers()
                if is_binary:
                    self.wfile.write(content)
                else:
                    self.wfile.write(content.encode())

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                params = parse_qs(parsed.query)

                # Serve web UI at root
                if path == '/' or path == '/index.html':
                    self.send_static_file('index.html')
                    return

                # Serve static files from /static/ path
                if path.startswith('/static/'):
                    filename = path[8:]  # Remove '/static/' prefix
                    # Security: prevent directory traversal
                    if '..' in filename or filename.startswith('/'):
                        self.send_error(403, "Forbidden")
                        return
                    self.send_static_file(filename)
                    return

                # Serve about page
                if path == '/about' or path == '/about.html':
                    self.send_static_file('about.html')
                    return

                # Serve update page
                if path == '/update' or path == '/update.html':
                    self.send_static_file('update.html')
                    return

                # Serve README.md content as JSON (for the about page)
                if path == '/readme':
                    self.send_json({"content": load_readme()})
                    return

                # List all documentation files
                if path == '/api/docs':
                    docs = list_docs()
                    self.send_json({"docs": docs})
                    return

                # Get documentation structure with sections and titles
                if path == '/api/docs/structure':
                    self.send_json(get_docs_structure())
                    return

                # Serve a specific documentation file
                if path.startswith('/api/docs/'):
                    doc_path = path[10:]  # Remove '/api/docs/' prefix
                    if not doc_path:
                        self.send_json({"docs": list_docs()})
                        return
                    content = load_doc(doc_path)
                    if content is not None:
                        self.send_json({"content": content, "path": doc_path})
                    else:
                        self.send_json({"error": f"Document not found: {doc_path}"}, 404)
                    return

                # Serve static assets from docs/ (images, etc.)
                if path.startswith('/docs-assets/'):
                    asset_path = path[13:]  # Remove '/docs-assets/' prefix
                    # Security: prevent directory traversal
                    if '..' in asset_path or asset_path.startswith('/'):
                        self.send_error(403, "Forbidden")
                        return
                    self._serve_docs_asset(asset_path)
                    return

                if path == '/status':
                    self.send_json(controller.slideshow.get_status())

                elif path == '/pause':
                    controller.execute_action("pause")
                    self.send_json({"success": True, "paused": True})

                elif path == '/resume':
                    controller.execute_action("resume")
                    self.send_json({"success": True, "paused": False})

                elif path == '/skip':
                    controller.execute_action("skip")
                    self.send_json({"success": True})

                elif path == '/duration':
                    if 'seconds' in params:
                        seconds = int(params['seconds'][0])
                        controller.execute_action("set_duration", {"seconds": seconds})
                        self.send_json({"success": True, "duration": seconds})
                    else:
                        self.send_json({"error": "Missing 'seconds' parameter"}, 400)

                elif path == '/filter':
                    if 'folder' in params:
                        controller.execute_action("set_filter", {"folder": params['folder'][0]})
                        self.send_json({"success": True, "filter": params['folder'][0]})
                    else:
                        self.send_json({"error": "Missing 'folder' parameter"}, 400)

                elif path == '/filter/clear':
                    controller.execute_action("filter_clear")
                    self.send_json({"success": True, "filter": None})

                elif path == '/monitor/on':
                    controller.execute_action("monitor_on")
                    self.send_json({"success": True, "monitor_on": True})

                elif path == '/monitor/off':
                    controller.execute_action("monitor_off")
                    self.send_json({"success": True, "monitor_on": False})

                elif path == '/restart':
                    self.send_json({"success": True, "message": "Restarting..."})
                    # Exit after response - systemd will restart the service
                    def delayed_exit():
                        time.sleep(0.5)
                        os._exit(0)
                    threading.Thread(target=delayed_exit, daemon=True).start()

                elif path == '/folders':
                    folders = set()
                    effective_dir = controller.slideshow.get_effective_image_dir()
                    for root, dirs, _ in os.walk(effective_dir):
                        rel_root = os.path.relpath(root, effective_dir)
                        if rel_root != '.':
                            folders.add(rel_root)
                        for d in dirs:
                            folders.add(os.path.join(rel_root, d) if rel_root != '.' else d)
                    self.send_json({"folders": sorted(folders)})

                # Update API endpoints
                elif path == '/api/update/status':
                    if update_manager:
                        self.send_json(update_manager.get_status())
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                # Image preparation endpoints
                elif path == '/prepare' or path == '/prepare.html':
                    self.send_static_file('prepare.html')

                elif path == '/api/prepare/status':
                    if prepare_job:
                        self.send_json(prepare_job.get_status())
                    else:
                        self.send_json({"error": "Prepare job not initialized"}, 500)

                elif path == '/api/prepare/cancel':
                    if prepare_job:
                        prepare_job.cancel()
                        self.send_json({"success": True, "message": "Cancellation requested"})
                    else:
                        self.send_json({"error": "Prepare job not initialized"}, 500)

                elif path == '/api/prepare/count':
                    self._handle_prepare_count(params)

                elif path == '/api/prepare/defaults':
                    # Return default configuration and paths
                    self.send_json({
                        "input_dir": controller.slideshow.upload_dir,
                        "output_dir": controller.slideshow.image_dir,
                        "mode": "hybrid-stretch",
                        "target_size": "1920x1080",
                        "pad_mode": "average",
                        "crop_min": 0.8,
                        "stretch_max": 0.2,
                        "no_stretch_limit": 0.4,
                        "modes": ["pad", "crop", "hybrid", "hybrid-stretch"],
                        "pad_modes": ["gray", "white", "black", "average"],
                    })

                else:
                    self.send_json({
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
                    })

            def _serve_docs_asset(self, asset_path):
                """Serve a static asset from the docs/ directory."""
                filepath = os.path.join(paths.DOCS_DIR, asset_path)
                if not os.path.isfile(filepath):
                    self.send_error(404, f"Asset not found: {asset_path}")
                    return

                ext = os.path.splitext(asset_path)[1].lower()
                mime_type = paths.MIME_TYPES.get(ext, 'application/octet-stream')
                is_binary = ext in ('.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp')

                try:
                    mode = 'rb' if is_binary else 'r'
                    with open(filepath, mode) as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', mime_type)
                    self.end_headers()
                    if is_binary:
                        self.wfile.write(content)
                    else:
                        self.wfile.write(content.encode())
                except Exception as e:
                    self.send_error(500, f"Error reading asset: {e}")

            def _handle_prepare_count(self, params):
                """Handle /api/prepare/count endpoint."""
                # Import here to avoid circular imports
                from ..utils import resolve_safe_path, PathSecurityError, get_imgPrepare

                dir_param = params.get('dir', [controller.slideshow.image_dir])[0]
                try:
                    directory = resolve_safe_path(dir_param)
                except PathSecurityError as e:
                    self.send_json({"error": str(e)}, 400)
                    return
                module = get_imgPrepare()
                if module:
                    from pathlib import Path
                    count = module.count_image_files(Path(directory))
                    self.send_json({"count": count, "directory": directory})
                else:
                    self.send_json({"error": "imgPrepare not available"}, 500)

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path

                # Read POST body
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

                try:
                    data = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    self.send_json({"error": "Invalid JSON"}, 400)
                    return

                if path == '/api/update/check':
                    if update_manager:
                        result = update_manager.check_for_updates()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/update/download':
                    if update_manager:
                        result = update_manager.download_update()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/update/apply':
                    if update_manager:
                        result = update_manager.apply_update()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/update/rollback':
                    if update_manager:
                        result = update_manager.rollback()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/update/enable':
                    if update_manager:
                        result = update_manager.enable_updates()
                        self.send_json(result)
                    else:
                        self.send_json({"error": "Update manager not initialized"}, 500)

                elif path == '/api/prepare/start':
                    self._handle_prepare_start(data)

                else:
                    self.send_json({"error": "Unknown endpoint"}, 404)

            def _handle_prepare_start(self, data):
                """Handle /api/prepare/start endpoint."""
                # Import here to avoid circular imports
                from ..utils import resolve_safe_path, PathSecurityError, get_imgPrepare

                module = get_imgPrepare()
                if not module:
                    self.send_json({"error": "imgPrepare module not available"}, 500)
                    return

                if not prepare_job:
                    self.send_json({"error": "Prepare job not initialized"}, 500)
                    return

                # Parse configuration from POST data
                from pathlib import Path as PathLib
                try:
                    # Validate and resolve paths safely
                    input_dir_str = data.get('input_dir', controller.slideshow.upload_dir)
                    output_dir_str = data.get('output_dir', controller.slideshow.image_dir)

                    try:
                        input_dir = resolve_safe_path(input_dir_str)
                        output_dir = resolve_safe_path(output_dir_str)
                    except PathSecurityError as e:
                        self.send_json({"error": str(e)}, 400)
                        return

                    # Parse target size
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
                        quiet=True,  # Don't spam console from web jobs
                    )

                    success, message = prepare_job.start(config)
                    if success:
                        self.send_json({"success": True, "message": message})
                    else:
                        self.send_json({"success": False, "error": message}, 409)

                except Exception as e:
                    self.send_json({"error": str(e)}, 400)

        return Handler
