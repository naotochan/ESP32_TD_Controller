"""Display smoke test: fills screen blue then shows text."""
from machine import SPI, Pin
from lib.ili9341 import ILI9341, RED, GREEN, BLUE, WHITE, BLACK

spi = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft = ILI9341(spi, cs=Pin(15), dc=Pin(2), bl=Pin(21))

tft.fill(BLUE)
tft.fill_rect(10, 10, 300, 50, BLACK)
tft.text("ESP32 TD CONTROLLER", 12, 22, WHITE, BLACK, scale=1)
tft.fill_rect(10, 80, 140, 60, RED)
tft.text("HELLO", 30, 103, WHITE, RED, scale=2)
tft.fill_rect(170, 80, 140, 60, GREEN)
tft.text("TD OSC", 183, 103, BLACK, GREEN, scale=2)

print("Display test done")
