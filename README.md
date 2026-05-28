# ESP32 TD Controller

日本語 · [English](README_EN.md)

ESP32 + 2.8インチタッチスクリーンを **TouchDesigner 向け OSC コントローラ** にするプロジェクト。

タッチ操作（ボタン・スライダー・カラーピッカー・ページ切替）を WiFi 経由で OSC メッセージとして送信し、TouchDesigner で受信できます。ウィジェットレイアウトは **ブラウザ上のエディタ** でドラッグ&ドロップ編集 → ワンクリックで ESP32 にデプロイできます。

```
[Web エディタ] --Deploy ボタン--> [ローカル deploy server] --USB--> [ESP32]
                                                                       ↓ WiFi
                                                              [TouchDesigner (OSC In CHOP)]
```

---

## 必要なもの

- **ハードウェア**: ESP32-2432S028R (通称 CYD = Cheap Yellow Display, デュアル USB バリアント) [AliExpress](https://ja.aliexpress.com/item/1005007774435209.html?spm=a2g0o.order_list.order_list_main.35.2491585aMPDhYX&gatewayAdapt=glo2jpn)
- **ソフトウェア**: macOS / Linux, Python 3.10+, [uv](https://github.com/astral-sh/uv), Node.js 18+
- **ブラウザ**: Web エディタの Open / Save が File System Access API を使うため **Chrome / Edge 必須**（Safari / Firefox は未対応）
- **ケーブル**: データ通信できるケーブル

---

## クイックスタート (初めての人向け)

### 1. リポジトリを clone してセットアップ

```bash
git clone https://github.com/naotochan/ESP32_TD_Controller.git
cd ESP32_TD_Controller
uv venv
uv pip install "esptool<5" mpremote
cd ui-editor && npm install && cd ..
```

### 2. ESP32 を接続してポートを確認

```bash
ls /dev/cu.usbserial-* /dev/cu.usbmodem*
# 例: /dev/cu.usbserial-110
```

以降のコマンドの **ポート名は環境に合わせて読み替えてください**。

### 3. MicroPython を焼く (初回のみ)

リポジトリに同梱の `micropython_esp32.bin`（v1.25.0, CYD で動作確認済み）を使います:

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

### 5. 初期デプロイ

```bash
./deploy.sh
# 自動検出が誤る / 複数機器がある場合はポート明示
./deploy.sh /dev/cu.usbserial-XXX
```

これだけで `boot.py` / `main.py` / `ui.py` / `widgets.py` / `lib/*` / `.env` を全部 ESP32 に書き込んで再起動します。

**ESP32 の他に USB シリアル機器がつながっている場合，書き込み先を誤ることがあります。 ESP32 だけを接続するか，ESP32 のシリアルポートを正しく指定してください。**

### 6. TouchDesigner 側

OSC In CHOP を配置し **Port を 7000** に設定 → Active をオン。ESP32 のタッチ操作が CHOP に流れてきます。

---

## 二回目以降の手順

初回セットアップ（venv / `npm install` / MicroPython 焼き / `.env` 作成）が済んでいれば、普段の作業は **Web エディタの Deploy ボタン** だけで完結します。

### レイアウトを編集してデプロイ（普段の作業）

```bash
./start.sh
# → エディタ (http://localhost:5173) と deploy server (port 3737) が同時起動
```

ブラウザで widget をドラッグ&ドロップで配置・編集 → 「**Deploy**」ボタンで `layout.json` が ESP32 に転送され、自動再起動します。エディタ右上に **ESP32 接続状態** が表示されるので、USB を挿し直すと自動で再認識されます。

### CLI から layout だけデプロイしたいとき

保存済みの `layout.json` を CLI で送り込むケース:

```bash
./deploy-layout.sh
./deploy-layout.sh /dev/cu.usbserial-XXX
```

### コード本体や `.env` を変更したとき

```bash
./deploy.sh                              # 全ファイル再転送
./deploy.sh /dev/cu.usbserial-XXX
```

`main.py` / `ui.py` / `lib/*` / `boot.py` / `.env` を編集したとき用。

### ESP32 の挙動を確認したい (REPL)

```bash
./.venv/bin/mpremote connect /dev/cu.usbserial-XXX repl
# 物理 RST ボタンを押すと boot.py / main.py の出力が流れる
# Ctrl+X で抜ける
```

---

## OSC メッセージ仕様

| ウィジェット | アドレス例 | 型 | 値 |
|---|---|---|---|
| Button | `/esp32/button/1` | float | `1.0` 押下 / `0.0` 離上 |
| Slider | `/esp32/slider/1` | float | `0.0` 〜 `255.0` 連続値（縦） |
| HSlider | `/esp32/hslider/1` | float | `0.0` 〜 `255.0` 連続値（横） |
| HSVPicker | `/esp32/color/1` | int×3 | `r, g, b` (各 0〜255) |
| PageButton | — | — | ページ切替（OSC は送信しない） |

アドレスはエディタで自由に変更可能。

---

## ファイル構成

```
.
├── deploy.sh             # 全ファイルをまとめて ESP32 に転送 + 再起動
├── deploy-layout.sh      # layout.json と main.py だけ転送
├── start.sh              # エディタ + deploy server を同時起動
├── server.py             # ローカル deploy server（エディタからの POST を受ける）
├── boot.py               # 起動時の WiFi 接続
├── main.py               # メインループ: タッチ → ウィジェット処理 → OSC 送信
├── ui.py                 # Widget クラス (Button / Slider / HSlider / HSVPicker / IPDisplay / PageButton)
├── widgets.py            # フォールバック用の初期レイアウト（layout.json がない場合に使用）
├── layout.json.example   # 起動時に layout.json へコピーされるサンプル（layout.json 自体は git 管理外）
├── lib/
│   ├── ili9341.py        # TFT ディスプレイドライバ
│   ├── xpt2046.py        # タッチパネルドライバ
│   ├── osc.py            # OSC 1.0 UDP 送信
│   └── dotenv.py         # .env パーサ（MicroPython 用）
├── ui-editor/            # ブラウザのレイアウトエディタ (Vite + React)
├── micropython_esp32.bin # ESP32 用 MicroPython ファームウェア（v1.25.0）
├── LICENSE               # MIT
└── .env                  # WiFi・OSC 設定（git 管理外、各自作成）
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

### 画面が真っ黒のまま

`.env` の転送漏れで `KeyError` の可能性大。`./deploy.sh` 経由なら `.env` も自動転送されます。プロジェクトルートに `.env` が存在することをまず確認。

実行中のエラーを見たいとき:

```bash
./.venv/bin/mpremote connect /dev/cu.usbserial-110 repl
# 物理 RST を押すと boot.py / main.py の出力が流れる
# Ctrl+X で抜ける
```

### Web エディタの「Deploy」が失敗する

- ESP32 が USB 接続されているか（エディタ右上の状態表示を確認）
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

---

## ライセンス

[MIT License](LICENSE)
