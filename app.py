"""Small dependency-free web application for the Docker homework."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PORT = int(os.environ.get("PORT", "8000"))
APP_MESSAGE = os.environ.get("APP_MESSAGE", "Hello from Docker!")
PAGE = Path(__file__).with_name("index.html").read_bytes()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            body, content_type, status = PAGE, "text/html; charset=utf-8", 200
        elif path == "/api/info":
            body = json.dumps({"message": APP_MESSAGE, "port": PORT}).encode()
            content_type, status = "application/json; charset=utf-8", 200
        elif path == "/health":
            body, content_type, status = b'{"status":"ok"}', "application/json", 200
        else:
            body, content_type, status = b"Not found", "text/plain", 404
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Listening on 0.0.0.0:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
