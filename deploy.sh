#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# macOS + Linux serial ports. Prefer CH340/CP210x-style (usbserial / ttyUSB).
list_ports() {
    ls /dev/cu.usbserial-* /dev/cu.usbmodem* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | sort -u || true
}

prefer_ports() {
    local all="$1"
    local preferred
    preferred=$(echo "$all" | grep -E 'usbserial|ttyUSB' || true)
    if [ -n "$preferred" ]; then
        echo "$preferred"
    else
        echo "$all"
    fi
}

if [ -n "${1:-}" ]; then
    PORT="$1"
else
    ALL_PORTS=$(list_ports)
    if [ -z "$ALL_PORTS" ]; then
        echo "Usage: $0 [/dev/cu.usbserial-XXX | /dev/ttyUSB0 | ...]"
        echo "No device found. Connect ESP32 and retry, or specify port."
        echo "  macOS:  /dev/cu.usbserial-* /dev/cu.usbmodem*"
        echo "  Linux:  /dev/ttyUSB* /dev/ttyACM*"
        exit 1
    fi
    CANDIDATES=$(prefer_ports "$ALL_PORTS")
    COUNT=$(echo "$CANDIDATES" | grep -c . || true)
    if [ "$COUNT" -gt 1 ]; then
        echo "Multiple serial ports found (ambiguous):"
        echo "$ALL_PORTS" | sed 's/^/  /'
        echo "Specify the ESP32 port explicitly, e.g.:"
        echo "  $0 $(echo "$CANDIDATES" | head -1)"
        exit 1
    fi
    PORT=$(echo "$CANDIDATES" | head -1)
fi

# layout.json: same as server.py — copy from example if missing
if [ ! -f layout.json ]; then
    if [ -f layout.json.example ]; then
        cp layout.json.example layout.json
        echo "Initialized layout.json from layout.json.example"
    else
        echo "layout.json not found (and no layout.json.example)."
        exit 1
    fi
fi

echo "Deploying to $PORT ..."

MPREMOTE="$SCRIPT_DIR/.venv/bin/mpremote"

# Optional calib.json transfer
CALIB_ARGS=()
if [ -f calib.json ]; then
    CALIB_ARGS=(+ cp calib.json :calib.json)
    echo "Including calib.json"
fi

# Single mpremote session — one connection, one reset.
# Use '+' as explicit subcommand separator (required when cp dest is ':' or path).
"$MPREMOTE" connect "$PORT" \
    exec "import os" + \
    exec "'lib' in os.listdir() or os.mkdir('lib')" + \
    cp main.py :main.py + \
    cp ui.py :ui.py + \
    cp widgets.py :widgets.py + \
    cp layout.json :layout.json + \
    cp lib/dotenv.py :lib/dotenv.py + \
    cp lib/ili9341.py :lib/ili9341.py + \
    cp lib/osc.py :lib/osc.py + \
    cp lib/xpt2046.py :lib/xpt2046.py + \
    cp .env :.env + \
    cp boot.py :boot.py \
    "${CALIB_ARGS[@]}" + \
    reset

echo "Done."
