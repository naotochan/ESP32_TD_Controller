"""CYD表示確認テスト - rotation 0〜3 を順番に表示して正しいものを特定する

見方:
  - 画面が縦長(portrait)になるrotationを探す
  - 四隅の色ブロックが画面の端ぴったりに収まるrotationが正解
    左上=赤  右上=緑  左下=青  右下=黄
  - 切れや余白がなければOK
"""
from machine import SPI, Pin
from lib.ili9341 import ILI9341, BLACK, WHITE, RED, GREEN, BLUE, YELLOW, CYAN
import time

spi = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft = ILI9341(spi, cs=Pin(15), dc=Pin(2), bl=Pin(21), rotation=0)

SZ = 30  # コーナーブロックのサイズ

def draw_test(rot):
    tft.set_rotation(rot)
    W, H = tft.width, tft.height
    print(f"rotation={rot}  w={W}  h={H}")

    tft.fill(BLACK)

    # 外枠
    for x in range(W):
        tft.pixel(x, 0, WHITE)
        tft.pixel(x, H - 1, WHITE)
    for y in range(H):
        tft.pixel(0, y, WHITE)
        tft.pixel(W - 1, y, WHITE)

    # 四隅の色ブロック
    tft.fill_rect(1,       1,       SZ, SZ, RED)    # TL=赤
    tft.fill_rect(W-SZ-1,  1,       SZ, SZ, GREEN)  # TR=緑
    tft.fill_rect(1,       H-SZ-1,  SZ, SZ, BLUE)   # BL=青
    tft.fill_rect(W-SZ-1,  H-SZ-1,  SZ, SZ, YELLOW) # BR=黄

    # コーナーラベル
    tft.text("TL", 4, 4, CYAN, BLACK)
    tft.text("TR", W - 20, 4, CYAN, BLACK)
    tft.text("BL", 4, H - 12, CYAN, BLACK)
    tft.text("BR", W - 20, H - 12, CYAN, BLACK)

    # 中央に情報
    mx, my = W // 2, H // 2
    tft.text(f"{W}X{H}", mx - 28, my - 10, GREEN, BLACK)
    tft.text(f"ROT {rot}", mx - 28, my + 4, YELLOW, BLACK)

for rot in [0, 1, 2, 3]:
    draw_test(rot)
    time.sleep(3)

print("全rotation表示完了")
print("切れや余白がなく縦長に見えたrotationが正解です")
