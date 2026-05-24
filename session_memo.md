# Session Memo

## 2026-05-23

### 完了したこと

- ハードウェア確認
  - 購入ボード: ESP32-2432S028R（CYD デュアルUSBバリアント）
  - micro-USB × 1、Type-C × 1。Type-C は充電専用だったため micro-USB でデータ接続
  - シリアルポート: `/dev/cu.usbserial-110`

- MicroPython フラッシュ
  - `uv venv` でプロジェクトローカルの仮想環境を作成
  - `esptool` v5.2.0 で ESP32_GENERIC v1.25.0 を書き込み・検証 OK
  - `mpremote` で REPL 応答確認 (`>>>`)

- ライブラリ作成（`lib/`）
  - `ili9341.py` — ILI9341 TFT ドライバ（fill / fill_rect / pixel / text）
  - `xpt2046.py` — XPT2046 タッチドライバ（複数サンプル平均・座標マッピング）
  - `osc.py` — OSC 1.0 UDP 送信（int / float / str / bool 対応、自前実装）
  - `dotenv.py` — MicroPython 用 .env パーサ

- 動作確認
  - ディスプレイ表示 OK（青背景 + テキスト）
  - WiFi 接続 OK（IP: 192.168.68.69）
  - OSC 送信 OK（`/esp32/status "online"` → 192.168.68.62:7000）
  - タッチ検出 OK（座標を REPL と OSC で確認）

- ボタン UI 実装
  - `ui.py` — Button クラス（描画・押下ハイライト・ヒットテスト）
  - `boot.py` — 起動時 WiFi 接続
  - `main.py` — 2×2 ボタン UI + 押下/離上を OSC 送信
  - OSC アドレス: `/esp32/button/1〜4`、値: 1.0（押）/ 0.0（離）

### ピン配置メモ（デュアルUSBバリアント）

| 用途 | ピン |
|---|---|
| TFT MOSI/MISO/SCK/CS/DC/BL | 13/12/14/15/2/21 |
| Touch MOSI/MISO/SCK/CS/IRQ | 32/39/25/33/36 |
| SD MOSI/MISO/SCK/CS | 23/19/18/5 |
| RGB LED (active LOW) | R=4, G=16, B=17 |

### 次のステップ

- TouchDesigner で OSC 受信を確認
- タッチキャリブレーション（`xpt2046.py` の x_min/max, y_min/max を実測で調整）
- UI 拡張（スライダー、トグルボタン、ページ切替など）
- SD カードへのプリセット保存/読み込み
