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

    Subclasses implement: draw(), on_touch(tx, ty), on_move(tx, ty), on_release()
    - on_release() must return True to trigger OSC on release, False to suppress.
    process(pos) dispatches to these handlers automatically.
    """
    throttle = False  # set True on continuous-value widgets (Slider, HSlider)

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


class Toggle(Widget):
    """Latching button — tap toggles on/off, OSC sends 1.0 / 0.0."""

    _ON_BG      = color565(20, 100, 70)
    _OFF_BG     = color565(30, 40, 50)
    _ON_BORDER  = color565(60, 220, 140)
    _OFF_BORDER = color565(120, 130, 150)
    _PRESS_BG   = color565(40, 140, 100)

    def __init__(self, tft, x, y, w, h, label, osc_addr, default=0):
        super().__init__(tft, x, y, w, h, osc_addr)
        self.label = label
        self._on = bool(default)
        self._pending_osc = False

    @property
    def value(self):
        return 1.0 if self._on else 0.0

    def set_on(self, on, redraw=True):
        self._on = bool(on)
        if redraw:
            self.draw()

    def draw(self):
        if self._touching:
            bg, c = self._PRESS_BG, self._ON_BORDER
        elif self._on:
            bg, c = self._ON_BG, self._ON_BORDER
        else:
            bg, c = self._OFF_BG, self._OFF_BORDER
        t = self.tft
        t.fill_rect(self.x, self.y, self.w, self.h, bg)
        for i in range(2):
            bx, by = self.x + i, self.y + i
            bw, bh = self.w - i * 2, self.h - i * 2
            t.fill_rect(bx, by, bw, 1, c)
            t.fill_rect(bx, by + bh - 1, bw, 1, c)
            t.fill_rect(bx, by, 1, bh, c)
            t.fill_rect(bx + bw - 1, by, 1, bh, c)
        # ON indicator bar on the left
        if self._on:
            t.fill_rect(self.x + 3, self.y + 3, 4, self.h - 6, self._ON_BORDER)
        text = self.label
        lx = self.x + (self.w - len(text) * 8) // 2
        ly = self.y + (self.h - 8) // 2
        t.text(text, lx, ly, _LABEL_COLOR, bg)

    def on_touch(self, tx, ty):
        self._on = not self._on
        self._pending_osc = True
        self.draw()

    def on_release(self):
        self.draw()
        return False

    def osc_message(self):
        if not self._pending_osc:
            return None
        self._pending_osc = False
        return (1.0 if self._on else 0.0,)


class Slider(Widget):
    """Vertical slider (0-255). Sends float value while dragging.

    Uses differential drawing: only the knob is redrawn on move.
    Optional label is drawn at the bottom of the widget.
    """
    throttle = True
    _KNOB_W = 4
    _LABEL_H = 10
    _TRACK_COLOR = color565(80, 80, 100)
    _KNOB_COLOR  = color565(100, 180, 255)
    _KNOB_PRESSED = color565(140, 210, 255)

    def __init__(self, tft, x, y, w, h, osc_addr, default=127, label=''):
        super().__init__(tft, x, y, w, h, osc_addr)
        self.label = label or ''
        self._value = default
        self._prev_ky = None

    @property
    def value(self):
        return self._value

    def set_value(self, v, redraw=True):
        self._value = int(max(0, min(255, v)))
        self._prev_ky = None
        if redraw:
            self.draw()

    def _label_reserve(self):
        return self._LABEL_H if self.label else 0

    def _track_top(self):
        return self.y + 8

    def _track_bot(self):
        return self.y + self.h - 8 - self._label_reserve()

    def _knob_y(self):
        top = self._track_top() + 2
        bot = self._track_bot() - 2
        range_px = max(bot - top, 1)
        return top + int(range_px * (1 - self._value / 255))

    def _draw_label(self):
        if not self.label:
            return
        t = self.tft
        max_chars = max(1, self.w // 8)
        text = self.label[:max_chars]
        lx = self.x + (self.w - len(text) * 8) // 2
        ly = self.y + self.h - 9
        t.text(text, lx, ly, _LABEL_COLOR, BLACK)

    def draw(self):
        """Full redraw: called on touch start and release."""
        t = self.tft
        cx = self.x + self.w // 2
        t.fill_rect(self.x, self.y, self.w, self.h, BLACK)
        top = self._track_top()
        bot = self._track_bot()
        th = max(bot - top, 1)
        t.fill_rect(cx - 1, top, 3, th, self._TRACK_COLOR)
        ky = self._knob_y()
        kc = self._KNOB_PRESSED if self._touching else self._KNOB_COLOR
        t.fill_rect(cx - self._KNOB_W // 2, ky - 4, self._KNOB_W, 9, kc)
        self._prev_ky = ky
        self._draw_label()

    def _move_knob(self):
        """Differential update: erase old knob, restore track, draw new knob."""
        ky = self._knob_y()
        if ky == self._prev_ky:
            return
        t = self.tft
        cx = self.x + self.w // 2
        kw2 = self._KNOB_W // 2
        top = self._track_top()
        bot = self._track_bot()

        # Erase old knob and restore track pixels
        if self._prev_ky is not None:
            t.fill_rect(cx - kw2, self._prev_ky - 4, self._KNOB_W, 9, BLACK)
            tk_top = max(top, self._prev_ky - 4)
            tk_bot = min(bot, self._prev_ky + 5)
            if tk_bot > tk_top:
                t.fill_rect(cx - 1, tk_top, 3, tk_bot - tk_top, self._TRACK_COLOR)

        t.fill_rect(cx - kw2, ky - 4, self._KNOB_W, 9, self._KNOB_PRESSED)
        self._prev_ky = ky

    def _set_value(self, ty):
        top = self._track_top() + 2
        bot = self._track_bot() - 2
        range_px = max(bot - top, 1)
        ratio = (ty - top) / range_px
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


class HSlider(Widget):
    """Horizontal slider (0-255). Sends float value while dragging.

    Optional label is drawn above the track.
    """
    throttle = True
    _KNOB_W      = 4
    _LABEL_H     = 10
    _TRACK_COLOR  = color565(80, 80, 100)
    _KNOB_COLOR   = color565(100, 180, 255)
    _KNOB_PRESSED = color565(140, 210, 255)

    def __init__(self, tft, x, y, w, h, osc_addr, default=127, label=''):
        super().__init__(tft, x, y, w, h, osc_addr)
        self.label = label or ''
        self._value = default
        self._prev_kx = None

    @property
    def value(self):
        return self._value

    def set_value(self, v, redraw=True):
        self._value = int(max(0, min(255, v)))
        self._prev_kx = None
        if redraw:
            self.draw()

    def _label_reserve(self):
        return self._LABEL_H if self.label else 0

    def _track_y(self):
        # Center track in the area below the label strip.
        top = self.y + self._label_reserve()
        return top + (self.h - self._label_reserve()) // 2

    def _knob_x(self):
        range_px = max(self.w - 20, 1)
        return self.x + 10 + int(range_px * (self._value / 255))

    def _knob_rect(self, kx):
        top = self.y + self._label_reserve() + 1
        h = max(self.h - self._label_reserve() - 2, 4)
        kw2 = self._KNOB_W // 2
        return kx - kw2, top, self._KNOB_W, h

    def _draw_label(self):
        if not self.label:
            return
        t = self.tft
        max_chars = max(1, self.w // 8)
        text = self.label[:max_chars]
        lx = self.x + (self.w - len(text) * 8) // 2
        t.text(text, lx, self.y + 1, _LABEL_COLOR, BLACK)

    def draw(self):
        t = self.tft
        cy = self._track_y()
        t.fill_rect(self.x, self.y, self.w, self.h, BLACK)
        t.fill_rect(self.x + 8, cy - 1, self.w - 16, 3, self._TRACK_COLOR)
        kx = self._knob_x()
        kc = self._KNOB_PRESSED if self._touching else self._KNOB_COLOR
        rx, ry, rw, rh = self._knob_rect(kx)
        t.fill_rect(rx, ry, rw, rh, kc)
        self._prev_kx = kx
        self._draw_label()

    def _move_knob(self):
        kx = self._knob_x()
        if kx == self._prev_kx:
            return
        t = self.tft
        cy = self._track_y()
        if self._prev_kx is not None:
            ox, oy, ow, oh = self._knob_rect(self._prev_kx)
            t.fill_rect(ox, oy, ow, oh, BLACK)
            tk_lo = max(self.x + 8, self._prev_kx - self._KNOB_W // 2)
            tk_hi = min(self.x + self.w - 12, self._prev_kx + self._KNOB_W // 2 + 1)
            if tk_hi > tk_lo:
                t.fill_rect(tk_lo, cy - 1, tk_hi - tk_lo, 3, self._TRACK_COLOR)
        nx, ny, nw, nh = self._knob_rect(kx)
        t.fill_rect(nx, ny, nw, nh, self._KNOB_PRESSED)
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

    def __init__(self, tft, x, y, w, h, nav_mode='goto', target_page=0, label=''):
        super().__init__(tft, x, y, w, h, osc_addr='')
        self.nav_mode = nav_mode
        self.target_page = target_page
        if label:
            self._label = label
        elif nav_mode == 'prev':
            self._label = '<<'
        elif nav_mode == 'next':
            self._label = '>>'
        else:
            self._label = f'>{target_page + 1}'

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
