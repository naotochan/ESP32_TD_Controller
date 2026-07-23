# ESP32 TD Controller

[日本語](README.md) · English

Turn an ESP32 + 2.8" touch screen into an **OSC controller for TouchDesigner**.

Touch interactions (buttons, toggles, sliders, color pickers, page switching) are sent as OSC messages over WiFi to TouchDesigner. The widget layout is editable via a **browser-based editor**: drag-and-drop widgets and deploy to the ESP32 with one click.

```
┌─────────────┐     Deploy      ┌──────────────┐     USB      ┌─────────┐
│  Web Editor │ ──────────────► │  server.py   │ ──────────► │  ESP32  │
│  :5173      │   layout.json   │  :3737       │  mpremote   │  (CYD)  │
└─────────────┘                 └──────────────┘             └────┬────┘
                                                                  │ OSC/UDP
                                                                  ▼
                                                           ┌─────────────┐
                                                           │TouchDesigner│
                                                           └─────────────┘
```

**Version:** 0.2.1

---

## Requirements

- **Hardware**: ESP32-2432S028R (aka CYD = Cheap Yellow Display, dual USB variant) [AliExpress](https://www.aliexpress.com/item/1005007774435209.html)
- **Software**: macOS / Linux, Python 3.10+, [uv](https://github.com/astral-sh/uv), Node.js 18+
- **Browser**: Web Editor uses the File System Access API for Open/Save — **Chrome or Edge required** (Safari/Firefox not supported)
- **Cable**: A data-capable USB cable

---

## Quick Start (First Time Setup)

### 1. Clone and set up

```bash
git clone https://github.com/naotochan/ESP32_TD_Controller.git
cd ESP32_TD_Controller
uv sync
cd ui-editor && npm install && cd ..
```

`uv sync` installs dependencies from `pyproject.toml` (`esptool<5`, `mpremote`) into `.venv`. Alternative: `uv venv && uv pip install "esptool<5" mpremote`.

### 2. Connect the ESP32 and check the port

```bash
# macOS
ls /dev/cu.usbserial-* /dev/cu.usbmodem*
# Linux
ls /dev/ttyUSB* /dev/ttyACM*
# Example: /dev/cu.usbserial-110  or  /dev/ttyUSB0
```

**Replace the port name in the commands below with your actual device path.** If multiple candidates appear, do not rely on auto-detect — specify the port explicitly.

### 3. Flash MicroPython (first time only)

Use the bundled `micropython_esp32.bin` (v1.25.0, verified on CYD):

```bash
./.venv/bin/esptool.py --port /dev/cu.usbserial-110 erase_flash
./.venv/bin/esptool.py --port /dev/cu.usbserial-110 --baud 460800 write_flash 0x1000 micropython_esp32.bin
```

### 4. Create `.env`

```bash
cat > .env << EOF
WIFI_SSID=your_wifi_ssid
WIFI_PASSWORD=your_wifi_password
OSC_HOST=192.168.x.x        # IP of the machine running TouchDesigner
OSC_PORT=7000
# OSC_LISTEN_PORT=7001      # optional: TD→ESP32 receive (omit to disable)
EOF
```

### 5. Initial deploy

```bash
./deploy.sh
# If auto-detection fails or multiple devices are connected, specify the port explicitly
./deploy.sh /dev/cu.usbserial-XXX
# Linux example
./deploy.sh /dev/ttyUSB0
```

This writes `boot.py` / `main.py` / `ui.py` / `widgets.py` / `layout.json` / `lib/*` / `.env` (and `calib.json` if present) to the ESP32 and reboots. If `layout.json` is missing, it is copied from `layout.json.example`.

**If another USB serial device is connected, the wrong target may be written. Disconnect other devices or specify the correct port.**

### 6. TouchDesigner side

Place an OSC In CHOP, set **Port to 7000**, and enable Active. Touch input from the ESP32 will flow into the CHOP.

For TD→ESP32 (remote slider/toggle updates), add `OSC_LISTEN_PORT=7001` to `.env`, redeploy, and send OSC to that port from TD.

---

## Everyday Workflow (After First Setup)

Once initial setup (venv / `npm install` / flashing MicroPython / creating `.env`) is done, daily work is just pressing the **Deploy** button in the Web Editor.

### Edit layout and deploy (daily use)

```bash
./start.sh
# → Launches editor (http://localhost:5173) and deploy server (port 3737) together
```

Drag-and-drop widgets in the browser, then hit **Deploy** — `layout.json` is transferred to the ESP32 which auto-reboots. Connection status (candidate count / selected port) is shown at the top-right; ambiguous multi-port situations show a warning.

### Deploy layout only from CLI

```bash
./deploy-layout.sh
./deploy-layout.sh /dev/cu.usbserial-XXX
```

### When code or `.env` changes

```bash
./deploy.sh
./deploy.sh /dev/cu.usbserial-XXX
```

### Touch calibration

```bash
./.venv/bin/mpremote connect /dev/cu.usbserial-XXX cp calibrate_touch.py :calibrate_touch.py
./.venv/bin/mpremote connect /dev/cu.usbserial-XXX exec "import calibrate_touch"
# After on-screen prompts, pull results to the host:
./.venv/bin/mpremote cp :calib.json calib.json
./deploy.sh   # transfers calib.json when present
```

`main.py` loads calibration in order: `calib.json` → `.env` `CALIB_*` → built-in defaults.

### Inspect ESP32 behavior (REPL)

```bash
./.venv/bin/mpremote connect /dev/cu.usbserial-XXX repl
# Press the physical RST button to see boot.py / main.py output
# Ctrl+X to exit
```

---

## OSC Message Specification

| Widget | Address Example | Type | Value |
|---|---|---|---|
| Button | `/esp32/button/1` | float | `1.0` press / `0.0` release |
| Toggle | `/esp32/toggle/1` | float | `1.0` ON / `0.0` OFF (latching) |
| Slider | `/esp32/slider/1` | float | `0.0` — `255.0` continuous (vertical) |
| HSlider | `/esp32/hslider/1` | float | `0.0` — `255.0` continuous (horizontal) |
| HSVPicker | `/esp32/color/1` | int×3 | `r, g, b` (each 0—255) |
| PageButton | — | — | Page switch (no OSC sent) |

Addresses can be freely changed in the editor.

**Receive (optional):** When `OSC_LISTEN_PORT` is set, sending a float to the same address updates Slider / HSlider / Toggle display values.

---

## File Structure

```
.
├── deploy.sh             # Transfer all files to ESP32 + reboot
├── deploy-layout.sh      # Transfer only layout.json and main.py
├── start.sh              # Launch editor + deploy server together
├── server.py             # Local deploy server (receives POST from editor)
├── pyproject.toml        # Python deps (esptool, mpremote)
├── boot.py               # WiFi connection at startup
├── main.py               # Main loop: touch → widget processing → OSC
├── ui.py                 # Widget classes (Button / Toggle / Slider / …)
├── widgets.py            # Fallback initial layout
├── layout.json.example   # Sample for layout.json (layout.json is not tracked)
├── calib.json.example    # Sample touch calibration (calib.json is not tracked)
├── calibrate_touch.py    # Touch calibration utility
├── lib/
│   ├── ili9341.py        # TFT display driver
│   ├── xpt2046.py        # Touch panel driver
│   ├── osc.py            # OSC 1.0 UDP send/receive
│   └── dotenv.py         # .env parser (for MicroPython)
├── ui-editor/            # Browser-based layout editor (Vite + React)
├── micropython_esp32.bin # ESP32 MicroPython firmware (v1.25.0)
├── LICENSE               # MIT
└── .env                  # WiFi / OSC settings (not tracked by git)
```

---

## Pinout (ESP32-2432S028R Dual USB Variant)

| Purpose | Pin |
|---|---|
| TFT MOSI / MISO / SCK / CS / DC / BL | 13 / 12 / 14 / 15 / 2 / 21 |
| Touch MOSI / MISO / SCK / CS / IRQ | 32 / 39 / 25 / 33 / 36 |
| SD MOSI / MISO / SCK / CS | 23 / 19 / 18 / 5 |
| RGB LED (active LOW) | R=4, G=16, B=17 |

Back silkscreen reference photo: `back_silkscreen_spec.jpg`

---

## Troubleshooting

### Screen shows ERROR / stays black

Missing `.env` or required keys are shown on the display. Running `./deploy.sh` transfers `.env` — confirm it exists in the project root.

WiFi FAILED is also shown on screen (UI still runs; OSC is skipped).

```bash
./.venv/bin/mpremote connect /dev/cu.usbserial-110 repl
# Press physical RST to see boot.py / main.py output
```

### Web Editor "Deploy" fails

- Is the ESP32 connected via USB? (check status indicator at top-right)
- Are multiple ports ambiguous? (unplug extras or specify port via CLI)
- Is the deploy server running on port 3737? (auto-starts via `./start.sh`)

### Nuclear option

Erase flash → re-flash MicroPython → redeploy everything:

```bash
./.venv/bin/esptool.py --port /dev/cu.usbserial-110 erase_flash
./.venv/bin/esptool.py --port /dev/cu.usbserial-110 --baud 460800 write_flash 0x1000 micropython_esp32.bin
./deploy.sh
```

---

## CYD Hardware Notes

- **Display rotation**: `rotation=0` is portrait (240×320). `ili9341.py` `set_rotation()` sets `width=240, height=320` when `r % 2 == 0` (opposite of landscape)
- **Touch X-axis inversion**: The XPT2046 X coordinate is physically mirrored; `xpt2046.py` already applies `sx = screen_w - 1 - sx`

---

## License

[MIT License](LICENSE)
