# ESP32 TD Controller

ESP32 + 2.8 インチタッチスクリーンを **TouchDesigner 向け OSC コントローラ** にするプロジェクト。

タッチ操作（ボタン・スライダー・カラーピッカー・ページ切替）を WiFi 経由で OSC メッセージとして送信。レイアウトは **ブラウザの Web エディタ** でドラッグ&ドロップ編集し、ワンクリックで ESP32 にデプロイできます。

```
[Web エディタ] --Deploy ボタン--> [ローカル deploy server] --USB--> [ESP32]
                                                                       ↓ WiFi
                                                              [TouchDesigner (OSC In CHOP)]
```

---

## 必要なもの

- **ハードウェア**: ESP32-2432S028R（通称 CYD = Cheap Yellow Display, **デュアル USB バリアント**）
- **ソフトウェア**: macOS / Linux, Python 3.10+, [uv](https://github.com/astral-sh/uv), Node.js 18+
- **ケーブル**: データ通信できる **micro-USB ケーブル**（Type-C は充電専用なので NG）

---

## クイックスタート

### 1. リポジトリを clone してセットアップ

```bash
git clone <this-repo>
cd ESP32_TD_Controller
uv venv
uv pip install esptool mpremote
cd ui-editor && npm install && cd ..
```

### 2. ESP32 を micro-USB で接続 → ポート確認

```bash
ls /dev/cu.usbserial-* /dev/cu.usbmodem*
# 例: /dev/cu.usbserial-110
```

### 3. MicroPython を焼く（初回のみ）

リポジトリに同梱の `micropython_esp32.bin`（v1.25.0, CYD で動作確認済み）を使用:

```bash
./.venv/bin/esptool.py --port /dev/cu.usbserial-110 erase_flash
./.venv/bin/esptool.py --port /dev/cu.usbserial-110 --baud 460800 write_flash 0x1000 micropython_esp32.bin
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

### 5. 初期デプロイ（全ファイル転送）

```bash
./deploy.sh
```

`boot.py` / `main.py` / `ui.py` / `widgets.py` / `lib/*` / `.env` を ESP32 に書き込んで再起動します。ポートが自動検出できない場合は `./deploy.sh /dev/cu.usbserial-XXX` のように引数で指定。

### 6. TouchDesigner 側

OSC In CHOP を配置し **Port を 7000** に設定 → Active をオン。ESP32 のタッチ操作が CHOP に流れてきます。

---

## レイアウト編集 (Web エディタ)

### 起動

```bash
./start.sh
```

- Vite dev サーバ（エディタ UI）と Python deploy server を同時起動
- ブラウザで http://localhost:5173 を開く
- ヘッダーに ESP32 の接続状態が表示される（USB 抜き挿しで自動検出）

### 使い方

1. パネルから widget をドラッグして配置（Button / Slider / HSlider / HSVPicker / IPDisplay / PageButton）
2. プロパティで OSC アドレスなどを編集
3. **Deploy** ボタン → 自動で `layout.json` を ESP32 に転送して再起動
4. （任意）**Save** で `layout.json` をローカル保存、**Open** で読み込み

### CLI でレイアウトのみデプロイ

エディタを使わず CLI で完結させたい場合:

```bash
./deploy-layout.sh
```

`layout.json` と `main.py` だけ転送して再起動。

---

## OSC メッセージ仕様

| ウィジェット | アドレス例 | 型 | 値 |
|---|---|---|---|
| Button | `/esp32/button/1` | float | `1.0` 押下 / `0.0` 離上 |
| Slider | `/esp32/slider/1` | float | `0.0` 〜 `1.0` 連続値 |
| HSlider | `/esp32/hslider/1` | float | `0.0` 〜 `1.0` 連続値（横） |
| HSVPicker | `/esp32/color/1` | float×3 | `r, g, b` (各 0.0〜1.0) |
| PageButton | — | — | ページ切替（OSC は送信しない） |

アドレスはエディタで自由に変更可能。

---

## ファイル構成

```
.
├── deploy.sh             # 全ファイルをまとめて ESP32 に転送 + 再起動
├── deploy-layout.sh      # layout.json と main.py だけ転送
├── start.sh              # エディタ + deploy server を同時起動
├── server.py             # ローカル deploy server（Web エディタからの POST を受ける）
├── boot.py               # 起動時: .deploying チェック + WiFi 接続
├── main.py               # メインループ: タッチ → ウィジェット処理 → OSC 送信
├── ui.py                 # Widget クラス (Button / Slider / HSlider / HSVPicker / IPDisplay / PageButton)
├── widgets.py            # フォールバック用の初期レイアウト（layout.json がない場合に使用）
├── layout.json           # Web エディタが書き出すレイアウト定義（実環境では server.py が上書き）
├── lib/
│   ├── ili9341.py        # TFT ディスプレイドライバ
│   ├── xpt2046.py        # タッチパネルドライバ
│   ├── osc.py            # OSC 1.0 UDP 送信
│   └── dotenv.py         # .env パーサ（MicroPython 用）
├── ui-editor/            # ブラウザのレイアウトエディタ (Vite + React)
├── micropython_esp32.bin # ESP32 用 MicroPython ファームウェア（v1.25.0）
└── .env                  # WiFi・OSC 設定 (git 管理外、各自作成)
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

ESP32 を手動でダウンロードモードに入れる:

1. **BOOT** ボタンを押しっぱなしのまま
2. **RST/EN** を 1 回押して離す
3. **BOOT** を離す → 再度コマンド実行

### `could not enter raw repl` (mpremote)

`deploy.sh` を使わずに個別 `mpremote` を呼んだ場合に発生しやすい。`boot.py` には 2 秒の deploy 待ち窓があるが、複数回 mpremote を起動するとリセットのタイミングがずれて失敗する。

**対策**: 必ず `./deploy.sh` か `./deploy-layout.sh` を使う（1 セッションで全コマンドをチェーンするためリセット 1 回で済む）。

### 画面が真っ黒のまま

`.env` の転送漏れで `KeyError` の可能性大。`./deploy.sh` 経由なら `.env` も自動転送される。プロジェクトルートに `.env` が存在することをまず確認。

実行中のエラーを確認したいとき:

```bash
./.venv/bin/mpremote connect /dev/cu.usbserial-110 repl
# 物理 RST を押すと boot.py / main.py の出力が流れる
# Ctrl+X で抜ける
```

### Web エディタの「Deploy」が失敗する

- ESP32 が USB 接続されているか（ヘッダーの状態表示を確認）
- deploy server (port 3737) が起動しているか（`./start.sh` 経由なら自動起動）

### どうしようもなくなった

flash 全消去 → MicroPython 焼き直し → `deploy.sh` で全部入れ直し:

```bash
./.venv/bin/esptool.py --port /dev/cu.usbserial-110 erase_flash
./.venv/bin/esptool.py --port /dev/cu.usbserial-110 --baud 460800 write_flash 0x1000 micropython_esp32.bin
./deploy.sh
```

---

## CYD ハードウェアの注意点

- **display rotation**: `rotation=0` が縦向き portrait (240×320)。`ili9341.py` の `set_rotation()` は `r % 2 == 0` のとき `width=240, height=320` を設定（横向きと逆）
- **タッチ X 軸反転**: XPT2046 の X 座標は物理的に左右逆なので `xpt2046.py` 内で `sx = screen_w - 1 - sx` で反転済み
- **micro-USB のみデータ通信可**。Type-C は充電専用

---

## 開発メモ

- ESP32 上の MicroPython には `os.path` が無い → 存在判定は `".env" in os.listdir()` か `try: os.stat(); except OSError`
- `mpremote` のサブコマンドチェーンは `+` 区切りで明示するのが安全
- 起動時のレイアウト読み込み優先順位: `layout.json` → `widgets.py`（フォールバック）
- 詳細な開発履歴は `tasks/session_log.md`（ローカルのみ）
