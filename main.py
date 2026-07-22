"""ESP32 TD Controller - main entry point."""
__version__ = "0.2.0"

import time
from machine import SPI, Pin
from lib.dotenv import load
from lib.ili9341 import ILI9341, color565, WHITE, RED
from lib.xpt2046 import XPT2046
from lib.osc import OSCSender, OSCReceiver
from ui import Button, Toggle, Slider, HSlider, HSVPicker, IPDisplay, PageButton

# Default touch calibration (overridden by calib.json / CALIB_* in .env)
_DEFAULT_CALIB = dict(x_min=350, x_max=3799, y_min=199, y_max=3721)


def _load_layout():
    try:
        import ujson
        with open('layout.json') as f:
            d = ujson.load(f)
        return d.get('orientation', 'portrait'), d.get('rotation', 0), d.get('pages', [[]])
    except Exception:
        pass

    try:
        import widgets as _w
        orientation = getattr(_w, 'ORIENTATION', 'portrait')
        rotation    = getattr(_w, 'ROTATION',    0)
        pages       = getattr(_w, 'PAGES', None) or [getattr(_w, 'WIDGETS', [])]
        return orientation, rotation, pages
    except ImportError:
        return 'portrait', 0, [[]]


def _load_calib(env):
    """Prefer calib.json, then CALIB_* in .env, then built-in defaults."""
    calib = dict(_DEFAULT_CALIB)
    try:
        import ujson
        with open('calib.json') as f:
            d = ujson.load(f)
        for k in ('x_min', 'x_max', 'y_min', 'y_max'):
            if k in d:
                calib[k] = int(d[k])
        return calib
    except Exception:
        pass
    for k in ('x_min', 'x_max', 'y_min', 'y_max'):
        ek = 'CALIB_' + k.upper()
        if ek in env:
            try:
                calib[k] = int(env[ek])
            except ValueError:
                pass
    return calib


def _wifi_connected():
    """Cached WLAN check (refreshed every ~2s)."""
    now = time.ticks_ms()
    if not hasattr(_wifi_connected, '_at') or time.ticks_diff(now, _wifi_connected._at) > 2000:
        _wifi_connected._at = now
        try:
            import network
            _wifi_connected._ok = network.WLAN(network.STA_IF).isconnected()
        except Exception:
            _wifi_connected._ok = False
    return _wifi_connected._ok


def _show_error(tft, lines, fatal=True):
    """Draw error lines on screen. If fatal, loop forever."""
    bg = color565(40, 0, 0) if fatal else color565(40, 30, 0)
    tft.fill(bg)
    y = 12
    tft.text("ERROR", 4, y, RED, bg)
    y += 20
    for line in lines:
        # wrap roughly at 28 chars (240px / 8)
        while line:
            chunk = line[:28]
            line = line[28:]
            tft.text(chunk, 4, y, WHITE, bg)
            y += 14
            if y > 300:
                break
    if fatal:
        while True:
            time.sleep(1)


ORIENTATION, ROTATION, PAGES = _load_layout()
SCREEN_W, SCREEN_H = (320, 240) if ORIENTATION == "landscape" else (240, 320)

# --- Hardware (TFT first so we can show errors) ---
spi_tft = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft = ILI9341(spi_tft, cs=Pin(15), dc=Pin(2), bl=Pin(21), rotation=ROTATION)

# --- Config ---
env = load()
_required = ('WIFI_SSID', 'WIFI_PASSWORD', 'OSC_HOST', 'OSC_PORT')
_missing = [k for k in _required if k not in env or not str(env.get(k, '')).strip()]
if _missing:
    _show_error(tft, [
        ".env missing keys:",
        ", ".join(_missing),
        "",
        "Create .env and",
        "run ./deploy.sh",
    ], fatal=True)

host = env["OSC_HOST"]
try:
    port = int(env["OSC_PORT"])
except ValueError:
    _show_error(tft, ["OSC_PORT invalid:", str(env.get("OSC_PORT", ""))], fatal=True)

if not _wifi_connected():
    _show_error(tft, [
        "WiFi FAILED",
        "Check WIFI_SSID /",
        "WIFI_PASSWORD in .env",
        "",
        "UI still runs;",
        "OSC will be skipped",
    ], fatal=False)
    time.sleep(2)

calib = _load_calib(env)

spi_touch = SPI(2, baudrate=1_000_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
touch = XPT2046(spi_touch, cs=Pin(33), irq=Pin(36),
                x_min=calib['x_min'], x_max=calib['x_max'],
                y_min=calib['y_min'], y_max=calib['y_max'],
                screen_w=SCREEN_W, screen_h=SCREEN_H, rotation=ROTATION)
osc = OSCSender(host, port)

# Optional OSC listen (TD → ESP32). Unset = receive off.
osc_rx = None
_listen = env.get('OSC_LISTEN_PORT', '').strip()
if _listen:
    try:
        osc_rx = OSCReceiver(int(_listen))
    except Exception as e:
        print("OSC listen failed:", e)
        osc_rx = None

# --- Instantiate widgets for all pages ---
WIDGET_MAP = {
    "Button": Button, "Toggle": Toggle, "Slider": Slider, "HSlider": HSlider,
    "HSVPicker": HSVPicker, "IPDisplay": IPDisplay, "PageButton": PageButton,
}

all_pages = []
for page_widgets in PAGES:
    instances = []
    for w in page_widgets:
        cls = WIDGET_MAP.get(w["type"])
        if cls is None:
            continue
        kwargs = {k: v for k, v in w.items() if k not in ("type", "id")}
        instances.append(cls(tft, **kwargs))
    all_pages.append(instances)

if not all_pages:
    all_pages = [[]]

current_page = 0

# Address → widgets (for inbound OSC)
_addr_index = {}
for page in all_pages:
    for w in page:
        addr = getattr(w, 'osc_addr', None)
        if addr:
            _addr_index.setdefault(addr, []).append(w)


def draw_page(page_idx):
    tft.fill(color565(10, 10, 20))
    for w in all_pages[page_idx]:
        w.draw()
    # Version badge (bottom-right)
    ver = "v" + __version__
    vx = max(0, SCREEN_W - len(ver) * 8 - 4)
    tft.text(ver, vx, SCREEN_H - 12, color565(80, 80, 100), color565(10, 10, 20))


def _apply_inbound(addr, args):
    """Update widget values from TD→ESP32 OSC. Minimal: Slider/HSlider/Toggle."""
    widgets = _addr_index.get(addr)
    if not widgets or not args:
        return False
    redraw = False
    for w in widgets:
        if isinstance(w, (Slider, HSlider)):
            try:
                v = int(args[0])
            except (TypeError, ValueError):
                continue
            on_page = w in all_pages[current_page]
            w.set_value(v, redraw=on_page)
            redraw = redraw or on_page
        elif isinstance(w, Toggle):
            try:
                on = float(args[0]) >= 0.5
            except (TypeError, ValueError):
                continue
            on_page = w in all_pages[current_page]
            w.set_on(on, redraw=on_page)
            redraw = redraw or on_page
    return redraw


def _safe_send(address, *args):
    if not _wifi_connected():
        return
    try:
        osc.send(address, *args)
    except Exception:
        pass


draw_page(current_page)

# --- Main loop ---
_OSC_INTERVAL_MS = 20
_last_osc = {}

try:
    while True:
        if osc_rx:
            for addr, args in osc_rx.poll():
                _apply_inbound(addr, args)

        pos = touch.get_pos()
        now = time.ticks_ms()

        for w in all_pages[current_page]:
            claimed = w.process(pos)
            if claimed:
                if isinstance(w, PageButton) and not w._touching:
                    mode = getattr(w, 'nav_mode', 'goto')
                    if mode == 'prev':
                        new_page = (current_page - 1) % len(all_pages)
                    elif mode == 'next':
                        new_page = (current_page + 1) % len(all_pages)
                    else:
                        new_page = w.target_page
                    if new_page != current_page:
                        current_page = new_page
                        draw_page(current_page)
                else:
                    msg = w.osc_message()
                    if msg is not None:
                        if getattr(w, 'throttle', False):
                            wid = id(w)
                            if time.ticks_diff(now, _last_osc.get(wid, 0)) >= _OSC_INTERVAL_MS:
                                _safe_send(w.osc_addr, *msg)
                                _last_osc[wid] = now
                        else:
                            _safe_send(w.osc_addr, *msg)
                break

        time.sleep_ms(10)
except KeyboardInterrupt:
    pass
finally:
    osc.close()
    if osc_rx:
        osc_rx.close()
