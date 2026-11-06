"""Drawing helpers for the Sky look: a canvas that remembers which areas are
clickable, glass cards, text measuring and wrapping, and line and bar charts
with axes, a "now" line and a picked point."""

import math

import fenn

WHITE = "#FFFFFF"
SOFT = "#FFFFFFB8"
FAINT = "#FFFFFF73"
LINE = "#FFFFFF2E"
CARD = "#0000001F"
CARD_RIM = "#FFFFFF24"
BLUE = "#5AC8FA"

WIDTHS = {" ": 0.27, ".": 0.27, ",": 0.27, ":": 0.28, ";": 0.28, "%": 0.82, "°": 0.38, "/": 0.36,
          "-": 0.36, "–": 0.55, "·": 0.27, "(": 0.33, ")": 0.33, "'": 0.22, "’": 0.22,
          "i": 0.25, "l": 0.25, "j": 0.25, "t": 0.34, "f": 0.33, "r": 0.36, "m": 0.83, "w": 0.75,
          "I": 0.28, "M": 0.84, "W": 0.92}


def tw(text, size, bold=False):
    w = 0.0
    for ch in str(text):
        if ch in WIDTHS:
            w += WIDTHS[ch]
        elif ch.isdigit():
            w += 0.58
        elif ch.isupper():
            w += 0.66
        else:
            w += 0.53
    return w * size * (1.04 if bold else 1.0)


def fit(text, size, room, bold=False):
    text = str(text)
    if tw(text, size, bold) <= room:
        return text
    while text and tw(text + "…", size, bold) > room:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap(text, size, room, lines=2, bold=False):
    words, out, cur = str(text).split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if tw(trial, size, bold) <= room or not cur:
            cur = trial
        else:
            out.append(cur)
            cur = wd
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = fit(out[-1] + " …", size, room, bold)
    return out


def mix(a, b, t):
    t = min(1.0, max(0.0, t))
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(f"{round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t):02X}" for i in (0, 2, 4))


def scale_color(stops, v):
    """stops: [(value, "#RRGGBB"), ...] ascending."""
    if v <= stops[0][0]:
        return stops[0][1]
    for (v0, c0), (v1, c1) in zip(stops, stops[1:]):
        if v <= v1:
            return mix(c0, c1, (v - v0) / ((v1 - v0) or 1))
    return stops[-1][1]


class Canvas:
    """Shapes plus clickable regions (checked top-most first)."""

    def __init__(self, width):
        self.w = width
        self.shapes = []
        self.regions = []
        self.h = 0

    def add(self, shapes):
        self.shapes += shapes

    def text(self, x, y, value, size=13, color=WHITE, anchor="start", bold=False):
        self.shapes.append(fenn.label(x, y, value, size=size, color=color, anchor=anchor, bold=bold))

    def rect(self, x, y, w, h, fill=None, radius=0, stroke=None, width=1):
        self.shapes.append(fenn.rect(x, y, w, h, fill=fill, radius=radius, stroke=stroke, width=width if stroke else None))

    def line(self, pts, color=WHITE, width=1):
        self.shapes.append(fenn.line(pts, color=color, width=width))

    def circle(self, x, y, r, fill=None, stroke=None, width=1):
        self.shapes.append(fenn.circle(x, y, r, fill=fill, stroke=stroke, width=width if stroke else None))

    def glyph(self, x, y, name, size=14, color=WHITE, fill=True):
        self.shapes.append(fenn.glyph(x, y, name, size, color, fill))

    def region(self, left, top, right, bottom, action, **extra):
        self.regions.append((left, top, right, bottom, action, extra))

    def hit(self, x, y):
        for x0, y0, x1, y1, action, extra in reversed(self.regions):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return action, extra
        return None, None

    def node(self, cid):
        return fenn.canvas(self.h, self.shapes, width=self.w, id=cid)


def card(c, x, y, w, h, title=None, icon=None, action=None, selected=False):
    c.rect(x, y, w, h, fill="#FFFFFF24" if selected else CARD, radius=16, stroke=CARD_RIM)
    if title:
        tx = x + 14
        if icon:
            c.glyph(x + 20, y + 17, icon, 11, SOFT)
            tx = x + 30
        c.text(tx, y + 17, title.upper(), size=10, color=SOFT, bold=True)
    if action:
        c.region(x, y, x + w, y + h, action)


def pill(c, x, y, label, action, on=False, size=11, pad=9, h=22):
    w = tw(label, size, True) + pad * 2
    c.rect(x, y, w, h, fill="#FFFFFF40" if on else "#FFFFFF14", radius=h / 2)
    c.text(x + w / 2, y + h / 2, label, size=size, color=WHITE if on else SOFT, anchor="center", bold=True)
    c.region(x, y, x + w, y + h, action)
    return w


def round_line(c, a, b, color, width):
    c.line([a, b], color, width)
    c.circle(a[0], a[1], width / 2, fill=color)
    c.circle(b[0], b[1], width / 2, fill=color)


def nice_range(lo, hi, ticks=4, floor_zero=False):
    if lo is None or hi is None:
        return 0, 1, [0, 1]
    if floor_zero:
        lo = min(0, lo)
    if hi - lo < 1e-9:
        hi = lo + 1
    raw = (hi - lo) / ticks
    exp = math.floor(math.log10(raw))
    base = raw / 10 ** exp
    step = (1 if base <= 1 else 2 if base <= 2 else 2.5 if base <= 2.5 else 5 if base <= 5 else 10) * 10 ** exp
    lo2 = math.floor(lo / step) * step
    hi2 = math.ceil(hi / step) * step
    n = round((hi2 - lo2) / step)
    return lo2, hi2, [lo2 + i * step for i in range(n + 1)]


def chart(c, x, y, w, h, times, series, y_fmt, x_label, now_index=None, sel=None, action="pick",
          floor_zero=False, fixed=None, bars=None, bar_color=BLUE, color_fn=None, markers=()):
    """A chart over len(times) points. series: [{"values", "color", "width",
    "fill"}]; bars: values drawn as bars (on their own 0-based scale when a
    line shares the chart, see bar_max). y labels on the right like the
    system weather app. Returns nothing; registers a click region."""
    n = len(times)
    if n < 2:
        return
    vals = [v for s in series for v in s["values"] if v is not None]
    if bars:
        vals += [v for v in bars if v is not None]
    lo, hi = (fixed[0], fixed[1]) if fixed else (min(vals) if vals else 0, max(vals) if vals else 1)
    if not fixed:
        pad = (hi - lo) * 0.12 or 1
        lo, hi = (lo - pad if not floor_zero else lo), hi + pad
    lo, hi, ticks = nice_range(lo, hi, 4, floor_zero) if not fixed else (fixed[0], fixed[1], fixed[2])
    right = 38
    pw = w - right
    X = lambda i: x + pw * i / (n - 1)
    Y = lambda v: y + h - (v - lo) / ((hi - lo) or 1) * h
    # grid and y labels
    for t in ticks:
        yy = Y(t)
        c.line([(x, yy), (x + pw, yy)], "#FFFFFF1A", 1)
        c.text(x + pw + 6, yy, y_fmt(t), size=10, color=SOFT)
    # x labels (and light verticals)
    for i, tm in enumerate(times):
        lab = x_label(i, tm)
        if lab:
            c.line([(X(i), y), (X(i), y + h)], "#FFFFFF10", 1)
            c.text(X(i), y + h + 12, lab, size=10, color=SOFT, anchor="center")
    # bars
    if bars:
        bw = max(2.0, pw / n * 0.62)
        for i, v in enumerate(bars):
            if v and v > 0:
                top = Y(v)
                col = bar_color(i) if callable(bar_color) else bar_color
                c.rect(X(i) - bw / 2, top, bw, y + h - top, fill=col, radius=min(2, bw / 2))
    # lines (filled below when asked: one convex quad per step)
    for s in series:
        v = s["values"]
        if s.get("fill"):
            for i in range(n - 1):
                if v[i] is None or v[i + 1] is None:
                    continue
                base = Y(max(lo, 0 if floor_zero else lo))
                c.shapes.append(fenn.polygon([(X(i), Y(v[i])), (X(i + 1), Y(v[i + 1])), (X(i + 1), base), (X(i), base)],
                                             fill=s["fill"]))
        for i in range(n - 1):
            if v[i] is None or v[i + 1] is None:
                continue
            col = color_fn(v[i]) if color_fn and s.get("colored") else s.get("color", WHITE)
            c.line([(X(i), Y(v[i])), (X(i + 1), Y(v[i + 1]))], col, s.get("width", 2))
    # now
    if now_index is not None and 0 <= now_index < n:
        nx = X(now_index)
        yy = y
        while yy < y + h:
            c.line([(nx, yy), (nx, min(y + h, yy + 3))], "#FFFFFF80", 1)
            yy += 6
    for i, text in markers:  # e.g. the day's high and low
        v = series[0]["values"][i]
        if v is not None:
            c.circle(X(i), Y(v), 3, fill=WHITE)
            c.text(X(i), Y(v) - 10 if text.startswith("H") else Y(v) + 11, text, size=10, color=WHITE, anchor="center", bold=True)
    # the picked point
    if sel is not None and 0 <= sel < n:
        sx = X(sel)
        c.line([(sx, y - 4), (sx, y + h)], WHITE, 1.2)
        for s in series:
            v = s["values"][sel]
            if v is not None:
                c.circle(sx, Y(v), 5, fill=WHITE)
                c.circle(sx, Y(v), 3, fill=s.get("color", WHITE) if s.get("color") != WHITE else "#5E8BC7")
    c.region(x - 4, y - 8, x + pw + 4, y + h + 18, action, x0=x, x1=x + pw, n=n)


def pick_index(extra, px):
    n = extra["n"]
    t = (px - extra["x0"]) / ((extra["x1"] - extra["x0"]) or 1)
    return max(0, min(n - 1, round(t * (n - 1))))


# ---- drawing Sky's cards on Fenn's own glass (the Glossy look)

TEXT_TONES = {"#FFFFFF": "text", "#FFFFFFB8": "dim", "#FFFFFF73": "faint"}
LIGHT_SOLIDS = {"FFFFFF": "#7E8794", "F2F4F7": "#8E97A5", "FFFDF2": "#8E97A5",
                "C9CFD8": "#6F7886", "AEB6C2": "#5F6876"}


def _tone(color, dark):
    rgb, alpha = color[1:7].upper(), color[7:9]
    if dark:
        if rgb == "000000" and alpha:  # dark tints read as nothing on dark glass
            return f"#FFFFFF{round(int(alpha, 16) * 0.6):02X}"
        return color
    if rgb == "FFFFFF" and alpha:
        return f"#000000{round(int(alpha, 16) * 0.7):02X}"
    if not alpha and rgb in LIGHT_SOLIDS:
        return LIGHT_SOLIDS[rgb]
    return color


def themed(shapes, dark):
    """Sky's shapes (white on a colored sky) restyled for Fenn's glass: text
    in the theme's text colors, white tints dark in light mode."""
    out = []
    for sh in shapes:
        sh = dict(sh)
        if sh.get("type") == "text":
            c = sh.get("color")
            if c in TEXT_TONES:
                sh["color"] = TEXT_TONES[c]
            elif c is None:
                sh["color"] = "text"
        else:
            for key in ("fill", "stroke", "color"):
                c = sh.get(key)
                if isinstance(c, str) and c.startswith("#") and len(c) in (7, 9):
                    sh[key] = _tone(c, dark)
        out.append(sh)
    return out
