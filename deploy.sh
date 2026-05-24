#!/bin/bash
set -e

PORT="${1:-$(ls /dev/cu.usbserial-* /dev/cu.usbmodem* 2>/dev/null | head -1 || true)}"
if [ -z "$PORT" ]; then
    echo "Usage: $0 [/dev/cu.usbserial-XXX | /dev/cu.usbmodemXXX]"
    echo "No device found. Connect ESP32 and retry, or specify port."
    exit 1
fi

echo "Deploying to $PORT ..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MPREMOTE="$SCRIPT_DIR/.venv/bin/mpremote"
cd "$SCRIPT_DIR"

# Single mpremote session — one connection, one reset.
# Use '+' as explicit subcommand separator (required when cp dest is ':' or path).
"$MPREMOTE" connect "$PORT" \
    exec "import os" + \
    exec "'lib' in os.listdir() or os.mkdir('lib')" + \
    cp main.py :main.py + \
    cp ui.py :ui.py + \
    cp widgets.py :widgets.py + \
    cp lib/dotenv.py :lib/dotenv.py + \
    cp lib/ili9341.py :lib/ili9341.py + \
    cp lib/osc.py :lib/osc.py + \
    cp lib/xpt2046.py :lib/xpt2046.py + \
    cp .env :.env + \
    cp boot.py :boot.py + \
    reset

echo "Done."
