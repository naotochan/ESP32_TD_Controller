#!/bin/bash
set -e

PORT="${1:-$(ls /dev/cu.usbserial-* /dev/cu.usbmodem* 2>/dev/null | head -1 || true)}"
if [ -z "$PORT" ]; then
    echo "Usage: $0 [/dev/cu.usbserial-XXX]"
    echo "No device found. Connect ESP32 and retry."
    exit 1
fi

if [ ! -f layout.json ]; then
    echo "layout.json not found. Save it from the editor first."
    exit 1
fi

echo "Deploying layout.json to $PORT ..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MPREMOTE="$SCRIPT_DIR/.venv/bin/mpremote"
cd "$SCRIPT_DIR"

"$MPREMOTE" connect "$PORT" \
    cp layout.json :layout.json + \
    cp main.py :main.py + \
    reset

echo "Done."
