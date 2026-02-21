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
            self.path = "./web" + self.path
            super().do_GET()

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
            with socketserver.TCPServer(("", self.PORT), Handler) as h:
                self.httpd = h
                PIHOME_LOGGER.info("Server: PiHome Server Listening on port: {}".format(self.PORT))
                while not self.shutting_down:
                    h.serve_forever()
        except Exception as e:
            PIHOME_LOGGER.error("Server: PiHome Server failed to start: {}".format(e))
            # try again after 20 seconds
            time.sleep(20)
            self._run()
                
    
    async def websocket_server(self, websocket):
        """
        WebSocket handler - compatible with websockets 10.0+
        In older versions, this received (websocket, path) but newer versions only pass websocket.
        Path is now accessible via websocket.request.path if needed.
        """
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