#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# deploy server をバックグラウンドで起動
python3 "$SCRIPT_DIR/server.py" &
SERVER_PID=$!

# エディターを起動（Ctrl+C で終了）
cd "$SCRIPT_DIR/ui-editor" && npm run dev

# エディター終了時にサーバーも止める
kill $SERVER_PID 2>/dev/null
