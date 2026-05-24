"""ESP32 TD Controller - main entry point."""
import os

# --- Deploy guard (early): skip everything if .deploying flag exists ---
if ".deploying" in os.listdir():
    raise SystemExit("Deploy mode — skipping main.py")

import time
import network
from machine import SPI, Pin
from lib.dotenv import load
from lib.ili9341 import ILI9341, BLACK, WHITE, GREEN, RED, color565
from lib.xpt2046 import XPT2046
from lib.osc import OSCSender
from ui import Button, Slider, RGBPicker

try:
    from widgets import WIDGETS, ORIENTATION, ROTATION
except ImportError:
    from widgets import WIDGETS
    ORIENTATION = "portrait"
    ROTATION = 0

# --- Screen ---
SCREEN_W, SCREEN_H = (320, 240) if ORIENTATION == "landscape" else (240, 320)
STATUS_Y = SCREEN_H - 24
STATUS_H = 24

# --- Config ---
env  = load()
host = env["OSC_HOST"]
port = int(env["OSC_PORT"])

# --- Hardware ---
spi_tft   = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft       = ILI9341(spi_tft, cs=Pin(15), dc=Pin(2), bl=Pin(21), rotation=ROTATION)
spi_touch = SPI(2, baudrate=1_000_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
touch     = XPT2046(spi_touch, cs=Pin(33), irq=Pin(36), screen_w=SCREEN_W, screen_h=SCREEN_H, rotation=ROTATION)
osc       = OSCSender(host, port)

# --- Instantiate widgets from data config ---
WIDGET_MAP = {"Button": Button, "Slider": Slider, "RGBPicker": RGBPicker}

widget_instances = []
for w in WIDGETS:
    cls = WIDGET_MAP.get(w["type"])
    if cls is None:
        continue
    kwargs = {k: v for k, v in w.items() if k != "type"}
    widget_instances.append(cls(tft, **kwargs))


# --- Status bar ---
def draw_status(text, color):
    tft.fill_rect(0, STATUS_Y, SCREEN_W, STATUS_H, BLACK)
    tft.text(text, 4, STATUS_Y + 2, color, BLACK)


# --- Draw initial UI ---
tft.fill(color565(10, 10, 20))
for w in widget_instances:
    w.draw()

wlan = network.WLAN(network.STA_IF)
if wlan.isconnected():
    draw_status("WiFi: " + wlan.ifconfig()[0], GREEN)
else:
    draw_status("WiFi: --", RED)


# --- Main loop (generic - no widget type knowledge needed) ---
try:
    while True:
        pos = touch.get_pos()

        # Active widgets claim the touch. First match wins.
        for w in widget_instances:
            claimed = w.process(pos)
            if claimed:
                msg = w.osc_message()
                if msg is not None:
                    osc.send(w.osc_addr, *msg)

        time.sleep_ms(30)
except KeyboardInterrupt:
    pass
finally:
    osc.close()
