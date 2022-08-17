import http.server
import json
import socketserver
from threading import Thread

from util.const import SERVER_PORT
from util.helpers import audio_player

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.path = './web/index.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        # print("POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n", str(self.path), str(self.headers), post_data.decode('utf-8'))
        try:
            payload = json.loads(post_data.decode('utf-8'))
            if "play" in payload:
                url = payload["play"]
                audio_player().play(url)
            if "stop" in payload:
                audio_player().stop()
            if "volume" in payload: 
                v = int(payload["volume"])
                audio_player().set_volume(v)
        except:
            pass
        self._set_response()
        self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))

    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/javascript')
        self.end_headers()
 
 
class PiHomeServer():
    PORT = SERVER_PORT
    SERVER_THREAD = None
    httpd = None
    def __init__(self, **kwargs):
        super(PiHomeServer, self).__init__(**kwargs)

    def start_server(self):
        self.SERVER_THREAD = Thread(target=self._run)
        self.SERVER_THREAD.start()

    def stop_server(self):
        self.httpd.shutdown()
        

    def _run(self):
        Handler = MyHttpRequestHandler
        with socketserver.TCPServer(("", self.PORT), Handler) as h:
            self.httpd = h
            h.serve_forever()