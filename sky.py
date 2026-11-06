"""The "Sky" look: a scrolling dashboard on a sky-colored background (blue by
day, grey when cloudy or raining, warm at sunset, deep blue at night) with
glass cards: hourly forecast (conditions, rain, wind), 10-day forecast, rain
in the next two hours, air quality, wind, sunrise and sunset, moon, UV,
precipitation, feels like, humidity, visibility and pressure. Every card
opens a detail view with a chart; clicking the chart picks a point.

`m` is main.py: its settings, the Model (`m.model`), the clock helpers and
the view state. Everything is drawn on Fenn canvases (ui.Canvas), which
remember their clickable areas."""

import math
from datetime import datetime, timedelta

import ambient
import astro
import fenn
import symbols
import units as u
import wx
from ui import (BLUE, FAINT, LINE, SOFT, WHITE, Canvas, card, chart, fit, mix, pill, scale_color, tw, wrap)

P = 12  # outer padding inside the sky

SKIES = {
    "clear-day": ("#2F7FD6", "#5DA9EC"),
    "fair-day": ("#4A86C8", "#78A8D8"),
    "cloudy-day": ("#5F7186", "#8494A7"),
    "rain-day": ("#4B5968", "#6C7987"),
    "snow-day": ("#71849C", "#9DAEC2"),
    "storm-day": ("#353C49", "#565E6D"),
    "fog-day": ("#7D8792", "#A1A9B3"),
    "dusk": ("#33427A", "#C9806A"),
    "clear-night": ("#0A1631", "#1F3260"),
    "fair-night": ("#141E38", "#2C3B5E"),
    "cloudy-night": ("#202733", "#3A4352"),
    "rain-night": ("#1B222D", "#343E4C"),
    "snow-night": ("#2A3446", "#4A576C"),
    "storm-night": ("#15191F", "#30363F"),
    "fog-night": ("#2B3038", "#474D57"),
}


def sky_kind(code, day):
    base = wx.ICONS.get(int(code or 0), "cloudy")
    kind = {"clear": "clear", "mostly": "fair", "partly": "fair", "overcast": "cloudy", "cloudy": "cloudy",
            "fog": "fog", "drizzle": "rain", "rain": "rain", "heavy-rain": "rain", "showers": "rain",
            "sleet": "snow", "snow": "snow", "heavy-snow": "snow", "thunder": "storm", "hail": "storm"}[base]
    return f"{kind}-{'day' if day else 'night'}"


def sky_colors(M):
    kind = sky_kind(M.cur("weather_code"), M.is_day())
    if kind.startswith(("clear", "fair")):
        rise, sset = M.sun(M.today())
        now = M.now()
        if abs((now - sset).total_seconds()) < 2700 or abs((now - rise).total_seconds()) < 2700:
            kind = "dusk"
    return SKIES[kind]


def gradient_box(x, y, w, h, top, bottom, radius=18, steps=40):
    """Shapes for a rounded box with a vertical gradient: rounded caps and
    solid bands between them."""
    r = min(radius, h / 2)
    out = [fenn.rect(x, y, w, r * 2, fill=top, radius=r), fenn.rect(x, y + h - r * 2, w, r * 2, fill=bottom, radius=r)]
    band = (h - 2 * r) / steps
    for i in range(steps):
        out.append(fenn.rect(x, y + r + i * band, w, band + 0.6, fill=mix(top, bottom, (i + 0.5) / steps)))
    return out


BG = 1.0   # how opaque the sky background is (settings: Sky background)
FX = 1.0   # how strong the clouds, sun, stars, rain... are (settings: Sky effects)


def paint_sky(c, top, bottom, scene=None, t=0.0):
    """The gradient under everything on the canvas; with a scene, the
    ambient sky and its fade go between the gradient and the content. The
    layers are kept on the canvas so the animation can redraw just the sky."""
    if BG >= 0.999:
        base = gradient_box(0, 0, c.w, c.h, top, bottom)
    else:
        # see-through: one shape, since overlapping bands would show as strips
        base = [fenn.rect(0, 0, c.w, c.h, fill=f"{mix(top, bottom, 0.35)}{round(255 * BG):02X}", radius=18)]
    rim = [fenn.rect(0, 0, c.w, c.h, stroke="#FFFFFF1C", width=1, radius=18)]
    if scene is None:
        c.shapes = base + c.shapes + rim
        return
    h = c.h
    # solid: a band of the card's color covers the sky's bottom edge; see-through:
    # the sky's shapes fade out by themselves (see sky_shapes)
    cover = ambient.fade(c.w, lambda y: mix(top, bottom, (y - 18) / max(1, h - 36))) if BG >= 0.999 else []
    c.scene = scene
    c.below = base
    c.above = cover + c.shapes + rim
    c.shapes = base + sky_shapes(c, t) + c.above


def moon_shapes(out, x, y, r, phase, lat=0.0):
    tmp = Canvas(0)
    moon_disc(tmp, x, y, r, phase, lat)
    out += tmp.shapes


def sky_shapes(c, t):
    lat = c.scene.get("lat", 0.0)
    shapes = ambient.draw(c.scene, c.w, t, lambda out, x, y, r, ph: moon_shapes(out, x, y, r, ph, lat))
    return ambient.scale_alpha(shapes, FX, 0.0 if BG >= 0.999 else 1.0)


def ambient_scene(m):
    M = m.model
    place = m.settings["place"] or {"lat": 0, "lon": 0}
    now = M.now()
    rise, sset = M.sun(M.today())
    now_utc = M.to_utc(now)
    moon = None
    try:
        moon = (astro.moon_illumination(now_utc)[1],
                math.degrees(astro.moon_altitude(now_utc, place["lat"], place["lon"])))
    except (ValueError, KeyError):
        pass
    seed = int(now.strftime("%Y%m%d")) * 1000 + int(abs(place["lat"]) * 10) % 1000
    sc = ambient.scene(M.cur("weather_code"), M.cur("cloud_cover"), M.is_day(), M.cur("wind_speed_10m"),
                       now, rise, sset, seed, moon)
    sc["lat"] = place["lat"]
    return sc


def bg_at(top, bottom, y, h):
    """The card's color at a height, for the symbols' cut-out rings; none
    when the background is see-through (a ring would show as an outline)."""
    if BG < 0.999:
        return None
    return mix(top, bottom, (y - 18) / max(1, h - 36))


def sym(code, day, temp=None, wind=None):
    return symbols.resolve(code, day, temp, wind)


# ---- scales and words

UV_STOPS = [(0, "#3FC86B"), (3, "#F5D33B"), (6, "#F39A2E"), (8, "#E8453C"), (11, "#B04FD6")]
UV_NAMES = [(3, "Low"), (6, "Moderate"), (8, "High"), (11, "Very high"), (99, "Extreme")]

EU_AQI = [(20, "Good", "#50F0E6"), (40, "Fair", "#50CCAA"), (60, "Moderate", "#F0E641"), (80, "Poor", "#FF5050"),
          (100, "Very poor", "#960032"), (10_000, "Extremely poor", "#7D2181")]
US_AQI = [(50, "Good", "#00E400"), (100, "Moderate", "#FFFF00"), (150, "Unhealthy for sensitive groups", "#FF7E00"),
          (200, "Unhealthy", "#FF0000"), (300, "Very unhealthy", "#8F3F97"), (10_000, "Hazardous", "#7E0023")]
AQI_ADVICE = {
    "Good": "Air quality is good. Enjoy your usual outdoor activities.",
    "Fair": "Air quality is fair. Enjoy your usual outdoor activities.",
    "Moderate": "Sensitive people may want to cut down on long or heavy outdoor activity.",
    "Poor": "Consider cutting down on heavy outdoor activity, especially if you have symptoms.",
    "Very poor": "Cut down on heavy outdoor activity; sensitive people should avoid it.",
    "Extremely poor": "Avoid heavy outdoor activity; everyone may feel effects.",
    "Unhealthy for sensitive groups": "Sensitive groups should reduce long or heavy outdoor exertion.",
    "Unhealthy": "Everyone should reduce long or heavy outdoor exertion.",
    "Very unhealthy": "Everyone should avoid long or heavy outdoor exertion.",
    "Hazardous": "Everyone should avoid outdoor activity.",
}


def uv_name(v):
    return next(n for lim, n in UV_NAMES if (v or 0) < lim)


def aqi_info(v, standard):
    table = US_AQI if standard == "us" else EU_AQI
    for lim, name, color in table:
        if v <= lim:
            return name, color
    return table[-1][1], table[-1][2]


def aqi_stops(standard):
    if standard == "us":
        return [(0, "#00E400"), (50, "#FFFF00"), (100, "#FF7E00"), (150, "#FF0000"), (200, "#8F3F97"), (300, "#7E0023")], 300
    return [(0, "#50F0E6"), (20, "#50CCAA"), (40, "#F0E641"), (60, "#FF5050"), (80, "#960032"), (100, "#7D2181")], 100


def visibility_words(m):
    if m is None:
        return ""
    if m >= 20000:
        return "Perfectly clear view."
    if m >= 10000:
        return "Clear view."
    if m >= 4000:
        return "Slightly hazy."
    if m >= 1000:
        return "Hazy; distant things look blurred."
    return "Fog; visibility is very low."


def feels_words(actual, feels, wind, humidity):
    if actual is None or feels is None:
        return ""
    diff = feels - actual
    if abs(diff) < 1.5:
        return "Similar to the actual temperature."
    if diff < 0:
        return "Wind is making it feel colder." if (wind or 0) >= 8 else "It feels colder than the actual temperature."
    if (humidity or 0) >= 60:
        return "Humidity is making it feel warmer."
    return "It feels warmer than the actual temperature."


def dew_words(dp):
    if dp is None:
        return ""
    if dp < 10:
        return "the air feels dry."
    if dp < 16:
        return "the air feels comfortable."
    if dp < 20:
        return "the air feels humid."
    return "the air feels muggy and oppressive."


def gradient_bar(c, x, y, w, stops, vmax, value, h=5):
    n = 24
    for i in range(n):
        c.rect(x + w * i / n, y - h / 2, w / n + 0.6, h, fill=scale_color(stops, vmax * (i + 0.5) / n))
    c.circle(x, y, h / 2, fill=scale_color(stops, 0))
    c.circle(x + w, y, h / 2, fill=scale_color(stops, vmax))
    if value is not None:
        vx = x + w * min(1, max(0, value / vmax))
        c.circle(vx, y, h * 0.95, fill="#00000055")
        c.circle(vx, y, h * 0.8, fill=WHITE)


TEMP_STOPS = [(-15, "#6E6BFF"), (-5, "#5AA8FF"), (3, "#62D2F0"), (10, "#8EDC8A"), (17, "#E9D84A"),
              (24, "#F6B23C"), (31, "#F27B33"), (38, "#E8483A")]


def temp_bar(c, x, y, w, lo, hi, wmin, wmax, now=None):
    span = max(1e-6, wmax - wmin)
    c.rect(x, y - 2.5, w, 5, fill="#0000002E", radius=2.5)
    a = x + (lo - wmin) / span * w
    b = max(a + 5, x + (hi - wmin) / span * w)
    c.circle(a + 2.5, y, 2.5, fill=scale_color(TEMP_STOPS, lo))
    c.circle(b - 2.5, y, 2.5, fill=scale_color(TEMP_STOPS, hi))
    n = max(1, int((b - a - 5) // 4))
    step = (b - a - 5) / n
    for i in range(n):
        c.rect(a + 2.5 + i * step, y - 2.5, step + 0.5, 5, fill=scale_color(TEMP_STOPS, lo + (hi - lo) * (i + 0.5) / n))
    if now is not None and lo - 0.5 <= now <= hi + 0.5:
        nx = min(b - 3, max(a + 3, x + (now - wmin) / span * w))
        c.circle(nx, y, 4.2, fill="#00000040")
        c.circle(nx, y, 3.4, fill=WHITE)


def arrow(c, cx, cy, length, to_deg, color=WHITE, width=2):
    """An arrow pointing toward `to_deg` (0 = up/north, clockwise)."""
    a = math.radians(to_deg)
    dx, dy = math.sin(a), -math.cos(a)
    tail = (cx - dx * length / 2, cy - dy * length / 2)
    head = (cx + dx * length / 2, cy + dy * length / 2)
    c.line([tail, (head[0] - dx * 3, head[1] - dy * 3)], color, width)
    px, py = -dy, dx
    hl = max(4, length * 0.3)
    c.shapes.append(fenn.polygon([head, (head[0] - dx * hl + px * hl * 0.55, head[1] - dy * hl + py * hl * 0.55),
                                  (head[0] - dx * hl - px * hl * 0.55, head[1] - dy * hl - py * hl * 0.55)], fill=color))


def compass(c, cx, cy, r, direction, speed_text, unit_text):
    for k in range(72):
        a = math.radians(k * 5)
        long = k % 18 == 0
        r0 = r - (7 if long else 4)
        c.line([(cx + math.sin(a) * r0, cy - math.cos(a) * r0), (cx + math.sin(a) * r, cy - math.cos(a) * r)],
               WHITE if long else "#FFFFFF59", 1.4 if long else 1)
    for lab, a in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        t = math.radians(a)
        c.text(cx + math.sin(t) * (r - 15), cy - math.cos(t) * (r - 15), lab, size=10, color=SOFT, anchor="center", bold=True)
    if direction is not None:
        a = math.radians(direction + 180)  # where it blows to
        dx, dy = math.sin(a), -math.cos(a)
        tail = (cx - dx * (r - 3), cy - dy * (r - 3))
        head = (cx + dx * (r - 3), cy + dy * (r - 3))
        c.line([tail, (cx - dx * 17, cy - dy * 17)], WHITE, 2)
        c.line([(cx + dx * 17, cy + dy * 17), (head[0] - dx * 6, head[1] - dy * 6)], WHITE, 2)
        c.circle(tail[0], tail[1], 3.5, fill=WHITE)
        px, py = -dy, dx
        c.shapes.append(fenn.polygon([head, (head[0] - dx * 9 + px * 5, head[1] - dy * 9 + py * 5),
                                      (head[0] - dx * 9 - px * 5, head[1] - dy * 9 - py * 5)], fill=WHITE))
    c.text(cx, cy - 4, speed_text, size=15, color=WHITE, anchor="center", bold=True)
    c.text(cx, cy + 10, unit_text, size=9, color=SOFT, anchor="center", bold=True)


def moon_disc(c, cx, cy, r, phase, lat=0.0):
    """The moon with its lit part (smooth half-disc and half-ellipse shapes),
    mirrored south of the equator."""
    dark, lit = "#2C3240", "#ECE8DD"
    k = math.cos(2 * math.pi * phase)          # 1 new, 0 quarter, -1 full
    side = 1 if phase <= 0.5 else -1           # lit on the right while waxing
    if lat < 0:
        side = -side
    n = max(12, int(r * 1.2))

    def half(rx, s):
        """Half an ellipse (rx wide, r tall) on side s, as a convex polygon."""
        return [(cx + s * rx * math.sin(math.pi * i / n), cy - r * math.cos(math.pi * i / n)) for i in range(n + 1)]

    c.circle(cx, cy, r, fill=dark)
    if abs(k) < 0.999 or k < 0:
        c.shapes.append(fenn.polygon(half(r, side), fill=lit))
        if k > 0:      # crescent: cut the inner half-ellipse back out
            c.shapes.append(fenn.polygon(half(r * k, side), fill=dark))
        elif k < 0:    # gibbous: add the other side's half-ellipse
            c.shapes.append(fenn.polygon(half(r * -k, -side), fill=lit))
    for dx, dy, rr in ((-0.3, -0.25, 0.22), (0.2, -0.35, 0.14), (0.25, 0.15, 0.2), (-0.15, 0.35, 0.13), (-0.45, 0.1, 0.1)):
        c.circle(cx + dx * r, cy + dy * r, rr * r, fill="#00000014")


# ---- the dashboard

def hour_entries(m, mode):
    """The next 24 hours; in Conditions, sunrise and sunset in between."""
    M = m.model
    start = M.hour_now()
    out, events = [], []
    if mode == "conditions":
        for k in range(len(M.days)):
            rise, sset = M.sun(k)
            events += [(rise, True), (sset, False)]
    now = M.now()
    for n, i in enumerate(range(start, min(start + 24, len(M.times)))):
        t = M.times[i]
        for et, rising in events:
            if n > 0 and now < et <= t and t - et < timedelta(hours=1):
                out.append({"event": rising, "time": et})
        out.append({"i": i, "time": t, "now": n == 0})
    return out


def dashboard(m, W):
    M = m.model
    S = m.settings
    c = Canvas(W)
    scene = ambient_scene(m)  # (first: a dev override also sets the colors)
    top, bottom = sky_colors(M)
    CW = W - 2 * P
    k0 = M.today()

    place = S["place"] or {}
    c.text(W / 2, 20, "MY LOCATION" if S["auto"] else (place.get("country") or "").upper(), size=10, color=SOFT,
           anchor="center", bold=True)
    c.text(W / 2, 41, fit(place.get("name", ""), 21, W - 80), size=21, anchor="center")
    c.text(W / 2, 86, u.deg(M.cur("temperature_2m")), size=60, anchor="center")
    now_sym = sym(M.cur("weather_code"), M.is_day(), M.cur("temperature_2m"), M.cur("wind_speed_10m"))
    c.text(W / 2, 126, symbols.LABELS.get(now_sym, M.condition()), size=14, anchor="center", bold=True)
    c.text(W / 2, 145, f"H:{u.deg(M.d('temperature_2m_max', k0))}   L:{u.deg(M.d('temperature_2m_min', k0))}",
           size=13, anchor="center", bold=True)
    c.region(W / 2 - 140, 8, W / 2 + 140, 152, "detail:temp")
    y = 166

    y = rain_card(m, c, P, y, CW) or y
    y = hourly_card(m, c, P, y, CW, top, bottom) + 10

    w2 = (CW - 10) / 2
    days = list(range(k0, min(k0 + 10, len(M.days))))
    rh = 27
    h10 = 36 + rh * len(days) + 6
    ten_day_card(m, c, P, y, w2, h10, days, rh, top, bottom)
    hs = (h10 - 10) / 2
    aqi_card(m, c, P + w2 + 10, y, w2, hs)
    wind_card(m, c, P + w2 + 10, y + hs + 10, w2, hs)
    y += h10 + 10

    w3 = (CW - 20) / 3
    h3 = 150
    order = [k for k in m.card_order() if k in SMALL and k not in S["cards_hidden"]]
    for n, key in enumerate(order):
        SMALL[key](m, c, P + (n % 3) * (w3 + 10), y + (n // 3) * (h3 + 10), w3, h3)
    if order:
        y += ((len(order) + 2) // 3) * (h3 + 10)

    upd = datetime.fromtimestamp(M.fc.get("fetched", 0))
    c.text(W / 2, y + 8, f"Weather data: Open-Meteo.com · updated {m.clock(upd)}" + (" · offline" if m.error else ""),
           size=10, color=FAINT, anchor="center")
    c.h = y + 26
    paint_sky(c, top, bottom, scene, m.anim_time())
    return c


def rain_card(m, c, x, y, w):
    M = m.model
    mf = M.fc.get("minutely_15") or {}
    times = [wx.parse_local(t) for t in mf.get("time", [])]
    now = M.now()
    idx = [i for i, t in enumerate(times) if t > now - timedelta(minutes=15)][:9]
    if not idx:
        return None
    amounts = [(mf["precipitation"][i] or 0) for i in idx]
    snow = any(((mf.get("snowfall") or [0] * len(times))[i] or 0) > 0 for i in idx)
    raining = amounts[0] >= 0.05 or (M.cur("precipitation") or 0) > 0
    if not raining and max(amounts) < 0.05:
        return None
    what = "Snow" if snow else "Rain"
    if raining:
        stop = next((n for n, a in enumerate(amounts) if a < 0.05), None)
        text = f"{what} for the next two hours." if stop is None else f"{what} stopping around {m.clock(times[idx[stop]])}."
    else:
        begin = next(n for n, a in enumerate(amounts) if a >= 0.05)
        text = f"{what} starting around {m.clock(times[idx[begin]])}."
    h = 112
    card(c, x, y, w, h, f"{what} forecast", "umbrella", action="detail:precip")
    c.text(x + 14, y + 40, text, size=14, bold=True)
    bx0, bx1, base, bh = x + 54, x + w - 16, y + 88, 32
    for lab, frac in (("Heavy", 1.0), ("Light", 0.25)):
        c.text(x + 14, base - bh * frac, lab, size=9, color=FAINT)
        c.line([(bx0, base - bh * frac), (bx1, base - bh * frac)], "#FFFFFF14", 1)
    n = len(amounts)
    bw = (bx1 - bx0) / n
    for k, a in enumerate(amounts):
        mmh = a * 4
        frac = min(1.0, (mmh / 8) ** 0.5) if mmh > 0 else 0
        if frac > 0:
            c.rect(bx0 + k * bw + 3, base - bh * frac, bw - 6, bh * frac, fill=WHITE if snow else BLUE, radius=2)
        else:
            c.rect(bx0 + k * bw + 3, base - 1.5, bw - 6, 1.5, fill="#FFFFFF33")
    c.line([(bx0, base), (bx1, base)], "#FFFFFF40", 1)
    for k, lab in ((0, "Now"), (2, "30 min"), (4, "1 h"), (6, "1.5 h"), (8, "2 h")):
        if k < n:
            c.text(bx0 + k * bw + bw / 2, base + 12, lab, size=9, color=SOFT, anchor="center")
    return y + h + 10


MODES = [("conditions", "Conditions"), ("precip", "Rain"), ("wind", "Wind")]


def hourly_card(m, c, x, y, w, top, bottom):
    M = m.model
    mode = m.state["hour_mode"]
    lines = wrap(M.summary(), 12.5, w - 28, 2)
    head = 34 + (len(lines) * 17 + 6 if lines else 0)
    entries = hour_entries(m, mode)
    pages = max(1, (len(entries) + 7) // 8)
    page = max(0, min(m.state["hour_page"], pages - 1))
    shown = entries[page * 8: page * 8 + 8]
    sel = m.state["hour_sel"]
    sel_ok = sel is not None and any(e.get("i") == sel for e in entries)
    h = head + 92 + (24 if sel_ok else 6)
    title = {"conditions": "Hourly forecast", "precip": "Hourly precipitation", "wind": "Hourly wind"}[mode]
    card(c, x, y, w, h, title, "clock")
    c.region(x, y, x + 180, y + 30, "detail:" + {"conditions": "temp", "precip": "precip", "wind": "wind"}[mode])
    px = x + w - 12
    for key, lab in reversed(MODES):
        px -= tw(lab, 10, True) + 16
        pill(c, px, y + 7, lab, f"mode:{key}", on=key == mode, size=10, pad=8, h=20)
        px -= 5
    for n, line in enumerate(lines):
        c.text(x + 14, y + 42 + n * 17, line, size=12.5)
    yy = y + head
    c.line([(x + 14, yy), (x + w - 14, yy)], LINE, 1)
    gx0, gx1 = x + 26, x + w - 26
    cw = (gx1 - gx0) / 8
    for side, ok, act, gl in ((x + 13, page > 0, "hpage:-1", "caret-left"),
                              (x + w - 13, page < pages - 1, "hpage:1", "caret-right")):
        if ok:
            c.circle(side, yy + 46, 9, fill="#FFFFFF1F")
            c.glyph(side, yy + 46, gl, 11, WHITE)
            c.region(side - 13, yy + 20, side + 13, yy + 72, act)
    pmax = max([0.5] + [M.h("precipitation", e["i"]) or 0 for e in shown if "i" in e])
    for k, e in enumerate(shown):
        cx = gx0 + cw * (k + 0.5)
        if "event" in e:
            c.text(cx, yy + 16, m.clock(e["time"]), size=10.5, color=SOFT, anchor="center", bold=True)
            c.add(symbols.draw("sunrise" if e["event"] else "sunset", cx, yy + 42, 23))
            c.text(cx, yy + 73, "Sunrise" if e["event"] else "Sunset", size=11, anchor="center", bold=True)
            continue
        i = e["i"]
        if i == sel:
            c.rect(cx - cw / 2 + 2, yy + 4, cw - 4, 84, fill="#FFFFFF24", radius=10)
        c.region(cx - cw / 2, yy + 2, cx + cw / 2, yy + 88, f"hour:{i}")
        c.text(cx, yy + 16, "Now" if e["now"] else m.hour_label(e["time"]), size=10.5,
               color=WHITE if e["now"] else SOFT, anchor="center", bold=True)
        prob = M.h("precipitation_probability", i) or 0
        if mode == "conditions":
            t = M.cur("temperature_2m") if e["now"] else M.h("temperature_2m", i)
            code = M.cur("weather_code") if e["now"] else M.h("weather_code", i)
            day = M.is_day() if e["now"] else bool(M.h("is_day", i))
            sy = yy + (39 if prob >= 10 else 42)
            c.add(symbols.draw(sym(code, day, t, M.h("wind_speed_10m", i)), cx, sy, 23, bg_at(top, bottom, sy, 1300)))
            if prob >= 10:
                c.text(cx, yy + 57, f"{prob}%", size=9, color=BLUE, anchor="center", bold=True)
            c.text(cx, yy + 73, u.deg(t), size=13, anchor="center", bold=True)
        elif mode == "precip":
            a = M.h("precipitation", i) or 0
            snow = (M.h("snowfall", i) or 0) > 0
            bh = 30 * (a / pmax) ** 0.6 if a > 0 else 0
            base = yy + 58
            c.rect(cx - 8, base - 30, 16, 30, fill="#FFFFFF10", radius=3)
            if bh:
                c.rect(cx - 8, base - bh, 16, bh, fill=WHITE if snow else BLUE, radius=3)
            c.text(cx, yy + 70, u.precip(a, False), size=12, anchor="center", bold=True)
            c.text(cx, yy + 84, f"{prob}%", size=9, color=BLUE, anchor="center", bold=True)
        else:
            sp, gu, di = M.h("wind_speed_10m", i), M.h("wind_gusts_10m", i), M.h("wind_direction_10m", i)
            if di is not None:
                arrow(c, cx, yy + 40, 20, di + 180)
            c.text(cx, yy + 66, u.wind(sp, False), size=13, anchor="center", bold=True)
            c.text(cx, yy + 81, f"gusts {u.wind(gu, False)}", size=9, color=SOFT, anchor="center")
    if sel_ok:
        i = sel
        t = M.times[i]
        kd = M.days.index(t.strftime("%Y-%m-%d"))
        text = (f"{M.day_name(kd)} {m.clock(t)} · {wx.condition(M.h('weather_code', i), bool(M.h('is_day', i)))} · "
                f"{u.deg(M.h('temperature_2m', i))}, feels {u.deg(M.h('apparent_temperature', i))} · "
                f"rain {M.h('precipitation_probability', i) or 0}% ({u.precip(M.h('precipitation', i))}) · "
                f"wind {u.wind(M.h('wind_speed_10m', i))} {u.compass(M.h('wind_direction_10m', i))}")
        c.text(x + 14, yy + 102, fit(text, 11, w - 28), size=11, color=SOFT)
    return y + h


def ten_day_card(m, c, x, y, w, h, days, rh, top, bottom):
    M = m.model
    card(c, x, y, w, h, f"{len(days)}-day forecast", "calendar-blank")
    lows = [M.d("temperature_2m_min", k) for k in days]
    highs = [M.d("temperature_2m_max", k) for k in days]
    wmin, wmax = min(v for v in lows if v is not None), max(v for v in highs if v is not None)
    bx0, bx1 = x + 128, x + w - 42
    for r, k in enumerate(days):
        cy = y + 36 + rh * r + rh / 2
        if r:
            c.line([(x + 14, cy - rh / 2), (x + w - 14, cy - rh / 2)], "#FFFFFF1A", 1)
        c.region(x, cy - rh / 2, x + w, cy + rh / 2, f"detail:day:{k}")
        c.text(x + 14, cy, M.day_name(k), size=12.5, bold=True)
        rain = M.d("precipitation_probability_max", k) or 0
        sy = cy - (4 if rain >= 20 else 0)
        c.add(symbols.draw(sym(M.d("weather_code", k), True, highs[r], M.d("wind_speed_10m_max", k)),
                           x + 66, sy, 18 if rain >= 20 else 20, bg_at(top, bottom, sy, 1300)))
        if rain >= 20:
            c.text(x + 66, cy + 9, f"{rain}%", size=8, color=BLUE, anchor="center", bold=True)
        c.text(bx0 - 8, cy, u.deg(lows[r]), size=12.5, color=SOFT, anchor="end", bold=True)
        temp_bar(c, bx0, cy, bx1 - bx0, lows[r], highs[r], wmin, wmax, M.cur("temperature_2m") if r == 0 else None)
        c.text(x + w - 14, cy, u.deg(highs[r]), size=12.5, anchor="end", bold=True)


def aqi_card(m, c, x, y, w, h):
    M = m.model
    std = m.aqi_standard()
    card(c, x, y, w, h, "Air quality", "leaf", action="detail:aqi")
    v = M.aq_now(std)
    if v is None:
        c.text(x + 14, y + 52, "Not available here", size=13, color=SOFT)
        return
    name, _ = aqi_info(v, std)
    c.text(x + 14, y + 50, str(round(v)), size=26)
    c.text(x + 14 + tw(str(round(v)), 26) + 8, y + 54, "US AQI" if std == "us" else "European AQI", size=10, color=SOFT, bold=True)
    c.text(x + 14, y + 76, fit(name, 14, w - 28, True), size=14, bold=True)
    stops, vmax = aqi_stops(std)
    gradient_bar(c, x + 14, y + 94, w - 28, stops, vmax, min(v, vmax))
    for n, line in enumerate(wrap(AQI_ADVICE.get(name, ""), 11, w - 28, 2)):
        c.text(x + 14, y + 112 + n * 14, line, size=11, color=SOFT)


def wind_card(m, c, x, y, w, h):
    M = m.model
    card(c, x, y, w, h, "Wind", "wind", action="detail:wind")
    rows = [("Wind", u.wind(M.cur("wind_speed_10m"))), ("Gusts", u.wind(M.cur("wind_gusts_10m"))),
            ("Direction", f"{round(M.cur('wind_direction_10m') or 0)}° {u.compass(M.cur('wind_direction_10m'))}")]
    col = w - 120
    for n, (lab, val) in enumerate(rows):
        ry = y + 46 + n * 30
        c.text(x + 14, ry, lab, size=12, bold=True)
        c.text(x + col, ry, val, size=12, color=SOFT, anchor="end")
        if n < 2:
            c.line([(x + 14, ry + 15), (x + col, ry + 15)], "#FFFFFF1A", 1)
    r = min(48, h / 2 - 22)
    compass(c, x + w - 62, y + h / 2 + 10, r, M.cur("wind_direction_10m"), u.wind(M.cur("wind_speed_10m"), False), u.label("wind"))


# ---- small cards

def big_value(c, x, y, text, size=26):
    c.text(x + 14, y + 50, text, size=size)


def foot(c, x, y, w, h, text, lines=3, size=11):
    ls = wrap(text, size, w - 28, lines)
    for n, line in enumerate(ls):
        c.text(x + 14, y + h - 14 - (len(ls) - 1 - n) * 14, line, size=size)


def sun_card(m, c, x, y, w, h):
    M = m.model
    k = M.today()
    rise, sset = M.sun(k)
    now = M.now()
    if now < rise:
        title, big, small = "Sunrise", rise, f"Sunset: {m.clock(sset)}"
    elif now < sset:
        title, big, small = "Sunset", sset, f"Sunrise: {m.clock(rise)}"
    else:
        title, big, small = "Sunrise", M.sun(min(k + 1, len(M.days) - 1))[0], f"Sunset: {m.clock(sset)}"
    card(c, x, y, w, h, title, "sun-horizon", action="detail:sun")
    big_value(c, x, y, m.clock(big), 24)
    place = m.settings["place"]
    day0 = M.day_date(k)
    gx0, gx1, gy0, gy1 = x + 12, x + w - 12, y + 72, y + 118
    pts = []
    for s in range(49):
        t = day0 + timedelta(minutes=30 * s)
        pts.append((gx0 + (gx1 - gx0) * s / 48, astro.sun_altitude(M.to_utc(t), place["lat"], place["lon"])))
    amax = max(10, max(a for _, a in pts))
    amin = min(-10, min(a for _, a in pts))
    Y = lambda a: gy0 + (gy1 - gy0) * (amax - a) / (amax - amin)
    for (x0, a0), (x1, a1) in zip(pts, pts[1:]):
        c.line([(x0, Y(a0)), (x1, Y(a1))], WHITE if a0 > 0 and a1 > 0 else "#FFFFFF55", 2)
    c.line([(gx0, Y(0)), (gx1, Y(0))], "#FFFFFF66", 1)
    frac = (now - day0).total_seconds() / 86400
    alt = astro.sun_altitude(M.to_utc(now), place["lat"], place["lon"])
    sx, sy = gx0 + (gx1 - gx0) * frac, Y(alt)
    c.circle(sx, sy, 7, fill="#FFFFFF33")
    c.circle(sx, sy, 4.5, fill=WHITE)
    c.text(x + 14, y + h - 14, small, size=11)


def moon_card(m, c, x, y, w, h):
    M = m.model
    place = m.settings["place"]
    now_utc = M.to_utc(M.now())
    frac, phase = astro.moon_illumination(now_utc)
    card(c, x, y, w, h, astro.phase_name(phase), "moon", action="detail:moon")
    moon_disc(c, x + w / 2, y + 66, 27, phase, place["lat"])
    midnight = M.to_utc(datetime.combine(M.now().date(), datetime.min.time()))
    rise, sset = astro.moon_times(midnight, place["lat"], place["lon"])
    up = astro.moon_altitude(now_utc, place["lat"], place["lon"]) > 0
    ev = ("Moonset", sset) if up and sset and sset > now_utc else ("Moonrise", rise)
    c.text(x + 14, y + h - 30, f"Illumination {round(frac * 100)}%", size=11)
    c.text(x + 14, y + h - 14, f"{ev[0]}: {m.clock(M.to_local(ev[1])) if ev[1] else 'none today'}", size=11)


def uv_card(m, c, x, y, w, h):
    M = m.model
    v = M.cur("uv_index")
    card(c, x, y, w, h, "UV index", "sun-dim", action="detail:uv")
    big_value(c, x, y, str(round(v or 0)))
    c.text(x + 14, y + 74, uv_name(v), size=14, bold=True)
    gradient_bar(c, x + 14, y + 92, w - 28, UV_STOPS, 11, min(11, v or 0))
    idx = M.day_hours(M.today())
    high = [M.times[i] for i, uv in zip(idx, M.hs("uv_index", idx)) if (uv or 0) >= 3]
    if high and M.now() < high[-1] + timedelta(hours=1):
        text = f"Use sun protection {m.clock(high[0])}–{m.clock(high[-1] + timedelta(hours=1))}."
    else:
        text = "Low for the rest of the day."
    foot(c, x, y, w, h, text, 2)


def precip_card(m, c, x, y, w, h):
    M = m.model
    start = M.hour_now()
    past = sum(v or 0 for v in M.hs("precipitation", range(max(0, start - 24), start)))
    nxt = sum(v or 0 for v in M.hs("precipitation", range(start, min(start + 24, len(M.times)))))
    card(c, x, y, w, h, "Precipitation", "drop", action="detail:precip")
    big_value(c, x, y, u.precip(past), 24)
    c.text(x + 14, y + 72, "in last 24 h", size=13, bold=True)
    foot(c, x, y, w, h, f"{u.precip(nxt)} expected in next 24 h." if nxt >= 0.05 else "None expected in next 24 h.", 2)


def feels_card(m, c, x, y, w, h):
    M = m.model
    card(c, x, y, w, h, "Feels like", "thermometer", action="detail:feels")
    big_value(c, x, y, u.deg(M.cur("apparent_temperature")))
    foot(c, x, y, w, h, feels_words(M.cur("temperature_2m"), M.cur("apparent_temperature"),
                                    M.cur("wind_speed_10m"), M.cur("relative_humidity_2m")), 3)


def humidity_card(m, c, x, y, w, h):
    M = m.model
    card(c, x, y, w, h, "Humidity", "drop-half", action="detail:humidity")
    big_value(c, x, y, f"{round(M.cur('relative_humidity_2m') or 0)}%")
    foot(c, x, y, w, h, f"The dew point is {u.deg(M.cur('dew_point_2m'))} right now.", 3)


def visibility_card(m, c, x, y, w, h):
    M = m.model
    card(c, x, y, w, h, "Visibility", "eye", action="detail:visibility")
    big_value(c, x, y, u.dist(M.cur("visibility")))
    foot(c, x, y, w, h, visibility_words(M.cur("visibility")), 3)


def pressure_trend(M):
    i = M.hour_now()
    a, b = M.h("pressure_msl", max(0, i - 3)), M.cur("pressure_msl")
    if a is None or b is None:
        return "stable", 0
    d = b - a
    return ("rising" if d > 0.8 else "falling" if d < -0.8 else "stable"), d


def pressure_card(m, c, x, y, w, h):
    M = m.model
    v = M.cur("pressure_msl")
    card(c, x, y, w, h, "Pressure", "gauge", action="detail:pressure")
    cx, cy, r = x + w / 2, y + 86, 44
    lo, hi = 960, 1060
    for k in range(41):
        a = math.radians(-135 + 270 * k / 40)
        c.line([(cx + math.sin(a) * (r - 6), cy - math.cos(a) * (r - 6)), (cx + math.sin(a) * r, cy - math.cos(a) * r)],
               "#FFFFFF59", 1.2)
    if v is not None:
        a = math.radians(-135 + 270 * min(1, max(0, (v - lo) / (hi - lo))))
        c.line([(cx + math.sin(a) * (r - 10), cy - math.cos(a) * (r - 10)), (cx + math.sin(a) * (r + 1), cy - math.cos(a) * (r + 1))],
               WHITE, 3)
    trend, _ = pressure_trend(M)
    c.glyph(cx, cy - 16, {"rising": "arrow-up", "falling": "arrow-down", "stable": "equals"}[trend], 12, WHITE)
    c.text(cx, cy + 2, u.pressure(v, False), size=17, anchor="center", bold=True)
    c.text(cx, cy + 18, u.label("pressure"), size=10, color=SOFT, anchor="center", bold=True)
    c.text(cx - r + 4, cy + r - 2, "Low", size=9, color=SOFT, anchor="center")
    c.text(cx + r - 4, cy + r - 2, "High", size=9, color=SOFT, anchor="center")


SMALL = {
    "sun": sun_card, "moon": moon_card, "uv": uv_card, "precip": precip_card, "feels": feels_card,
    "humidity": humidity_card, "visibility": visibility_card, "pressure": pressure_card,
}
CARD_NAMES = {"sun": "Sunrise and sunset", "moon": "Moon", "uv": "UV index", "precip": "Precipitation",
              "feels": "Feels like", "humidity": "Humidity", "visibility": "Visibility", "pressure": "Pressure"}


# ---- detail views

TITLES = {"temp": ("Temperature", "thermometer"), "day": ("Daily forecast", "calendar-blank"),
          "precip": ("Precipitation", "drop"), "wind": ("Wind", "wind"), "aqi": ("Air quality", "leaf"),
          "uv": ("UV index", "sun-dim"), "humidity": ("Humidity", "drop-half"), "visibility": ("Visibility", "eye"),
          "pressure": ("Pressure", "gauge"), "feels": ("Feels like", "thermometer"), "sun": ("Sun", "sun-horizon"),
          "moon": ("Moon", "moon")}

SUBS = {"precip": ["Amount", "Chance"], "humidity": ["Humidity", "Dew point"], "temp": ["Temperature", "With feels like"],
        "day": ["Temperature", "With feels like"]}


def detail(m, W, glossy=False):
    M = m.model
    st = m.state["detail"]
    kind = st["kind"]
    c = Canvas(W)
    top, bottom = sky_colors(M)
    title, icon = TITLES.get(kind, ("", "info"))
    c.glyph(P + 10, 20, icon, 14, WHITE)
    c.text(P + 24, 20, title, size=15, bold=True)
    c.text(W - P - 4, 20, (m.settings["place"] or {}).get("name", ""), size=11, color=SOFT, anchor="end", bold=True)
    y = 40
    if kind == "moon":
        y = moon_detail(m, c, y, W)
    else:
        y = day_chips(m, c, y, W, kind)
        if kind in SUBS:
            px = P
            for n, lab in enumerate(SUBS[kind]):
                px += pill(c, px, y, lab, f"sub:{n}", on=st.get("sub", 0) == n, size=10, pad=9, h=20) + 6
            y += 28
        y = {"temp": temp_detail, "day": temp_detail, "feels": temp_detail, "precip": precip_detail,
             "wind": wind_detail, "aqi": aqi_detail, "uv": uv_detail, "humidity": humidity_detail,
             "visibility": visibility_detail, "pressure": pressure_detail, "sun": sun_detail}[kind](m, c, y, W)
    c.text(W / 2, y + 10, "Open-Meteo.com" + (" · air quality: Copernicus CAMS" if kind == "aqi" else "")
           + f" · updated {m.clock(datetime.fromtimestamp(M.fc.get('fetched', 0)))}", size=10, color=FAINT, anchor="center")
    c.h = y + 28
    if not glossy:
        paint_sky(c, top, bottom)
    return c


def day_chips(m, c, y, W, kind):
    M = m.model
    k0 = M.today()
    first = k0 - 1 if kind == "pressure" else k0
    last = min(len(M.days), (k0 + 4) if kind == "aqi" else k0 + 10)
    ks = list(range(max(0, first), last))
    cw = (W - 2 * P) / max(len(ks), 1)
    sel = m.state["detail"]["day"]
    for n, k in enumerate(ks):
        x = P + n * cw
        on = k == sel
        c.rect(x + 2, y, cw - 4, 36, fill="#FFFFFF40" if on else "#FFFFFF12", radius=10)
        d = M.day_date(k)
        c.text(x + cw / 2, y + 12, "Today" if k == k0 else "Yday" if k == k0 - 1 else d.strftime("%a"), size=10,
               color=WHITE if on else SOFT, anchor="center", bold=True)
        c.text(x + cw / 2, y + 26, str(d.day), size=12, anchor="center", bold=on)
        c.region(x, y, x + cw, y + 36, f"day:{k}")
    return y + 46


def hour_axis(M, idx):
    return [M.times[i] for i in idx], (lambda n, t: f"{t.hour:02d}" if t.hour % 6 == 0 else "")


def now_index(M, idx):
    hn = M.hour_now()
    return idx.index(hn) if hn in idx else None


def readout(c, x, y, w, text):
    c.rect(x, y - 11, w, 22, fill="#0000001F", radius=11)
    c.text(x + w / 2, y, fit(text, 11.5, w - 20, True), size=11.5, anchor="center", bold=True)


def stat_grid(c, x, y, w, items, cols=3):
    cw = w / cols
    for n, (lab, val) in enumerate(items):
        cx = x + (n % cols) * cw
        cy = y + (n // cols) * 40
        c.text(cx, cy + 10, lab.upper(), size=9, color=SOFT, bold=True)
        c.text(cx, cy + 27, fit(val, 14, cw - 8, True), size=14, bold=True)
    return y + ((len(items) + cols - 1) // cols) * 40


def explain(c, x, y, w, text, lines=4):
    ls = wrap(text, 11.5, w, lines)
    for n, line in enumerate(ls):
        c.text(x, y + n * 16, line, size=11.5, color=SOFT)
    return y + len(ls) * 16 + 4


def sel_hour(m, idx):
    sel = m.state["detail"].get("sel")
    if sel is None or sel not in idx:
        hn = m.model.hour_now()
        sel = hn if hn in idx else idx[min(12, len(idx) - 1)]
    return sel


def chart_box(c, y, W, h=150):
    c.rect(P, y - 8, W - 2 * P, h + 34, fill="#0000001A", radius=14)
    return P + 10, y + 6, W - 2 * P - 20, h - 10


def headline(c, y, big, sub, size=32):
    c.text(P + 4, y + 18, big, size=size)
    c.text(P + 4 + tw(big, size) + 12, y + 22, sub, size=13, color=SOFT, bold=True)
    return y + 46


def temp_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    k = st["day"]
    idx = M.day_hours(k)
    sel = sel_hour(m, idx)
    temps = [u.t(v) for v in M.hs("temperature_2m", idx)]
    feels = [u.t(v) for v in M.hs("apparent_temperature", idx)]
    both = st["kind"] == "feels" or st.get("sub", 0) == 1
    hi, lo = M.d("temperature_2m_max", k), M.d("temperature_2m_min", k)
    if st["kind"] == "feels":
        big = u.deg(M.cur("apparent_temperature") if k == M.today() else M.d("apparent_temperature_max", k))
        sub = f"feels like · actual {u.deg(M.cur('temperature_2m') if k == M.today() else hi)}"
    elif k == M.today():
        big, sub = u.deg(M.cur("temperature_2m")), f"{M.condition()} · H:{u.deg(hi)} L:{u.deg(lo)}"
    else:
        big, sub = f"{u.deg(hi)} / {u.deg(lo)}", f"{wx.condition(M.d('weather_code', k))} · {M.day_name(k, False)}"
    y = headline(c, y, big, sub)
    bx, by, bw, bh = chart_box(c, y + 26, W)
    for n, i in enumerate(idx):
        if M.times[i].hour % 3 == 0:
            c.add(symbols.draw(sym(M.h("weather_code", i), bool(M.h("is_day", i))), bx + (bw - 38) * n / (len(idx) - 1), y + 8, 17))
    times, lab = hour_axis(M, idx)
    clean = [t for t in temps if t is not None]
    imax, imin = temps.index(max(clean)), temps.index(min(clean))
    series = [{"values": temps, "color": WHITE, "width": 2.4, "fill": "#FFFFFF14"}]
    if both:
        series.append({"values": feels, "color": "#FFD27A", "width": 1.6})
    chart(c, bx, by, bw, bh, times, series, lambda v: f"{round(v)}°", lab, now_index(M, idx), idx.index(sel),
          markers=[(imax, "H"), (imin, "L")])
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(M.times[sel])} · {wx.condition(M.h('weather_code', sel), bool(M.h('is_day', sel)))} · "
            f"{u.deg(M.h('temperature_2m', sel))} · feels like {u.deg(M.h('apparent_temperature', sel))}")
    y += 22
    rise, sset = M.sun(k)
    items = [("High", u.deg(hi)), ("Low", u.deg(lo)),
             ("Feels like", f"{u.deg(M.d('apparent_temperature_min', k))} to {u.deg(M.d('apparent_temperature_max', k))}"),
             ("Precipitation", f"{u.precip(M.d('precipitation_sum', k))} · {M.d('precipitation_probability_max', k) or 0}%"),
             ("Wind", f"{u.wind(M.d('wind_speed_10m_max', k))} {u.compass(M.d('wind_direction_10m_dominant', k))}"),
             ("UV index", f"{round(M.d('uv_index_max', k) or 0)} {uv_name(M.d('uv_index_max', k))}")]
    hum = [v for v in M.hs("relative_humidity_2m", idx) if v is not None]
    if hum:
        items.append(("Humidity", f"{round(sum(hum) / len(hum))}% average"))
    items += [("Sunrise", m.clock(rise)), ("Sunset", m.clock(sset))]
    y = stat_grid(c, P + 4, y, W - 2 * P - 8, items)
    if st["kind"] == "feels":
        d = [f - a for f, a in zip(M.hs("apparent_temperature", idx), M.hs("temperature_2m", idx)) if f is not None and a is not None]
        text = "Feels like combines the temperature with wind and humidity. "
        if d and min(d) < -2:
            text += f"Wind chill makes it feel up to {round(u.t_delta(-min(d)))}° colder this day. "
        if d and max(d) > 2:
            text += f"Humidity and sun make it feel up to {round(u.t_delta(max(d)))}° warmer this day."
    else:
        rain = M.d("precipitation_probability_max", k) or 0
        text = (f"{M.day_name(k, False)}: {wx.condition(M.d('weather_code', k)).lower()}, with a high of {u.deg(hi)} "
                f"and a low of {u.deg(lo)}. " + (f"{rain}% chance of precipitation." if rain >= 10 else "No precipitation expected."))
    return explain(c, P + 4, y + 6, W - 2 * P - 8, text) + 4


def precip_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    k = st["day"]
    idx = M.day_hours(k)
    sel = sel_hour(m, idx)
    amounts = [u.p(v) for v in M.hs("precipitation", idx)]
    snow = M.hs("snowfall", idx)
    total = M.d("precipitation_sum", k)
    y = headline(c, y, u.precip(total), "total today" if k == M.today() else f"total on {M.day_name(k, False)}")
    bx, by, bw, bh = chart_box(c, y + 6, W)
    times, lab = hour_axis(M, idx)
    if st.get("sub", 0) == 0:
        mx = max([0.5 if u.unit("precip") == "mm" else 0.02] + [a or 0 for a in amounts]) * 1.15
        inch = u.unit("precip") == "in"
        chart(c, bx, by, bw, bh, times, [], lambda v: f"{v:.2f}" if inch else f"{v:.1f}", lab, now_index(M, idx),
              idx.index(sel), bars=amounts, bar_color=lambda n: WHITE if (snow[n] or 0) > 0 else BLUE,
              fixed=(0, mx, [0, mx / 2, mx]))
    else:
        chart(c, bx, by, bw, bh, times, [{"values": M.hs("precipitation_probability", idx), "color": BLUE, "width": 2.2,
                                          "fill": "#5AC8FA2E"}],
              lambda v: f"{round(v)}%", lab, now_index(M, idx), idx.index(sel), fixed=(0, 100, [0, 25, 50, 75, 100]))
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(M.times[sel])} · {u.precip(M.h('precipitation', sel))}"
            f"{' of snow' if (M.h('snowfall', sel) or 0) > 0 else ''} · chance {M.h('precipitation_probability', sel) or 0}%")
    y += 22
    sn = M.d("snowfall_sum", k) or 0
    items = [("Total", u.precip(total)), ("Rain", u.precip(M.d("rain_sum", k))),
             ("Snow", f"{sn:.1f} cm" if u.unit("precip") == "mm" else f"{sn / 2.54:.1f} in"),
             ("Hours with precipitation", f"{round(M.d('precipitation_hours', k) or 0)} h"),
             ("Highest chance", f"{M.d('precipitation_probability_max', k) or 0}%")]
    y = stat_grid(c, P + 4, y, W - 2 * P - 8, items) + 6
    c.text(P + 4, y + 6, "NEXT DAYS", size=9, color=SOFT, bold=True)
    y += 16
    ks = list(range(M.today(), min(M.today() + 10, len(M.days))))
    sums = [M.d("precipitation_sum", kk) or 0 for kk in ks]
    mx = max([1.0] + sums)
    cw = (W - 2 * P) / len(ks)
    for n, kk in enumerate(ks):
        x = P + n * cw
        bh2 = 34 * (sums[n] / mx) ** 0.6 if sums[n] > 0 else 0
        if kk == k:
            c.rect(x + 2, y - 4, cw - 4, 72, fill="#FFFFFF1F", radius=8)
        c.rect(x + cw / 2 - 7, y, 14, 34, fill="#FFFFFF10", radius=3)
        if bh2:
            c.rect(x + cw / 2 - 7, y + 34 - bh2, 14, bh2, fill=WHITE if (M.d("snowfall_sum", kk) or 0) > 0 else BLUE, radius=3)
        c.text(x + cw / 2, y + 46, u.precip(sums[n], False), size=10, anchor="center", bold=kk == k)
        c.text(x + cw / 2, y + 60, M.day_name(kk), size=9, color=WHITE if kk == k else SOFT, anchor="center", bold=True)
        c.region(x, y, x + cw, y + 66, f"day:{kk}")
    y += 74
    return explain(c, P + 4, y, W - 2 * P - 8, "Amounts are hourly model forecasts in " + u.label("precip")
                   + "; white bars are snow. The chance is the probability of at least 0.1 mm in that hour.") + 4


def wind_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    k = st["day"]
    idx = M.day_hours(k)
    sel = sel_hour(m, idx)
    today = k == M.today()
    y = headline(c, y, u.wind(M.cur("wind_speed_10m") if today else M.d("wind_speed_10m_max", k)),
                 f"{u.compass(M.cur('wind_direction_10m'))} · now" if today else "strongest", 30)
    bx, by, bw, bh = chart_box(c, y + 26, W)
    for n, i in enumerate(idx):
        if M.times[i].hour % 2 == 0 and M.h("wind_direction_10m", i) is not None:
            arrow(c, bx + (bw - 38) * n / (len(idx) - 1), y + 8, 14, M.h("wind_direction_10m", i) + 180, SOFT, 1.6)
    times, lab = hour_axis(M, idx)
    chart(c, bx, by, bw, bh, times, [{"values": [u.w(v) for v in M.hs("wind_speed_10m", idx)], "color": WHITE, "width": 2.4,
                                      "fill": "#FFFFFF14"},
                                     {"values": [u.w(v) for v in M.hs("wind_gusts_10m", idx)], "color": "#FFFFFF80", "width": 1.4}],
          lambda v: f"{round(v)}", lab, now_index(M, idx), idx.index(sel), floor_zero=True)
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(M.times[sel])} · {u.wind(M.h('wind_speed_10m', sel))} from "
            f"{u.compass(M.h('wind_direction_10m', sel))} ({round(M.h('wind_direction_10m', sel) or 0)}°) · gusts {u.wind(M.h('wind_gusts_10m', sel))}")
    y += 22
    kmh = M.h("wind_speed_10m", sel) or 0
    compass(c, W - P - 64, y + 58, 52, M.h("wind_direction_10m", sel), u.wind(M.h("wind_speed_10m", sel), False), u.label("wind"))
    items = [("Strongest wind", u.wind(M.d("wind_speed_10m_max", k))), ("Strongest gusts", u.wind(M.d("wind_gusts_10m_max", k))),
             ("Mostly from", u.compass(M.d("wind_direction_10m_dominant", k))),
             ("Beaufort", f"{u.beaufort(kmh)} · {u.BEAUFORT_NAMES[u.beaufort(kmh)]}")]
    y = max(stat_grid(c, P + 4, y, W - 2 * P - 150, items, cols=2), y + 120)
    return explain(c, P + 4, y, W - 2 * P - 8, "Wind 10 m above the ground; the arrows point where it blows. "
                   "Gusts (the faint line) are the strongest short bursts in each hour.") + 4


POLLUTANTS = [("pm2_5", "PM2.5", [10, 20, 25, 50, 75]), ("pm10", "PM10", [20, 40, 50, 100, 150]),
              ("ozone", "Ozone (O₃)", [50, 100, 130, 240, 380]), ("nitrogen_dioxide", "NO₂", [40, 90, 120, 230, 340]),
              ("sulphur_dioxide", "SO₂", [100, 200, 350, 500, 750]), ("carbon_monoxide", "CO", None)]
BAND_COLORS = ["#50F0E6", "#50CCAA", "#F0E641", "#FF5050", "#960032", "#7D2181"]


def aqi_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    aq = M.aq
    std = m.aqi_standard()
    if not aq:
        c.text(P + 4, y + 20, "Air quality isn't available for this place right now.", size=13, color=SOFT)
        return y + 40
    key = "us_aqi" if std == "us" else "european_aqi"
    date = M.days[st["day"]]
    times_all = aq["hourly"]["time"]
    idx = [i for i, t in enumerate(times_all) if t.startswith(date)]
    if not idx:
        c.text(P + 4, y + 20, "No air quality forecast for this day.", size=13, color=SOFT)
        return y + 40
    vals = [aq["hourly"][key][i] for i in idx]
    times = [wx.parse_local(times_all[i]) for i in idx]
    nowkey = M.now().strftime("%Y-%m-%dT%H")
    now_i = next((n for n, i in enumerate(idx) if times_all[i][:13] == nowkey), None)
    sel = st.get("sel_aq")
    if sel is None or sel >= len(idx):
        sel = now_i if now_i is not None else min(12, len(idx) - 1)
    v = vals[sel]
    name, _ = aqi_info(v or 0, std)
    y = headline(c, y, "–" if v is None else str(round(v)), f"{name} · {'US AQI (EPA)' if std == 'us' else 'European AQI (EEA)'}")
    bx, by, bw, bh = chart_box(c, y + 6, W)
    stops, vmax = aqi_stops(std)
    hi = max(vmax * 0.6, max((x or 0) for x in vals) * 1.15)
    chart(c, bx, by, bw, bh, times, [{"values": vals, "color": WHITE, "width": 2.6, "colored": True}],
          lambda t: f"{round(t)}", lambda n, t: f"{t.hour:02d}" if t.hour % 6 == 0 else "", now_i, sel, action="pick_aq",
          fixed=(0, hi, [round(hi * f) for f in (0, 0.25, 0.5, 0.75, 1)]), color_fn=lambda t: scale_color(stops, t))
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(times[sel])} · AQI {'–' if v is None else round(v)} · {name}")
    y += 24
    c.text(P + 4, y + 4, "POLLUTANTS AT THIS HOUR (µg/m³)", size=9, color=SOFT, bold=True)
    y += 14
    cw = (W - 2 * P) / 3
    for n, (keyp, label, bands) in enumerate(POLLUTANTS):
        val = (aq["hourly"].get(keyp) or [None] * len(times_all))[idx[sel]]
        x = P + 4 + (n % 3) * cw
        yy = y + (n // 3) * 40
        c.text(x, yy + 10, label, size=10, color=SOFT, bold=True)
        dx = 0
        if val is not None and bands:
            band = next((b for b, lim in enumerate(bands) if val <= lim), 5)
            c.circle(x + 5, yy + 27, 4, fill=BAND_COLORS[band])
            dx = 14
        c.text(x + dx, yy + 27, "not available" if val is None else f"{val:.0f}" if val >= 10 else f"{val:.1f}", size=14, bold=True)
    y += 84
    return explain(c, P + 4, y, W - 2 * P - 8, AQI_ADVICE.get(name, "") + " From the Copernicus (CAMS) air quality "
                   "model (about 10 km grid in Europe), not a monitoring station. Dots use the European pollutant bands.") + 4


def uv_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    k = st["day"]
    idx = M.day_hours(k)
    sel = sel_hour(m, idx)
    vals = M.hs("uv_index", idx)
    today = k == M.today()
    v = M.cur("uv_index") if today else M.d("uv_index_max", k)
    y = headline(c, y, str(round(v or 0)), f"{uv_name(v)} · {'now' if today else 'highest'}")
    bx, by, bw, bh = chart_box(c, y + 6, W)
    times, lab = hour_axis(M, idx)
    top_v = max(11, max((x or 0) for x in vals) + 1)
    chart(c, bx, by, bw, bh, times, [{"values": vals, "color": WHITE, "width": 2.6, "colored": True, "fill": "#FFFFFF10"}],
          lambda t: f"{round(t)}", lab, now_index(M, idx), idx.index(sel), fixed=(0, top_v, [0, 3, 6, 8, 11]),
          color_fn=lambda t: scale_color(UV_STOPS, t))
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(M.times[sel])} · UV {M.h('uv_index', sel) or 0:.1f} · {uv_name(M.h('uv_index', sel))}")
    y += 22
    peak_n = max(range(len(vals)), key=lambda n: vals[n] or 0)
    high = [M.times[i] for i, x in zip(idx, vals) if (x or 0) >= 3]
    items = [("Highest", f"{round(M.d('uv_index_max', k) or 0)} {uv_name(M.d('uv_index_max', k))}"),
             ("Peak around", m.clock(M.times[idx[peak_n]])),
             ("Sun protection", f"{m.clock(high[0])}–{m.clock(high[-1] + timedelta(hours=1))}" if high else "Not needed")]
    y = stat_grid(c, P + 4, y, W - 2 * P - 8, items)
    return explain(c, P + 4, y + 4, W - 2 * P - 8, "0–2 low: no protection needed. 3–5 moderate and 6–7 high: "
                   "seek shade at midday, wear a hat and sunscreen. 8–10 very high and 11+ extreme: avoid the midday "
                   "sun; unprotected skin can burn in minutes.", 5) + 4


def humidity_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    k = st["day"]
    idx = M.day_hours(k)
    sel = sel_hour(m, idx)
    hum = M.hs("relative_humidity_2m", idx)
    today = k == M.today()
    clean = [x for x in hum if x is not None]
    big = f"{round(M.cur('relative_humidity_2m') or 0)}%" if today else f"{round(sum(clean) / len(clean))}%"
    y = headline(c, y, big, ("now" if today else "average") + f" · dew point {u.deg(M.cur('dew_point_2m') if today else M.h('dew_point_2m', sel))}")
    bx, by, bw, bh = chart_box(c, y + 6, W)
    times, lab = hour_axis(M, idx)
    if st.get("sub", 0) == 0:
        chart(c, bx, by, bw, bh, times, [{"values": hum, "color": "#7FD6FF", "width": 2.4, "fill": "#7FD6FF22"}],
              lambda t: f"{round(t)}%", lab, now_index(M, idx), idx.index(sel), fixed=(0, 100, [0, 25, 50, 75, 100]))
    else:
        chart(c, bx, by, bw, bh, times, [{"values": [u.t(v) for v in M.hs("dew_point_2m", idx)], "color": WHITE, "width": 2.4,
                                          "fill": "#FFFFFF14"}],
              lambda t: f"{round(t)}°", lab, now_index(M, idx), idx.index(sel))
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(M.times[sel])} · humidity {M.h('relative_humidity_2m', sel) or 0}% · dew point {u.deg(M.h('dew_point_2m', sel))}")
    y += 22
    dew = [x for x in M.hs("dew_point_2m", idx) if x is not None]
    y = stat_grid(c, P + 4, y, W - 2 * P - 8, [("Lowest", f"{min(clean)}%"), ("Highest", f"{max(clean)}%"),
                                                ("Dew point", f"{u.deg(min(dew))} to {u.deg(max(dew))}")])
    return explain(c, P + 4, y + 4, W - 2 * P - 8, "Relative humidity is how much water vapour the air holds compared "
                   "with the most it could hold at that temperature. The dew point says more about how it feels: at this "
                   "hour " + dew_words(M.h("dew_point_2m", sel))) + 4


def visibility_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    k = st["day"]
    idx = M.day_hours(k)
    sel = sel_hour(m, idx)
    f = 1609.344 if u.unit("dist") == "mi" else 1000
    now_v = M.cur("visibility") if k == M.today() else M.h("visibility", sel)
    y = headline(c, y, u.dist(now_v), visibility_words(now_v))
    bx, by, bw, bh = chart_box(c, y + 6, W)
    times, lab = hour_axis(M, idx)
    chart(c, bx, by, bw, bh, times, [{"values": [None if v is None else v / f for v in M.hs("visibility", idx)],
                                      "color": WHITE, "width": 2.4, "fill": "#FFFFFF14"}],
          lambda t: f"{round(t)}", lab, now_index(M, idx), idx.index(sel), floor_zero=True)
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(M.times[sel])} · {u.dist(M.h('visibility', sel))} · {visibility_words(M.h('visibility', sel))}")
    y += 22
    clean = [v for v in M.hs("visibility", idx) if v is not None]
    y = stat_grid(c, P + 4, y, W - 2 * P - 8, [("Lowest", u.dist(min(clean))), ("Highest", u.dist(max(clean)))])
    return explain(c, P + 4, y + 4, W - 2 * P - 8, "How far you can clearly see, from the forecast model (" + u.label("dist")
                   + "). Fog, rain, snow and haze lower it.") + 4


def pressure_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    k = st["day"]
    idx = M.day_hours(k)
    sel = sel_hour(m, idx)
    trend, d = pressure_trend(M)
    today = k == M.today()
    y = headline(c, y, u.pressure(M.cur("pressure_msl") if today else M.h("pressure_msl", sel)), trend if today else "", 30)
    bx, by, bw, bh = chart_box(c, y + 6, W)
    times, lab = hour_axis(M, idx)
    inhg = u.unit("pressure") == "inhg"
    chart(c, bx, by, bw, bh, times, [{"values": [u.pr(v) for v in M.hs("pressure_msl", idx)], "color": WHITE, "width": 2.4,
                                      "fill": "#FFFFFF14"}],
          lambda t: f"{t:.2f}" if inhg else f"{round(t)}", lab, now_index(M, idx), idx.index(sel))
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(M.times[sel])} · {u.pressure(M.h('pressure_msl', sel))}")
    y += 22
    clean = [v for v in M.hs("pressure_msl", idx) if v is not None]
    change = (f"{abs(d) * 0.02953:.2f}" if inhg else f"{abs(u.pr(d)):.1f}") + " " + u.label("pressure")
    y = stat_grid(c, P + 4, y, W - 2 * P - 8, [("Lowest", u.pressure(min(clean))), ("Highest", u.pressure(max(clean))),
                                                ("Last 3 hours", ("+" if d >= 0 else "−") + change)])
    return explain(c, P + 4, y + 4, W - 2 * P - 8, "Mean sea-level pressure from the forecast model, not a station "
                   "reading. Falling pressure often brings clouds and rain; rising pressure, calmer and drier weather.") + 4


def sun_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    k = st["day"]
    place = m.settings["place"]
    day0 = M.day_date(k)
    times = [day0 + timedelta(minutes=15 * s) for s in range(97)]
    alts = [astro.sun_altitude(M.to_utc(t), place["lat"], place["lon"]) for t in times]
    ev = astro.sun_times(M.to_utc(day0 + timedelta(hours=12)), place["lat"], place["lon"])
    L = lambda key: M.to_local(ev.get(key))
    rise, sset = L("sunrise"), L("sunset")
    length = (sset - rise) if rise and sset else None
    prev = astro.sun_times(M.to_utc(day0 - timedelta(hours=12)), place["lat"], place["lon"])
    change = length - (prev["sunset"] - prev["sunrise"]) if length and prev.get("sunrise") and prev.get("sunset") else None
    y = headline(c, y, f"{m.clock(rise)} – {m.clock(sset)}" if rise and sset else "No sunrise or sunset",
                 M.day_name(k, False), 26)
    bx, by, bw, bh = chart_box(c, y + 6, W)
    sel = st.get("sel_sun")
    if sel is None:
        now = M.now()
        sel = round((now - day0).total_seconds() / 900) if now.date() == day0.date() else 48
    sel = max(0, min(96, sel))
    amin, amax = min(-30, min(alts)), max(30, max(alts) + 5)
    Y = lambda a: by + bh - (a - amin) / (amax - amin) * bh
    for lo_a, hi_a, col in ((-6, 0, "#FFFFFF16"), (-12, -6, "#FFFFFF0D"), (-18, -12, "#FFFFFF07")):
        if hi_a > amin:
            c.rect(bx, Y(hi_a), bw - 38, Y(max(lo_a, amin)) - Y(hi_a), fill=col)
    now_n = round((M.now() - day0).total_seconds() / 900)
    chart(c, bx, by, bw, bh, times, [{"values": alts, "color": "#FFD60A", "width": 2.4}],
          lambda t: f"{round(t)}°", lambda n, t: f"{t.hour:02d}" if t.minute == 0 and t.hour % 6 == 0 else "",
          now_n if 0 <= now_n <= 96 else None, sel, action="pick_sun", fixed=(amin, amax, [round(amin), 0, round(amax)]))
    c.line([(bx, Y(0)), (bx + bw - 38, Y(0))], "#FFFFFF80", 1)
    y = by + bh + 44
    readout(c, P, y, W - 2 * P, f"{m.clock(times[sel])} · the sun is {abs(alts[sel]):.0f}° "
            f"{'above' if alts[sel] >= 0 else 'below'} the horizon")
    y += 22
    hm = lambda td: f"{int(td.total_seconds() // 3600)} h {int(td.total_seconds() % 3600 // 60)} min"
    T = lambda key: m.clock(L(key)) if L(key) else "–"
    if change is not None:
        s = int(round(change.total_seconds()))
        ch = ("+" if s >= 0 else "−") + f"{abs(s) // 60} min {abs(s) % 60} s"
    else:
        ch = "–"
    items = [("Astronomical dawn", T("astro_dawn")), ("Nautical dawn", T("nautical_dawn")), ("Civil dawn", T("dawn")),
             ("Sunrise", T("sunrise")), ("Solar noon", T("noon")), ("Sunset", T("sunset")),
             ("Civil dusk", T("dusk")), ("Nautical dusk", T("nautical_dusk")), ("Astronomical dusk", T("astro_dusk")),
             ("Daylight", hm(length) if length else "–"), ("Than the day before", ch)]
    y = stat_grid(c, P + 4, y, W - 2 * P - 8, items)
    return explain(c, P + 4, y + 4, W - 2 * P - 8, "Civil twilight: the sun is up to 6° below the horizon and it's "
                   "still light. Nautical: up to 12°, the horizon fades. Astronomical: up to 18°; after that the "
                   "sky is fully dark. Computed for this place's coordinates.") + 4


def moon_detail(m, c, y, W):
    M = m.model
    st = m.state["detail"]
    place = m.settings["place"]
    off = st.get("moon_day", 0)
    base = datetime.combine(M.now().date(), datetime.min.time())
    day = base + timedelta(days=off)
    at = M.to_utc(day + timedelta(hours=12)) if off else M.to_utc(M.now())
    frac, phase = astro.moon_illumination(at)
    moon_disc(c, P + 74, y + 72, 58, phase, place["lat"])
    rise, sset = astro.moon_times(M.to_utc(day), place["lat"], place["lon"])
    full, new = astro.next_phase(at, 0.5), astro.next_phase(at, 0.0)
    x = P + 160
    c.text(x, y + 16, astro.phase_name(phase), size=20, bold=True)
    c.text(x, y + 36, "Today" if off == 0 else day.strftime("%A, %d %B %Y"), size=11, color=SOFT, bold=True)
    days_to = lambda t: max(0, round((t - at).total_seconds() / 86400))
    items = [("Illumination", f"{round(frac * 100)}%"),
             ("Moonrise", m.clock(M.to_local(rise)) if rise else "none"),
             ("Moonset", m.clock(M.to_local(sset)) if sset else "none"),
             ("Next full moon", f"{M.to_local(full).strftime('%d %b')} · in {days_to(full)} d" if full else "–"),
             ("Next new moon", f"{M.to_local(new).strftime('%d %b')} · in {days_to(new)} d" if new else "–"),
             ("Moon age", f"{phase * 29.53:.1f} days")]
    stat_grid(c, x, y + 50, W - x - P, items, cols=2)
    y += 166
    px = P
    for lab, act in (("‹ Week", "moon:-7"), ("‹ Day", "moon:-1"), ("Today", "moon:0"), ("Day ›", "moon:1"), ("Week ›", "moon:7")):
        px += pill(c, px, y, lab, act, on=(act == "moon:0" and off == 0), size=10.5, pad=10, h=24) + 6
    y += 36
    cw = (W - 2 * P) / 15
    for n in range(30):
        d = off - 7 + n
        dd = base + timedelta(days=d)
        _, ph2 = astro.moon_illumination(M.to_utc(dd + timedelta(hours=12)))
        cx = P + (n % 15) * cw + cw / 2
        cy = y + (n // 15) * 52 + 14
        if d == off:
            c.rect(cx - cw / 2 + 1, cy - 14, cw - 2, 48, fill="#FFFFFF2E", radius=8)
        moon_disc(c, cx, cy, 10, ph2, place["lat"])
        c.text(cx, cy + 22, dd.strftime("%d"), size=9, color=WHITE if d == off else SOFT, anchor="center", bold=d == off)
        c.region(cx - cw / 2, cy - 14, cx + cw / 2, cy + 34, f"moonday:{d}")
    y += 108
    return explain(c, P + 4, y, W - 2 * P - 8, "Phase, illumination, moonrise and moonset are computed for this "
                   "place's coordinates. Click a day to see it; the moon is drawn as seen from this hemisphere.") + 4


# ---- places

def places(m, W):
    """The saved places as sky cards: name, local time, temperature,
    condition, high and low. In edit mode: remove and move up."""
    S = m.settings
    c = Canvas(W)
    entries = [("auto", S.get("auto_place") or {})] + [(str(n), p) for n, p in enumerate(S["places"])]
    cw = (W - 10) / 2
    ch = 82
    for n, (key, p) in enumerate(entries):
        x = (n % 2) * (cw + 10)
        y = (n // 2) * (ch + 10)
        s = m.summary_for(key)
        cur = (s or {}).get("current") or {}
        top, bottom = SKIES[sky_kind(cur.get("weather_code"), bool(cur.get("is_day", 1)))] if s else ("#3A4A63", "#55657E")
        c.add(gradient_box(x, y, cw, ch, top, bottom, 14, 12))
        selected = (key == "auto" and S["auto"]) or (key != "auto" and not S["auto"] and S["place"] and p
                                                       and round(S["place"]["lat"], 3) == round(p["lat"], 3)
                                                       and round(S["place"]["lon"], 3) == round(p["lon"], 3))
        c.rect(x, y, cw, ch, stroke=WHITE if selected else "#FFFFFF2E", width=2 if selected else 1, radius=14)
        name = p.get("name", "") if key != "auto" else "My location"
        c.text(x + 12, y + 18, fit(name, 14, cw - 90, True), size=14, bold=True)
        if key == "auto" and p.get("name"):
            c.glyph(x + 12 + tw(name, 14, True) + 10, y + 18, "navigation-arrow", 10, WHITE)
        if s:
            local = datetime.utcnow() + timedelta(seconds=int(s.get("utc_offset_seconds") or 0))
            sub = m.clock(local) + (f" · {p.get('name')}" if key == "auto" and p.get("name") else "")
            c.text(x + 12, y + 35, fit(sub, 10.5, cw - 90), size=10.5, color=SOFT, bold=True)
            c.text(x + cw - 12, y + 30, u.deg(cur.get("temperature_2m")), size=30, anchor="end")
            c.text(x + 12, y + ch - 14, fit(wx.condition(cur.get("weather_code"), bool(cur.get("is_day", 1))), 10.5, cw / 2),
                   size=10.5, bold=True)
            d = s.get("daily") or {}
            hi = (d.get("temperature_2m_max") or [None])[0]
            lo = (d.get("temperature_2m_min") or [None])[0]
            c.text(x + cw - 12, y + ch - 14, f"H:{u.deg(hi)} L:{u.deg(lo)}", size=10.5, anchor="end", bold=True)
        else:
            c.text(x + 12, y + ch - 14, "Loading…" if m.summaries_busy else "", size=10.5, color=SOFT)
        if m.state["edit_places"] and key != "auto":
            for gx, gl, act in ((x + cw - 22, "x", f"premove:{key}"), (x + cw - 52, "caret-up", f"pup:{key}")):
                c.circle(gx, y + ch / 2 + 2, 12, fill="#000000AA")
                c.glyph(gx, y + ch / 2 + 2, gl, 12, WHITE)
                c.region(gx - 14, y + ch / 2 - 12, gx + 14, y + ch / 2 + 16, act)
        else:
            c.region(x, y, x + cw, y + ch, f"popen:{key}")
    c.h = ((len(entries) + 1) // 2) * (ch + 10) - 10
    return c


# ---- tile

def tile(m, w, h):
    M = m.model
    c = Canvas(w)
    c.add(symbols.draw(sym(M.cur("weather_code"), M.is_day(), M.cur("temperature_2m"), M.cur("wind_speed_10m")), 16, h / 2, 26))
    c.text(34, h / 2 - 7, u.deg(M.cur("temperature_2m")), size=16, color="text", bold=True)
    c.text(34, h / 2 + 9, fit(M.condition(), 10, w - 36), size=10, color="dim")
    return fenn.canvas(h, c.shapes, width=w)
