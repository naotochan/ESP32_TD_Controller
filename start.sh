#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# deploy server をバックグラウンドで起動
python3 "$SCRIPT_DIR/server.py" &
SERVER_PID=$!

# Ctrl+C 時にサーバーも一緒に止める
cleanup() {
    kill $SERVER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
    exit
}
trap cleanup INT TERM

# エディターを起動（Ctrl+C で終了）
cd "$SCRIPT_DIR/ui-editor" && npm run dev

# エディター終了時にサーバーも止める
cleanup
