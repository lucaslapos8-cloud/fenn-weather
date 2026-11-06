"""The "Glossy" look (the default): 3D icons on Fenn's own glass.

Top: today's card with the sunrise / day length / sunset bar, rain,
humidity and wind, and the next 7 days or hours. Under it:

- Overview: one chart with Temperature / Rain / Humidity / Wind tabs for
  the next 24 hours or 7 days; click a point to see its value in a bubble.
- Today's highlights: tiles with 3D icons (wind, humidity, UV, visibility,
  feels like, rain today, clouds, sunrise, sunset).
- Should I go outside?: umbrella, sun protection, what to wear and a
  verdict for the next 8 hours.
- Air quality: the index on its color scale, the next 24 hours as a line,
  and the main pollutants.
- Your places: the saved places with their weather; open one with a click.

`m` is main.py."""

import math
import os
from datetime import timedelta

import fenn
import sky
import units as u
import wx
from ui import Canvas, fit, nice_range, scale_color, tw

GAP = 6
ACCENT = "#6EA8FF"
WARM = "#FFB547"
RAIN = "#5BC8FF"


def icon(name, small=False):
    return os.path.join("icons", "sm" if small else "lg", name + ".png")


def now_info(M):
    code = M.cur("weather_code")
    day = M.is_day()
    return {"temp": M.cur("temperature_2m"), "feels": M.cur("apparent_temperature"),
            "humidity": M.cur("relative_humidity_2m"), "wind": M.cur("wind_speed_10m"), "code": code, "day": day,
            "text": wx.condition(code, day), "icon": wx.icon_name(code, day)}


def tile(m, size):
    M = m.model
    n = now_info(M)
    k = M.today()
    if size == "small":
        return fenn.column([fenn.image(icon(n["icon"], True), width=24, height=24),
                            fenn.text(u.deg(n["temp"]), size="small", bold=True)], gap=0, align="center", justify="center")
    if size == "large":
        return fenn.column([
            fenn.text(m.settings["place"]["name"] if m.settings["place"] else "", size="small", color="dim"),
            fenn.row([fenn.text(u.deg(n["temp"]), size="big"), fenn.spacer(), fenn.image(icon(n["icon"]), width=40, height=40)], gap=4),
            fenn.text(n["text"], size="small"),
            fenn.text(f"H {u.deg(M.d('temperature_2m_max', k))}  L {u.deg(M.d('temperature_2m_min', k))}", size="small", color="dim"),
        ], gap=2)
    return fenn.row([fenn.image(icon(n["icon"], True), width=30, height=30),
                     fenn.column([fenn.text(u.deg(n["temp"]), size="title"), fenn.text(n["text"], size="small", color="dim")], gap=0)],
                    gap=6, align="center")


def node(m, cid, c):
    """A clickable canvas: remembered so main.py can hit-test its regions."""
    m.canvases[cid] = c
    return fenn.canvas(c.h, c.shapes, width=c.w, id=cid)


def tones(m):
    """Glass, lines and tints that read in Fenn's dark and light themes."""
    if m.app.dark:
        return {"glass": "#FFFFFF0F", "rim": "#FFFFFF12", "well": "#0000002E", "on": "#FFFFFF26",
                "grid": "#FFFFFF16", "halo": "#00000066"}
    return {"glass": "#FFFFFF8C", "rim": "#0000000F", "well": "#0000000C", "on": "#FFFFFFFF",
            "grid": "#00000014", "halo": "#FFFFFFCC"}


# ---- top: today, rain / humidity / wind, the next 7 days or hours

def hero(m):
    M = m.model
    n = now_info(M)
    k = M.today()
    inner = m.page_w - 24
    img = 84
    cw = inner - img - 12
    now = M.now()
    title = f"{n['text']} {u.deg(n['temp'])}{u.label('temp')[1:]}"
    place = wx.place_line(m.settings["place"]) if m.settings["place"] else ""
    hi_lo = f"H {u.deg(M.d('temperature_2m_max', k))}   L {u.deg(M.d('temperature_2m_min', k))}"
    feels = f"Feels like {u.deg(n['feels'])}"
    side = max(tw(hi_lo, 12), tw(feels, 12)) + 14
    c = Canvas(cw)
    c.h = img
    c.shapes = [
        fenn.label(0, 14, now.strftime("%A") + ", " + m.clock(now), size=12, color="dim"),
        fenn.label(0, 43, fit(title, 25, cw - side), size=25, bold=True, color="text"),
        fenn.label(0, 71, fit(place, 14, cw - side), size=14, color="dim"),
        fenn.label(cw, 14, hi_lo, size=12, color="dim", anchor="end"),
        fenn.label(cw, 71, feels, size=12, color="faint", anchor="end"),
    ]
    c.region(0, 0, cw, img, "ovtab:temp")
    top = fenn.row([fenn.image(icon(n["icon"]), width=img, height=img), node(m, "g:hero", c)], gap=12)
    return fenn.card([top, sun_bar(m, inner, k)], padding=12, gap=8)


def dashes(x0, x1, y, color, dash=5, gap=5, width=1.2):
    out, x = [], x0
    while x + dash <= x1:
        out.append(fenn.line([(x, y), (x + dash, y)], color=color, width=width))
        x += dash + gap
    return out


def sun_bar(m, w, k):
    M = m.model
    rise, sset = M.sun(k)
    secs = int(M.d("daylight_duration", k) or (sset - rise).total_seconds())
    length = f"{secs // 3600} h {secs % 3600 // 60} m"
    a, b = m.clock(rise), m.clock(sset)
    h, y = 34, 17
    shapes = [
        fenn.rect(0, 0, w, h, fill="#00000052" if m.app.dark else "#0000000F", radius=17),
        fenn.glyph(20, y, "sun-horizon", size=17, color="#FFB547"),
        fenn.label(36, y, a, size=13, color="text"),
        fenn.label(w / 2, y, length, size=13, color="dim", anchor="center"),
        fenn.label(w - 36, y, b, size=13, color="text", anchor="end"),
        fenn.glyph(w - 20, y, "moon", size=15, color="#B9C2FF"),
    ]
    mid = tw(length, 13) / 2 + 12
    shapes += dashes(36 + tw(a, 13) + 12, w / 2 - mid, y, "faint")
    shapes += dashes(w / 2 + mid, w - 36 - tw(b, 13) - 12, y, "faint")
    return fenn.canvas(h, shapes, width=w)


def stats(m):
    """Rain, humidity and wind now; each switches the Overview chart."""
    M = m.model
    n = now_info(M)
    rain = M.d("precipitation_probability_max", M.today())
    w, h, y = m.page_w, 32, 16
    c = Canvas(w)
    c.h = h

    def pair(x, label, value, anchor="start"):
        lw, vw = tw(label, 13), tw(value, 13)
        if anchor == "end":
            x -= lw + 4 + vw
        elif anchor == "center":
            x -= (lw + 4 + vw) / 2
        return [fenn.label(x, y, label, size=13, color="dim"), fenn.label(x + lw + 4, y, value, size=13, color="text")], x, lw + 4 + vw

    rs, _, rw = pair(34, "Rain:", f"{rain or 0}%")
    c.shapes = [fenn.rect(0, 0, 34 + rw + 14, h, fill="#FFFFFF14" if m.app.dark else "#0000000C", radius=16),
                fenn.glyph(18, y, "drop", size=15, color=RAIN, fill=True)] + rs
    c.region(0, 0, 34 + rw + 14, h, "ovtab:rain")
    hs, hx, hw = pair(w / 2 + 10, "Humidity:", f"{round(n['humidity'] or 0)}%", "center")
    c.shapes += hs
    c.region(hx - 10, 0, hx + hw + 10, h, "ovtab:humidity")
    ws, wx0, _ = pair(w - 2, "Wind:", u.wind(n["wind"]), "end")
    c.shapes += ws
    c.region(wx0 - 10, 0, w, h, "ovtab:wind")
    return node(m, "g:stats", c)


def picked_day(m):
    """The day picked in the strip (today unless one was clicked)."""
    M = m.model
    k = m.state.get("g_day")
    return k if k is not None and M.today() <= k < len(M.days) else M.today()


def strip(m):
    """The next 7 days or hours. Their name and temperatures are clickable
    (Fenn can't click a whole card): a day shows in the Overview, an hour is
    picked in it."""
    M = m.model
    cells = []
    if m.settings["strip"] == "hours":
        n = now_info(M)
        start = M.hour_now()
        hourly = m.state.get("ov_range", "24h") == "24h" and picked_day(m) == M.today()
        sel = m.state.get("ov_sel", 0) if hourly else -1
        for k, i in enumerate(range(start, min(start + 7, len(M.times)))):
            rain = M.h("precipitation_probability", i) or 0
            temp, code, day = (n["temp"], n["code"], n["day"]) if k == 0 else \
                (M.h("temperature_2m", i), M.h("weather_code", i), bool(M.h("is_day", i)))
            cells.append(cell(m, f"ghour:{k}", "Now" if k == 0 else m.hour_label(M.times[i]),
                              icon(wx.icon_name(code, day), True), u.deg(temp), f"{rain}%" if rain >= 10 else " ",
                              k == sel, RAIN))
    else:
        start = M.today()
        pick = picked_day(m)
        for k in range(start, min(start + 7, len(M.days))):
            cells.append(cell(m, f"gday:{k}", "Today" if k == start else M.day_date(k).strftime("%a"),
                              icon(wx.icon_name(M.d("weather_code", k), True), True),
                              u.deg(M.d("temperature_2m_max", k)), u.deg(M.d("temperature_2m_min", k)), k == pick))
    return fenn.grid(len(cells) or 1, cells, gap=GAP)


def cell(m, cid, top, image, big, small, selected=False, small_color="dim"):
    """One day or hour. Fenn can't click a card, so an invisible clickable
    canvas is laid over the whole cell (a negative gap stacks it on top)."""
    cw = (m.page_w - GAP * 6) / 7
    head = fenn.canvas(25, [fenn.label(cw / 2, 16, top, size=11.5, color="text" if selected else "dim",
                                       anchor="center", bold=selected)], width=cw)
    foot = fenn.canvas(45, [fenn.label(cw / 2, 10, big, size=13.5, color="text", anchor="center", bold=True),
                            fenn.label(cw / 2, 29, small, size=11, color=small_color, anchor="center")], width=cw)
    body = fenn.column([head, fenn.image(image, width=34, height=34), foot], gap=3, align="center")
    height = 25 + 3 + 34 + 3 + 45
    hit = fenn.canvas(height, [], width=cw, id=cid, tooltip="Show in the overview")
    inner = fenn.card([fenn.column([body, hit], gap=-height)], padding=0, gap=0)
    return fenn.card([inner], padding=0) if selected else inner


# ---- Overview chart

TABS = [("temp", "Temperature"), ("rain", "Rain"), ("humidity", "Humidity"), ("wind", "Wind")]
RANGES = [("24h", "24 hours"), ("7d", "7 days")]


def smooth(pts, steps=8):
    """A Catmull-Rom curve through the points."""
    if len(pts) < 3:
        return pts
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(0, i - 1)], pts[i], pts[i + 1]
        p3 = pts[min(len(pts) - 1, i + 2)]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    out.append(pts[-1])
    return out


def segmented(c, m, x, y, items, current, action, size=11):
    """A segmented control; returns its width."""
    T = tones(m)
    widths = [tw(lab, size, True) + 20 for _, lab in items]
    total = sum(widths) + 6
    c.rect(x, y, total, 26, fill=T["well"], radius=13)
    px = x + 3
    for (key, lab), wd in zip(items, widths):
        on = key == current
        if on:
            c.rect(px, y + 3, wd, 20, fill=T["on"], radius=10)
        c.text(px + wd / 2, y + 13, lab, size=size, color="text" if on else "dim", anchor="center", bold=True)
        c.region(px, y, px + wd, y + 26, f"{action}:{key}")
        px += wd
    return total


def hours_shown(m):
    """The hours the 24-hour chart shows: from now for today, else the
    picked day from midnight to midnight."""
    M = m.model
    k = picked_day(m)
    if k == M.today():
        start = M.hour_now()
        return list(range(start, min(start + 25, len(M.times))))
    hours = M.day_hours(k)
    return hours + ([hours[-1] + 1] if hours and hours[-1] + 1 < len(M.times) else [])


def series(m, tab, rng):
    """(labels, x tick labels, lines, bars, caption(i), bubble(i)) for the chart."""
    M = m.model
    if rng == "24h":
        idx = hours_shown(m)
        live = idx[0] == M.hour_now()  # starts now (today): the first point is the current weather
        times = [M.times[i] for i in idx]
        ticks = [("Now" if live else m.hour_label(t)) if n == 0 else m.hour_label(t) if n % 4 == 0 else ""
                 for n, t in enumerate(times)]
        when = lambda n: ("Now" if n == 0 and live else
                          f"{M.day_name(M.days.index(times[n].strftime('%Y-%m-%d')))} {m.clock(times[n])}")
        cond = lambda n: wx.condition(M.h("weather_code", idx[n]), bool(M.h("is_day", idx[n])))
        if tab == "temp":
            temps = ([M.cur("temperature_2m")] + M.hs("temperature_2m", idx[1:])) if live else M.hs("temperature_2m", idx)
            return ticks, [(([u.t(v) for v in temps]), ACCENT, True)], None, \
                lambda n: f"{when(n)} · {cond(n)} · feels {u.deg(M.h('apparent_temperature', idx[n]))}", \
                lambda n: u.deg(temps[n])
        if tab == "rain":
            probs = M.hs("precipitation_probability", idx)
            return ticks, [], probs, \
                lambda n: f"{when(n)} · {u.precip(M.h('precipitation', idx[n]))}" + \
                (" of snow" if (M.h("snowfall", idx[n]) or 0) > 0 else ""), \
                lambda n: f"{probs[n] or 0}%"
        if tab == "humidity":
            hum = M.hs("relative_humidity_2m", idx)
            return ticks, [(hum, "#7FD6FF", True)], None, \
                lambda n: f"{when(n)} · dew point {u.deg(M.h('dew_point_2m', idx[n]))}", \
                lambda n: f"{hum[n] or 0}%"
        speed = [u.w(v) for v in M.hs("wind_speed_10m", idx)]
        gust = [u.w(v) for v in M.hs("wind_gusts_10m", idx)]
        dirs = M.hs("wind_direction_10m", idx)
        return ticks, [(speed, "#8FE3C0", True), (gust, "#8FE3C066", False)], None, \
            lambda n: f"{when(n)} · from {u.compass(dirs[n])} · gusts {u.wind(M.h('wind_gusts_10m', idx[n]))}", \
            lambda n: u.wind(M.h("wind_speed_10m", idx[n]))
    ks = list(range(M.today(), min(M.today() + 7, len(M.days))))
    ticks = [M.day_name(k) for k in ks]
    when = lambda n: M.day_name(ks[n], False)
    cond = lambda n: wx.condition(M.d("weather_code", ks[n]))
    if tab == "temp":
        hi = [u.t(M.d("temperature_2m_max", k)) for k in ks]
        lo = [u.t(M.d("temperature_2m_min", k)) for k in ks]
        return ticks, [(hi, WARM, True), (lo, ACCENT, False)], None, \
            lambda n: f"{when(n)} · {cond(n)}", \
            lambda n: f"{u.deg(M.d('temperature_2m_max', ks[n]))} / {u.deg(M.d('temperature_2m_min', ks[n]))}"
    if tab == "rain":
        probs = [M.d("precipitation_probability_max", k) for k in ks]
        return ticks, [], probs, \
            lambda n: f"{when(n)} · {u.precip(M.d('precipitation_sum', ks[n]))} in {round(M.d('precipitation_hours', ks[n]) or 0)} h", \
            lambda n: f"{probs[n] or 0}%"
    if tab == "humidity":
        hum = []
        for k in ks:
            v = [x for x in M.hs("relative_humidity_2m", M.day_hours(k)) if x is not None]
            hum.append(round(sum(v) / len(v)) if v else None)
        return ticks, [(hum, "#7FD6FF", True)], None, \
            lambda n: f"{when(n)} · average humidity", lambda n: f"{hum[n] or 0}%"
    speed = [u.w(M.d("wind_speed_10m_max", k)) for k in ks]
    gust = [u.w(M.d("wind_gusts_10m_max", k)) for k in ks]
    return ticks, [(speed, "#8FE3C0", True), (gust, "#8FE3C066", False)], None, \
        lambda n: f"{when(n)} · mostly from {u.compass(M.d('wind_direction_10m_dominant', ks[n]))} · gusts {u.wind(M.d('wind_gusts_10m_max', ks[n]))}", \
        lambda n: u.wind(M.d("wind_speed_10m_max", ks[n]))


def overview(m):
    st = m.state
    tab, rng = st.get("ov_tab", "temp"), st.get("ov_range", "24h")
    T = tones(m)
    W = m.page_w
    H = 240
    c = Canvas(W)
    c.h = H
    c.rect(0, 0, W, H, fill=T["glass"], radius=16, stroke=T["rim"])
    c.text(16, 22, "Overview", size=17, color="text", bold=True)
    k = picked_day(m)
    if rng == "24h" and k != m.model.today():
        c.text(16 + tw("Overview", 17, True) + 10, 23, f"\u00b7 {m.model.day_name(k, False)}", size=14, color="dim", bold=True)
        c.text(16 + tw("Overview", 17, True) + 10 + tw(f"\u00b7 {m.model.day_name(k, False)}", 14, True) + 10, 23,
               "\u00d7 Today", size=11, color="faint", bold=True)
        tx = 16 + tw("Overview", 17, True) + 10 + tw(f"\u00b7 {m.model.day_name(k, False)}", 14, True) + 6
        c.region(tx, 10, tx + tw("\u00d7 Today", 11, True) + 10, 36, "gtoday")
    rw = sum(tw(lab, 11, True) + 20 for _, lab in RANGES) + 6
    segmented(c, m, W - 12 - rw, 9, RANGES, rng, "ovrange")
    segmented(c, m, 12, 42, TABS, tab, "ovtab")

    ticks, lines, bars, caption, bubble = series(m, tab, rng)
    n = len(ticks)
    sel = max(0, min(st.get("ov_sel", 0), n - 1))
    x0, x1 = 44, W - 22
    top, y1 = 112, H - 32       # the plot; the bubble rises above `top`
    if rng == "7d":  # days sit in the middle of equal slots
        slot = (x1 - x0) / n
        X = lambda i: x0 + slot * (i + 0.5)
    else:
        X = lambda i: x0 + (x1 - x0) * i / max(1, n - 1)
    if bars is not None or tab == "humidity":
        lo, hi, grid = 0, 100, [0, 25, 50, 75, 100]
        fmt = lambda v: f"{round(v)}%"
    else:
        vals = [v for vs, _, _ in lines for v in vs if v is not None]
        lo, hi, grid = nice_range(min(vals), max(vals), 4, floor_zero=tab == "wind")
        fmt = lambda v: f"{round(v)}°" if tab == "temp" else f"{round(v)}"
    Y = lambda v: y1 - (v - lo) / ((hi - lo) or 1) * (y1 - top)
    for g in grid:
        c.add(dashes(x0, x1, Y(g), T["grid"], 4, 4, 1))
        c.text(x0 - 8, Y(g), fmt(g), size=10, color="faint", anchor="end")
    for i, lab in enumerate(ticks):
        if lab and (rng == "7d" or i % 4 == 0):
            c.text(X(i), y1 + 16, lab, size=10, color="text" if i == sel else "faint", anchor="center", bold=i == sel)
    # bars (rain chance)
    if bars is not None:
        bw = max(4, (x1 - x0) / n * (0.5 if rng == "7d" else 0.55))
        for i, v in enumerate(bars):
            v = v or 0
            c.rect(X(i) - bw / 2, top, bw, y1 - top, fill=T["well"], radius=min(4, bw / 2))
            if v > 0:
                bh = max(3, (y1 - top) * v / 100)
                c.rect(X(i) - bw / 2, y1 - bh, bw, bh, fill=RAIN if i == sel else RAIN + "99", radius=min(4, bw / 2))
    # lines: a soft fill under the main one, a glow, then the line
    for vs, color, main in lines:
        pts = [(X(i), Y(v)) for i, v in enumerate(vs) if v is not None]
        curve = smooth(pts)
        if main:
            base = color[:7]
            for depth, alpha in ((y1, "10"), (22, "12"), (10, "14")):
                for (ax, ay), (bx, by) in zip(curve, curve[1:]):
                    ya, yb = (y1, y1) if depth == y1 else (min(ay + depth, y1), min(by + depth, y1))
                    c.shapes.append(fenn.polygon([(ax, ay), (bx, by), (bx, yb), (ax, ya)], fill=base + alpha))
            c.line(curve, base + "40", 6)
        c.line(curve, color, 2.4 if main else 1.6)
    if tab == "wind" and rng == "24h":
        dirs = m.model.hs("wind_direction_10m", hours_shown(m))
        for i in range(0, n, 3):
            if dirs[i] is not None:
                sky.arrow(c, X(i), top - 2, 11, dirs[i] + 180, "dim", 1.5)
    # the picked point: a line, a dot and the value in a bubble
    sx = X(sel)
    yy = top - 6
    while yy < y1:
        c.line([(sx, yy), (sx, min(y1, yy + 3))], "#FFFFFF55" if m.app.dark else "#00000040", 1.2)
        yy += 6
    anchor_y = top
    if lines:
        v = lines[0][0][sel]
        if v is not None:
            anchor_y = Y(v)
            c.circle(sx, anchor_y, 7, fill=T["halo"])
            c.circle(sx, anchor_y, 5, fill="#FFFFFF")
            c.circle(sx, anchor_y, 3, fill=lines[0][1][:7])
    elif bars is not None:
        anchor_y = y1 - max(3, (y1 - top) * (bars[sel] or 0) / 100)
    label = bubble(sel)
    bwid = tw(label, 12, True) + 22
    bx = min(max(sx - bwid / 2, 8), W - 8 - bwid)
    by = max(74, anchor_y - 36)
    c.rect(bx, by, bwid, 24, fill="#4C8DFF", radius=12)
    c.shapes.append(fenn.polygon([(sx - 5, by + 23), (sx + 5, by + 23), (sx, by + 29)], fill="#4C8DFF"))
    c.text(bx + bwid / 2, by + 12, label, size=12, color="#FFFFFF", anchor="center", bold=True)
    # what the point is
    segw = sum(tw(lab, 11, True) + 20 for _, lab in TABS) + 6
    c.text(W - 16, 55, fit(caption(sel), 11, W - 16 - 12 - segw - 14), size=11, color="dim", anchor="end")
    c.region(x0 - 14, top - 40, x1 + 14, y1 + 26, "ovpick", x0=X(0), x1=X(n - 1), n=n)
    return node(m, "g:overview", c)


# ---- Today's highlights

def ago(m, t):
    """'in 2 h 10 min' or '3 h ago'."""
    d = (t - m.model.now()).total_seconds()
    mins = abs(int(d // 60)) if d >= 0 else abs(int(-d // 60))
    text = f"{mins // 60} h {mins % 60} min" if mins >= 60 else f"{mins} min"
    return f"in {text}" if d >= 0 else f"{text} ago"


def highlight(name, title, value, caption):
    return fenn.card([fenn.row([
        fenn.image(icon(name, True), width=38, height=38),
        fenn.column([fenn.text(title, size="small", color="dim"), fenn.text(value, size="title"),
                     fenn.text(caption, size="small", color="faint")], gap=1),
    ], gap=8)], padding=10)


def highlights(m):
    M = m.model
    k = M.today()
    rise, sset = M.sun(k)
    nxt = M.sun(min(k + 1, len(M.days) - 1))[0]
    kmh = M.cur("wind_speed_10m") or 0
    uv = M.cur("uv_index") or 0
    idx = M.day_hours(k)
    uvs = M.hs("uv_index", idx)
    strong = [M.times[i] for i, v in zip(idx, uvs) if (v or 0) >= 3]
    uv_note = f"Protect {m.clock(strong[0])}–{m.clock(strong[-1] + timedelta(hours=1))}" if strong else "No protection needed"
    feels, actual = M.cur("apparent_temperature"), M.cur("temperature_2m")
    diff = None if feels is None or actual is None else feels - actual
    clouds = M.cur("cloud_cover")
    tiles = [
        highlight("wind", "Wind", u.wind(kmh), f"{u.compass(M.cur('wind_direction_10m'))} · {u.BEAUFORT_NAMES[u.beaufort(kmh)]}"),
        highlight("drop", "Humidity", f"{round(M.cur('relative_humidity_2m') or 0)}%", f"Dew point {u.deg(M.cur('dew_point_2m'))}"),
        highlight("clear-day", "UV index", f"{round(uv)} {sky.uv_name(uv)}", uv_note),
        highlight("fog", "Visibility", u.dist(M.cur("visibility")), sky.visibility_words(M.cur("visibility")).rstrip(".")),
        highlight("thermometer", "Feels like", u.deg(feels),
                  "Same as actual" if diff is None or abs(diff) < 1.5 else
                  f"{round(abs(u.t_delta(diff)))}° {'warmer' if diff > 0 else 'colder'}"),
        highlight("umbrella", "Rain today", u.precip(M.d("precipitation_sum", k)),
                  f"{M.d('precipitation_probability_max', k) or 0}% chance"),
        highlight("cloudy", "Clouds", "–" if clouds is None else f"{round(clouds)}%",
                  "Clear" if (clouds or 0) < 15 else "Some clouds" if clouds < 50 else "Mostly cloudy" if clouds < 85 else "Overcast"),
        highlight("sunrise", "Sunrise", m.clock(rise if M.now() < rise else nxt), ago(m, rise if M.now() < rise else nxt)),
        highlight("sunset", "Sunset", m.clock(sset), ago(m, sset)),
    ]
    return [fenn.text("Today's highlights", bold=True), fenn.grid(3, tiles, gap=8)]


# ---- Should I go outside?

def outside(m):
    M = m.model
    start = M.hour_now()
    idx = list(range(start, min(start + 8, len(M.times))))
    prob = max([v or 0 for v in M.hs("precipitation_probability", idx)] or [0])
    mm = sum(v or 0 for v in M.hs("precipitation", idx))
    snow = sum(v or 0 for v in M.hs("snowfall", idx)) > 0
    feels = [v for v in M.hs("apparent_temperature", idx) if v is not None] or [M.cur("apparent_temperature") or 0]
    gust = max([v or 0 for v in M.hs("wind_gusts_10m", idx)] or [0])
    uv = max([v or 0 for v in M.hs("uv_index", idx)] or [0])
    storm = any((c or 0) >= 95 for c in M.hs("weather_code", idx))
    cold = min(feels)
    if storm or gust >= 65 or (prob >= 80 and mm >= 5):
        verdict, color = "Better stay in", "#FF7A6B"
    elif prob >= 40 or mm >= 0.5:
        verdict, color = ("Yes, but dress for snow" if snow else "Yes, but take an umbrella"), "#FFC24B"
    elif cold < -5:
        verdict, color = "Yes, wrap up warm", "#7FD6FF"
    elif uv >= 6:
        verdict, color = "Yes, with sun protection", "#FFC24B"
    else:
        verdict, color = "Yes, it's a good time to go out", "#6FDB8B"
    umbrella = "Take one" if prob >= 50 or mm >= 0.5 else "Maybe" if prob >= 25 else "Not needed"
    hi_idx = [i for i in idx if (M.h("uv_index", i) or 0) >= 3]
    sun = "SPF and sunglasses" if uv >= 6 else (f"SPF until {m.clock(M.times[hi_idx[-1]] + timedelta(hours=1))}" if hi_idx else "Not needed")
    wear = ("Winter coat" if cold < 0 else "Warm jacket" if cold < 8 else "Light jacket" if cold < 14
            else "Long sleeves" if cold < 20 else "T-shirt")
    wear_icon = "coat-hanger" if cold < 14 else "hoodie" if cold < 20 else "t-shirt"
    walk = "Windy, take care" if gust >= 50 else "Wet" if prob >= 50 else "Great" if 12 <= cold <= 26 else "Fine"

    def item(glyph, col, label, value):
        return fenn.row([fenn.icon(glyph, size=18, color=col, fill=True),
                         fenn.column([fenn.text(label, size="small", color="dim"), fenn.text(value, bold=True)], gap=0)], gap=8)

    lo, hi = min(feels), max(feels)
    sub = (f"Next 8 hours: feels {u.deg(lo)}" + (f" to {u.deg(hi)}" if round(u.t(hi)) != round(u.t(lo)) else "")
           + f" · rain {prob}% · gusts up to {u.wind(gust)}")
    return fenn.card([
        fenn.row([
            fenn.image(icon("umbrella", True), width=44, height=44),
            fenn.column([fenn.text("Should I go outside?", size="small", color="dim", bold=True),
                         fenn.text(verdict, size="title", color=color),
                         fenn.text(sub, size="small", color="faint")], gap=1),
        ], gap=10),
        fenn.divider(),
        fenn.grid(2, [item("umbrella", RAIN, "Umbrella", umbrella),
                      item("sunglasses", "#FFC24B", "Sun protection", sun),
                      item(wear_icon, "#C9A7FF", "Wear", wear),
                      item("person-simple-walk", "#6FDB8B", "Walking outside", walk)], gap=8),
    ], padding=12, gap=10)


# ---- Air quality

POLL = [("pm2_5", "PM2.5"), ("pm10", "PM10"), ("ozone", "O₃"), ("nitrogen_dioxide", "NO₂")]


def air(m):
    M = m.model
    aq = M.aq
    std = m.aqi_standard()
    v = M.aq_now(std)
    if not aq or v is None:
        return fenn.card([fenn.row([fenn.image(icon("leaf", True), width=40, height=40),
                                    fenn.column([fenn.text("Air quality", size="small", color="dim"),
                                                 fenn.text("Not available here", color="faint")], gap=1)], gap=10)], padding=12)
    name, color = sky.aqi_info(v, std)
    stops, vmax = sky.aqi_stops(std)
    key = "us_aqi" if std == "us" else "european_aqi"
    times = aq["hourly"]["time"]
    nowkey = M.now().strftime("%Y-%m-%dT%H")
    start = next((i for i, t in enumerate(times) if t[:13] >= nowkey), 0)
    trend = [x for x in aq["hourly"][key][start:start + 25]]
    W = m.page_w - 24
    c = Canvas(W)
    c.h = 108
    T = tones(m)
    # the scale with a knob
    n = 30
    for i in range(n):
        c.rect(W * i / n, 6, W / n + 0.6, 6, fill=scale_color(stops, vmax * (i + 0.5) / n))
    kx = W * min(1, v / vmax)
    c.circle(kx, 9, 7, fill=T["halo"])
    c.circle(kx, 9, 5.5, fill="#FFFFFF")
    # the next 24 hours
    vals = [x for x in trend if x is not None]
    if len(vals) > 2:
        lo, hi = min(vals), max(vals)
        span = max(5, hi - lo)
        pts = [(W * i / (len(trend) - 1), 70 - (x - lo) / span * 36) for i, x in enumerate(trend) if x is not None]
        curve = smooth(pts, 6)
        for (ax, ay), (bx, by) in zip(curve, curve[1:]):
            c.line([(ax, ay), (bx, by)], scale_color(stops, lo + (70 - (ay + by) / 2) / 36 * span), 2.2)
        c.text(0, 86, "Now", size=10, color="faint")
        c.text(W / 2, 86, "+12 h", size=10, color="faint", anchor="center")
        c.text(W, 86, "+24 h", size=10, color="faint", anchor="end")
        c.text(W, 26, f"next 24 h: {round(min(vals))}–{round(max(vals))}", size=10, color="faint", anchor="end")
    # the main pollutants now
    x = 0
    for k, lab in POLL:
        val = (aq.get("current") or {}).get(k)
        text = f"{lab} {'–' if val is None else round(val)}"
        wd = tw(text, 10.5, True) + 16
        c.rect(x, 96, wd, 20, fill=T["well"], radius=10)
        c.text(x + wd / 2, 106, text, size=10.5, color="dim", anchor="center", bold=True)
        x += wd + 6
    c.h = 118
    unit = "US AQI" if std == "us" else "European AQI"
    return fenn.card([
        fenn.row([fenn.image(icon("leaf", True), width=40, height=40),
                  fenn.column([fenn.text("Air quality", size="small", color="dim"),
                               fenn.text(f"{round(v)} · {name}", size="title", color=color),
                               fenn.text(f"{unit} · µg/m³ below", size="small", color="faint")], gap=1)], gap=10),
        fenn.text(sky.AQI_ADVICE.get(name, ""), size="small", color="dim", wrap=True),
        fenn.canvas(c.h, c.shapes, width=W),
    ], padding=12, gap=8)


# ---- Your places

def places(m):
    m.load_summaries()
    S = m.settings
    entries = ([("auto", S["auto_place"])] if S.get("auto_place") else []) + [(str(n), p) for n, p in enumerate(S["places"])]
    cards = []
    for key, p in entries:
        s = m.summary_for(key)
        name = "My location" if key == "auto" else p["name"]
        if s:
            cur = s["current"]
            d = s.get("daily") or {}
            img = icon(wx.icon_name(cur.get("weather_code"), bool(cur.get("is_day", 1))), True)
            sub = wx.condition(cur.get("weather_code"), bool(cur.get("is_day", 1)))
            temp = u.deg(cur.get("temperature_2m"))
            hl = f"H {u.deg((d.get('temperature_2m_max') or [None])[0])}  L {u.deg((d.get('temperature_2m_min') or [None])[0])}"
        else:
            img, sub, temp, hl = icon("cloudy", True), "Loading…" if m.summaries_busy else "", "", ""
        where = p.get("name", "") if key == "auto" else (p.get("country") or p.get("region") or "")
        cards.append(fenn.card([fenn.row([
            fenn.image(img, width=40, height=40),
            fenn.column([fenn.text(fit(name, 13, 120, True), bold=True), fenn.text(fit(f"{where} · {sub}" if where else sub, 11, 130), size="small", color="dim"),
                         fenn.text(hl, size="small", color="faint")], gap=1),
            fenn.spacer(),
            fenn.text(temp, size="title"),
            fenn.button(f"city:{key}", icon="caret-right", tooltip=f"Show {name}"),
        ], gap=8)], padding=10))
    parts = [fenn.text("Your places", bold=True)]
    if cards:
        parts.append(fenn.grid(2, cards, gap=8))
    parts.append(fenn.button("places", label="Add or manage places", icon="plus", width=0))
    return parts


def view(m, footer):
    parts = [hero(m), stats(m), strip(m), overview(m)]
    parts += highlights(m)
    parts += [outside(m), air(m)]
    parts += places(m)
    parts += footer
    return fenn.column(parts, gap=10, scroll=True, id="glossy")
