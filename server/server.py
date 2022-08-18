import http.server
import json
import socketserver
from threading import Thread

from util.const import SERVER_PORT, _MUSIC_SCREEN
from util.helpers import audio_player, goto_screen

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            self.path = './web/index.html'
            resp = http.server.SimpleHTTPRequestHandler.do_GET(self)
            return resp
        except:
            pass
    
    def do_POST(self):
        # print("POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n", str(self.path), str(self.headers), post_data.decode('utf-8'))
        try:
            content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
            post_data = self.rfile.read(content_length) # <--- Gets the data itself
            payload = json.loads(post_data.decode('utf-8'))
            if "play" in payload:
                url = payload["play"]
                audio_player().play(url)
                goto_screen(_MUSIC_SCREEN)
            if "stop" in payload:
                audio_player().stop()
            if "volume" in payload: 
                v = int(payload["volume"])
                audio_player().set_volume(v)
            self._set_response()
            self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))
        except:
            pass

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

    def stop_server(self):
        if self.is_online():
            self.shutting_down = True
            self.httpd.shutdown()
            self.httpd = None

    def is_online(self):
        if self.httpd == None:
            return False
        return True

    def _run(self):
        Handler = MyHttpRequestHandler
        with socketserver.TCPServer(("", self.PORT), Handler) as h:
            self.httpd = h
            while not self.shutting_down:
                h.serve_forever()