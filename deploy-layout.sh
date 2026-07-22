#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

if [ ! -f layout.json ]; then
    echo "layout.json not found. Save it from the editor first."
    exit 1
fi

echo "Deploying layout.json to $PORT ..."

MPREMOTE="$SCRIPT_DIR/.venv/bin/mpremote"

"$MPREMOTE" connect "$PORT" \
    cp layout.json :layout.json + \
    cp main.py :main.py + \
    reset

echo "Done."
