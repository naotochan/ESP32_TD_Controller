"""ILI9341 TFT display driver for MicroPython (ESP32-2432S028R / CYD)."""
import time
from micropython import const

# ILI9341 commands
_SWRESET = const(0x01)
_SLPOUT  = const(0x11)
_DISPON  = const(0x29)
_CASET   = const(0x2A)
_PASET   = const(0x2B)
_RAMWR   = const(0x2C)
_MADCTL  = const(0x36)
_COLMOD  = const(0x3A)
_FRMCTR1 = const(0xB1)
_DFUNCTR = const(0xB6)
_PWCTR1  = const(0xC0)
_PWCTR2  = const(0xC1)
_VMCTR1  = const(0xC5)
_VMCTR2  = const(0xC7)
_GMCTRP1 = const(0xE0)
_GMCTRN1 = const(0xE1)

# Color constants (RGB565)
BLACK   = const(0x0000)
WHITE   = const(0xFFFF)
RED     = const(0xF800)
GREEN   = const(0x07E0)
BLUE    = const(0x001F)
YELLOW  = const(0xFFE0)
CYAN    = const(0x07FF)
MAGENTA = const(0xF81F)
GRAY    = const(0x8410)
ORANGE  = const(0xFD20)

def color565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


class ILI9341:
    def __init__(self, spi, cs, dc, rst=None, bl=None, width=320, height=240, rotation=0):
        self.spi = spi
        self.cs  = cs
        self.dc  = dc
        self.rst = rst
        self.bl  = bl
        self.width  = width
        self.height = height

        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        if rst:
            rst.init(rst.OUT, value=1)
        if bl:
            bl.init(bl.OUT, value=1)

        self._init_display()
        self.set_rotation(rotation)

    def _write_cmd(self, cmd):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytes([cmd]))
        self.cs(1)

    def _write_data(self, data):
        self.dc(1)
        self.cs(0)
        self.spi.write(data)
        self.cs(1)

    def _init_display(self):
        if self.rst:
            self.rst(0); time.sleep_ms(50)
            self.rst(1); time.sleep_ms(150)

        for cmd, data in (
            (_SWRESET, None),
            (_SLPOUT,  None),
            (_COLMOD,  b'\x55'),          # 16-bit color
            (_FRMCTR1, b'\x00\x1B'),
            (_MADCTL,  b'\x48'),
            (_DFUNCTR, b'\x0A\x82\x27'),
            (_PWCTR1,  b'\x23'),
            (_PWCTR2,  b'\x10'),
            (_VMCTR1,  b'\x3E\x28'),
            (_VMCTR2,  b'\x86'),
            (_GMCTRP1, b'\x0F\x31\x2B\x0C\x0E\x08\x4E\xF1\x37\x07\x10\x03\x0E\x09\x00'),
            (_GMCTRN1, b'\x00\x0E\x14\x03\x11\x07\x31\xC1\x48\x08\x0F\x0C\x31\x36\x0F'),
            (_DISPON,  None),
        ):
            self._write_cmd(cmd)
            if data:
                self._write_data(data)
            if cmd in (_SWRESET, _SLPOUT):
                time.sleep_ms(120)

    def set_rotation(self, r):
        vals = [0x48, 0x28, 0x88, 0xE8]
        self._write_cmd(_MADCTL)
        self._write_data(bytes([vals[r % 4]]))
        if r % 2 == 0:
            self.width, self.height = 240, 320
        else:
            self.width, self.height = 320, 240

    def _set_window(self, x0, y0, x1, y1):
        self._write_cmd(_CASET)
        self._write_data(bytes([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self._write_cmd(_PASET)
        self._write_data(bytes([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self._write_cmd(_RAMWR)

    def fill(self, color):
        self._set_window(0, 0, self.width - 1, self.height - 1)
        c = bytes([(color >> 8) & 0xFF, color & 0xFF])
        self.dc(1); self.cs(0)
        chunk = c * 64
        for _ in range(self.width * self.height // 64):
            self.spi.write(chunk)
        self.cs(1)

    def fill_rect(self, x, y, w, h, color):
        if x >= self.width or y >= self.height or w <= 0 or h <= 0:
            return
        x1 = min(x + w - 1, self.width - 1)
        y1 = min(y + h - 1, self.height - 1)
        self._set_window(x, y, x1, y1)
        count = (x1 - x + 1) * (y1 - y + 1)
        c = bytes([(color >> 8) & 0xFF, color & 0xFF])
        self.dc(1); self.cs(0)
        chunk = c * 64
        for _ in range(count // 64):
            self.spi.write(chunk)
        rem = count % 64
        if rem:
            self.spi.write(c * rem)
        self.cs(1)

    def pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self._set_window(x, y, x, y)
            self._write_data(bytes([(color >> 8) & 0xFF, color & 0xFF]))

    # ---- text rendering (built-in 8x8 font) ----
    _FONT = {
        ' ': b'\x00\x00\x00\x00\x00\x00\x00\x00',
        '!': b'\x18\x3C\x3C\x18\x18\x00\x18\x00',
        '0': b'\x3C\x66\x6E\x76\x66\x66\x3C\x00',
        '1': b'\x18\x38\x18\x18\x18\x18\x7E\x00',
        '2': b'\x3C\x66\x06\x0C\x18\x30\x7E\x00',
        '3': b'\x7E\x0C\x18\x0C\x06\x66\x3C\x00',
        '4': b'\x0C\x1C\x3C\x6C\x7E\x0C\x0C\x00',
        '5': b'\x7E\x60\x7C\x06\x06\x66\x3C\x00',
        '6': b'\x1C\x30\x60\x7C\x66\x66\x3C\x00',
        '7': b'\x7E\x06\x0C\x18\x30\x30\x30\x00',
        '8': b'\x3C\x66\x66\x3C\x66\x66\x3C\x00',
        '9': b'\x3C\x66\x66\x3E\x06\x0C\x38\x00',
        'A': b'\x18\x3C\x66\x7E\x66\x66\x66\x00',
        'B': b'\x7C\x66\x66\x7C\x66\x66\x7C\x00',
        'C': b'\x3C\x66\x60\x60\x60\x66\x3C\x00',
        'D': b'\x78\x6C\x66\x66\x66\x6C\x78\x00',
        'E': b'\x7E\x60\x60\x78\x60\x60\x7E\x00',
        'F': b'\x7E\x60\x60\x78\x60\x60\x60\x00',
        'G': b'\x3C\x66\x60\x6E\x66\x66\x3C\x00',
        'H': b'\x66\x66\x66\x7E\x66\x66\x66\x00',
        'I': b'\x3C\x18\x18\x18\x18\x18\x3C\x00',
        'J': b'\x1E\x0C\x0C\x0C\x0C\x6C\x38\x00',
        'K': b'\x66\x6C\x78\x70\x78\x6C\x66\x00',
        'L': b'\x60\x60\x60\x60\x60\x60\x7E\x00',
        'M': b'\x63\x77\x7F\x6B\x63\x63\x63\x00',
        'N': b'\x66\x76\x7E\x7E\x6E\x66\x66\x00',
        'O': b'\x3C\x66\x66\x66\x66\x66\x3C\x00',
        'P': b'\x7C\x66\x66\x7C\x60\x60\x60\x00',
        'Q': b'\x3C\x66\x66\x66\x6E\x3C\x06\x00',
        'R': b'\x7C\x66\x66\x7C\x6C\x66\x66\x00',
        'S': b'\x3C\x66\x60\x3C\x06\x66\x3C\x00',
        'T': b'\x7E\x18\x18\x18\x18\x18\x18\x00',
        'U': b'\x66\x66\x66\x66\x66\x66\x3C\x00',
        'V': b'\x66\x66\x66\x66\x66\x3C\x18\x00',
        'W': b'\x63\x63\x63\x6B\x7F\x77\x63\x00',
        'X': b'\x66\x66\x3C\x18\x3C\x66\x66\x00',
        'Y': b'\x66\x66\x66\x3C\x18\x18\x18\x00',
        'Z': b'\x7E\x06\x0C\x18\x30\x60\x7E\x00',
        ':': b'\x00\x18\x18\x00\x18\x18\x00\x00',
        '.': b'\x00\x00\x00\x00\x00\x18\x18\x00',
        '-': b'\x00\x00\x00\x7E\x00\x00\x00\x00',
        '/': b'\x03\x06\x0C\x18\x30\x60\x40\x00',
        '+': b'\x00\x18\x18\x7E\x18\x18\x00\x00',
        '%': b'\x62\x66\x0C\x18\x30\x66\x46\x00',
    }

    def text(self, s, x, y, color=WHITE, bg=BLACK, scale=1):
        for ch in s.upper():
            bmp = self._FONT.get(ch, self._FONT[' '])
            for row, byte in enumerate(bmp):
                for col in range(8):
                    c = color if (byte >> (7 - col)) & 1 else bg
                    if scale == 1:
                        self.pixel(x + col, y + row, c)
                    else:
                        self.fill_rect(x + col * scale, y + row * scale, scale, scale, c)
            x += 8 * scale
