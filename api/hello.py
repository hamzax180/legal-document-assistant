from http.server import BaseHTTPRequestHandler
import sys

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        
        try:
            import backend.app
            import_status = "SUCCESS"
        except Exception as e:
            import_status = f"FAILED: {e}"

        msg = f"Hello from minimal function. Python {sys.version}\nBackend Import: {import_status}"
        self.wfile.write(msg.encode('utf-8'))
        return
