from cmath import inf
import http.server
import json
import socketserver
import time
from events.pihomeevent import PihomeEventFactory
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from server.socket_handler import SocketHandler
import websockets
import asyncio
from threading import Thread
from services.audio.audioplayernew import AUDIO_PLAYER
from services.wallpaper.wallpaper import WALLPAPER_SERVICE, Wallpaper

from util.const import SERVER_PORT, _MUSIC_SCREEN
from util.helpers import get_app, process_webhook, toast
from util.phlog import PIHOME_LOGGER

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_GET(self):
        PIHOME_LOGGER.info("Server: GET Request Initiated")
        if self.path.startswith("/status"):
            self._get_status(self.path.replace("/status", "").replace("/", ""))
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

    def do_OPTIONS(self):
        self._set_response()
    
    def do_POST(self):
        try:
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

            self._set_response()
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


class PiHomeServer():
    PORT = SERVER_PORT
    SOCKET_PORT = 9090
    SERVER_THREAD = None
    SOCKET_THREAD = None
    SOCKET_LOOP = None
    SOCKET_SERVER = None
    httpd = None
    shutting_down = False
    SOCKET_HANDLER = SocketHandler()
    def __init__(self, **kwargs):
        super(PiHomeServer, self).__init__(**kwargs)

    def start_server(self):
        self.SERVER_THREAD = Thread(target=self._run, daemon=True)
        self.SERVER_THREAD.start()
        self.SOCKET_THREAD = Thread(target=self._run_socket, daemon=True)
        self.SOCKET_THREAD.start()
        
        PIHOME_LOGGER.info("Server: PiHome Server has started")

    def stop_server(self):
        if self.is_online():
            self.shutting_down = True
            self.httpd.shutdown()
            self.httpd = None
            PIHOME_LOGGER.info("Server: PiHome Server has shutdown")
        else:
            PIHOME_LOGGER.warn("Server: Failed to shutdown PiHome server.  It is not running")
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
        Handler = MyHttpRequestHandler
        try:
            from server.ssl_cert import make_ssl_context
            ssl_ctx = make_ssl_context()
            with PiHomeTCPServer(("", self.PORT), Handler) as h:
                if ssl_ctx:
                    h.socket = ssl_ctx.wrap_socket(h.socket, server_side=True)
                    PIHOME_LOGGER.info("Server: PiHome Server Listening on port: {} (HTTPS)".format(self.PORT))
                else:
                    PIHOME_LOGGER.warning("Server: SSL setup failed — falling back to HTTP")
                    PIHOME_LOGGER.info("Server: PiHome Server Listening on port: {} (HTTP)".format(self.PORT))
                self.httpd = h
                while not self.shutting_down:
                    h.serve_forever()
        except Exception as e:
            PIHOME_LOGGER.error("Server: PiHome Server failed to start: {}".format(e))
            # try again after 20 seconds
            time.sleep(20)
            self._run()
                
    
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
        await asyncio.Future()  # Wait indefinitely
            

SERVER = PiHomeServer()