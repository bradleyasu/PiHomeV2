import http.server
import socketserver
from threading import Thread

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.path = './web/index.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
 
 
class PiHomeServer():
    PORT = 80
    SERVER_THREAD = None
    def __init__(self, **kwargs):
        super(PiHomeServer, self).__init__(**kwargs)

    def start_server(self):
        self.SERVER_THREAD = Thread(target=self._run)
        self.SERVER_THREAD.start()

    def stop_server(self):
        self.SERVER_THREAD.join()
        

    def _run(self):
        Handler = MyHttpRequestHandler
        with socketserver.TCPServer(("", self.PORT), Handler) as httpd:
            print("Http Server Serving at port", self.PORT)
            httpd.serve_forever()