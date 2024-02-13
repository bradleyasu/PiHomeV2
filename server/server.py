from cmath import inf
import http.server
import json
import socketserver
from server.socket_handler import SocketHandler
import websockets
import asyncio
from threading import Thread
from services.wallpaper.wallpaper import Wallpaper

from util.const import SERVER_PORT, _MUSIC_SCREEN
from util.helpers import audio_player, error, get_app, goto_screen, info, process_webhook, toast, warn

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        info("Server: GET Request Initiated")
        if self.path == "/status":
            self._get_status()
        elif self.path == "/" or self.path == "" or self.path == "/index.html":
            self._get_index()
        else:
            self.path = "./web" + self.path
            super().do_GET()

    # def guess_type(self, path):
    #     # Override the default MIME type guessing to handle CSS files.
    #     if path.endswith(".css"):
    #         return "text/css"
    #     if path.endswith(".js"):
    #         return "application/javascript"
    #     return super().guess_type(path)
    
    def _get_status(self):
        info("Server: Getting current status from multiple services")
        try:
            wallpaper = get_app().wallpaper_service.source
            self._set_response()
            # self.wfile.write(json.dumps({
            #     'wallpaper': wallpaper
            # }).encode("utf-8"))
        except Exception as e:
            error("Failed to get status of services: {}".format(e))

    def _get_index(self):
        try:
            self.path = './web/index.html'
            # resp = http.server.SimpleHTTPRequestHandler.do_GET(self)
            # return resp
            super().do_GET()

        except Exception as e:
            error("Failed to process GET request.  Fetching index page")
            error(e)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Origin, Content-Type")
        self.end_headers()

    
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
            post_data = self.rfile.read(content_length) # <--- Gets the data itself
            payload = json.loads(post_data.decode('utf-8'))
            info("POST request: {} | {}".format(str(self.path), post_data.decode('utf-8')))
            if "stop" in payload:
                audio_player().stop()
            if "clear_queue" in payload:
                audio_player().clear_playlist()
            if "volume" in payload: 
                v = int(payload["volume"])
                audio_player().set_volume(v)
            if "play" in payload:
                url = payload["play"]
                audio_player().play(url)
                goto_screen(_MUSIC_SCREEN)
            if "app" in payload:
                goto_screen(payload["app"])
            if "webhook" in payload:
                process_webhook(payload["webhook"])

            self._set_response()
            # self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))
        except Exception as e:
            toast("An error occurred processing the server request", "warn", 10)
            error("Server: POST Request Failed: {}".format(e))

    def _set_response(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

        response_data = {
            "status": "success"
        }

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
        self.SERVER_THREAD = Thread(target=self._run)
        self.SERVER_THREAD.start()
        self.SOCKET_THREAD = Thread(target=self._run_socket)
        self.SOCKET_THREAD.start()
        
        info("Server: PiHome Server has started")

    def stop_server(self):
        if self.is_online():
            self.shutting_down = True
            self.httpd.shutdown()
            self.httpd = None
            info("Server: PiHome Server has shutdown")
        else:
            warn("Server: Failed to shutdown PiHome server.  It is not running")
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
            error("Socket Server Error: {}".format(e))
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
        with socketserver.TCPServer(("", self.PORT), Handler) as h:
            self.httpd = h
            info("Server: PiHome Server Listening on port: {}".format(self.PORT))
            while not self.shutting_down:
                h.serve_forever()
                
    
    async def websocket_server(self, websocket, path):
        toast("Socket Connected", "info", 2)
        try:
            async for message in websocket:
                await self.SOCKET_HANDLER.handle_message(message, websocket)
        finally:
            print("WebSocket connection closed")

    async def start_socket_server(self):
        self.SOCKET_SERVER = await websockets.serve(self.websocket_server, "0.0.0.0", 8765)
        await asyncio.Future()  # Wait indefinitely
            