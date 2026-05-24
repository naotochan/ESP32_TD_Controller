# ESP32 TD Controller

ESP32 + 2.8インチタッチスクリーンを **TouchDesigner 向け OSC コントローラ** にするプロジェクト。

タッチ操作 (ボタン押下・スライダー・RGB ピッカー) を WiFi 経由で OSC メッセージとして送信し、TouchDesigner で受信できます。ウィジェットレイアウトは **ブラウザ上のエディタ** でドラッグ&ドロップで作って書き出せます。

```
[ESP32 + タッチ画面]  --WiFi--> [OSC UDP]  -->  [TouchDesigner (OSC In CHOP)]
       ↑
   ブラウザのエディタでレイアウト作成 → widgets.py として書き出し
```

---

## 必要なもの

- **ハードウェア**: ESP32-2432S028R (通称 CYD = Cheap Yellow Display, デュアル USB バリアント)
- **ソフトウェア**: macOS / Linux, Python 3.10+, [uv](https://github.com/astral-sh/uv)
- **ケーブル**: データ通信できる **micro-USB ケーブル** (Type-C は充電専用なので NG)

---

## クイックスタート (初めての人向け)

### 1. リポジトリを clone して仮想環境を作る

```bash
git clone <this-repo>
cd ESP32_TD_Controller
uv venv
uv pip install esptool mpremote
```

### 2. ESP32 を micro-USB で接続してポートを確認

```bash
ls /dev/cu.usbserial-*
# 例: /dev/cu.usbserial-110 や /dev/cu.usbserial-210 が出る
```

> 以降のコマンドの **ポート名は環境に合わせて読み替えてください**。

### 3. MicroPython を焼く (初回のみ)

```bash
./.venv/bin/esptool.py --port /dev/cu.usbserial-210 erase_flash
./.venv/bin/esptool.py --port /dev/cu.usbserial-210 --baud 460800 write_flash 0x1000 micropython_esp32.bin
```

### 4. `.env` を作成

```bash
cat > .env << EOF
WIFI_SSID=your_wifi_ssid
WIFI_PASSWORD=your_wifi_password
OSC_HOST=192.168.x.x        # TouchDesigner を動かしている PC の IP
OSC_PORT=7000
EOF
```

### 5. デプロイ

```bash
./deploy.sh
```

これだけで `boot.py` / `main.py` / `ui.py` / `widgets.py` / `lib/*` / `.env` を全部 ESP32 に書き込んで再起動します。

> ポートが `/dev/cu.usbserial-210` 以外の場合は `./deploy.sh /dev/cu.usbserial-XXX` のように引数で指定。

### 6. TouchDesigner 側

OSC In CHOP を配置し **Port を 7000** に設定 → Active をオン。ESP32 のタッチ操作が CHOP に流れてきます。

---

## OSC メッセージ仕様

| ウィジェット | アドレス例 | 型 | 値 |
|---|---|---|---|
| Button | `/esp32/button/1` | float | `1.0` 押下 / `0.0` 離上 |
| Slider | `/esp32/slider/1` | float | `0.0` 〜 `1.0` 連続値 |
| RGBPicker | `/esp32/color/1` | float×3 | `r, g, b` (各 0.0〜1.0) |

アドレスはエディタで自由に変更可能。

---

## レイアウトの編集 (Web エディタ)

`ui-editor/` に React 製のレイアウトエディタがあります。

```bash
cd ui-editor
npm install
npm run dev
# → http://localhost:5173
```

ブラウザでウィジェットをドラッグ&ドロップで配置 → 「Export」ボタンで `widgets.py` をダウンロード → プロジェクトルートに置き換えて `./deploy.sh`。

---

## ファイル構成

```
.
├── deploy.sh            # ★ 全ファイルをまとめて ESP32 に転送 + 再起動
├── boot.py              # 起動時: .deploying チェック + WiFi 接続
├── main.py              # メインループ: タッチ → ウィジェット処理 → OSC 送信
├── ui.py                # Widget 基底クラス + Button / Slider / RGBPicker
├── widgets.py           # ★ ウィジェットレイアウト (UI エディタで生成)
├── lib/
│   ├── ili9341.py       # TFT ディスプレイドライバ
│   ├── xpt2046.py       # タッチパネルドライバ
│   ├── osc.py           # OSC 1.0 UDP 送信
│   └── dotenv.py        # .env パーサ
├── ui-editor/           # ブラウザのレイアウトエディタ (Vite + React)
├── .env                 # WiFi・OSC 設定 (git 管理外)
├── micropython_esp32.bin  # ESP32 用 MicroPython ファームウェア
└── tasks/               # session_log.md, todo.md
```

---

## ピン配置 (ESP32-2432S028R デュアルUSBバリアント)

| 用途 | ピン |
|---|---|
| TFT MOSI / MISO / SCK / CS / DC / BL | 13 / 12 / 14 / 15 / 2 / 21 |
| Touch MOSI / MISO / SCK / CS / IRQ | 32 / 39 / 25 / 33 / 36 |
| SD MOSI / MISO / SCK / CS | 23 / 19 / 18 / 5 |
| RGB LED (active LOW) | R=4, G=16, B=17 |

---

## トラブルシューティング

### `Failed to connect` (esptool)

ESP32 を手動でダウンロードモードに入れます:

1. **BOOT** ボタンを押しっぱなしのまま
2. **RST/EN** を 1回押して離す
3. **BOOT** を離す

→ 再度コマンド実行。

### `could not enter raw repl` (mpremote)

`deploy.sh` を使わずに個別 `mpremote` を呼んだ場合に発生しやすい問題です。`mpremote connect` は毎回 ESP32 をリセット → boot.py の途中で raw REPL に入れず失敗、というパターン。

**対策**: 必ず `./deploy.sh` を使う (1セッションで全コマンドをチェーンするため、リセットは1回だけ)。

### 画面が真っ黒のまま

`.env` の転送漏れで `KeyError` が起きている可能性大。`./deploy.sh` で `.env` も転送されるので、まず `.env` がプロジェクトルートに存在することを確認。

実行中のエラーを見たい時:

```bash
./.venv/bin/mpremote connect /dev/cu.usbserial-210 repl
# 物理 RST を押すと boot.py / main.py の出力が流れる
# Ctrl+X で抜ける
```

### どうしようもなくなった

flash 全消去 → MicroPython 焼き直し → deploy.sh で全部入れ直し:

```bash
./.venv/bin/esptool.py --port /dev/cu.usbserial-210 erase_flash
./.venv/bin/esptool.py --port /dev/cu.usbserial-210 --baud 460800 write_flash 0x1000 micropython_esp32.bin
./deploy.sh
```

---

## CYD ハードウェアの注意点

- **display rotation**: `rotation=0` が縦向き portrait (240×320)。`ili9341.py` の `set_rotation()` は `r % 2 == 0` のとき `width=240, height=320` を設定 (横向きと逆)
- **タッチ X 軸反転**: XPT2046 の X 座標は物理的に左右逆なので `xpt2046.py` 内で `sx = screen_w - 1 - sx` で反転済み
- **micro-USB のみデータ通信可**。Type-C は充電専用

---

## 開発メモ

- ESP32 上の MicroPython には `os.path` が **無い**。ファイル存在は `".env" in os.listdir()` か `try: os.stat(); except OSError` で判定
- `mpremote` のサブコマンドチェーンは `+` 区切りで明示するのが安全 (特に `cp src dst` が連続する場合)
- 1ファイルだけ差し替えたい場合も `./deploy.sh` で OK (全部書き直すが数秒で終わる)
- 詳細な開発履歴は `tasks/session_log.md` 参照
