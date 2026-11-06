"""Flat, multicolor weather symbols in the style of the system weather sets
(white clouds, yellow sun, blue rain), drawn from Fenn canvas shapes so they
stay sharp at any size.

draw(name, x, y, s, bg) returns the shapes of one symbol centered on (x, y)
in an s-point box. bg is the color behind it: overlapping parts get a thin
cut-out ring in that color (a sun behind a cloud, the moon's crescent). With
bg=None the parts simply overlap.

resolve(code, day, temp_c, wind_kmh) picks the symbol for a WMO weather code,
and turns calm skies into "windy", "hot" or "ice", and snow into "blowing
snow" or "blizzard", when the wind or the temperature says so."""

import math

import fenn

WHITE = "#FFFFFF"
CLOUD = "#F2F4F7"
GREY = "#C9CFD8"
DARK = "#AEB6C2"
YELLOW = "#FFD60A"
BLUE = "#40C8FF"
RED = "#FF453A"
ICE = "#64D2FF"

NAMES = [
    "sun", "moon", "cloud-sun", "cloud-moon", "cloud", "clouds", "fog", "haze", "wind",
    "drizzle", "rain", "heavy-rain", "showers-sun", "showers-moon", "sleet", "hail",
    "flurry", "snow", "blizzard", "blowing-snow", "thunder", "thunder-rain", "thunder-sun",
    "thunder-moon", "hot", "ice", "sunrise", "sunset", "none",
]

LABELS = {"wind": "Windy", "hot": "Hot", "ice": "Frigid", "blowing-snow": "Blowing snow", "blizzard": "Blizzard"}

_BY_CODE = {
    0: "clear", 1: "clear", 2: "partly", 3: "clouds", 45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "rain", 56: "sleet", 57: "sleet",
    61: "rain", 63: "rain", 65: "heavy-rain", 66: "sleet", 67: "sleet",
    71: "flurry", 73: "snow", 75: "blizzard", 77: "snow",
    80: "showers", 81: "showers", 82: "heavy-rain", 85: "flurry", 86: "blizzard",
    95: "thunder-rain", 96: "thunder", 99: "thunder",
}


def resolve(code, day=True, temp_c=None, wind_kmh=None):
    base = _BY_CODE.get(int(code or 0), "cloud")
    windy = wind_kmh is not None and wind_kmh >= 39
    if base in ("clear", "partly") and temp_c is not None:
        if temp_c >= 35:
            return "hot"
        if temp_c <= -15:
            return "ice"
    if base in ("clear", "partly", "clouds") and windy:
        return "wind"
    if base in ("flurry", "snow") and windy:
        return "blowing-snow"
    if base == "snow" and wind_kmh is not None and wind_kmh >= 56:
        return "blizzard"
    if base == "clear":
        return "sun" if day else "moon"
    if base == "partly":
        return "cloud-sun" if day else "cloud-moon"
    if base == "showers":
        return "showers-sun" if day else "showers-moon"
    return base


# ---- building blocks

def _rline(a, b, w, color):
    """A line with round ends."""
    return [fenn.line([a, b], color=color, width=w),
            fenn.circle(a[0], a[1], w / 2, fill=color), fenn.circle(b[0], b[1], w / 2, fill=color)]


def _cloud_shapes(cx, cy, w, color, grow=0.0):
    """A cloud w wide, its box centered on (cx, cy): a pill-ended base and
    three round puffs, all grown by `grow` (for the cut-out ring)."""
    g = grow
    base_h = 0.36 * w
    return [
        fenn.rect(cx - 0.5 * w - g, cy - 0.02 * w - g, w + 2 * g, base_h + 2 * g, fill=color, radius=base_h / 2 + g),
        fenn.circle(cx - 0.21 * w, cy + 0.02 * w, 0.21 * w + g, fill=color),
        fenn.circle(cx + 0.07 * w, cy - 0.07 * w, 0.27 * w + g, fill=color),
        fenn.circle(cx + 0.31 * w, cy + 0.08 * w, 0.17 * w + g, fill=color),
    ]


def cloud(cx, cy, w, color=CLOUD, bg=None, ring=1.6):
    out = _cloud_shapes(cx, cy, w, bg, ring) if bg else []
    return out + _cloud_shapes(cx, cy, w, color)


def sun(cx, cy, r, color=YELLOW, rays=True, ray_w=None):
    out = [fenn.circle(cx, cy, r, fill=color)]
    if rays:
        rw = ray_w or max(1.3, r * 0.3)
        for k in range(8):
            a = math.pi / 4 * k
            c, s = math.cos(a), math.sin(a)
            out += _rline((cx + c * r * 1.55, cy + s * r * 1.55), (cx + c * r * 2.05, cy + s * r * 2.05), rw, color)
    return out


def moon(cx, cy, r, color=WHITE, bg=None):
    if not bg:
        return [fenn.glyph(cx, cy, "moon", r * 2.3, color, True)]
    return [fenn.circle(cx, cy, r, fill=color),
            fenn.circle(cx + r * 0.62, cy - r * 0.48, r * 0.76, fill=bg)]


def sparkle(cx, cy, s, color=WHITE):
    """A four-pointed star (two thin diamonds)."""
    k = s * 0.24
    return [fenn.polygon([(cx, cy - s), (cx + k, cy), (cx, cy + s), (cx - k, cy)], fill=color),
            fenn.polygon([(cx - s, cy), (cx, cy - k), (cx + s, cy), (cx, cy + k)], fill=color)]


def flake(cx, cy, r, w, color=WHITE, branches=True):
    out = []
    for k in range(3):
        a = math.pi / 2 + k * math.pi / 3
        dx, dy = math.cos(a) * r, math.sin(a) * r
        out += _rline((cx - dx, cy - dy), (cx + dx, cy + dy), w, color)
        if branches:
            for sign in (-1, 1):
                tx, ty = cx + dx * 0.6 * sign, cy + dy * 0.6 * sign
                for turn in (-0.6, 0.6):
                    b = a + (0 if sign > 0 else math.pi) + turn
                    out.append(fenn.line([(tx, ty), (tx + math.cos(b) * r * 0.36, ty + math.sin(b) * r * 0.36)],
                                         color=color, width=w * 0.8))
    return out


def bolt(cx, top, s, color=YELLOW, bg=None):
    """A lightning bolt from `top` down, about 0.5 s tall (two triangles)."""
    def tri(grow):
        g = grow
        return [fenn.polygon([(cx + 0.13 * s + g, top - g), (cx - 0.15 * s - g, top + 0.28 * s + g * 0.5), (cx + 0.04 * s + g, top + 0.28 * s + g * 0.5)], fill=None),
                fenn.polygon([(cx - 0.04 * s - g, top + 0.21 * s - g * 0.5), (cx + 0.15 * s + g, top + 0.21 * s - g * 0.5), (cx - 0.11 * s - g, top + 0.52 * s + g)], fill=None)]
    out = []
    if bg:
        for p in tri(1.4):
            p["fill"] = bg
            out.append(p)
    for p in tri(0):
        p["fill"] = color
        out.append(p)
    return out


def drops(cx, top, s, n, length, width, color=BLUE, rows=1):
    out = []
    gap = s * (0.2 if n > 3 else 0.24)
    for row in range(rows):
        y0 = top + row * (length + s * 0.07)
        shift = gap / 2 if row % 2 else 0
        x0 = cx - gap * (n - 1) / 2 + shift
        for i in range(n - (1 if row % 2 else 0)):
            x = x0 + i * gap
            out += _rline((x + length * 0.32, y0), (x - length * 0.32, y0 + length), width, color)
    return out


def wind_lines(cx, cy, s, color=WHITE, w=None):
    w = w or max(1.4, s * 0.075)
    out = []
    # top line, curling up at its right end
    y1, x1 = cy - s * 0.17, cx + s * 0.12
    out += _rline((cx - s * 0.42, y1), (x1, y1), w, color)
    out.append(fenn.arc(x1, y1 - s * 0.1, s * 0.1, 180, -70, color=color, width=w))
    # middle line, the longest, curling down
    y2, x2 = cy + s * 0.04, cx + s * 0.26
    out += _rline((cx - s * 0.46, y2), (x2, y2), w, color)
    out.append(fenn.arc(x2, y2 + s * 0.11, s * 0.11, 0, 250, color=color, width=w))
    # short bottom line
    out += _rline((cx - s * 0.36, cy + s * 0.24), (cx - s * 0.02, cy + s * 0.24), w, color)
    return out


def thermometer(cx, cy, s, liquid, bg=None):
    stem_w = s * 0.17
    top, bulb_y, bulb_r = cy - s * 0.4, cy + s * 0.25, s * 0.15
    out = [fenn.rect(cx - stem_w / 2, top, stem_w, s * 0.6, fill=WHITE, radius=stem_w / 2),
           fenn.circle(cx, bulb_y, bulb_r, fill=WHITE),
           fenn.rect(cx - stem_w * 0.22, cy - s * 0.12, stem_w * 0.44, s * 0.34, fill=liquid, radius=stem_w * 0.22),
           fenn.circle(cx, bulb_y, bulb_r * 0.62, fill=liquid)]
    return out


def horizon_sun(cx, cy, s, rising, bg=None):
    """Half a sun on the horizon with an arrow above it."""
    r = s * 0.2
    base = cy + s * 0.2
    pts = [(cx + math.cos(math.pi + math.pi * i / 16) * r, base + math.sin(math.pi + math.pi * i / 16) * r) for i in range(17)]
    out = [fenn.polygon(pts, fill=YELLOW)]
    w = max(1.3, s * 0.07)
    for a in (-150, -120, -60, -30):
        t = math.radians(a)
        out += _rline((cx + math.cos(t) * r * 1.45, base + math.sin(t) * r * 1.45),
                      (cx + math.cos(t) * r * 1.9, base + math.sin(t) * r * 1.9), w, YELLOW)
    out += _rline((cx - s * 0.42, base + w), (cx + s * 0.42, base + w), w, WHITE)
    ay0, ay1 = cy - s * 0.42, cy - s * 0.16
    out += _rline((cx, ay0), (cx, ay1), w, WHITE)
    tip, back = (ay0, ay0 + s * 0.1) if rising else (ay1, ay1 - s * 0.1)
    out += _rline((cx - s * 0.1, back), (cx, tip), w, WHITE) + _rline((cx + s * 0.1, back), (cx, tip), w, WHITE)
    return out


# ---- the symbols

def draw(name, x, y, s, bg=None):
    w = max(1.4, s * 0.075)  # line width for rain, snow and wind
    if name == "sun":
        return sun(x, y, s * 0.2)
    if name == "moon":
        return moon(x - s * 0.04, y + s * 0.04, s * 0.32, WHITE, bg) + sparkle(x + s * 0.3, y - s * 0.3, s * 0.11)
    if name in ("cloud-sun", "showers-sun", "thunder-sun"):
        out = sun(x - s * 0.14, y - s * 0.18, s * 0.15)
        cy, cw = (y + s * 0.13, s * 0.78) if name == "cloud-sun" else (y - s * 0.02, s * 0.74)
        out += cloud(x + s * 0.09, cy, cw, CLOUD, bg)
        if name == "showers-sun":
            out += drops(x + s * 0.09, cy + s * 0.32, s, 3, s * 0.12, w)
        elif name == "thunder-sun":
            out += bolt(x + s * 0.08, cy + s * 0.12, s, YELLOW, bg)
        return out
    if name in ("cloud-moon", "showers-moon", "thunder-moon"):
        out = moon(x + s * 0.2, y - s * 0.22, s * 0.21, WHITE, bg) + sparkle(x - s * 0.22, y - s * 0.34, s * 0.075)
        cy, cw = (y + s * 0.13, s * 0.78) if name == "cloud-moon" else (y - s * 0.02, s * 0.74)
        out += cloud(x - s * 0.08, cy + s * 0.02, cw, CLOUD, bg)
        if name == "showers-moon":
            out += drops(x - s * 0.06, cy + s * 0.32, s, 3, s * 0.12, w)
        elif name == "thunder-moon":
            out += bolt(x - s * 0.07, cy + s * 0.12, s, YELLOW, bg)
        return out
    if name == "cloud":
        return cloud(x, y + s * 0.04, s * 0.9, CLOUD)
    if name == "clouds":
        return cloud(x + s * 0.12, y - s * 0.1, s * 0.66, DARK) + cloud(x - s * 0.06, y + s * 0.1, s * 0.78, CLOUD, bg)
    if name == "wind":
        return wind_lines(x, y, s)
    if name == "hot":
        return sun(x - s * 0.2, y - s * 0.1, s * 0.11) + thermometer(x + s * 0.14, y, s, RED)
    if name == "ice":
        return flake(x - s * 0.2, y - s * 0.12, s * 0.16, w * 0.8) + thermometer(x + s * 0.14, y, s, ICE)
    if name == "blowing-snow":
        return flake(x - s * 0.24, y - s * 0.2, s * 0.17, w * 0.8) + wind_lines(x + s * 0.08, y + s * 0.08, s * 0.72)
    if name == "haze":
        return horizon_sun(x, y - s * 0.12, s * 0.9, True)[:5] + [
            *_rline((x - s * 0.42, y + s * 0.18), (x + s * 0.42, y + s * 0.18), w, WHITE),
            *_rline((x - s * 0.32, y + s * 0.32), (x + s * 0.32, y + s * 0.32), w, WHITE)]
    if name in ("sunrise", "sunset"):
        return horizon_sun(x, y, s, name == "sunrise")
    if name == "flurry":
        return flake(x, y, s * 0.4, w * 1.05)
    if name == "none":
        return [fenn.label(x, y, "– – –", size=s * 0.5, color=WHITE, anchor="center")]

    # a cloud with something falling out of it
    cy = y - s * 0.12
    cw = s * 0.86
    grey = name in ("heavy-rain", "thunder", "thunder-rain", "hail", "sleet", "blizzard")
    out = cloud(x, cy, cw, GREY if grey else CLOUD)
    below = cy + cw * 0.36 + s * 0.05
    if name == "fog":
        out += _rline((x - s * 0.36, below + s * 0.02), (x + s * 0.36, below + s * 0.02), w, CLOUD)
        out += _rline((x - s * 0.26, below + s * 0.15), (x + s * 0.26, below + s * 0.15), w, CLOUD)
    elif name == "drizzle":
        out += drops(x, below + s * 0.02, s, 4, s * 0.03, w, rows=2)
    elif name == "rain":
        out += drops(x, below, s, 3, s * 0.15, w)
    elif name == "heavy-rain":
        out += drops(x, below, s, 4, s * 0.22, w)
    elif name == "sleet":
        out += flake(x - s * 0.1, below + s * 0.11, s * 0.1, w * 0.7, branches=False)
        out += drops(x + s * 0.14, below, s, 2, s * 0.15, w)
    elif name == "hail":
        for k, (dx, dy) in enumerate(((-0.22, 0.05), (0.0, 0.05), (0.22, 0.05), (-0.11, 0.2), (0.11, 0.2))):
            out.append(fenn.circle(x + dx * s, below + dy * s, s * 0.05, fill=WHITE))
    elif name in ("snow", "blizzard"):
        spots = ((-0.22, 0.07), (0.0, 0.07), (0.22, 0.07)) if name == "snow" else \
            ((-0.26, 0.05), (-0.08, 0.05), (0.1, 0.05), (0.28, 0.05), (-0.17, 0.21), (0.01, 0.21), (0.19, 0.21))
        for dx, dy in spots:
            out += flake(x + dx * s, below + dy * s, s * 0.065, w * 0.6, branches=False)
    elif name in ("thunder", "thunder-rain"):
        out += bolt(x, cy + s * 0.2, s, YELLOW, bg)
        if name == "thunder-rain":
            out += drops(x - s * 0.26, below, s, 1, s * 0.15, w) + drops(x + s * 0.26, below, s, 1, s * 0.15, w)
    return out
