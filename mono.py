"""The "Mono" look: calm and monochrome. Thin outline icons, hairlines and
plain numbers on Fenn's glass, and nothing in color:

- the temperature, condition and today's high and low;
- the next hours (icon and rain chance) and the next 7 days;
- now: precipitation chance, humidity, wind, feels like, pressure,
  visibility, UV, sunrise and sunset;
- precipitation for the next 24 hours as thin bars;
- wind for the next hours (direction and speed);
- air quality: the index, each pollutant as a bar, and the scale;
- pollen (Europe only: Open-Meteo has no pollen elsewhere);
- what to wear now and over the next hours.

`m` is main.py. Clicks come back as "mo_" actions."""

import math

import fenn
import glossy
import sky
import units as u
import wx
from ui import Canvas, fit, nice_range, tw

PAD = 16


def node(m, cid, c):
    m.canvases[cid] = c
    return fenn.canvas(c.h, c.shapes, width=c.w, id=cid)


def tones(m):
    if m.app.dark:
        return {"line": "#FFFFFF2A", "strong": "#FFFFFFE6", "soft": "#FFFFFF66", "track": "#FFFFFF1A"}
    return {"line": "#00000024", "strong": "#000000D9", "soft": "#00000059", "track": "#00000014"}


def outline(code, day=True):
    """A thin outline glyph for a weather code."""
    code = int(code or 0)
    if code == 0:
        return "sun" if day else "moon"
    if code in (1, 2):
        return "cloud-sun" if day else "cloud-moon"
    if code in (45, 48):
        return "cloud-fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "snowflake"
    if code >= 95:
        return "cloud-lightning"
    if code >= 51:
        return "cloud-rain"
    return "cloud"


def section(c, y, title, W):
    c.text(0, y, title.upper(), size=10, color="dim", bold=True)
    return y + 16


def hair(c, T, y, W, x0=0):
    c.line([(x0, y), (W, y)], T["line"], 1)


# ---- the top

def hero(m, W):
    M = m.model
    n = glossy.now_info(M)
    k = M.today()
    c = Canvas(W)
    place = (m.settings.get("place") or {}).get("name", "")
    c.text(W / 2, 12, place, size=12, color="dim", anchor="center")
    c.text(W / 2, 62, u.deg(n["temp"]), size=60, color="text", anchor="center")
    c.text(W / 2, 108, n["text"], size=13, color="text", anchor="center")
    c.text(W / 2, 128, f"{u.deg(M.d('temperature_2m_min', k))} / {u.deg(M.d('temperature_2m_max', k))}"
                       f"   ·   feels {u.deg(n['feels'])}", size=11.5, color="dim", anchor="center")
    c.h = 142
    return node(m, "mo:hero", c)


def hours(m, W):
    """The next hours: time, icon, rain chance."""
    M = m.model
    T = tones(m)
    c = Canvas(W)
    start = M.hour_now()
    count = 8 if W >= 440 else 6
    cw = W / count
    for j, i in enumerate(range(start, min(start + count, len(M.times)))):
        x = cw * j + cw / 2
        code = M.cur("weather_code") if j == 0 else M.h("weather_code", i)
        day = M.is_day() if j == 0 else bool(M.h("is_day", i))
        temp = M.cur("temperature_2m") if j == 0 else M.h("temperature_2m", i)
        c.text(x, 10, "Now" if j == 0 else f"{M.times[i].hour:02d}" if m.settings["clock24"] else m.hour_label(M.times[i]),
               size=11, color="text" if j == 0 else "dim", anchor="center", bold=j == 0)
        c.glyph(x, 36, outline(code, day), 20, "text", False)
        c.text(x, 62, u.deg(temp), size=12.5, color="text", anchor="center")
        rain = M.h("precipitation_probability", i) or 0
        c.text(x, 80, f"{rain}%", size=10, color="dim" if rain >= 20 else "faint", anchor="center")
    c.h = 90
    hair(c, T, 89, W)
    return node(m, "mo:hours", c)


def days(m, W):
    M = m.model
    T = tones(m)
    c = Canvas(W)
    k0 = M.today()
    ks = list(range(k0, min(k0 + 7, len(M.days))))
    lo_all = min(M.d("temperature_2m_min", k) for k in ks)
    hi_all = max(M.d("temperature_2m_max", k) for k in ks)
    y = 4
    for k in ks:
        y += 26
        name = "Today" if k == k0 else M.day_date(k).strftime("%A")
        c.text(0, y - 13, name, size=12.5, color="text")
        c.glyph(W * 0.36, y - 13, outline(M.d("weather_code", k)), 17, "text", False)
        rain = M.d("precipitation_probability_max", k) or 0
        if rain >= 20:
            c.text(W * 0.36 + 16, y - 13, f"{rain}%", size=10, color="dim")
        lo, hi = M.d("temperature_2m_min", k), M.d("temperature_2m_max", k)
        # a thin range bar, monochrome
        bx0, bx1 = W * 0.56, W - 70
        span = (hi_all - lo_all) or 1
        a = bx0 + (lo - lo_all) / span * (bx1 - bx0)
        b = bx0 + (hi - lo_all) / span * (bx1 - bx0)
        c.line([(bx0, y - 13), (bx1, y - 13)], T["track"], 2)
        c.line([(a, y - 13), (max(b, a + 2), y - 13)], T["strong"], 2)
        c.text(W, y - 13, f"{u.deg(lo)} / {u.deg(hi)}", size=12.5, color="text", anchor="end")
        if k != ks[-1]:
            hair(c, T, y, W)
    c.h = y + 6
    return node(m, "mo:days", c)


# ---- now

def details(m, W):
    M = m.model
    T = tones(m)
    k = M.today()
    rise, sset = M.sun(k)
    rain = M.h("precipitation_probability", M.hour_now()) or 0
    rows = [("Precipitation", f"{rain}%"),
            ("Humidity", f"{round(M.cur('relative_humidity_2m') or 0)}%"),
            ("Wind speed", f"{u.wind(M.cur('wind_speed_10m'))}  {u.compass(M.cur('wind_direction_10m'))}"),
            ("Feels like", u.deg(M.cur("apparent_temperature"))),
            ("Pressure", u.pressure(M.cur("pressure_msl"))),
            ("Visibility", u.dist(M.cur("visibility"))),
            ("UV index", f"{round(M.cur('uv_index') or 0)}  {sky.uv_name(M.cur('uv_index'))}"),
            ("Sunrise", m.clock(rise)), ("Sunset", m.clock(sset))]
    c = Canvas(W)
    y = section(c, 8, "Now", W)
    for j, (lab, val) in enumerate(rows):
        y += 24
        c.text(0, y - 12, lab, size=12.5, color="text")
        c.text(W, y - 12, val, size=12.5, color="text", anchor="end")
        if j < len(rows) - 1:
            hair(c, T, y, W)
    c.h = y + 4
    return node(m, "mo:now", c)


def precip(m, W):
    """The next 24 hours as thin bars: the amount, or the chance when dry."""
    M = m.model
    T = tones(m)
    start = M.hour_now()
    idx = list(range(start, min(start + 24, len(M.times))))
    mm = [u.p(v) or 0 for v in M.hs("precipitation", idx)]
    prob = [v or 0 for v in M.hs("precipitation_probability", idx)]
    wet = sum(mm) > 0.05
    vals = mm if wet else prob
    top = max(vals) if wet else 100
    c = Canvas(W)
    y = section(c, 8, "Precipitation", W)
    c.text(W, 8, f"{u.precip(sum(v or 0 for v in M.hs('precipitation', idx)))} in 24 h" if wet else
           "Chance of rain, next 24 h", size=10, color="dim", anchor="end")
    y0, y1 = y + 6, y + 76
    n = len(vals)
    step = W / max(1, n)
    for j, v in enumerate(vals):
        x = step * j + step / 2
        h = max(2, (y1 - y0) * (v / (top or 1)))
        c.line([(x, y1), (x, y1 - h)], T["strong"] if v else T["track"], 2)
        if j % 3 == 0:
            c.text(x, y1 + 12, f"{M.times[idx[j]].hour:02d}" if m.settings["clock24"] else
                   m.hour_label(M.times[idx[j]]).replace(" ", ""), size=9.5, color="dim", anchor="center")
    c.h = y1 + 22
    return node(m, "mo:precip", c)


def wind(m, W):
    """The next hours as columns: time, temperature, arrow, speed."""
    M = m.model
    T = tones(m)
    start = M.hour_now()
    count = 8 if W >= 440 else 6
    idx = list(range(start, min(start + count * 2, len(M.times)), 2))
    c = Canvas(W)
    y = section(c, 8, "Wind", W)
    c.text(W, 8, u.label("wind"), size=10, color="dim", anchor="end")
    cw = W / len(idx)
    for j, i in enumerate(idx):
        x = cw * j + cw / 2
        c.text(x, y + 8, "Now" if j == 0 else f"{M.times[i].hour:02d}" if m.settings["clock24"] else
               m.hour_label(M.times[i]).replace(" ", ""), size=10.5, color="dim", anchor="center")
        c.text(x, y + 28, u.deg(M.h("temperature_2m", i)), size=12.5, color="text", anchor="center")
        d = M.h("wind_direction_10m", i)
        if d is not None:
            tmp = Canvas(W)
            sky.arrow(tmp, x, y + 52, 16, d + 180, T["strong"], 1.4)
            c.add(tmp.shapes)
        c.text(x, y + 76, u.wind(M.h("wind_speed_10m", i), False), size=12.5, color="text", anchor="center")
        c.text(x, y + 92, f"gust {u.wind(M.h('wind_gusts_10m', i), False)}", size=9, color="dim", anchor="center")
    c.h = y + 102
    return node(m, "mo:wind", c)


# ---- air and pollen

LIMITS = {"pm2_5": 25, "pm10": 50, "ozone": 120, "nitrogen_dioxide": 40, "sulphur_dioxide": 125,
          "carbon_monoxide": 4000}
NAMES = [("pm2_5", "PM2.5", "Fine particulate matter"), ("pm10", "PM10", "Particulate matter"),
         ("ozone", "O₃", "Ozone"), ("nitrogen_dioxide", "NO₂", "Nitrogen dioxide"),
         ("sulphur_dioxide", "SO₂", "Sulphur dioxide"), ("carbon_monoxide", "CO", "Carbon monoxide")]


def air(m, W):
    M = m.model
    T = tones(m)
    std = m.aqi_standard()
    v = M.aq_now(std)
    cur = (M.aq or {}).get("current") or {}
    c = Canvas(W)
    y = section(c, 8, "Air quality", W)
    if v is None:
        c.text(0, y + 10, "Not available here.", size=12.5, color="dim")
        c.h = y + 24
        return node(m, "mo:air", c)
    name, _ = sky.aqi_info(v, std)
    c.text(W / 2, y + 30, str(round(v)), size=40, color="text", anchor="center")
    c.text(W / 2, y + 62, f"{name} · {'US AQI' if std == 'us' else 'European AQI'}", size=11.5, color="dim",
           anchor="center")
    # one thin bar per pollutant, its height against the health limit
    by0, by1 = y + 86, y + 146
    cw = W / len(NAMES)
    for j, (key, short, _) in enumerate(NAMES):
        x = cw * j + cw / 2
        val = cur.get(key)
        frac = min(1.0, (val or 0) / LIMITS[key])
        c.line([(x, by1), (x, by0)], T["track"], 2)
        c.line([(x, by1), (x, by1 - max(2, (by1 - by0) * frac))], T["strong"], 2)
        c.text(x, by1 + 12, short, size=9.5, color="dim", anchor="center")
    # the scale with a marker, in grey
    sy = by1 + 34
    stops, vmax = sky.aqi_stops(std)
    c.line([(0, sy), (W, sy)], T["track"], 2)
    for lim, _, _ in (sky.US_AQI if std == "us" else sky.EU_AQI)[:-1]:
        x = W * min(1, lim / vmax)
        c.line([(x, sy - 3), (x, sy + 3)], T["soft"], 1)
    mx = W * min(1, v / vmax)
    c.circle(mx, sy, 5, fill=T["strong"])
    y = sy + 18
    main = max(NAMES[:4], key=lambda p: (cur.get(p[0]) or 0) / LIMITS[p[0]])
    rows = [("Dominant pollutant", main[2])] + [(long, f"{round(cur.get(key) or 0)} µg/m³") for key, _, long in NAMES
                                                if cur.get(key) is not None]
    for j, (lab, val) in enumerate(rows):
        y += 24
        c.text(0, y - 12, lab, size=12, color="text")
        c.text(W, y - 12, val, size=12, color="text", anchor="end")
        if j < len(rows) - 1:
            hair(c, T, y, W)
    c.h = y + 4
    return node(m, "mo:air", c)


POLLEN = [("alder_pollen", "Alder"), ("birch_pollen", "Birch"), ("grass_pollen", "Grass"),
          ("mugwort_pollen", "Mugwort"), ("olive_pollen", "Olive"), ("ragweed_pollen", "Ragweed")]


def pollen_level(v):
    """grains/m³ -> (0..5, words)."""
    if v is None:
        return None, "–"
    for lim, n, word in ((0.5, 0, "None"), (10, 1, "Very low"), (30, 2, "Low"), (100, 3, "Moderate"), (300, 4, "High")):
        if v < lim:
            return n, word
    return 5, "Very high"


def pollen(m, W):
    M = m.model
    T = tones(m)
    cur = (M.aq or {}).get("current") or {}
    c = Canvas(W)
    y = section(c, 8, "Pollen", W)
    have = [(lab, cur.get(key)) for key, lab in POLLEN if cur.get(key) is not None]
    if not have:
        c.text(0, y + 10, "Pollen forecasts only cover Europe.", size=12.5, color="dim")
        c.h = y + 24
        return node(m, "mo:pollen", c)
    worst = max(pollen_level(v)[0] for _, v in have)
    c.text(W, 8, f"{worst}/5", size=10, color="dim", anchor="end")
    for j, (lab, v) in enumerate(have):
        y += 26
        n, word = pollen_level(v)
        c.text(0, y - 13, lab, size=12.5, color="text")
        for d in range(5):  # five dots
            c.circle(W - 160 + d * 12, y - 13, 3.2, fill=T["strong"] if d < n else T["track"])
        c.text(W, y - 13, word, size=12, color="text" if n else "dim", anchor="end")
        if j < len(have) - 1:
            hair(c, T, y, W)
    c.h = y + 4
    return node(m, "mo:pollen", c)


# ---- what to wear

def outfit_for(feels, rain, wind_kmh, uv):
    """(icon, top length, thickness, outerwear, extra)."""
    if feels < 0:
        top = ("coat-hanger", "Long", "Warm", "Winter coat")
    elif feels < 8:
        top = ("coat-hanger", "Long", "Thick", "Warm jacket")
    elif feels < 14:
        top = ("hoodie", "Long", "Medium", "Light jacket")
    elif feels < 20:
        top = ("hoodie", "Long", "Light", "None")
    else:
        top = ("t-shirt", "Short", "Light", "None")
    extra = ("Umbrella" if rain >= 50 else "Hat and gloves" if feels < 2 else
             "Sunglasses" if uv >= 5 else "Windproof layer" if wind_kmh >= 35 else "None")
    return top + (extra,)


def outfit(m, W):
    M = m.model
    T = tones(m)
    start = M.hour_now()
    idx = list(range(start, min(start + 6, len(M.times))))
    feels = M.cur("apparent_temperature") or 0
    rain = max([v or 0 for v in M.hs("precipitation_probability", idx)] or [0])
    icon, length, thick, outer, extra = outfit_for(feels, rain, M.cur("wind_speed_10m") or 0,
                                                   max([v or 0 for v in M.hs("uv_index", idx)] or [0]))
    c = Canvas(W)
    y = section(c, 8, "What to wear", W)
    c.glyph(W / 2, y + 36, icon, 46, "text", False)
    c.text(W / 2, y + 76, f"Feels {u.deg(feels)}", size=12, color="dim", anchor="center")
    y += 92
    rows = [("Length", length), ("Thickness", thick), ("Outerwear", outer), ("Take", extra)]
    for j, (lab, val) in enumerate(rows):
        y += 24
        c.text(0, y - 12, lab, size=12.5, color="text")
        c.text(W, y - 12, val, size=12.5, color="text", anchor="end")
        hair(c, T, y, W)
    # through the day
    later = list(range(start, min(start + 18, len(M.times)), 3))
    cw = W / max(1, len(later))
    y += 10
    for j, i in enumerate(later):
        x = cw * j + cw / 2
        f = M.h("apparent_temperature", i) or 0
        ic = outfit_for(f, M.h("precipitation_probability", i) or 0, M.h("wind_speed_10m", i) or 0,
                        M.h("uv_index", i) or 0)[0]
        c.text(x, y + 8, "Now" if j == 0 else f"{M.times[i].hour:02d}" if m.settings["clock24"] else
               m.hour_label(M.times[i]).replace(" ", ""), size=10, color="dim", anchor="center")
        c.glyph(x, y + 30, ic, 18, "text", False)
        c.text(x, y + 52, u.deg(f), size=11.5, color="text", anchor="center")
    c.h = y + 62
    return node(m, "mo:outfit", c)


def view(m, footer):
    W = m.page_w - 14  # room for the scrollbar
    parts = [hero(m, W), hours(m, W), days(m, W), fenn.spacer(6), details(m, W), fenn.spacer(6), precip(m, W),
             fenn.spacer(6), wind(m, W), fenn.spacer(6), air(m, W), fenn.spacer(6), pollen(m, W), fenn.spacer(6),
             outfit(m, W)]
    return fenn.column(parts + footer, gap=10, scroll=True, id="mono")


def click(m, head, arg, extra, x):
    pass
