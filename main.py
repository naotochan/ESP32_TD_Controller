"""ESP32 TD Controller - main entry point."""
import os

# --- Deploy guard (early): skip everything if .deploying flag exists ---
if ".deploying" in os.listdir():
    raise SystemExit("Deploy mode — skipping main.py")

import time
from machine import SPI, Pin
from lib.dotenv import load
from lib.ili9341 import ILI9341, color565
from lib.xpt2046 import XPT2046
from lib.osc import OSCSender
from ui import Button, Slider, HSlider, HSVPicker, IPDisplay

try:
    from widgets import WIDGETS, ORIENTATION, ROTATION
except ImportError:
    from widgets import WIDGETS
    ORIENTATION = "portrait"
    ROTATION = 0

# --- Screen ---
SCREEN_W, SCREEN_H = (320, 240) if ORIENTATION == "landscape" else (240, 320)

# --- Config ---
env  = load()
host = env["OSC_HOST"]
port = int(env["OSC_PORT"])

# --- Hardware ---
spi_tft   = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft       = ILI9341(spi_tft, cs=Pin(15), dc=Pin(2), bl=Pin(21), rotation=ROTATION)
spi_touch = SPI(2, baudrate=1_000_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
touch     = XPT2046(spi_touch, cs=Pin(33), irq=Pin(36),
                   x_min=599, x_max=3443, y_min=445, y_max=3564,
                   screen_w=SCREEN_W, screen_h=SCREEN_H, rotation=ROTATION)
osc       = OSCSender(host, port)

# --- Instantiate widgets from data config ---
WIDGET_MAP = {"Button": Button, "Slider": Slider, "HSlider": HSlider, "HSVPicker": HSVPicker, "IPDisplay": IPDisplay}

widget_instances = []
for w in WIDGETS:
    cls = WIDGET_MAP.get(w["type"])
    if cls is None:
        continue
    kwargs = {k: v for k, v in w.items() if k != "type"}
    widget_instances.append(cls(tft, **kwargs))


# --- Draw initial UI ---
tft.fill(color565(10, 10, 20))
for w in widget_instances:
    w.draw()


# --- Main loop ---
# OSC throttle: continuous-value widgets (Slider, HSVPicker) are rate-limited
# to avoid flooding the network. Buttons always send immediately.
_OSC_INTERVAL_MS = 20
_last_osc = {}

try:
    while True:
        pos = touch.get_pos()
        now = time.ticks_ms()

        for w in widget_instances:
            claimed = w.process(pos)
            if claimed:
                msg = w.osc_message()
                if msg is not None:
                    if getattr(w, 'throttle', False):
                        wid = id(w)
                        if time.ticks_diff(now, _last_osc.get(wid, 0)) >= _OSC_INTERVAL_MS:
                            osc.send(w.osc_addr, *msg)
                            _last_osc[wid] = now
                    else:
                        osc.send(w.osc_addr, *msg)
                break  # claimed widget exclusively owns this touch frame

        time.sleep_ms(10)
except KeyboardInterrupt:
    pass
finally:
    osc.close()
