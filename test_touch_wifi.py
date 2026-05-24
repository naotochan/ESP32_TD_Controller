"""Touch + WiFi + OSC smoke test."""
import time
import network
from machine import SPI, Pin
from lib.dotenv import load
from lib.ili9341 import ILI9341, BLACK, WHITE, GREEN, RED, BLUE, YELLOW
from lib.xpt2046 import XPT2046
from lib.osc import OSCSender

env = load()

# --- Display ---
spi_tft = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft = ILI9341(spi_tft, cs=Pin(15), dc=Pin(2), bl=Pin(21))

def status(msg, color=WHITE):
    tft.fill_rect(0, 110, 320, 20, BLACK)
    tft.text(msg[:40], 4, 113, color, BLACK)

tft.fill(BLACK)
tft.text("TOUCH + WIFI TEST", 4, 4, WHITE, BLACK)

# --- Touch ---
spi_touch = SPI(2, baudrate=1_000_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
touch = XPT2046(spi_touch, cs=Pin(33), irq=Pin(36))

# --- WiFi ---
status("CONNECTING WIFI...", YELLOW)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(env["WIFI_SSID"], env["WIFI_PASSWORD"])

for _ in range(20):
    if wlan.isconnected():
        break
    time.sleep(0.5)

if wlan.isconnected():
    ip = wlan.ifconfig()[0]
    status("WIFI OK: " + ip, GREEN)
    print("WiFi connected:", ip)
    osc = OSCSender(env["OSC_HOST"], int(env["OSC_PORT"]))
    osc.send("/esp32/status", "online")
    print("OSC sent /esp32/status online")
else:
    status("WIFI FAILED", RED)
    print("WiFi failed")
    osc = None

time.sleep(1)
tft.fill_rect(0, 140, 320, 20, BLACK)
tft.text("TOUCH SCREEN TO TEST", 4, 143, WHITE, BLACK)

# --- Touch loop (10 seconds) ---
deadline = time.ticks_add(time.ticks_ms(), 10_000)
while time.ticks_diff(deadline, time.ticks_ms()) > 0:
    pos = touch.get_pos()
    if pos:
        x, y = pos
        msg = "X:" + str(x) + " Y:" + str(y)
        tft.fill_rect(0, 170, 320, 20, BLACK)
        tft.text(msg, 4, 173, YELLOW, BLACK)
        tft.pixel(x, y, YELLOW)
        if osc:
            osc.send("/esp32/touch", float(x), float(y))
        print("touch:", x, y)
    time.sleep_ms(50)

status("DONE", GREEN)
print("Test complete")
