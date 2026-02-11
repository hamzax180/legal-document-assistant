from http.server import BaseHTTPRequestHandler
import sys

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        msg = f"Hello from minimal function. Python {sys.version}"
        self.wfile.write(msg.encode('utf-8'))
        return
