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
        self.rotation = rotation

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
        """Return (screen_x, screen_y) mapped to display pixels, or None."""
        raw = self.get_raw()
        if raw is None:
            return None
        rx, ry = raw

        # Rotation 0 (portrait 240×320): raw X→screen X (mirrored), raw Y→screen Y
        # Rotation 1 (landscape 320×240): raw Y→screen X, raw X→screen Y
        if self.rotation == 0:
            sx = int((rx - self.x_min) * 239 / (self.x_max - self.x_min))
            sy = int((ry - self.y_min) * 319 / (self.y_max - self.y_min))
            sx = 239 - max(0, min(239, sx))
            sy = max(0, min(319, sy))
        elif self.rotation == 1:
            sx = int((ry - self.y_min) * 319 / (self.y_max - self.y_min))
            sy = int((rx - self.x_min) * 239 / (self.x_max - self.x_min))
            sx = max(0, min(319, sx))
            sy = max(0, min(239, sy))
        else:
            sx = int((rx - self.x_min) * (self.screen_w - 1) / (self.x_max - self.x_min))
            sy = int((ry - self.y_min) * (self.screen_h - 1) / (self.y_max - self.y_min))
            sx = max(0, min(self.screen_w - 1, sx))
            sy = max(0, min(self.screen_h - 1, sy))

        return sx, sy
