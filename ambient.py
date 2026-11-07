"""The sky behind the Sky look's header: soft clouds that drift with the
wind, the sun with its glow and halo, sunrise and sunset light, stars and
the moon at night, rain with drops on the glass, snow, fog and lightning.
It changes with the weather code, cloud cover, wind and time of day, and
fades out before the first card.

scene(...) describes what to draw from the forecast; draw(scene, t) returns
the canvas shapes at time t (seconds), so the page can redraw it every frame
for the animation, or once for a still picture."""

import math
import random

import fenn

FADE_FROM, FADE_TO = 108, 162   # the ambient fades out between these heights
TOP = 168                       # nothing is drawn below this
CORNER = 18                     # the card's rounded corners


def _a(color, alpha):
    """#RRGGBB plus an alpha from 0..1 as #RRGGBBAA."""
    return f"{color}{max(0, min(255, round(alpha * 255))):02X}"


def scene(code, cloud_cover, is_day, wind_kmh, now, sunrise, sunset, seed, moon=None):
    """What the sky looks like. moon: (phase, altitude in degrees) or None."""
    code = int(code or 0)
    cc = cloud_cover if cloud_cover is not None else {0: 0, 1: 20, 2: 50, 3: 95}.get(code, 90)
    part = "day" if is_day else "night"
    if sunrise and sunset:
        if abs((now - sunrise).total_seconds()) < 3000:
            part = "dawn"
        elif abs((now - sunset).total_seconds()) < 3000:
            part = "dusk"
    rain = {51: 1, 53: 1, 55: 2, 56: 1, 57: 2, 61: 2, 63: 3, 65: 4, 66: 2, 67: 3,
            80: 2, 81: 3, 82: 4, 95: 4, 96: 4, 99: 4}.get(code, 0)
    snow = {71: 1, 73: 2, 75: 3, 77: 1, 85: 2, 86: 3}.get(code, 0)
    if code in (56, 57, 66, 67):  # freezing: a little snow in the rain
        snow = 1
    frac = None
    if sunrise and sunset and sunset > sunrise:
        frac = (now - sunrise).total_seconds() / (sunset - sunrise).total_seconds()
    heavy_sky = code in (3, 45, 48) or rain >= 2 or snow >= 2 or code >= 95
    return {
        "code": code, "cc": max(cc, 85 if heavy_sky else 0), "part": part, "rain": rain, "snow": snow,
        "fog": code in (45, 48), "storm": code >= 95, "wind": wind_kmh or 0, "frac": frac,
        "seed": seed, "moon": moon,
        # how often to redraw: falling things need more frames than drifting clouds
        "fps": 15 if rain or snow else 8,
    }


# ---- clouds

def _clouds(sc, W):
    """The clouds for this scene (puffs relative to each cloud); the same
    every frame, only their position moves."""
    rng = random.Random(sc["seed"])
    cc = sc["cc"]
    out = []
    count = 0 if cc < 8 else min(7, 1 + round(cc / 16))
    for n in range(count):
        far = rng.random() < 0.35
        width = rng.uniform(150, 260) * (0.7 if far else 1.0)
        height = width * rng.uniform(0.3, 0.42)
        puffs = []
        k = rng.randint(4, 6)
        for i in range(k):
            u = (i + rng.uniform(-0.25, 0.25)) / (k - 1)
            bulge = math.sin(math.pi * min(1, max(0, u)))
            r = height * (0.38 + 0.4 * bulge) * rng.uniform(0.9, 1.1)
            puffs.append((width * (u - 0.5), -bulge * height * 0.3 + rng.uniform(-3, 3), r))
        out.append({"x": rng.uniform(-150, W + 150), "y": rng.uniform(40, 100) if not far else rng.uniform(30, 74),
                    "puffs": puffs, "far": far, "alpha": rng.uniform(0.7, 1.0) * (0.6 if far else 1.0),
                    "speed": rng.uniform(0.7, 1.3) * (0.5 if far else 1.0)})
    return out


def _cloud_colors(sc):
    part = sc["part"]
    if sc["storm"]:
        return "#5D6573", "#8A93A1", 0.85
    if sc["rain"] or sc["snow"] or sc["code"] in (3, 45, 48):
        return ("#3A4150", "#59616F", 0.7) if part == "night" else ("#A9B3C1", "#DDE3EB", 0.75)
    if part == "night":
        return "#5F6D8C", "#8C9AB8", 0.55
    if part in ("dawn", "dusk"):
        return "#A27E9E", "#FFC9B3", 0.8
    return "#E3E9F2", "#FFFFFF", 0.85


def _band(x, y, w, h, color, W, radius=None):
    """A wide rect, trimmed so it stays inside the card's rounded top corners."""
    if y < CORNER:
        mid = max(y, 0) + min(h, CORNER) / 2
        inset = CORNER - math.sqrt(max(0.0, CORNER ** 2 - (CORNER - min(mid, CORNER)) ** 2))
        right = min(x + w, W - inset)
        x = max(x, inset)
        w = right - x
    if w <= 0 or h <= 0:
        return None
    return fenn.rect(x, max(y, 0), w, h, fill=color, radius=radius)


def _outside_corner(px, py, W):
    """Is this point in a top corner square but outside the card's curve?"""
    if py >= CORNER or py < 0:
        return False
    if px < CORNER:
        return math.hypot(px - CORNER, py - CORNER) > CORNER
    if px > W - CORNER:
        return math.hypot(px - (W - CORNER), py - CORNER) > CORNER
    return False


def _room(x, y, W):
    """How far a circle centered at (x, y) can reach before it covers the
    part of a top corner square that lies outside the card's curve."""
    R = CORNER
    if x > W / 2:
        x = W - x  # the right corner mirrors the left one
    if y >= R + W:  # far below: no limit
        return float("inf")
    d = math.hypot(x - R, y - R)
    if x <= R and y <= R and d <= R:
        best = R - d  # inside the curve, in the corner square
    else:
        best = float("inf")
    if 0 <= x <= R and 0 <= y <= R and d > R:
        return 0.0  # the center itself is outside the curve
    # the corner square's two outer edges (part of the outside area)
    best = min(best, math.hypot(max(0.0, x), max(0.0, y - R) if y > R else 0.0) if x >= 0 else 0.0)
    best = min(best, math.hypot(max(0.0, x - R) if x > R else 0.0, max(0.0, y)))
    return best


def _fit_circles(shapes, W):
    """Shrink circles that would poke past the card's rounded top corners
    (the canvas itself only clips to a square)."""
    out = []
    for sh in shapes:
        if sh.get("type") == "circle" and sh["y"] - sh["r"] < CORNER:
            room = _room(sh["x"], sh["y"], W)
            if sh["r"] > room:
                if room < 0.8:
                    continue
                sh = dict(sh, r=room)
        out.append(sh)
    return out


def _corner_safe(x, y, r, W):
    """Keep round shapes out of the card's rounded top corners."""
    if (x - r < CORNER or x + r > W - CORNER) and y - r < CORNER:
        y = max(y, CORNER + r * 0.6)
    return y


LAYERS = [(1.45, 0.035), (1.3, 0.04), (1.16, 0.05), (1.03, 0.06), (0.9, 0.07), (0.76, 0.07)]


def _draw_overcast(sc, W, t, out):
    """A cloud ceiling: a soft grey veil from the top that thins out, with
    slow lighter and darker patches."""
    base, light, strength = _cloud_colors(sc)
    k = (sc["cc"] - 70) / 30
    if k <= 0:
        return
    # stacked rounded rects from the top: their corners match the card's,
    # and together they fade from strong at the top to nothing at FADE_TO
    n = 28
    for i in range(n):
        h = FADE_TO * (1 - (i / n) ** (1 / 1.4))
        if h > 2:
            out.append(fenn.rect(0, 0, W, h, fill=_a(base, k * strength * 0.55 / n * 1.25), radius=CORNER))
    rng = random.Random(sc["seed"] + 3)
    drift = 2 + sc["wind"] * 0.15
    for i in range(10):
        x0, yy, r = rng.uniform(0, W + 300), rng.uniform(10, 90), rng.uniform(50, 90)
        x = (x0 + drift * t) % (W + 300) - 150
        col = light if i % 2 else base
        for f, al in ((1.3, 0.03), (1.0, 0.04), (0.7, 0.04)):
            rr = min(r * f, TOP - 6 - yy)
            cy = _corner_safe(x, yy, rr, W)
            if rr > 4:
                out.append(fenn.circle(x, cy, rr, fill=_a(col, al * k)))


def _draw_clouds(sc, W, t, out):
    _draw_overcast(sc, W, t, out)
    base, light, strength = _cloud_colors(sc)
    drift = 3 + sc["wind"] * 0.22  # points per second
    span = W + 360
    for cl in sc["_clouds"]:
        x0 = (cl["x"] + drift * cl["speed"] * t) % span - 180
        a = cl["alpha"] * strength
        # body: soft layers for every puff, outermost first
        for f, al in LAYERS:
            for dx, dy, r in cl["puffs"]:
                x, y = x0 + dx, cl["y"] + dy
                rr = r * f
                if x + rr < 0 or x - rr > W:
                    continue
                cy = _corner_safe(x, y, rr, W)
                if cy + rr > TOP:
                    rr = TOP - cy
                if rr > 2:
                    out.append(fenn.circle(x, cy, rr, fill=_a(base, a * al)))
        # light on the tops
        for dx, dy, r in cl["puffs"]:
            x, y = x0 + dx, cl["y"] + dy - r * 0.22
            for f, al in ((0.72, 0.08), (0.5, 0.1)):
                rr = r * f
                if x + rr < 0 or x - rr > W:
                    continue
                cy = _corner_safe(x, y, rr, W)
                out.append(fenn.circle(x, cy, rr, fill=_a(light, a * al)))


# ---- sun, stars, moon

def _draw_sun(sc, W, t, out):
    part, frac = sc["part"], sc["frac"]
    if part == "night" or sc["cc"] >= 85 or frac is None:
        return
    frac = min(1.05, max(-0.05, frac))
    # left at sunrise, high (mostly above the card) at noon, right at sunset
    sx = W * (0.1 + 0.8 * frac)
    sy = 112 - math.sin(math.pi * min(1, max(0, frac))) * 122
    low = part in ("dawn", "dusk")
    tint = "#FFB36B" if low else "#FFF4D6"
    veil = 1 - sc["cc"] / 110
    # a smooth glow: many faint discs, denser toward the middle, kept clear of
    # the card's rounded top corners and of the cards below
    reach = min(math.hypot(sx - 9, sy - 9), math.hypot(W - 9 - sx, sy - 9), 210)
    n = 72
    for k in range(n, 0, -1):
        r = reach * (k / n) ** 1.9
        r = min(r, TOP - 4 - sy)
        if r > 2:
            out.append(fenn.circle(sx, sy, r, fill=_a(tint, 0.0085 * veil)))
    if low:  # warm light along the horizon
        for k in range(12):
            out.append(fenn.rect(0, 100 + k * 5, W, 5, fill=_a("#FF9A6B", 0.012 + 0.006 * k)))
    out.append(fenn.circle(sx, sy, 24, fill=_a("#FFC58A" if low else "#FFFFFF", 0.22 * veil)))
    out.append(fenn.circle(sx, sy, 15, fill=_a("#FFD9A6" if low else "#FFFDF2", 0.92 * veil)))
    if not low and sc["cc"] < 40 and reach > 120 and sy + 112 < TOP:
        out.append(fenn.circle(sx, sy, 112, stroke=_a("#FFFFFF", 0.05), width=14))  # halo
    if not low and sc["cc"] < 40:
        tx, ty = W * 0.5 + (W * 0.5 - sx) * 0.6, 150
        for f, r, al in ((0.45, 11, 0.06), (0.7, 6, 0.08), (0.92, 16, 0.045)):  # lens flares
            fx, fy = sx + (tx - sx) * f, sy + (ty - sy) * f
            if fy + r < FADE_TO and fy - r > 0:
                out.append(fenn.circle(fx, fy, r, fill=_a("#FFFFFF", al)))


def _draw_stars(sc, W, t, out):
    if sc["part"] != "night" or sc["cc"] >= 75:
        return
    rng = random.Random(sc["seed"] + 7)
    n = int(70 * (1 - sc["cc"] / 85))
    for i in range(n):
        x, y = rng.uniform(CORNER, W - CORNER), rng.uniform(10, 140)
        size = rng.choice((0.6, 0.8, 0.8, 1.0, 1.3, 1.7))
        tw = 0.65 + 0.35 * math.sin(t * rng.uniform(0.8, 2.6) + rng.uniform(0, 6.3))
        out.append(fenn.circle(x, y, size, fill=_a("#FFFFFF", rng.uniform(0.35, 0.9) * tw)))


def _draw_moon(sc, W, t, out):
    moon = sc["moon"]
    if sc["part"] not in ("night", "dusk") or not moon or moon[1] <= 0 or sc["cc"] >= 85:
        return
    phase, alt = moon
    mx, my, r = W * 0.84, 62 - min(alt, 60) * 0.4, 13
    for k in range(6, 0, -1):
        out.append(fenn.circle(mx, my, r * (1 + k * 0.9), fill=_a("#DCE6FF", 0.025)))
    sc["_moon_fn"](out, mx, my, r, phase)


# ---- falling things

def _draw_rain(sc, W, t, out):
    level = sc["rain"]
    if not level:
        return
    rng = random.Random(sc["seed"] + 11)
    n = [0, 34, 60, 95, 140][level]
    slant = 0.12 + min(sc["wind"], 60) / 160
    span = TOP + 30
    for i in range(n):
        # every random number first: a skipped drop must not shift the others' numbers
        x0, y0 = rng.uniform(-20, W + 40), rng.uniform(0, span)
        length = rng.uniform(9, 17) * (1.2 if level >= 3 else 1)
        speed = rng.uniform(380, 520)
        alpha = rng.uniform(0.18, 0.38)
        y = (y0 + speed * t) % span - 20
        x = x0 - slant * y
        y1 = min(y + length, TOP - 4)
        if y1 <= max(y, 2) or x < 2 or x > W - 2:
            continue
        ys = max(y, CORNER if (x < CORNER or x > W - CORNER) else 2)
        out.append(fenn.line([(x, ys), (x - slant * (y1 - ys), y1)], color=_a("#FFFFFF", alpha), width=1.1))


def _draw_drops(sc, W, t, out):
    """Raindrops on the glass; a few slide down slowly."""
    if sc["rain"] < 2 and not sc["storm"]:
        return
    rng = random.Random(sc["seed"] + 23)
    for i in range(18):
        x, y0, r = rng.uniform(26, W - 26), rng.uniform(26, 130), rng.uniform(1.6, 4.2)
        slide = rng.random() < 0.3
        y = y0 + ((t * rng.uniform(6, 14)) % 90 if slide else 0)
        if y + r > FADE_TO:
            continue
        out.append(fenn.circle(x, y, r, fill=_a("#FFFFFF", 0.08), stroke=_a("#FFFFFF", 0.3), width=0.8))
        out.append(fenn.circle(x - r * 0.35, y - r * 0.35, max(0.6, r * 0.3), fill=_a("#FFFFFF", 0.75)))
        if slide and r > 2.5:
            out.append(fenn.line([(x, y - r), (x, max(y0, y - r - 14))], color=_a("#FFFFFF", 0.12), width=r * 0.6))


def _draw_snow(sc, W, t, out):
    level = sc["snow"]
    if not level:
        return
    rng = random.Random(sc["seed"] + 31)
    n = [0, 55, 95, 150][level]
    span = TOP + 10
    drift = sc["wind"] * 0.25
    for i in range(n):
        # every random number first: a skipped flake must not shift the others' numbers
        # (that made flakes jump to new places from one frame to the next)
        r = rng.choice((0.9, 1.2, 1.5, 1.8, 2.3, 2.8))
        x0, y0 = rng.uniform(0, W), rng.uniform(0, span)
        sway_rate, sway_phase, sway = rng.uniform(0.6, 1.4), rng.uniform(0, 6.3), rng.uniform(4, 12)
        alpha = rng.uniform(0.55, 0.9)
        speed = 14 + r * 11
        y = (y0 + speed * t) % span - 5
        x = (x0 + drift * t + math.sin(t * sway_rate + sway_phase) * sway) % W
        if y - r < 2 or y + r > TOP or ((x < CORNER or x > W - CORNER) and y < CORNER):
            continue
        out.append(fenn.circle(x, y, r, fill=_a("#FFFFFF", alpha)))


def _draw_fog(sc, W, t, out):
    if not sc["fog"]:
        return
    rng = random.Random(sc["seed"] + 41)
    for i in range(7):
        h = rng.uniform(18, 36)
        y = rng.uniform(40, 140)
        off = math.sin(t * rng.uniform(0.05, 0.12) + i) * 40
        al = rng.uniform(0.012, 0.02)
        for f in (1.0, 0.8, 0.6, 0.42, 0.26):  # soft top and bottom
            hh = h * f * 2
            out.append(_band(-60 + off, y - hh / 2, W + 120, hh, _a("#FFFFFF", al), W, hh / 2))


def _draw_lightning(sc, W, t, out):
    if not sc["storm"]:
        return
    period = 9.0
    k = int(t // period)
    ph = t - k * period
    if not (ph < 0.14 or 0.3 < ph < 0.38):
        return
    rng = random.Random(sc["seed"] * 31 + k)
    flash = _a("#FFFFFF", 0.16 if ph < 0.14 else 0.08)
    out.append(fenn.rect(0, 0, W, CORNER * 2, fill=flash, radius=CORNER))
    out.append(fenn.rect(0, CORNER * 2, W, TOP - CORNER * 2, fill=flash))
    x, y = rng.uniform(W * 0.2, W * 0.8), 24
    pts = [(x, y)]
    while y < 140:
        y += rng.uniform(12, 24)
        x += rng.uniform(-22, 22)
        pts.append((x, min(y, 150)))
    out.append(fenn.line(pts, color=_a("#CFE0FF", 0.35), width=6))
    out.append(fenn.line(pts, color=_a("#FFFFFF", 0.95), width=1.8))


def draw(sc, W, t, moon_fn=None):
    """Every ambient shape at time t."""
    if "_clouds" not in sc:
        sc["_clouds"] = _clouds(sc, W)
    sc["_moon_fn"] = moon_fn or (lambda out, x, y, r, phase: out.append(fenn.circle(x, y, r, fill="#F2EFE6")))
    out = []
    _draw_sun(sc, W, t, out)
    _draw_stars(sc, W, t, out)
    _draw_moon(sc, W, t, out)
    _draw_fog(sc, W, t, out)
    _draw_clouds(sc, W, t, out)
    _draw_lightning(sc, W, t, out)
    _draw_rain(sc, W, t, out)
    _draw_snow(sc, W, t, out)
    _draw_drops(sc, W, t, out)
    return _fit_circles([x for x in out if x is not None], W)


def scale_alpha(shapes, k, fade_mix=0.0):
    """Multiply every shape's opacity by k. With fade_mix > 0, shapes also
    fade out by height between FADE_FROM and FADE_TO (used when the card
    behind is see-through, so a solid cover band would show)."""
    if k >= 0.999 and fade_mix <= 0.001:
        return shapes
    out = []
    for sh in shapes:
        kk = k
        if fade_mix > 0:
            t = sh.get("type")
            if t == "circle" or t == "text":
                y = sh["y"]
            elif t == "rect":
                y = sh["y"] + sh.get("h", 0) / 2
            elif t in ("line", "polygon"):
                pts = sh.get("points") or [[0, 0]]
                y = sum(p[1] for p in pts) / len(pts)
            else:
                y = 0
            a = min(1.0, max(0.0, (y - FADE_FROM) / (FADE_TO - FADE_FROM)))
            a = a * a * (3 - 2 * a)
            kk *= 1 - fade_mix * a
        if kk <= 0.004:
            continue
        sh = dict(sh)
        for key in ("fill", "stroke", "color"):
            c = sh.get(key)
            if isinstance(c, str) and c.startswith("#") and len(c) in (7, 9):
                alpha = int(c[7:9], 16) if len(c) == 9 else 255
                sh[key] = f"{c[:7]}{round(alpha * kk):02X}"
        out.append(sh)
    return out


def fade(W, top_color_at):
    """Covers the ambient smoothly: bands of the card's own color going from
    clear to solid, then solid down to the first card."""
    out = []
    y = FADE_FROM
    step = 3
    while y < TOP + 6:
        a = min(1.0, max(0.0, (y - FADE_FROM) / (FADE_TO - FADE_FROM)))
        a = a * a * (3 - 2 * a)  # smoothstep
        out.append(fenn.rect(0, y, W, step, fill=_a(top_color_at(y + step / 2), a)))
        y += step
    return out
