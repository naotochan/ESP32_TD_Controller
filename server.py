"""Local deploy server — receives layout JSON from the editor and flashes it to ESP32 via USB."""
import glob
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 3737
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MPREMOTE = os.path.join(SCRIPT_DIR, ".venv", "bin", "mpremote")
LAYOUT_FILE = os.path.join(SCRIPT_DIR, "layout.json")
MAIN_FILE = os.path.join(SCRIPT_DIR, "main.py")


def find_port():
    candidates = glob.glob("/dev/cu.usbserial-*") + glob.glob("/dev/cu.usbmodem*")
    return candidates[0] if candidates else None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_GET(self):
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return
        esp_port = find_port()
        body = json.dumps({"port": esp_port}).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/deploy":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, "Invalid JSON")
            return

        with open(LAYOUT_FILE, "w") as f:
            json.dump(data, f, indent=2)

        esp_port = find_port()
        if not esp_port:
            self._respond(503, "ESP32 not found. Connect via USB.")
            return

        result = subprocess.run(
            [MPREMOTE, "connect", esp_port,
             "cp", LAYOUT_FILE, ":layout.json", "+",
             "cp", MAIN_FILE, ":main.py", "+",
             "reset"],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            self._respond(200, f"Deployed to {esp_port}")
        else:
            self._respond(500, result.stderr or "Deploy failed")

    def _respond(self, code, message):
        body = message.encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    httpd = ReusableHTTPServer(("localhost", PORT), Handler)
    print(f"Deploy server running at http://localhost:{PORT}")
    print("Waiting for deploy requests from the editor...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
