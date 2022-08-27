from cmath import inf
import http.server
import json
import socketserver
from threading import Thread

from util.const import SERVER_PORT, _MUSIC_SCREEN
from util.helpers import audio_player, error, goto_screen, info, toast, warn

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        info("Server: GET Request Initiated")
        try:
            self.path = './web/index.html'
            resp = http.server.SimpleHTTPRequestHandler.do_GET(self)
            return resp
        except Exception as e:
            error("Failed to process GET request")
    
    def do_POST(self):
        # print("POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n", str(self.path), str(self.headers), post_data.decode('utf-8'))
        info("Server: POST Request Initiated")
        try:
            content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
            post_data = self.rfile.read(content_length) # <--- Gets the data itself
            payload = json.loads(post_data.decode('utf-8'))
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
            self._set_response()
            self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))
        except Exception as e:
            toast("An error occurred processing the server request", "warn", 10)
            error("Server: POST Request Failed: {}".format(e))

    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/javascript')
        self.end_headers()
 
 
class PiHomeServer():
    PORT = SERVER_PORT
    SERVER_THREAD = None
    httpd = None
    shutting_down = False
    def __init__(self, **kwargs):
        super(PiHomeServer, self).__init__(**kwargs)

    def start_server(self):
        self.SERVER_THREAD = Thread(target=self._run)
        self.SERVER_THREAD.start()
        info("Server: PiHome Server has started")

    def stop_server(self):
        if self.is_online():
            self.shutting_down = True
            self.httpd.shutdown()
            self.httpd = None
            info("Server: PiHome Server has shutdown")
        else:
            warn("Server: Failed to shutdown PiHome server.  It is not running")

    def is_online(self):
        if self.httpd == None:
            return False
        return True

    def _run(self):
        Handler = MyHttpRequestHandler
        with socketserver.TCPServer(("", self.PORT), Handler) as h:
            self.httpd = h
            info("Server: PiHome Server Listening on port: {}".format(self.PORT))
            while not self.shutting_down:
                h.serve_forever()