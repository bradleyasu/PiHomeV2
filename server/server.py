from cmath import inf
import http.server
import json
import os
import socketserver
import time
from events.pihomeevent import PihomeEventFactory
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from server.socket_handler import SocketHandler
import websockets
import asyncio
from threading import Thread
from services.wallpaper.wallpaper import WALLPAPER_SERVICE, Wallpaper

from util.const import SERVER_PORT, HTTPS_CALLBACK_PORT, _MUSIC_SCREEN
from util.helpers import get_app, process_webhook, toast
from util.phlog import PIHOME_LOGGER

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_GET(self):
        PIHOME_LOGGER.info("Server: GET Request Initiated")
        if self.path.startswith("/status"):
            self._get_status(self.path.replace("/status", "").replace("/", ""))
        elif self.path.startswith("/wallpaper/"):
            self._get_wallpaper(self.path[len("/wallpaper/"):])
        elif self.path == "/airplay/artwork":
            self._get_airplay_artwork()
        elif self.path == "/settings/manifest":
            self._get_settings_manifest()
        elif self.path.startswith("/settings"):
            self._get_settings(self.path)
        elif self.path.startswith("/screens/"):
            self._get_screen_asset(self.path[len("/screens/"):])
        elif self.path == "/" or self.path == "" or self.path == "/index.html":
            self._get_index()
        else:
            if not self._dispatch_callback(self.path):
                self.path = "./web" + self.path
                super().do_GET()

    def _dispatch_callback(self, path: str) -> bool:
        """Check the generic callback registry and invoke a matching handler.

        Returns True if a handler was found and executed, False otherwise.
        The handler is called on the HTTP server thread; it should return an
        HTML string (or None) to send back to the browser.
        """
        from urllib.parse import urlparse, parse_qs
        from server.callbacks import _REGISTRY

        for prefix, handler in list(_REGISTRY.items()):
            if path.startswith(prefix):
                params = parse_qs(urlparse(path).query)
                try:
                    result = handler(params)
                except Exception as e:
                    PIHOME_LOGGER.error(
                        f"Server: callback handler '{prefix}' raised: {e}"
                    )
                    self._send_html_response(500, "<h2>Internal error</h2>")
                    return True
                html = result if isinstance(result, str) and result else (
                    "<p style='font-family:sans-serif'>"
                    "Request received. You can close this tab.</p>"
                )
                self._send_html_response(200, html)
                return True
        return False

    def _get_wallpaper(self, encoded_path: str):
        """Serve a wallpaper image from the Pi's filesystem.

        *encoded_path* is the URL-encoded file path after ``/wallpaper/``.
        Example: ``.%2F.temp%2Fimage.png`` → ``./.temp/image.png``
        """
        import mimetypes
        from urllib.parse import unquote

        file_path = unquote(encoded_path)
        if not os.path.isfile(file_path):
            PIHOME_LOGGER.warning(f"Server: wallpaper not found: {file_path!r}")
            self.send_error(404, "Wallpaper not found")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if not (mime_type and mime_type.startswith("image/")):
            PIHOME_LOGGER.warning(f"Server: wallpaper rejected non-image type '{mime_type}' for {file_path!r}")
            self.send_error(415, "Not an image file")
            return

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            PIHOME_LOGGER.error(f"Server: failed to serve wallpaper {file_path!r}: {e}")
            self.send_error(500, "Failed to read image")

    def _get_screen_asset(self, subpath: str):
        """Serve a static asset (icon, etc.) from the screens directory.

        *subpath* is everything after ``/screens/``.
        Example: ``Home/icon.png`` → ``./screens/Home/icon.png``
        Only image files are served; path traversal is blocked.
        """
        import mimetypes
        from urllib.parse import unquote

        subpath = unquote(subpath)
        if ".." in subpath:
            self.send_error(403, "Forbidden")
            return

        file_path = os.path.join(".", "screens", subpath)
        if not os.path.isfile(file_path):
            self.send_error(404, "Asset not found")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if not (mime_type and mime_type.startswith("image/")):
            self.send_error(415, "Not an image file")
            return

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            PIHOME_LOGGER.error(f"Server: failed to serve screen asset {file_path!r}: {e}")
            self.send_error(500, "Failed to read asset")

    def _send_html_response(self, code: int, html: str):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_status(self, service = ""):
        PIHOME_LOGGER.info("Server: Getting current status from multiple services")
        try:
            response = PihomeEventFactory.create_event_from_dict({"type": "status", "depth": "advanced"}).execute()
            if service != "" and service in response["body"]:
                response["body"] = response["body"][service]
            self._set_response(response["code"], response["body"])

        except Exception as e:
            PIHOME_LOGGER.error("Failed to get status of services: {}".format(e))

    def _get_index(self):
        try:
            self.path = './web/index.html'
            # resp = http.server.SimpleHTTPRequestHandler.do_GET(self)
            # return resp
            super().do_GET()

        except Exception as e:
            PIHOME_LOGGER.error("Failed to process GET request.  Fetching index page")
            PIHOME_LOGGER.error(e)

    def do_PUT(self):
        """Handle PUT requests for updating settings."""
        try:
            content_length = int(self.headers['Content-Length'])
            put_data = self.rfile.read(content_length)
            payload = json.loads(put_data.decode('utf-8'))

            if self.path.startswith("/settings/"):
                self._put_settings(self.path, payload)
            else:
                self._set_response(404, {"status": "error", "message": "Not found"})
        except Exception as e:
            PIHOME_LOGGER.error("Server: PUT Request Failed: {}".format(e))
            self._set_response(500, {"status": "error", "message": str(e)})

    def do_DELETE(self):
        """Placeholder — no DELETE routes yet."""
        self._set_response(404, {"status": "error", "message": "Not found"})

    def do_OPTIONS(self):
        self._set_response()

    def do_POST(self):
        try:
            # Handle reload endpoint (no body required)
            if self.path == "/settings/reload":
                self._post_settings_reload()
                return

            content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
            post_data = self.rfile.read(content_length) # <--- Gets the data itself
            payload = json.loads(post_data.decode('utf-8'))
            # PIHOME_LOGGER.info("POST request: {} | {}".format(str(self.path), post_data.decode('utf-8')))
            if "webhook" in payload:
                event = PihomeEventFactory.create_event_from_dict(payload["webhook"])
                try:
                    response = event.execute()
                    self._set_response(response["code"], response["body"])
                except Exception as e:
                    PIHOME_LOGGER.error("Failed to execute webhook: {}".format(e))
                    self._set_response(500, {"status": "error", "message": "Failed to execute webhook", "error": str(e)})
                return
            else:
                event = PihomeEventFactory.create_event_from_dict(payload)
                try:
                    response = event.execute()
                    self._set_response(response["code"], response["body"])
                except Exception as e:
                    PIHOME_LOGGER.error("Failed to execute event: {}".format(e))
                    self._set_response(500, {"status": "error", "message": "Failed to execute event", "error": str(e)})
                return
            # self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))
        except Exception as e:
            toast("An error occurred processing the server request", "warn", 10)
            PIHOME_LOGGER.error("Server: POST Request Failed: {}".format(e))
            # get stack trace of e
            stack_trace = e.__traceback__
            while stack_trace:
                readable = "File: {} | Line: {} | Function: {}".format(stack_trace.tb_frame.f_code.co_filename, stack_trace.tb_lineno, stack_trace.tb_frame.f_code.co_name)
                PIHOME_LOGGER.error(readable)
                stack_trace = stack_trace.tb_next
            # PIHOME_LOGGER.error("Server: POST Request Failed: {}".format(post_data.decode('utf-8')))

    def _get_airplay_artwork(self):
        """Serve the current AirPlay cover art as a binary image."""
        from services.airplay.airplay import AIRPLAY
        if AIRPLAY.cover_art_bytes is None:
            self.send_error(404, "No artwork available")
            return
        try:
            data = AIRPLAY.cover_art_bytes
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            PIHOME_LOGGER.error("Server: failed to serve airplay artwork: {}".format(e))
            self.send_error(500, "Failed to read artwork")

    def _get_settings_manifest(self):
        """Serve the combined settings manifest from all screen manifest.json files.

        Returns an ordered array of settings panels, each with a label
        and an array of field definitions (type, title, desc, section, key, options).
        This lets the web UI render typed inputs (bool switches, option dropdowns, etc.)
        instead of plain text fields for every setting.
        """
        import glob as _glob
        panels = []
        for manifest_path in sorted(_glob.glob('./screens/*/manifest.json')):
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                if 'settings' not in manifest:
                    continue
                panels.append({
                    "label": manifest.get('settingsLabel', manifest.get('label', 'Unknown')),
                    "sortIndex": manifest.get('settingsIndex', 9999),
                    "fields": manifest['settings'],
                })
            except Exception as e:
                PIHOME_LOGGER.error("Server: failed to read manifest {}: {}".format(manifest_path, e))
        panels.sort(key=lambda p: p['sortIndex'])
        self._set_response(200, {"panels": panels})

    def _post_settings_reload(self):
        """Trigger the full configuration reload cascade.

        Calls the app's reload_configuration() which:
          1. Re-reads base.ini into memory (CONFIG.reload)
          2. Restarts the wallpaper service
          3. Broadcasts on_config_update to all screens
        """
        try:
            from kivy.clock import Clock
            from util.helpers import get_app
            # Schedule on the Kivy main thread to avoid cross-thread issues
            Clock.schedule_once(lambda dt: get_app().reload_configuration(), 0)
            self._set_response(200, {"status": "success", "message": "Configuration reload triggered"})
        except Exception as e:
            PIHOME_LOGGER.error("Server: failed to trigger config reload: {}".format(e))
            self._set_response(500, {"status": "error", "message": str(e)})

    def _get_settings(self, path):
        """Serve configuration settings as JSON.

        Routes:
            GET /settings          → all sections and their key/value pairs
            GET /settings/{section} → keys for a specific section
        """
        from util.configuration import CONFIG
        parts = path.strip("/").split("/")  # ["settings"] or ["settings", "section"]

        if len(parts) == 1:
            # Return all sections
            result = {}
            for section in CONFIG.c.sections():
                result[section] = dict(CONFIG.c[section])
            self._set_response(200, result)
        elif len(parts) == 2:
            section = parts[1]
            if CONFIG.c.has_section(section):
                self._set_response(200, dict(CONFIG.c[section]))
            else:
                self._set_response(404, {"status": "error", "message": "Section '{}' not found".format(section)})
        else:
            self._set_response(400, {"status": "error", "message": "Invalid settings path"})

    def _put_settings(self, path, payload):
        """Update configuration settings.

        Routes:
            PUT /settings/{section}  → update multiple keys in a section
                Body: {"key1": "value1", "key2": "value2"}
        """
        from util.configuration import CONFIG
        parts = path.strip("/").split("/")  # ["settings", "section"]

        if len(parts) == 2:
            section = parts[1]
            if not isinstance(payload, dict):
                self._set_response(400, {"status": "error", "message": "Body must be a JSON object of key/value pairs"})
                return
            for key, value in payload.items():
                CONFIG.set(section, key, str(value))
            CONFIG.reload()
            self._set_response(200, {"status": "success", "section": section, "updated": list(payload.keys())})
        else:
            self._set_response(400, {"status": "error", "message": "Invalid settings path. Use PUT /settings/{section}"})

    def _set_response(self, code = 200, response_data = {"status": "success"}):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  
        self.send_header("Access-Control-Allow-Methods", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

        response_json = json.dumps(response_data)
        self.wfile.write(response_json.encode('utf-8'))

        

 
# Suppress harmless low-level socket errors that Python's built-in HTTP server
# surfaces when a client (e.g. a mobile browser) drops a connection or sends
# TLS handshake data to a plain-HTTP socket before the request line is read.
_IGNORED_SOCKET_ERRNOS = {
    9,   # EBADF  — bad file descriptor (connection dropped mid-read)
    32,  # EPIPE  — broken pipe
    54,  # ECONNRESET (macOS)
    104, # ECONNRESET (Linux)
}

class PiHomeTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
            return
        if isinstance(exc, OSError) and exc.errno in _IGNORED_SOCKET_ERRNOS:
            return
        # All other errors go to the normal logger instead of stderr
        PIHOME_LOGGER.error(
            f"Server: unhandled error from {client_address}: {exc!r}"
        )


class CallbackRequestHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTPS-only request handler that routes GET requests to the
    registered callback registry.  No static file serving, no POST — this
    server exists solely to receive OAuth/webhook redirects over a trusted
    HTTPS connection.
    """

    def do_GET(self):
        if not self._dispatch_callback(self.path):
            self._send_html_response(404, "<h2>Not found</h2>")

    def _dispatch_callback(self, path: str) -> bool:
        from urllib.parse import urlparse, parse_qs
        from server.callbacks import _REGISTRY
        for prefix, handler in list(_REGISTRY.items()):
            if path.startswith(prefix):
                params = parse_qs(urlparse(path).query)
                try:
                    result = handler(params)
                except Exception as e:
                    PIHOME_LOGGER.error(f"CallbackServer: handler '{prefix}' raised: {e}")
                    self._send_html_response(500, "<h2>Internal error</h2>")
                    return True
                html = result if isinstance(result, str) and result else (
                    "<p style='font-family:sans-serif'>Request received. You can close this tab.</p>"
                )
                self._send_html_response(200, html)
                return True
        return False

    def _send_html_response(self, code: int, html: str):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        PIHOME_LOGGER.info("CallbackServer: " + format % args)


class PiHomeServer():
    PORT = SERVER_PORT
    SOCKET_PORT = 9090
    SERVER_THREAD = None
    SOCKET_THREAD = None
    CALLBACK_THREAD = None
    SOCKET_LOOP = None
    SOCKET_SERVER = None
    httpd = None
    callback_httpd = None
    shutting_down = False
    SOCKET_HANDLER = SocketHandler()
    def __init__(self, **kwargs):
        super(PiHomeServer, self).__init__(**kwargs)

    def start_server(self):
        self.SERVER_THREAD = Thread(target=self._run, daemon=True)
        self.SERVER_THREAD.start()
        self.SOCKET_THREAD = Thread(target=self._run_socket, daemon=True)
        self.SOCKET_THREAD.start()
        self.CALLBACK_THREAD = Thread(target=self._run_callback, daemon=True)
        self.CALLBACK_THREAD.start()
        
        PIHOME_LOGGER.info("Server: PiHome Server has started")

    def stop_server(self):
        if self.is_online():
            self.shutting_down = True
            self.httpd.shutdown()
            self.httpd = None
            PIHOME_LOGGER.info("Server: PiHome Server has shutdown")
        else:
            PIHOME_LOGGER.warn("Server: Failed to shutdown PiHome server.  It is not running")
        if self.callback_httpd:
            self.callback_httpd.shutdown()
            self.callback_httpd = None
        self._shutdown_socket_loop()

    def is_online(self):
        if self.httpd == None:
            return False
        return True

    def _run_socket(self):
        if self.SOCKET_LOOP != None:
            return
        # create event loop
        self.SOCKET_LOOP = asyncio.new_event_loop()
        # Start WebSocket server
        try:
            self.SOCKET_LOOP.run_until_complete(self.start_socket_server())
            # self.SOCKET_LOOP.run_forever()
        except InterruptedError as e:
            PIHOME_LOGGER.error("Socket Server Error: {}".format(e))
            self._shutdown_socket_loop()

    def _shutdown_socket_loop(self):
        if self.SOCKET_SERVER != None:
            # force socket server to close
            self.SOCKET_SERVER.close()
            self.SOCKET_SERVER = None
        if self.SOCKET_LOOP != None:
            self.SOCKET_LOOP.stop()
            self.SOCKET_LOOP = None

    def _run(self):
        try:
            with PiHomeTCPServer(("", self.PORT), MyHttpRequestHandler) as h:
                PIHOME_LOGGER.info("Server: PiHome Server Listening on port: {} (HTTP)".format(self.PORT))
                self.httpd = h
                while not self.shutting_down:
                    h.serve_forever()
        except Exception as e:
            PIHOME_LOGGER.error("Server: PiHome Server failed to start: {}".format(e))
            time.sleep(20)
            self._run()

    def _run_callback(self):
        """Run the HTTPS-only callback server on HTTPS_CALLBACK_PORT.
        Uses the same self-signed cert as before — callers must accept it once
        in the browser, but the main app stays on plain HTTP.
        """
        try:
            from server.ssl_cert import make_ssl_context
            ssl_ctx = make_ssl_context()
            with PiHomeTCPServer(("", HTTPS_CALLBACK_PORT), CallbackRequestHandler) as h:
                if ssl_ctx:
                    h.socket = ssl_ctx.wrap_socket(h.socket, server_side=True)
                    PIHOME_LOGGER.info(
                        f"Server: Callback Server Listening on port: {HTTPS_CALLBACK_PORT} (HTTPS)"
                    )
                else:
                    PIHOME_LOGGER.warning(
                        f"Server: SSL unavailable — Callback Server on port: {HTTPS_CALLBACK_PORT} (HTTP)"
                    )
                self.callback_httpd = h
                while not self.shutting_down:
                    h.serve_forever()
        except Exception as e:
            PIHOME_LOGGER.error(f"Server: Callback Server failed to start: {e}")
            time.sleep(20)
            self._run_callback()
                
    
    async def websocket_server(self, websocket):
        # websockets 10+ no longer passes path as a second argument
        toast("Socket Connected", "info", 2)
        try:
            async for message in websocket:
                await self.SOCKET_HANDLER.handle_message(message, websocket)
        finally:
            print("WebSocket connection closed")

    async def start_socket_server(self):
        self.SOCKET_SERVER = await websockets.serve(self.websocket_server, "0.0.0.0", 8765)
        PIHOME_LOGGER.info("Server: WebSocket Listening on port: 8765 (WS)")
        await asyncio.Future()  # Wait indefinitely
            

SERVER = PiHomeServer()