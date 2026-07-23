"""XPT2046 resistive touch controller driver (ESP32-2432S028R dual-USB variant)."""
from micropython import const
import time

_CMD_X   = const(0xD0)
_CMD_Y   = const(0x90)
_SAMPLES = const(5)


class XPT2046:
    def __init__(self, spi, cs, irq=None,
                 x_min=200, x_max=3900, y_min=200, y_max=3900,
                 screen_w=320, screen_h=240, rotation=0):
        self.spi = spi
        self.cs  = cs
        self.irq = irq
        self.x_min, self.x_max = x_min, x_max
        self.y_min, self.y_max = y_min, y_max
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.rotation = rotation % 4

        self.cs.init(self.cs.OUT, value=1)
        if irq:
            irq.init(irq.IN)

    def _read_raw(self, cmd):
        buf = bytearray(3)
        self.cs(0)
        self.spi.write(bytes([cmd]))
        self.spi.readinto(buf)
        self.cs(1)
        return ((buf[0] << 8) | buf[1]) >> 3

    def _read_avg(self, cmd):
        samples = sorted(self._read_raw(cmd) for _ in range(_SAMPLES))
        return sum(samples[1:-1]) // (_SAMPLES - 2)

    def is_touched(self):
        if self.irq:
            return not self.irq.value()
        return True

    def get_raw(self):
        """Return (raw_x, raw_y) ADC values."""
        if not self.is_touched():
            return None
        x = self._read_avg(_CMD_X)
        y = self._read_avg(_CMD_Y)
        return x, y

    def get_pos(self):
        """Return (screen_x, screen_y) mapped to display pixels, or None.

        rotation matches ILI9341 set_rotation index (0..3 = 0/90/180/270°).
        CYD raw X is physically mirrored relative to rotation 0.
        """
        raw = self.get_raw()
        if raw is None:
            return None
        rx, ry = raw

        dx = self.x_max - self.x_min
        dy = self.y_max - self.y_min
        if dx == 0 or dy == 0:
            return None
        nx = (rx - self.x_min) / dx
        ny = (ry - self.y_min) / dy
        if nx < 0: nx = 0.0
        elif nx > 1: nx = 1.0
        if ny < 0: ny = 0.0
        elif ny > 1: ny = 1.0

        w1 = self.screen_w - 1
        h1 = self.screen_h - 1
        r = self.rotation % 4

        if r == 0:      # 0°   portrait  — mirror X
            sx = int((1.0 - nx) * w1)
            sy = int(ny * h1)
        elif r == 1:    # 90°  landscape
            sx = int(ny * w1)
            sy = int(nx * h1)
        elif r == 2:    # 180° portrait
            sx = int(nx * w1)
            sy = int((1.0 - ny) * h1)
        else:           # 270° landscape
            sx = int((1.0 - ny) * w1)
            sy = int((1.0 - nx) * h1)

        return sx, sy
