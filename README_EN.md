# ESP32 TD Controller

[日本語](README.md) · English

Turn an ESP32 + 2.8" touch screen into an **OSC controller for TouchDesigner**.

Touch interactions (buttons, sliders, color pickers, page switching) are sent as OSC messages over WiFi to TouchDesigner. The widget layout is editable via a **browser-based editor**: drag-and-drop widgets and deploy to the ESP32 with one click.

```
[Web Editor] --Deploy Button--> [Local Deploy Server] --USB--> [ESP32]
                                                                     ↓ WiFi
                                                            [TouchDesigner (OSC In CHOP)]
```

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
uv venv
uv pip install "esptool<5" mpremote
cd ui-editor && npm install && cd ..
```

### 2. Connect the ESP32 and check the port

```bash
ls /dev/cu.usbserial-* /dev/cu.usbmodem*
# Example: /dev/cu.usbserial-110
```

**Replace the port name in the commands below with your actual device path.**

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
EOF
```

### 5. Initial deploy

```bash
./deploy.sh
# If auto-detection fails or multiple devices are connected, specify the port explicitly
./deploy.sh /dev/cu.usbserial-XXX
```

This writes `boot.py` / `main.py` / `ui.py` / `widgets.py` / `lib/*` / `.env` to the ESP32 and reboots it.

**If another USB serial device is connected, the wrong target may be written. Disconnect other devices or specify the correct port.**

### 6. TouchDesigner side

Place an OSC In CHOP, set **Port to 7000**, and enable Active. Touch input from the ESP32 will flow into the CHOP.

---

## Everyday Workflow (After First Setup)

Once initial setup (venv / `npm install` / flashing MicroPython / creating `.env`) is done, daily work is just pressing the **Deploy** button in the Web Editor.

### Edit layout and deploy (daily use)

```bash
./start.sh
# → Launches editor (http://localhost:5173) and deploy server (port 3737) together
```

Drag-and-drop widgets in the browser to arrange and edit them, then hit **Deploy** — `layout.json` is transferred to the ESP32 which auto-reboots. The ESP32 connection status is shown at the top-right of the editor; replugging the USB cable triggers automatic re-detection.

### Deploy layout only from CLI

When you want to push a saved `layout.json` via command line:

```bash
./deploy-layout.sh
./deploy-layout.sh /dev/cu.usbserial-XXX
```

### When code or `.env` changes

```bash
./deploy.sh                              # Re-transfer all files
./deploy.sh /dev/cu.usbserial-XXX
```

Use this when you've edited `main.py`, `ui.py`, `lib/*`, `boot.py`, or `.env`.

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
| Slider | `/esp32/slider/1` | float | `0.0` — `255.0` continuous (vertical) |
| HSlider | `/esp32/hslider/1` | float | `0.0` — `255.0` continuous (horizontal) |
| HSVPicker | `/esp32/color/1` | int×3 | `r, g, b` (each 0—255) |
| PageButton | — | — | Page switch (no OSC sent) |

Addresses can be freely changed in the editor.

---

## File Structure

```
.
├── deploy.sh             # Transfer all files to ESP32 + reboot
├── deploy-layout.sh      # Transfer only layout.json and main.py
├── start.sh              # Launch editor + deploy server together
├── server.py             # Local deploy server (receives POST from editor)
├── boot.py               # WiFi connection at startup
├── main.py               # Main loop: touch → widget processing → OSC send
├── ui.py                 # Widget classes (Button / Slider / HSlider / HSVPicker / IPDisplay / PageButton)
├── widgets.py            # Fallback initial layout (used when layout.json is absent)
├── layout.json.example   # Sample copied to layout.json on first boot (layout.json itself is not tracked by git)
├── lib/
│   ├── ili9341.py        # TFT display driver
│   ├── xpt2046.py        # Touch panel driver
│   ├── osc.py            # OSC 1.0 UDP transmit
│   └── dotenv.py         # .env parser (for MicroPython)
├── ui-editor/            # Browser-based layout editor (Vite + React)
├── micropython_esp32.bin # ESP32 MicroPython firmware (v1.25.0)
├── LICENSE               # MIT
└── .env                  # WiFi / OSC settings (not tracked by git, create yourself)
```

---

## Pinout (ESP32-2432S028R Dual USB Variant)

| Purpose | Pin |
|---|---|
| TFT MOSI / MISO / SCK / CS / DC / BL | 13 / 12 / 14 / 15 / 2 / 21 |
| Touch MOSI / MISO / SCK / CS / IRQ | 32 / 39 / 25 / 33 / 36 |
| SD MOSI / MISO / SCK / CS | 23 / 19 / 18 / 5 |
| RGB LED (active LOW) | R=4, G=16, B=17 |

---

## Troubleshooting

### Screen stays black

Most likely a missing `.env` file causing `KeyError`. Running `./deploy.sh` auto-transfers `.env`. First confirm that `.env` exists in the project root.

To see runtime errors:

```bash
./.venv/bin/mpremote connect /dev/cu.usbserial-110 repl
# Press physical RST to see boot.py / main.py output
# Ctrl+X to exit
```

### Web Editor "Deploy" fails

- Is the ESP32 connected via USB? (check status indicator at top-right of editor)
- Is the deploy server running on port 3737? (auto-starts when launched via `./start.sh`)

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
