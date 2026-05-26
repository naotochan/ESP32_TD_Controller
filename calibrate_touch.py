"""Touch calibration utility for XPT2046.

Deploy and run this script once, then paste the printed values into main.py.
Works for both rotation=0 (portrait) and rotation=1 (landscape).
"""
import time
from machine import SPI, Pin
from lib.ili9341 import ILI9341, color565
from lib.xpt2046 import XPT2046

# --- Hardware setup (same pins as main.py) ---
spi_tft   = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft       = ILI9341(spi_tft, cs=Pin(15), dc=Pin(2), bl=Pin(21), rotation=1)
spi_touch = SPI(2, baudrate=1_000_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
touch     = XPT2046(spi_touch, cs=Pin(33), irq=Pin(36))

# --- Colors ---
BG     = color565(10, 10, 30)
WHITE  = color565(255, 255, 255)
YELLOW = color565(255, 230, 0)
GREEN  = color565(0, 220, 80)
CYAN   = color565(0, 220, 220)
RED    = color565(255, 60, 60)

SCREEN_W = 320
SCREEN_H = 240
CROSSHAIR_R = 12
SAMPLES = 16
MARGIN = CROSSHAIR_R + 2  # just enough for the crosshair to stay on screen

# Corners in screen coordinates: (label, screen_x, screen_y)
CORNERS = [
    ("TOP-LEFT",     MARGIN,              MARGIN),
    ("TOP-RIGHT",    SCREEN_W - MARGIN,   MARGIN),
    ("BOTTOM-RIGHT", SCREEN_W - MARGIN,   SCREEN_H - MARGIN),
    ("BOTTOM-LEFT",  MARGIN,              SCREEN_H - MARGIN),
]


def draw_crosshair(x, y, color):
    tft.fill_rect(x - CROSSHAIR_R, y - 1, CROSSHAIR_R * 2, 3, color)
    tft.fill_rect(x - 1, y - CROSSHAIR_R, 3, CROSSHAIR_R * 2, color)
    tft.fill_rect(x - 4, y - 4, 9, 9, BG)
    tft.fill_rect(x - 1, y - 4, 3, 9, color)
    tft.fill_rect(x - 4, y - 1, 9, 3, color)


def erase_crosshair(x, y):
    r = CROSSHAIR_R + 2
    tft.fill_rect(x - r, y - r, r * 2 + 1, r * 2 + 1, BG)


def draw_text_centered(text, y, color):
    x = max(0, (SCREEN_W - len(text) * 8) // 2)
    tft.text(text, x, y, color, BG)


def wait_for_stable_touch():
    """Wait until IRQ fires, then collect SAMPLES averaged raw readings."""
    # Wait for touch start
    while touch.irq.value():
        time.sleep_ms(10)
    time.sleep_ms(30)  # debounce

    readings_x = []
    readings_y = []
    for _ in range(SAMPLES):
        raw = touch.get_raw()
        if raw:
            readings_x.append(raw[0])
            readings_y.append(raw[1])
        time.sleep_ms(10)

    # Wait for release
    while not touch.irq.value():
        time.sleep_ms(10)
    time.sleep_ms(50)

    if not readings_x:
        return None
    return sum(readings_x) // len(readings_x), sum(readings_y) // len(readings_y)


# ---- Main calibration sequence ----
tft.fill(BG)
draw_text_centered("TOUCH CALIBRATION", 10, WHITE)
draw_text_centered("Touch each target", 30, CYAN)
time.sleep(1)

raw_results = {}

for label, sx, sy in CORNERS:
    tft.fill_rect(0, 50, SCREEN_W, SCREEN_H - 50, BG)
    draw_text_centered(label, 55, YELLOW)
    draw_text_centered("Touch the crosshair", 75, WHITE)
    draw_crosshair(sx, sy, YELLOW)

    raw = wait_for_stable_touch()
    if raw is None:
        draw_text_centered("No data - retry", 100, RED)
        time.sleep(1)
        continue

    raw_results[label] = (sx, sy, raw[0], raw[1])
    erase_crosshair(sx, sy)
    draw_crosshair(sx, sy, GREEN)
    msg = "rx=" + str(raw[0]) + " ry=" + str(raw[1])
    draw_text_centered(msg, 100, GREEN)
    print(label + ": screen(" + str(sx) + "," + str(sy) + ") raw(" + str(raw[0]) + "," + str(raw[1]) + ")")
    time.sleep(0.6)

# ---- Compute min/max ----
if len(raw_results) < 4:
    tft.fill(BG)
    draw_text_centered("CALIBRATION FAILED", 100, RED)
    draw_text_centered("Not enough data", 120, WHITE)
else:
    all_rx = [v[2] for v in raw_results.values()]
    all_ry = [v[3] for v in raw_results.values()]
    x_min, x_max = min(all_rx), max(all_rx)
    y_min, y_max = min(all_ry), max(all_ry)

    tft.fill(BG)
    draw_text_centered("CALIBRATION DONE", 10, GREEN)
    tft.text("x_min=" + str(x_min), 4, 40, CYAN, BG)
    tft.text("x_max=" + str(x_max), 4, 56, CYAN, BG)
    tft.text("y_min=" + str(y_min), 4, 72, CYAN, BG)
    tft.text("y_max=" + str(y_max), 4, 88, CYAN, BG)
    draw_text_centered("See serial for main.py snippet", 110, WHITE)

    snippet = (
        "XPT2046(spi_touch, cs=Pin(33), irq=Pin(36),\n"
        "        x_min=" + str(x_min) + ", x_max=" + str(x_max) + ",\n"
        "        y_min=" + str(y_min) + ", y_max=" + str(y_max) + ",\n"
        "        screen_w=SCREEN_W, screen_h=SCREEN_H, rotation=ROTATION)"
    )
    print("\n--- Paste into main.py ---")
    print("touch = " + snippet)
    print("--------------------------")
