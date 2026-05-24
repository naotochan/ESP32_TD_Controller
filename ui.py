"""UI widget framework for ILI9341 display."""
from lib.ili9341 import WHITE, BLACK, GRAY, color565

# --- Color palette ---
_PRESSED_BG     = color565(60, 120, 220)
_NORMAL_BG      = color565(30,  60, 120)
_PRESSED_BORDER = color565(100, 160, 255)
_NORMAL_BORDER  = color565(180, 180, 220)
_LABEL_COLOR    = WHITE


class Widget:
    """Base class for all UI widgets.

    Subclasses implement: draw(), hit(tx, ty), process(pos)
    - draw(): render current state to display
    - hit(tx, ty): return True if touch position is inside widget bounds
    - process(pos): handle touch event (pos=None means release). Return True if this widget consumed the touch.
    """

    def __init__(self, tft, x, y, w, h, osc_addr):
        self.tft = tft
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.osc_addr = osc_addr

    def draw(self):
        raise NotImplementedError

    def hit(self, tx, ty):
        return self.x <= tx < self.x + self.w and self.y <= ty < self.y + self.h

    def process(self, pos):
        """Handle touch. pos is (tx, ty) or None on release."""
        raise NotImplementedError

    def osc_message(self):
        """Return OSC args tuple, or None if no message should be sent."""
        return None


class Button(Widget):
    """Toggle button - sends 1.0 on press, 0.0 on release."""

    def __init__(self, tft, x, y, w, h, label, osc_addr):
        super().__init__(tft, x, y, w, h, osc_addr)
        self.label = label
        self._pressed = False

    def draw(self):
        bg = _PRESSED_BG if self._pressed else _NORMAL_BG
        c  = _PRESSED_BORDER if self._pressed else _NORMAL_BORDER
        t = self.tft
        t.fill_rect(self.x, self.y, self.w, self.h, bg)
        for i in range(2):
            bx, by = self.x + i, self.y + i
            bw, bh = self.w - i * 2, self.h - i * 2
            t.fill_rect(bx, by, bw, 1, c)
            t.fill_rect(bx, by + bh - 1, bw, 1, c)
            t.fill_rect(bx, by, 1, bh, c)
            t.fill_rect(bx + bw - 1, by, 1, bh, c)
        lx = self.x + (self.w - len(self.label) * 8) // 2
        ly = self.y + (self.h - 8) // 2
        t.text(self.label, lx, ly, _LABEL_COLOR, bg)

    def process(self, pos):
        if pos and not self._pressed:
            tx, ty = pos
            if self.hit(tx, ty):
                self._pressed = True
                self.draw()
                return True
        elif not pos and self._pressed:
            self._pressed = False
            self.draw()
            return True
        return self._pressed

    def osc_message(self):
        return (1.0 if self._pressed else 0.0,)


class Slider(Widget):
    """Vertical slider (0-255). Sends float value on touch move.

    Visual: thin bar with a draggable knob. Knob Y position maps to 0-255.
    """
    _KNOB_W = 4
    _TRACK_COLOR = color565(80, 80, 100)
    _KNOB_COLOR = color565(100, 180, 255)
    _KNOB_PRESSED = color565(140, 210, 255)

    def __init__(self, tft, x, y, w, h, osc_addr, default=127):
        super().__init__(tft, x, y, w, h, osc_addr)
        self._value = default
        self._active = False

    @property
    def value(self):
        return self._value

    def _knob_y(self):
        """Pixel Y of knob center based on current value."""
        range_px = max(self.h - 20, 1)
        ratio = self._value / 255
        return self.y + 10 + int(range_px * (1 - ratio))

    def draw(self):
        t = self.tft
        cx = self.x + self.w // 2
        # Track background
        t.fill_rect(cx - 2, self.y + 8, 5, self.h - 16, BLACK)
        # Track line
        t.fill_rect(cx - 1, self.y + 8, 3, self.h - 16, self._TRACK_COLOR)
        # Knob
        ky = self._knob_y()
        kc = self._KNOB_PRESSED if self._active else self._KNOB_COLOR
        t.fill_rect(cx - self._KNOB_W // 2, ky - 4, self._KNOB_W, 9, kc)

    def _set_value(self, ty):
        range_px = max(self.h - 20, 1)
        ratio = (ty - (self.y + 10)) / range_px
        ratio = max(0.0, min(1.0, ratio))
        self._value = int((1 - ratio) * 255)

    def process(self, pos):
        if pos:
            tx, ty = pos
            if not self._active and self.hit(tx, ty):
                self._active = True
                self._set_value(ty)
                self.draw()
                return True
            if self._active:
                self._set_value(ty)
                self.draw()
                return True
        elif self._active:
            self._active = False
            self.draw()
        return self._active

    def osc_message(self):
        return (float(self._value),)


class RGBPicker(Widget):
    """Three vertical sliders (R/G/B) that send a single OSC message with 3 int args.

    Layout: 3 thin tracks side by side, each with a knob.
    Hit area covers the entire widget bounding box.
    """
    _TRACK_W = 5
    _KNOB_H = 9
    _LABELS = ('R', 'G', 'B')
    _COLORS = (color565(255, 0, 0), color565(0, 255, 0), color565(0, 128, 255))

    def __init__(self, tft, x, y, w, h, osc_addr, default=(127, 127, 127)):
        super().__init__(tft, x, y, w, h, osc_addr)
        self._values = list(default)
        self._active_channel = None  # which channel (0/1/2) is being dragged

    @property
    def values(self):
        return tuple(self._values)

    def _track_x(self, ch):
        """Center X of a specific channel's track."""
        gap = self.w // 3
        return self.x + gap // 2 + ch * gap

    def _knob_y(self, ch):
        range_px = max(self.h - 20, 1)
        ratio = self._values[ch] / 255
        return self.y + 10 + int(range_px * (1 - ratio))

    def draw(self):
        t = self.tft
        for ch in range(3):
            cx = self._track_x(ch)
            # Track background
            t.fill_rect(cx - 2, self.y + 8, 5, self.h - 16, BLACK)
            # Track line
            tc = GRAY if self._active_channel != ch else self._COLORS[ch]
            t.fill_rect(cx - 1, self.y + 8, 3, self.h - 16, tc)
            # Knob
            ky = self._knob_y(ch)
            kc = self._COLORS[ch]
            t.fill_rect(cx - 2, ky - 4, 5, self._KNOB_H, kc)
        # Labels at bottom
        for ch in range(3):
            cx = self._track_x(ch)
            ly = self.y + self.h - 6
            t.text(self._LABELS[ch], cx - 2, ly, self._COLORS[ch], BLACK)

    def _set_channel_value(self, ch, ty):
        range_px = max(self.h - 20, 1)
        ratio = (ty - (self.y + 10)) / range_px
        ratio = max(0.0, min(1.0, ratio))
        self._values[ch] = int((1 - ratio) * 255)

    def _find_channel(self, tx):
        """Find which channel track is closest to touch X, or None."""
        for ch in range(3):
            cx = self._track_x(ch)
            if abs(tx - cx) <= 6:
                return ch
        return None

    def process(self, pos):
        if pos:
            tx, ty = pos
            if not self.hit(tx, ty):
                if self._active_channel is not None:
                    self._active_channel = None
                    self.draw()
                return False
            ch = self._find_channel(tx)
            if ch is not None:
                old_active = self._active_channel
                self._active_channel = ch
                self._set_channel_value(ch, ty)
                self.draw()
                return True
        elif self._active_channel is not None:
            self._active_channel = None
            self.draw()
        return self._active_channel is not None

    def osc_message(self):
        return (self._values[0], self._values[1], self._values[2])
