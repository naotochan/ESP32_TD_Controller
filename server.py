"""Local deploy server — receives layout JSON from the editor and flashes it to ESP32 via USB."""
import glob
import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 3737
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MPREMOTE = os.path.join(SCRIPT_DIR, ".venv", "bin", "mpremote")
LAYOUT_FILE = os.path.join(SCRIPT_DIR, "layout.json")
LAYOUT_EXAMPLE = os.path.join(SCRIPT_DIR, "layout.json.example")
MAIN_FILE = os.path.join(SCRIPT_DIR, "main.py")


def list_ports():
    """Return sorted unique serial port candidates (macOS + Linux)."""
    patterns = [
        "/dev/cu.usbserial-*",
        "/dev/cu.usbmodem*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
    ]
    found = []
    for pat in patterns:
        found.extend(glob.glob(pat))
    return sorted(set(found))


def _is_preferred(path):
    """CH340/CP210x-style ports are typical for CYD ESP32 boards."""
    name = os.path.basename(path)
    return "usbserial" in name or name.startswith("ttyUSB")


def select_port(candidates=None):
    """Pick a serial port.

    Returns (port_or_None, candidates, ambiguous).
    - 0 candidates → (None, [], False)
    - 1 candidate → that port, not ambiguous
    - multiple → prefer usbserial/ttyUSB; unique preferred → that port;
      otherwise ambiguous (port=None for deploy safety)
    """
    ports = list(candidates) if candidates is not None else list_ports()
    if not ports:
        return None, [], False
    if len(ports) == 1:
        return ports[0], ports, False

    preferred = [p for p in ports if _is_preferred(p)]
    if len(preferred) == 1:
        return preferred[0], ports, False
    # Ambiguous: multiple preferred or none preferred among many
    return None, ports, True


def find_port():
    """Backward-compatible: return selected port or None."""
    port, _, _ = select_port()
    return port


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
        port, ports, ambiguous = select_port()
        body = json.dumps({
            "port": port,
            "ports": ports,
            "count": len(ports),
            "ambiguous": ambiguous,
        }).encode()
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

        esp_port, ports, ambiguous = select_port()
        if not ports:
            self._respond(503, "ESP32 not found. Connect via USB.")
            return
        if ambiguous or not esp_port:
            listing = ", ".join(ports)
            self._respond(
                503,
                f"Multiple serial ports ({len(ports)}): {listing}. "
                f"Disconnect extras or use ./deploy-layout.sh <port>",
            )
            return

        try:
            result = subprocess.run(
                [MPREMOTE, "connect", esp_port,
                 "cp", LAYOUT_FILE, ":layout.json", "+",
                 "cp", MAIN_FILE, ":main.py", "+",
                 "reset"],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            self._respond(504, "mpremote timed out — check USB connection")
            return

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
    if not os.path.exists(LAYOUT_FILE) and os.path.exists(LAYOUT_EXAMPLE):
        shutil.copy(LAYOUT_EXAMPLE, LAYOUT_FILE)
        print(f"Initialized layout.json from {os.path.basename(LAYOUT_EXAMPLE)}")

    httpd = ReusableHTTPServer(("localhost", PORT), Handler)
    print(f"Deploy server running at http://localhost:{PORT}")
    print("Waiting for deploy requests from the editor...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
