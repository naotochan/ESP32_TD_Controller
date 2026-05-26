"""UI widget framework for ILI9341 display."""
import math
from lib.ili9341 import WHITE, BLACK, GRAY, color565

# --- Color palette ---
_PRESSED_BG     = color565(60, 120, 220)
_NORMAL_BG      = color565(30,  60, 120)
_PRESSED_BORDER = color565(100, 160, 255)
_NORMAL_BORDER  = color565(180, 180, 220)
_LABEL_COLOR    = WHITE


def _hsv_to_rgb(h, s, v):
    """h, s, v in [0.0, 1.0]. Returns (r, g, b) each in [0, 255]."""
    if s == 0:
        c = int(v * 255)
        return c, c, c
    h6 = h * 6.0
    i = int(h6) % 6
    f = h6 - int(h6)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    if i == 0:   r, g, b = v, t, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t, p, v
    else:        r, g, b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)


def _rgb_to_hsv(r, g, b):
    """r, g, b in [0.0, 1.0]. Returns (h, s, v) each in [0.0, 1.0]."""
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    diff = max_c - min_c
    v = max_c
    s = diff / max_c if max_c > 0 else 0.0
    if diff == 0:
        return 0.0, s, v
    if max_c == r:
        h = ((g - b) / diff) % 6 / 6.0
    elif max_c == g:
        h = ((b - r) / diff + 2.0) / 6.0
    else:
        h = ((r - g) / diff + 4.0) / 6.0
    return h, s, v


class Widget:
    """Base class for all UI widgets.

    Subclasses implement: draw(), on_touch(tx, ty), on_move(tx, ty), on_release()
    - on_release() must return True to trigger OSC on release, False to suppress.
    process(pos) dispatches to these handlers automatically.
    """
    throttle = False  # set True on continuous-value widgets (Slider, HSVPicker)

    def __init__(self, tft, x, y, w, h, osc_addr):
        self.tft = tft
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.osc_addr = osc_addr
        self._touching = False

    def draw(self):
        raise NotImplementedError

    def hit(self, tx, ty):
        return self.x <= tx < self.x + self.w and self.y <= ty < self.y + self.h

    def process(self, pos):
        if pos:
            tx, ty = pos
            if not self._touching:
                if self.hit(tx, ty):
                    self._touching = True
                    self.on_touch(tx, ty)
                    return True
                return False
            else:
                self.on_move(tx, ty)
                return True
        else:
            if self._touching:
                self._touching = False
                return self.on_release()
            return False

    def on_touch(self, tx, ty): pass
    def on_move(self, tx, ty):  pass
    def on_release(self):       return False
    def osc_message(self):      return None


class Button(Widget):
    """Momentary button — sends 1.0 while held, 0.0 on release."""

    def __init__(self, tft, x, y, w, h, label, osc_addr):
        super().__init__(tft, x, y, w, h, osc_addr)
        self.label = label

    def draw(self):
        bg = _PRESSED_BG if self._touching else _NORMAL_BG
        c  = _PRESSED_BORDER if self._touching else _NORMAL_BORDER
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

    def on_touch(self, tx, ty): self.draw()
    def on_release(self):
        self.draw()
        return True

    def osc_message(self):
        return (1.0 if self._touching else 0.0,)


class Slider(Widget):
    """Vertical slider (0-255). Sends float value while dragging.

    Uses differential drawing: only the knob is redrawn on move.
    """
    throttle = True
    _KNOB_W = 4
    _TRACK_COLOR = color565(80, 80, 100)
    _KNOB_COLOR  = color565(100, 180, 255)
    _KNOB_PRESSED = color565(140, 210, 255)

    def __init__(self, tft, x, y, w, h, osc_addr, default=127, label=''):
        super().__init__(tft, x, y, w, h, osc_addr)
        self._value = default
        self._prev_ky = None

    @property
    def value(self):
        return self._value

    def _knob_y(self):
        range_px = max(self.h - 20, 1)
        return self.y + 10 + int(range_px * (1 - self._value / 255))

    def draw(self):
        """Full redraw: called on touch start and release."""
        t = self.tft
        cx = self.x + self.w // 2
        t.fill_rect(self.x, self.y, self.w, self.h, BLACK)
        t.fill_rect(cx - 1, self.y + 8, 3, self.h - 16, self._TRACK_COLOR)
        ky = self._knob_y()
        kc = self._KNOB_PRESSED if self._touching else self._KNOB_COLOR
        t.fill_rect(cx - self._KNOB_W // 2, ky - 4, self._KNOB_W, 9, kc)
        self._prev_ky = ky

    def _move_knob(self):
        """Differential update: erase old knob, restore track, draw new knob."""
        ky = self._knob_y()
        if ky == self._prev_ky:
            return
        t = self.tft
        cx = self.x + self.w // 2
        kw2 = self._KNOB_W // 2

        # Erase old knob and restore track pixels
        if self._prev_ky is not None:
            t.fill_rect(cx - kw2, self._prev_ky - 4, self._KNOB_W, 9, BLACK)
            tk_top = max(self.y + 8, self._prev_ky - 4)
            tk_bot = min(self.y + self.h - 12, self._prev_ky + 5)
            if tk_bot > tk_top:
                t.fill_rect(cx - 1, tk_top, 3, tk_bot - tk_top, self._TRACK_COLOR)

        t.fill_rect(cx - kw2, ky - 4, self._KNOB_W, 9, self._KNOB_PRESSED)
        self._prev_ky = ky

    def _set_value(self, ty):
        range_px = max(self.h - 20, 1)
        ratio = (ty - (self.y + 10)) / range_px
        self._value = int((1 - max(0.0, min(1.0, ratio))) * 255)

    def on_touch(self, tx, ty):
        self._set_value(ty)
        self.draw()

    def on_move(self, tx, ty):
        old = self._value
        self._set_value(ty)
        if self._value != old:
            self._move_knob()

    def on_release(self):
        self._prev_ky = None
        self.draw()
        return False

    def osc_message(self):
        return (float(self._value),)


class HSVPicker(Widget):
    """Circular HSV color picker widget.

    Layout:
      - Color wheel (left): angle=hue, radius=saturation
      - Value bar (right): vertical gradient, top=bright, bottom=dark

    OSC: sends (r, g, b) as 3 int arguments (0-255).
    """
    throttle = True
    _BAR_W   = 16
    _BAR_PAD = 4
    _N_SEG   = 18

    def __init__(self, tft, x, y, w, h, osc_addr, default=(127, 127, 127), label=''):
        super().__init__(tft, x, y, w, h, osc_addr)
        r, g, b = [c / 255.0 for c in default]
        self._h, self._s, self._v = _rgb_to_hsv(r, g, b)
        self._active = None   # 'hs' | 'val'

    def _rgb(self):
        return _hsv_to_rgb(self._h, self._s, self._v)

    @property
    def _cx(self):
        return self.x + (self.w - self._BAR_W - self._BAR_PAD) // 2

    @property
    def _cy(self):
        return self.y + self.h // 2

    @property
    def _radius(self):
        return (self.w - self._BAR_W - self._BAR_PAD - 4) // 2

    @property
    def _bar_x(self):
        return self.x + self.w - self._BAR_W - 2

    # --- Drawing ---
    def _draw_wheel(self):
        t = self.tft
        r = self._radius
        n = self._N_SEG
        seg_w = (2 * r) // n

        for dy in range(-r, r + 1):
            dy2 = dy * dy
            dx_o = int((r * r - dy2) ** 0.5)
            if dx_o < 1:
                continue

            yo = self._cy + dy
            x_lo = self._cx - dx_o
            x_hi = self._cx + dx_o

            for i in range(n):
                sx = -r + i * seg_w
                ex = sx + seg_w - 1
                if ex < x_lo - self._cx or sx > x_hi - self._cx:
                    continue

                mx = (sx + ex) // 2
                angle = math.atan2(dy, mx)
                h = (angle / math.pi * 0.5 + 1.0) % 1.0
                rr, gg, bb = _hsv_to_rgb(h, 1.0, 1.0)

                dx = max(x_lo, self._cx + sx)
                dw = min(x_hi, self._cx + ex) - dx + 1
                if dw > 0:
                    t.fill_rect(dx, yo, dw, 1, color565(rr, gg, bb))

    def _draw_value_bar(self):
        t = self.tft
        bx = self._bar_x
        rh, rg, rb = self._rgb()
        for dy in range(self.h):
            vf = 1.0 - dy / max(1, self.h - 1)
            t.fill_rect(bx, self.y + dy, self._BAR_W, 1,
                        color565(int(rh * vf), int(rg * vf), int(rb * vf)))

    def draw(self):
        t = self.tft
        t.fill_rect(self.x, self.y, self.w, self.h, BLACK)
        self._draw_wheel()
        self._draw_value_bar()

    # --- Touch handling ---
    def _find_zone(self, tx, ty):
        if tx >= self._bar_x:
            return 'val'
        dx = tx - self._cx
        dy = ty - self._cy
        if (dx * dx + dy * dy) <= self._radius * self._radius:
            return 'hs'
        return None

    def _update_from_touch(self, tx, ty):
        if self._active == 'hs':
            dx = tx - self._cx
            dy = ty - self._cy
            angle = math.atan2(-dy, dx)
            self._h = (angle / math.pi * 0.5 + 1.0) % 1.0
            dist = (dx * dx + dy * dy) ** 0.5
            self._s = min(1.0, dist / max(1, self._radius))
        elif self._active == 'val':
            self._v = max(0.0, min(1.0, 1.0 - (ty - self.y) / max(1, self.h - 1)))

    def on_touch(self, tx, ty):
        self._active = self._find_zone(tx, ty)
        if self._active:
            self._update_from_touch(tx, ty)
            self.draw()

    def on_move(self, tx, ty):
        if not self._active:
            return
        self._update_from_touch(tx, ty)
        self.draw()

    def on_release(self):
        self._active = None
        return False

    def osc_message(self):
        r, g, b = self._rgb()
        return (r, g, b)


class HSlider(Widget):
    """Horizontal slider (0-255). Sends float value while dragging."""
    throttle = True
    _KNOB_W      = 4
    _TRACK_COLOR  = color565(80, 80, 100)
    _KNOB_COLOR   = color565(100, 180, 255)
    _KNOB_PRESSED = color565(140, 210, 255)

    def __init__(self, tft, x, y, w, h, osc_addr, default=127, label=''):
        super().__init__(tft, x, y, w, h, osc_addr)
        self._value = default
        self._prev_kx = None

    @property
    def value(self):
        return self._value

    def _knob_x(self):
        range_px = max(self.w - 20, 1)
        return self.x + 10 + int(range_px * (self._value / 255))

    def draw(self):
        t = self.tft
        cy = self.y + self.h // 2
        t.fill_rect(self.x, self.y, self.w, self.h, BLACK)
        t.fill_rect(self.x + 8, cy - 1, self.w - 16, 3, self._TRACK_COLOR)
        kx = self._knob_x()
        kc = self._KNOB_PRESSED if self._touching else self._KNOB_COLOR
        kw2 = self._KNOB_W // 2
        t.fill_rect(kx - kw2, self.y + 2, self._KNOB_W, self.h - 4, kc)
        self._prev_kx = kx

    def _move_knob(self):
        kx = self._knob_x()
        if kx == self._prev_kx:
            return
        t = self.tft
        cy = self.y + self.h // 2
        kw2 = self._KNOB_W // 2
        if self._prev_kx is not None:
            t.fill_rect(self._prev_kx - kw2, self.y + 2, self._KNOB_W, self.h - 4, BLACK)
            tk_lo = max(self.x + 8, self._prev_kx - kw2)
            tk_hi = min(self.x + self.w - 12, self._prev_kx + kw2 + 1)
            if tk_hi > tk_lo:
                t.fill_rect(tk_lo, cy - 1, tk_hi - tk_lo, 3, self._TRACK_COLOR)
        t.fill_rect(kx - kw2, self.y + 2, self._KNOB_W, self.h - 4, self._KNOB_PRESSED)
        self._prev_kx = kx

    def _set_value(self, tx, ty):
        range_px = max(self.w - 20, 1)
        ratio = (tx - (self.x + 10)) / range_px
        self._value = int(max(0.0, min(1.0, ratio)) * 255)

    def on_touch(self, tx, ty):
        self._set_value(tx, ty)
        self.draw()

    def on_move(self, tx, ty):
        old = self._value
        self._set_value(tx, ty)
        if self._value != old:
            self._move_knob()

    def on_release(self):
        self._prev_kx = None
        self.draw()
        return False

    def osc_message(self):
        return (float(self._value),)


class PageButton(Widget):
    """Tapping switches to the target page. No OSC message sent."""

    def __init__(self, tft, x, y, w, h, target_page, label=''):
        super().__init__(tft, x, y, w, h, osc_addr='')
        self.target_page = target_page
        self._label = label or f'>{target_page + 1}'

    def draw(self):
        bg = color565(20, 60, 40) if self._touching else color565(10, 30, 20)
        c  = color565(80, 220, 120) if self._touching else color565(50, 160, 80)
        t = self.tft
        t.fill_rect(self.x, self.y, self.w, self.h, bg)
        for i in range(2):
            bx, by = self.x + i, self.y + i
            bw, bh = self.w - i * 2, self.h - i * 2
            t.fill_rect(bx, by, bw, 1, c)
            t.fill_rect(bx, by + bh - 1, bw, 1, c)
            t.fill_rect(bx, by, 1, bh, c)
            t.fill_rect(bx + bw - 1, by, 1, bh, c)
        lx = self.x + (self.w - len(self._label) * 8) // 2
        ly = self.y + (self.h - 8) // 2
        t.text(self._label, lx, ly, color565(100, 255, 150), bg)

    def on_touch(self, tx, ty): self.draw()
    def on_release(self):
        self.draw()
        return True

    def osc_message(self):
        return None


class IPDisplay(Widget):
    """Displays the ESP32's WiFi IP address. Read-only."""

    def __init__(self, tft, x, y, w, h, osc_addr):
        super().__init__(tft, x, y, w, h, osc_addr)
        try:
            import network as _net
            wlan = _net.WLAN(_net.STA_IF)
            self._ip = wlan.ifconfig()[0] if wlan.isconnected() else '---'
        except Exception:
            self._ip = '---'

    def draw(self):
        t = self.tft
        t.fill_rect(self.x, self.y, self.w, self.h, BLACK)
        lx = self.x + (self.w - len(self._ip) * 6) // 2
        ly = self.y + (self.h - 8) // 2
        t.text(self._ip, lx, ly, GRAY, BLACK)

    def on_touch(self, tx, ty): pass
    def on_release(self):       return False
    def osc_message(self):      return None
