"""The "Panorama" look: a wide dashboard on Fenn's own glass, in the style
of a desktop weather app.

- Current weather: the big icon and temperature, what it feels like, a
  sentence about the next hours, and wind, humidity, visibility, pressure
  and dew point.
- Yesterday to five days ahead as cards; the picked day fills the chart.
- The chart: a metric bar (Overview, Precipitation, Wind, Air quality,
  Humidity, Cloud cover, Pressure, UV, Visibility, Feels like) over the
  day's 24 hours, with the conditions every two hours along the top,
  sunrise and sunset, "now", and the moon phase. Click it to read a value.
- Weather details: twelve cards with small gauges and charts.
- Monthly: this month and the next as a calendar (the past, then the
  16-day forecast; later days show the same day last year, faded) and a
  summary ring.
- Weather trends: the past 12 months by day (temperature, precipitation,
  humidity, wind) with the hottest, coldest, wettest and windiest month and
  the highs, averages and lows.

`m` is main.py. Clicks come back through main.on_canvas ("pn_" actions)
and main.on_event ("pnday:" cells)."""

import calendar
import math
from datetime import date, timedelta

import astro
import fenn
import glossy
import sky
import ui
import units as u
import wx
from ui import Canvas, fit, nice_range, scale_color, tw, wrap

GAP = 6
YELLOW = "#FFC83D"
ON_YELLOW = "#1C1A14"
BLUE = "#5BB4FF"
RED = "#FF6B5E"
TEAL = "#3FD0C5"


def tones(m):
    T = glossy.tones(m)
    T["card"] = T["glass"]
    T["track"] = "#FFFFFF1C" if m.app.dark else "#0000001A"
    T["line"] = "#FFFFFFCC" if m.app.dark else "#2B3445CC"
    T["soft"] = "#FFFFFF59" if m.app.dark else "#00000040"
    return T


def node(m, cid, c):
    m.canvases[cid] = c
    return fenn.canvas(c.h, c.shapes, width=c.w, id=cid)


def picked_day(m):
    M = m.model
    k = m.state.get("pn_day")
    return k if k is not None and 0 <= k < len(M.days) else M.today()


def card_box(c, T, x, y, w, h, title=None):
    c.rect(x, y, w, h, fill=T["card"], radius=14, stroke=T["rim"])
    if title:
        c.text(x + 14, y + 18, title, size=12, color="text", bold=True)


def themed_draw(m, c, fn, *args):
    """Draws with Sky's helpers (white on a colored sky), restyled for the glass."""
    tmp = Canvas(c.w)
    fn(tmp, *args)
    c.add(ui.themed(tmp.shapes, m.app.dark))


# ---- small weather glyphs for the canvases (the 3D icons are images)

def glyph_for(code, day=True):
    code = int(code or 0)
    if code == 0:
        return ("sun", "#FFB547") if day else ("moon", "#C9D1FF")
    if code in (1, 2):
        return ("cloud-sun", "#FFC86B") if day else ("cloud-moon", "#C9D1FF")
    if code == 3:
        return "cloud", "#AFC3D9"
    if code in (45, 48):
        return "cloud-fog", "#AFC3D9"
    if code in (71, 73, 75, 77, 85, 86):
        return "cloud-snow", "#DDEBFF"
    if code >= 95:
        return "cloud-lightning", "#FFD54A"
    if code >= 51:
        return "cloud-rain", "#5BC8FF"
    return "cloud", "#AFC3D9"


def wet(code, mm=None):
    return (mm or 0) >= 1 or int(code or 0) >= 51


# ---- current weather

def current(m):
    M = m.model
    n = glossy.now_info(M)
    k = M.today()
    W = m.page_w
    inner = W - 24
    T = tones(m)
    now = M.now()
    place = wx.place_line(m.settings["place"]) if m.settings["place"] else ""

    head = Canvas(inner)
    head.h = 34
    head.text(0, 9, "Current weather", size=13, color="text", bold=True)
    head.text(0, 26, m.clock(now), size=11, color="dim")
    head.text(inner, 9, fit(place, 11, inner - 150), size=11, color="dim", anchor="end")
    hi_lo = f"H {u.deg(M.d('temperature_2m_max', k))}  ·  L {u.deg(M.d('temperature_2m_min', k))}"
    head.text(inner, 26, hi_lo, size=11, color="dim", anchor="end")

    img = 72
    bw = inner - img - 10
    big = Canvas(bw)
    big.h = img
    temp = u.deg(n["temp"]).rstrip("°")
    big.text(0, 38, temp, size=46, color="text", bold=True)
    ux = tw(temp, 46, True) + 2
    big.text(ux, 18, u.label("temp"), size=17, color="text")
    tx = ux + tw(u.label("temp"), 17) + 18
    big.text(tx, 27, fit(n["text"], 16, bw - tx), size=16, color="text", bold=True)
    big.text(tx, 49, f"Feels like {u.deg(n['feels'])}", size=12, color="dim")
    big.region(0, 0, bw, img, "pn_tab:feels")

    words = M.summary() or f"{n['text']} for now."
    lows = M.d("temperature_2m_min", min(k + 1, len(M.days) - 1))
    if "low" not in words.lower() and lows is not None and not M.is_day():
        words += f" The low will be {u.deg(lows)}."

    stats = Canvas(inner)
    stats.h = 44
    items = [("Wind", f"{u.wind(M.cur('wind_speed_10m'))}", M.cur("wind_direction_10m"), "wind"),
             ("Humidity", f"{round(M.cur('relative_humidity_2m') or 0)}%", None, "humidity"),
             ("Visibility", u.dist(M.cur("visibility")), None, "visibility"),
             ("Pressure", u.pressure(M.cur("pressure_msl")), None, "pressure"),
             ("Dew point", u.deg(M.cur("dew_point_2m")), None, "humidity")]
    cw = inner / len(items)
    for i, (lab, val, direction, tab) in enumerate(items):
        x = i * cw
        stats.text(x, 11, lab, size=11, color="dim")
        stats.text(x, 31, fit(val, 13, cw - 18, True), size=13, color="text", bold=True)
        if direction is not None:
            themed_draw(m, stats, sky.arrow, x + tw(fit(val, 13, cw - 18, True), 13, True) + 10, 31, 11,
                        direction + 180, ui.WHITE, 1.6)
        stats.region(x, 0, x + cw, 44, f"pn_tab:{tab}")

    return fenn.card([
        node(m, "pn:head", head),
        fenn.row([fenn.image(glossy.icon(n["icon"]), width=img, height=img), node(m, "pn:big", big)], gap=10),
        fenn.text(words, size="small", color="dim", wrap=True),
        node(m, "pn:stats", stats),
    ], padding=12, gap=8)


# ---- the day cards

def day_cards(m):
    M = m.model
    k0 = M.today()
    pick = picked_day(m)
    first = max(0, k0 - 1)
    days = list(range(first, min(first + 7, len(M.days))))
    cw = (m.page_w - GAP * (len(days) - 1)) / max(1, len(days))
    cells = []
    for k in days:
        on = k == pick
        name = M.day_name(k)
        num = str(M.day_date(k).day)
        head = fenn.canvas(24, [fenn.label(8, 13, num, size=13, color="text", bold=True),
                                fenn.label(cw - 8, 13, fit(name, 10, cw - 24), size=10,
                                           color="text" if on else "dim", anchor="end", bold=on)], width=cw)
        img = fenn.image(glossy.icon(wx.icon_name(M.d("weather_code", k), True), True), width=34, height=34)
        foot = fenn.canvas(38, [fenn.label(cw / 2, 9, u.deg(M.d("temperature_2m_max", k)), size=13, color="text",
                                           anchor="center", bold=True),
                                fenn.label(cw / 2, 27, u.deg(M.d("temperature_2m_min", k)), size=11, color="dim",
                                           anchor="center")], width=cw)
        body = fenn.column([head, img, foot], gap=2, align="center")
        height = 24 + 2 + 34 + 2 + 38
        ring = [fenn.rect(1, 1, cw - 2, height - 2, stroke=YELLOW, width=2, radius=11)] if on else []
        hit = fenn.canvas(height, ring, width=cw, id=f"pnday:{k}", tooltip=f"{M.day_name(k, False)}: show in the chart")
        cells.append(fenn.card([fenn.column([body, hit], gap=-height)], padding=0, gap=0))
    return fenn.grid(len(cells) or 1, cells, gap=GAP)


# ---- the chart

TABS = [("overview", "Overview"), ("precip", "Precipitation"), ("wind", "Wind"), ("aqi", "Air quality"),
        ("humidity", "Humidity"), ("cloud", "Cloud cover"), ("pressure", "Pressure"), ("uv", "UV"),
        ("visibility", "Visibility"), ("feels", "Feels like")]


def pills(c, T, x, y, W, items, current, action, size=11):
    """Pills that wrap onto more lines; returns the y under them."""
    px, py = x, y
    for key, lab in items:
        w = tw(lab, size, True) + 22
        if px + w > W and px > x:
            px, py = x, py + 30
        on = key == current
        c.rect(px, py, w, 24, fill=YELLOW if on else T["well"], radius=12, stroke=None if on else T["rim"])
        c.text(px + w / 2, py + 12, lab, size=size, color=ON_YELLOW if on else "text", anchor="center", bold=True)
        c.region(px, py, px + w, py + 24, f"{action}:{key}")
        px += w + 6
    return py + 24


def aq_hours(m, idx):
    """The day's air quality index by hour (None where the forecast ends)."""
    M = m.model
    aq = M.aq
    if not aq:
        return [None] * len(idx)
    key = "us_aqi" if m.aqi_standard() == "us" else "european_aqi"
    pos = {t[:13]: i for i, t in enumerate(aq["hourly"]["time"])}
    col = aq["hourly"].get(key) or []
    out = []
    for i in idx:
        j = pos.get(M.fc["hourly"]["time"][i][:13])
        out.append(col[j] if j is not None and j < len(col) else None)
    return out


def series(m, tab, idx):
    """values, how to print one, its color and the axis for a metric."""
    M = m.model
    H = lambda name: M.hs(name, idx)
    temp_col = lambda v: scale_color(sky.TEMP_STOPS, v if u.unit("temp") == "c" else (v - 32) / 1.8)
    if tab in ("overview", "feels"):
        vals = [u.t(v) for v in H("temperature_2m" if tab == "overview" else "apparent_temperature")]
        return dict(values=vals, fmt=lambda v: f"{round(v)}°", color=temp_col, name="Temperature" if tab == "overview"
                    else "Feels like")
    if tab == "precip":
        vals = [u.p(v) for v in H("precipitation")]
        prob = H("precipitation_probability")
        snow = [(v or 0) > 0 for v in H("snowfall")]
        return dict(values=vals, bars=True, snow=snow, floor=True, fmt=lambda v: u.precip(v * (25.4 if u.unit("precip") == "in" else 1)),
                    axis=lambda v: (f"{v:.1f}" if v < 10 else f"{round(v)}"),
                    color=lambda v: BLUE, name="Precipitation", extra=lambda i: f"{prob[i] or 0}% chance")
    if tab == "wind":
        vals = [u.w(v) for v in H("wind_speed_10m")]
        gust = [u.w(v) for v in H("wind_gusts_10m")]
        dirs = H("wind_direction_10m")
        return dict(values=vals, second=gust, floor=True, fmt=lambda v: f"{round(v)} {u.label('wind')}",
                    color=lambda v: TEAL, name="Wind", extra=lambda i: f"gusts {round(gust[i] or 0)}, from {u.compass(dirs[i])}")
    if tab == "aqi":
        std = m.aqi_standard()
        stops, vmax = sky.aqi_stops(std)
        vals = aq_hours(m, idx)
        return dict(values=vals, floor=True, fmt=lambda v: f"{round(v)}", color=lambda v: scale_color(stops, v),
                    name="US AQI" if std == "us" else "European AQI",
                    extra=lambda i: sky.aqi_info(vals[i], std)[0] if vals[i] is not None else "")
    if tab == "humidity":
        dew = H("dew_point_2m")
        return dict(values=H("relative_humidity_2m"), fixed=(0, 100), fmt=lambda v: f"{round(v)}%",
                    color=lambda v: "#7FD6FF", name="Humidity", extra=lambda i: f"dew point {u.deg(dew[i])}")
    if tab == "cloud":
        return dict(values=H("cloud_cover"), fixed=(0, 100), fmt=lambda v: f"{round(v)}%",
                    color=lambda v: "#B7C6D8", name="Cloud cover")
    if tab == "pressure":
        return dict(values=[u.pr(v) for v in H("pressure_msl")],
                    fmt=lambda v: f"{v:.2f}" if u.unit("pressure") == "inhg" else f"{round(v)}",
                    color=lambda v: "#C9A7FF", name=f"Pressure ({u.label('pressure')})")
    if tab == "uv":
        return dict(values=H("uv_index"), floor=True, fmt=lambda v: f"{round(v)}", color=lambda v: scale_color(sky.UV_STOPS, v),
                    name="UV index", extra=lambda i: sky.uv_name(H("uv_index")[i]))
    vis = [None if v is None else (v / 1609.344 if u.unit("dist") == "mi" else v / 1000) for v in H("visibility")]
    return dict(values=vis, floor=True, fmt=lambda v: f"{v:.1f} {u.label('dist')}" if v < 10 else f"{round(v)} {u.label('dist')}",
                axis=lambda v: f"{round(v)}", color=lambda v: "#9FE0B0", name=f"Visibility ({u.label('dist')})")


def smooth(pts, steps=6):
    return glossy.smooth(pts, steps)


def chart(m):
    M = m.model
    T = tones(m)
    st = m.state
    W = m.page_w
    tab = st.get("pn_tab", "overview")
    k = picked_day(m)
    idx = M.day_hours(k)
    c = Canvas(W)
    if len(idx) < 2:
        c.h = 40
        return node(m, "pn:chart", c)
    s = series(m, tab, idx)
    vals = s["values"]
    n = len(vals)
    today = k == M.today()
    now_i = M.hour_now() - idx[0] if today else None
    sel = st.get("pn_sel")
    if sel is None or not (0 <= sel < n):
        sel = now_i if now_i is not None and 0 <= now_i < n else max(range(n), key=lambda i: vals[i] if vals[i] is not None else -1e9)

    # the metric bar
    y = pills(c, T, 0, 0, W, TABS, tab, "pn_tab") + 10
    top = y
    # the panel
    x0, x1 = 40, W - 14
    icons_y = top + 24
    plot_top, plot_bot = top + 108, top + 262
    H = plot_bot + 52 - top
    card_box(c, T, 0, top, W, H)
    c.text(14, top + 18, f"{M.day_name(k, False)} · {s['name']}", size=12, color="text", bold=True)

    X = lambda i: x0 + (x1 - x0) * i / max(1, n - 1)
    # the conditions every two hours along the top
    temps = M.hs("temperature_2m", idx)
    codes = M.hs("weather_code", idx)
    days = M.hs("is_day", idx)
    dirs = M.hs("wind_direction_10m", idx)
    for i in range(0, n, 2):
        x = X(i)
        lab = "Now" if now_i == i else m.hour_label(M.times[idx[i]]).replace(":00", "")
        c.text(x, icons_y + 8, lab, size=9.5, color="text" if now_i == i else "dim", anchor="center", bold=now_i == i)
        if tab == "wind" and dirs[i] is not None:
            themed_draw(m, c, sky.arrow, x, icons_y + 28, 14, dirs[i] + 180, ui.WHITE, 1.8)
            c.text(x, icons_y + 48, f"{round(vals[i] or 0)}", size=10, color="dim", anchor="center")
        else:
            g, col = glyph_for(codes[i], bool(days[i]))
            c.glyph(x, icons_y + 28, g, 15, col, True)
            c.text(x, icons_y + 48, u.deg(temps[i]), size=10, color="dim", anchor="center")

    # axis
    present = [v for v in vals if v is not None]
    if s.get("second"):
        present += [v for v in s["second"] if v is not None]
    if s.get("fixed"):
        lo, hi = s["fixed"]
        grid = [lo, (lo + hi) / 2, hi]
    elif present:
        lo, hi, grid = nice_range(min(present), max(present), 3, floor_zero=s.get("floor", False))
        if s.get("floor") and hi <= 0:
            lo, hi, grid = 0, 1, [0, 1]
    else:
        lo, hi, grid = 0, 1, [0, 1]
    Y = lambda v: plot_bot - (v - lo) / ((hi - lo) or 1) * (plot_bot - plot_top)
    axis = s.get("axis") or (lambda v: s["fmt"](v).split(" ")[0])
    for g in grid:
        c.add(glossy.dashes(x0, x1, Y(g), T["grid"], 4, 4, 1))
        c.text(x0 - 8, Y(g), axis(g), size=9.5, color="dim", anchor="end")

    color = s["color"]
    if not present:
        c.text((x0 + x1) / 2, (plot_top + plot_bot) / 2, "Not available for this day", size=12, color="dim", anchor="center")
    elif s.get("bars"):
        bw = max(3, (x1 - x0) / n * 0.6)
        if max(present) <= 0:
            c.text((x0 + x1) / 2, (plot_top + plot_bot) / 2 - 10, "No precipitation expected", size=12, color="dim",
                   anchor="center")
        snow = s.get("snow") or []
        for i, v in enumerate(vals):
            if v and v > 0:
                col = glossy.snow_color(m) if i < len(snow) and snow[i] else BLUE  # snow white, as in Sky
                c.rect(X(i) - bw / 2, Y(v), bw, max(2, plot_bot - Y(v)), fill=col if i == sel else col + "AA", radius=2)
    else:
        pts = [(X(i), Y(v), v) for i, v in enumerate(vals) if v is not None]
        curve = smooth([(x, yy) for x, yy, _ in pts])
        # the filled area, colored by value (one quad per step)
        span = max(1, len(curve) - 1)
        for j, ((ax, ay), (bx, by)) in enumerate(zip(curve, curve[1:])):
            v = lo + (plot_bot - (ay + by) / 2) / ((plot_bot - plot_top) or 1) * (hi - lo)
            col = color(v)[:7]
            c.shapes.append(fenn.polygon([(ax, ay), (bx, by), (bx, plot_bot), (ax, plot_bot)], fill=col + "55"))
        for (ax, ay), (bx, by) in zip(curve, curve[1:]):
            v = lo + (plot_bot - (ay + by) / 2) / ((plot_bot - plot_top) or 1) * (hi - lo)
            c.line([(ax, ay), (bx, by)], color(v)[:7], 2.2)
        if s.get("second"):
            sec = [(X(i), Y(v)) for i, v in enumerate(s["second"]) if v is not None]
            c.line(smooth(sec), T["soft"], 1.4)
    c.line([(x0, plot_bot), (x1, plot_bot)], T["grid"], 1)

    # sunrise and sunset under the axis
    rise, sset = M.sun(k)
    day0 = M.day_date(k)
    for t, glyph_name in ((rise, "sun-horizon"), (sset, "moon-stars")):
        frac = (t - day0).total_seconds() / 3600
        if 0 <= frac <= n - 1:
            x = X(frac)
            c.glyph(x - tw(m.clock(t), 10) / 2 - 9, plot_bot + 16, glyph_name, 12, "#FFB547" if glyph_name == "sun-horizon"
                    else "#C9D1FF", True)
            c.text(x + 2, plot_bot + 16, m.clock(t), size=10, color="dim", anchor="center")

    # now, and the picked hour
    if now_i is not None and 0 <= now_i < n:
        nx = X(now_i)
        yy = plot_top - 6
        while yy < plot_bot:
            c.line([(nx, yy), (nx, min(plot_bot, yy + 3))], T["soft"], 1.2)
            yy += 6
    v = vals[sel]
    sx = X(sel)
    if v is not None:
        vy = Y(v)
        c.line([(sx, vy), (sx, plot_bot)], T["line"], 1)
        c.circle(sx, vy, 7, fill=T["halo"])
        c.circle(sx, vy, 5, fill="#FFFFFF")
        c.circle(sx, vy, 3, fill=color(v)[:7])
        label = f"{m.hour_label(M.times[idx[sel]])}  ·  {s['fmt'](v)}"
        if s.get("extra") and s["extra"](sel):
            label += f"  ·  {s['extra'](sel)}"
        bw = tw(label, 11, True) + 20
        bx = min(max(sx - bw / 2, 6), W - 6 - bw)
        by = max(plot_top - 26, vy - 34)
        c.rect(bx, by, bw, 22, fill=YELLOW, radius=11)
        c.text(bx + bw / 2, by + 11, label, size=11, color=ON_YELLOW, anchor="center", bold=True)
    # the legend and the moon
    noon = M.to_utc(day0 + timedelta(hours=12))
    frac_lit, phase = astro.moon_illumination(noon)
    c.circle(20, plot_bot + 38, 4, fill=color(present[0] if present else 0)[:7] if present else BLUE)
    c.text(30, plot_bot + 38, s["name"], size=10.5, color="dim")
    moon = f"Moon phase: {astro.phase_name(phase)}"
    c.text(W - 14, plot_bot + 38, moon, size=10.5, color="dim", anchor="end")
    tmp = Canvas(W)
    sky.moon_disc(tmp, W - 14 - tw(moon, 10.5) - 12, plot_bot + 38, 6, phase, m.settings["place"]["lat"])
    c.add(tmp.shapes)
    c.region(x0 - 10, plot_top - 30, x1 + 10, plot_bot + 4, "pn_pick", x0=X(0), x1=X(n - 1), n=n)
    c.h = top + H
    return node(m, "pn:chart", c)


# ---- weather details

def gauge(c, T, cx, cy, r, frac, stops=None, color=None, width=7, sweep=240):
    start = -sweep / 2
    c.shapes.append(fenn.arc(cx, cy, r, start, start + sweep, color=T["track"], width=width))
    if stops:
        steps = 36
        for i in range(steps):
            a0 = start + sweep * i / steps
            c.shapes.append(fenn.arc(cx, cy, r, a0, a0 + sweep / steps + 0.6,
                                     color=scale_color(stops, stops[-1][0] * (i + 0.5) / steps), width=width))
    elif color and frac > 0:
        c.shapes.append(fenn.arc(cx, cy, r, start, start + sweep * min(1, frac), color=color, width=width))
    a = math.radians(start + sweep * min(1, max(0, frac)))
    kx, ky = cx + math.sin(a) * r, cy - math.cos(a) * r
    c.circle(kx, ky, width * 0.85, fill=T["halo"])
    c.circle(kx, ky, width * 0.65, fill="#FFFFFF")


def ring(c, T, cx, cy, r, frac, color, width=6):
    c.shapes.append(fenn.arc(cx, cy, r, 0, 360, color=T["track"], width=width))
    if frac > 0.004:
        c.shapes.append(fenn.arc(cx, cy, r, 0, 360 * min(1, frac), color=color, width=width))


def foot(c, x, y, w, h, title, text, lines=2):
    c.text(x + 14, y + h - 44 + (0 if lines > 1 else 14), title, size=11.5, color="text", bold=True)
    for j, line in enumerate(wrap(text, 10.5, w - 28, lines)):
        c.text(x + 14, y + h - 28 + j * 14 + (0 if lines > 1 else 14), line, size=10.5, color="dim")


def trend_word(M):
    i = M.hour_now()
    a, b = M.h("temperature_2m", i), M.h("temperature_2m", min(i + 3, len(M.times) - 1))
    if a is None or b is None or abs(b - a) < 1:
        return "Steady"
    return "Rising" if b > a else "Falling"


def d_temperature(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Temperature")
    k = M.today()
    idx = M.day_hours(k)
    vals = M.hs("temperature_2m", idx)
    gx0, gx1, gy0, gy1 = x + 14, x + w - 14, y + 40, y + 84
    good = [v for v in vals if v is not None]
    if good:
        lo, hi = min(good), max(good)
        Y = lambda v: gy1 - (v - lo) / ((hi - lo) or 1) * (gy1 - gy0)
        pts = [(gx0 + (gx1 - gx0) * i / (len(vals) - 1), Y(v)) for i, v in enumerate(vals) if v is not None]
        curve = smooth(pts, 4)
        for (ax, ay), (bx, by) in zip(curve, curve[1:]):
            c.shapes.append(fenn.polygon([(ax, ay), (bx, by), (bx, gy1 + 6), (ax, gy1 + 6)], fill=TEAL + "22"))
            c.line([(ax, ay), (bx, by)], TEAL, 2.4)
        ni = M.hour_now() - idx[0]
        if 0 <= ni < len(vals) and vals[ni] is not None:
            px, py = gx0 + (gx1 - gx0) * ni / (len(vals) - 1), Y(vals[ni])
            c.circle(px, py, 7, fill="#FFFFFF")
            c.circle(px, py, 4.5, fill=TEAL)
    c.text(x + w - 14, y + 18, u.deg(M.cur("temperature_2m")), size=18, color="text", anchor="end", bold=True)
    word = trend_word(M)
    nxt = list(range(M.hour_now(), min(M.hour_now() + 18, len(M.times))))
    temps = M.hs("temperature_2m", nxt)
    pairs = [(t, i) for t, i in zip(temps, nxt) if t is not None]
    if pairs:
        t_lo, i_lo = min(pairs)
        t_hi, i_hi = max(pairs)
        text = (f"Down to {u.deg(t_lo)} at {m.clock(M.times[i_lo])}." if word != "Rising"
                else f"Up to {u.deg(t_hi)} at {m.clock(M.times[i_hi])}.")
    else:
        text = ""
    tomorrow = M.d("temperature_2m_max", min(k + 1, len(M.days) - 1))
    today_hi = M.d("temperature_2m_max", k)
    if tomorrow is not None and today_hi is not None:
        d = u.t_delta(tomorrow - today_hi)
        text += " Tomorrow " + ("similar to today." if abs(d) < 2 else f"{round(abs(d))}° {'warmer' if d > 0 else 'colder'}.")
    foot(c, x, y, w, h, word, text)
    c.region(x, y, x + w, y + h, "pn_tab:overview")


def d_feels(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Feels like")
    feels, actual = M.cur("apparent_temperature"), M.cur("temperature_2m")
    wind, hum = M.cur("wind_speed_10m") or 0, M.cur("relative_humidity_2m") or 0
    gx0, gx1, gy = x + 14, x + w - 14, y + 46
    c.rect(gx0, gy - 2.5, gx1 - gx0, 5, fill=T["track"], radius=2.5)
    if feels is not None and actual is not None:
        lo, hi = min(feels, actual) - 6, max(feels, actual) + 6
        X = lambda v: gx0 + (v - lo) / (hi - lo) * (gx1 - gx0)
        a, b = sorted((X(feels), X(actual)))
        c.rect(a, gy - 2.5, max(5, b - a), 5, fill=BLUE if feels < actual else "#FF9F45", radius=2.5)
        c.circle(X(actual), gy, 4, fill=T["line"])
        c.circle(X(feels), gy, 7, fill="#FFFFFF")
        c.circle(X(feels), gy, 4.5, fill=BLUE if feels < actual else "#FF9F45")
    gap = 0 if feels is None or actual is None else feels - actual
    factor = "wind" if gap <= -1 else ("humidity" if hum >= 60 else "sun") if gap >= 1 else "none"
    c.text(x + 14, y + 72, f"Dominant factor: {factor}", size=10, color="dim")
    c.text(x + 14, y + 96, u.deg(feels), size=22, color="text", bold=True)
    c.text(x + w - 14, y + 96, f"Actual {u.deg(actual)}", size=11, color="dim", anchor="end")
    diff = None if feels is None or actual is None else u.t_delta(feels - actual)
    word = "Similar" if diff is None or abs(diff) < 1.5 else ("Colder" if diff < 0 else "Warmer")
    text = sky.feels_words(actual, feels, wind, hum)
    c.text(x + 14, y + h - 30, word, size=11.5, color="text", bold=True)
    for j, line in enumerate(wrap(text, 10.5, w - 28, 1)):
        c.text(x + 14, y + h - 14, line, size=10.5, color="dim")
    c.region(x, y, x + w, y + h, "pn_tab:feels")


def cloud_words(v):
    if v is None:
        return "–"
    return "Clear" if v < 15 else "Mostly clear" if v < 35 else "Partly cloudy" if v < 65 else "Mostly cloudy" if v < 90 else "Overcast"


def d_cloud(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Cloud cover")
    v = M.cur("cloud_cover")
    cx, cy = x + w / 2, y + 66
    ring(c, T, cx, cy, 32, (v or 0) / 100, "#B7C6D8")
    c.text(cx, cy, cloud_words(v), size=11, color="text", anchor="center", bold=True)
    later = M.hs("cloud_cover", range(M.hour_now() + 1, min(M.hour_now() + 7, len(M.times))))
    later = [x_ for x_ in later if x_ is not None]
    text = f"Next 6 h: {cloud_words(sum(later) / len(later)).lower()}." if later else ""
    foot(c, x, y, w, h, f"{cloud_words(v)} ({'–' if v is None else round(v)}%)", text, 1)
    c.region(x, y, x + w, y + h, "pn_tab:cloud")


def d_precip(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Precipitation")
    start = M.hour_now()
    rng = range(start, min(start + 24, len(M.times)))
    amount = sum(v or 0 for v in M.hs("precipitation", rng))
    prob = max([v or 0 for v in M.hs("precipitation_probability", rng)] or [0])
    cx, cy = x + w / 2, y + 66
    snow = sum(v or 0 for v in M.hs("snowfall", rng)) > 0 and         sum(v or 0 for v in M.hs("snowfall", rng)) * 0.7 >= sum(v or 0 for v in M.hs("rain", rng))  # cm vs mm
    ring(c, T, cx, cy, 32, prob / 100, glossy.snow_color(m) if snow else BLUE)
    c.text(cx, cy - 6, u.precip(amount), size=14, color="text", anchor="center", bold=True)
    c.text(cx, cy + 10, "next 24 h", size=9, color="dim", anchor="center")
    nxt = next((i for i in range(start, min(start + 96, len(M.times))) if (M.h("precipitation", i) or 0) >= 0.1), None)
    if nxt is None:
        text = "None expected in the next 4 days."
    else:
        when = M.times[nxt]
        dk = (when.date() - M.now().date()).days
        day = "today" if dk == 0 else "tomorrow" if dk == 1 else when.strftime("%A")
        part = "night" if when.hour < 6 or when.hour >= 21 else "morning" if when.hour < 12 else "afternoon" if when.hour < 18 else "evening"
        noun = "Snow" if (M.h("snowfall", nxt) or 0) > 0 else "Rain"
        text = f"{noun} expected {day} {part if dk else 'around ' + m.clock(when)}."
    foot(c, x, y, w, h, f"{prob}% chance" if amount >= 0.1 else "No precipitation", text, 1)
    c.region(x, y, x + w, y + h, "pn_tab:precip")


def d_wind(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Wind")
    kmh = M.cur("wind_speed_10m") or 0
    direction = M.cur("wind_direction_10m")
    cx, cy = x + 52, y + 74
    themed_draw(m, c, sky.compass, cx, cy, 36, direction, "", "")
    tx = x + 102
    c.text(tx, y + 44, u.wind(kmh, False), size=20, color="text", bold=True)
    c.text(tx + tw(u.wind(kmh, False), 20, True) + 4, y + 44, u.label("wind"), size=10, color="dim")
    c.text(tx, y + 60, f"From {u.compass(direction)}", size=10, color="dim")
    g = M.cur("wind_gusts_10m")
    c.text(tx, y + 84, u.wind(g, False), size=16, color="text", bold=True)
    c.text(tx + tw(u.wind(g, False), 16, True) + 4, y + 84, "gusts", size=10, color="dim")
    b = u.beaufort(kmh)
    c.text(x + 14, y + h - 14, f"Force {b}: {u.BEAUFORT_NAMES[b]}", size=11, color="text", bold=True)
    c.region(x, y, x + w, y + h, "pn_tab:wind")


def d_humidity(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Humidity")
    start = M.hour_now()
    vals = M.hs("relative_humidity_2m", range(start, min(start + 8, len(M.times))))
    bx, by0, by1 = x + 14, y + 36, y + 100
    bw = 9
    for j, v in enumerate(vals):
        px = bx + j * (bw + 5)
        c.rect(px, by0, bw, by1 - by0, fill=T["track"], radius=4)
        if v:
            hh = (by1 - by0) * v / 100
            c.rect(px, by1 - hh, bw, hh, fill="#6E9BFF" if j else "#9DBBFF", radius=4)
    tx = bx + 8 * (bw + 5) + 6
    c.text(tx, y + 50, f"{round(M.cur('relative_humidity_2m') or 0)}%", size=20, color="text", bold=True)
    c.text(tx, y + 66, "humidity", size=10, color="dim")
    c.text(tx, y + 90, u.deg(M.cur("dew_point_2m")), size=16, color="text", bold=True)
    c.text(tx, y + 104, "dew point", size=10, color="dim")
    words = sky.dew_words(M.cur("dew_point_2m")).split(".")[0]
    words = words[:1].upper() + words[1:]
    c.text(x + 14, y + h - 14, fit(words, 10.5, w - 28), size=10.5, color="dim")
    c.region(x, y, x + w, y + h, "pn_tab:humidity")


def d_uv(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "UV")
    v = M.cur("uv_index") or 0
    cx, cy = x + w / 2, y + 70
    gauge(c, T, cx, cy, 30, v / 11, stops=sky.UV_STOPS)
    c.text(cx, cy + 2, str(round(v)), size=20, color="text", anchor="center", bold=True)
    mx = M.d("uv_index_max", M.today())
    foot(c, x, y, w, h, sky.uv_name(v), f"Today's maximum: {round(mx or 0)} ({sky.uv_name(mx).lower()}).", 1)
    c.region(x, y, x + w, y + h, "pn_tab:uv")


def d_aqi(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Air quality")
    std = m.aqi_standard()
    v = M.aq_now(std)
    cx, cy = x + w / 2, y + 70
    stops, vmax = sky.aqi_stops(std)
    if v is None:
        c.text(cx, cy, "Not available", size=12, color="dim", anchor="center")
    else:
        gauge(c, T, cx, cy, 30, v / vmax, stops=stops)
        c.text(cx, cy + 2, str(round(v)), size=20, color="text", anchor="center", bold=True)
        name, col = sky.aqi_info(v, std)
        cur = (M.aq or {}).get("current") or {}
        main = max(glossy.POLL, key=lambda p: (cur.get(p[0]) or 0) / {"pm2_5": 25, "pm10": 50, "ozone": 120,
                                                                         "nitrogen_dioxide": 40}[p[0]])
        foot(c, x, y, w, h, name, f"Main pollutant: {main[1]} {round(cur.get(main[0]) or 0)} µg/m³.", 1)
    c.region(x, y, x + w, y + h, "pn_tab:aqi")


def d_moon(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Moon phase")
    now_utc = M.to_utc(M.now())
    frac, phase = astro.moon_illumination(now_utc)
    tmp = Canvas(c.w)
    sky.moon_disc(tmp, x + 52, y + 72, 32, phase, m.settings["place"]["lat"])
    c.add(tmp.shapes)
    tx = x + 100
    c.text(tx, y + 54, f"{round(frac * 100)}%", size=20, color="text", bold=True)
    c.text(tx, y + 70, "illuminated", size=10, color="dim")
    full = astro.next_phase(now_utc, 0.5)
    if full:
        c.text(tx, y + 94, M.to_local(full).strftime("%b %d").replace(" 0", " "), size=14, color="text", bold=True)
        c.text(tx, y + 108, "next full moon", size=10, color="dim")
    c.text(x + 14, y + h - 14, astro.phase_name(phase), size=11, color="text", bold=True)


def d_sun(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Sun")
    k = M.today()
    rise, sset = M.sun(k)
    now = M.now()
    cx, cy, r = x + w / 2, y + 96, min(56, w / 2 - 24)
    c.shapes.append(fenn.arc(cx, cy, r, -90, 90, color=T["track"], width=3))
    frac = (now - rise).total_seconds() / max(1, (sset - rise).total_seconds())
    if 0 < frac < 1:
        c.shapes.append(fenn.arc(cx, cy, r, -90, -90 + 180 * frac, color="#FFB547", width=3))
        a = math.radians(-90 + 180 * frac)
        c.circle(cx + math.sin(a) * r, cy - math.cos(a) * r, 7, fill="#FFB547")
    c.line([(x + 14, cy), (x + w - 14, cy)], T["grid"], 1)
    c.text(x + 14, y + h - 14, f"↑ {m.clock(rise)}", size=11, color="text", bold=True)
    c.text(x + w - 14, y + h - 14, f"↓ {m.clock(sset)}", size=11, color="text", anchor="end", bold=True)
    secs = int(M.d("daylight_duration", k) or (sset - rise).total_seconds())
    c.text(cx, cy - 14, f"{secs // 3600} h {secs % 3600 // 60} m", size=11, color="dim", anchor="center")


def d_pressure(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Pressure")
    v = M.cur("pressure_msl")
    cx, cy = x + w / 2, y + 70
    gauge(c, T, cx, cy, 30, ((v or 1013) - 970) / 80, color="#C9A7FF")
    c.text(cx, cy - 2, u.pressure(v, False), size=15, color="text", anchor="center", bold=True)
    c.text(cx, cy + 13, u.label("pressure"), size=9, color="dim", anchor="center")
    trend, d = sky.pressure_trend(M)
    foot(c, x, y, w, h, trend.capitalize(), "Higher pressure usually brings settled weather." if (v or 0) >= 1015
         else "Lower pressure often brings clouds and rain.", 1)
    c.region(x, y, x + w, y + h, "pn_tab:pressure")


def d_visibility(m, c, T, x, y, w, h):
    M = m.model
    card_box(c, T, x, y, w, h, "Visibility")
    v = M.cur("visibility")
    cx, cy = x + w / 2, y + 66
    ring(c, T, cx, cy, 32, min(1, (v or 0) / 24000), "#9FE0B0")
    c.text(cx, cy, u.dist(v), size=13, color="text", anchor="center", bold=True)
    words = sky.visibility_words(v).rstrip(".")
    foot(c, x, y, w, h, words.split(":")[0].split(",")[0], "", 1)
    c.region(x, y, x + w, y + h, "pn_tab:visibility")


DETAILS = [d_temperature, d_feels, d_cloud, d_precip, d_wind, d_humidity, d_uv, d_aqi, d_moon, d_sun,
           d_pressure, d_visibility]


def details(m):
    T = tones(m)
    W = m.page_w
    cols = 3 if W >= 600 else 2
    cw = (W - 8 * (cols - 1)) / cols
    ch = 150
    c = Canvas(W)
    for i, fn in enumerate(DETAILS):
        x = (i % cols) * (cw + 8)
        y = (i // cols) * (ch + 8)
        fn(m, c, T, x, y, cw, ch)
    c.h = math.ceil(len(DETAILS) / cols) * (ch + 8) - 8
    return node(m, "pn:details", c)


# ---- monthly

def first_weekday():
    """0 = Monday, as Windows' calendar is set (Sunday = 6)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\International") as k:
            return int(winreg.QueryValueEx(k, "iFirstDayOfWeek")[0]) % 7
    except (OSError, ValueError):
        return 0


def day_table(m):
    """date -> (code, high, low, mm, kind): "past"/"forecast" from the month
    request, "lastyear" from the past year's history."""
    out = {}
    hist = m.hist_data
    if hist and hist.get("daily"):
        d = hist["daily"]
        for i, t in enumerate(d["time"]):
            try:
                ly = date.fromisoformat(t)
                ly = ly.replace(year=ly.year + 1)
            except ValueError:
                continue
            out[ly.isoformat()] = (d["weather_code"][i], d["temperature_2m_max"][i], d["temperature_2m_min"][i],
                                   d["precipitation_sum"][i], "lastyear")
    md = m.month_data
    if md and md.get("daily"):
        d = md["daily"]
        today = m.model.now().date().isoformat()
        for i, t in enumerate(d["time"]):
            if d["temperature_2m_max"][i] is None:
                continue
            out[t] = (d["weather_code"][i], d["temperature_2m_max"][i], d["temperature_2m_min"][i],
                      d["precipitation_sum"][i], "past" if t < today else "forecast")
    return out


def monthly(m):
    T = tones(m)
    W = m.page_w
    M = m.model
    today = M.now().date()
    which = m.state.get("pn_month", 0)
    year, month = today.year, today.month
    if which:
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    c = Canvas(W)
    # month tabs
    names = []
    for j in range(2):
        yy, mm = (today.year, today.month) if j == 0 else ((today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1))
        names.append((str(j), calendar.month_name[mm] + (f" {yy}" if yy != today.year else "")))
    y = pills(c, T, 0, 0, W, names, str(which), "pn_month") + 10
    table = day_table(m)
    fw = first_weekday()
    heads = [calendar.day_abbr[(fw + i) % 7] for i in range(7)]
    gx, gw = 0, W
    cw = gw / 7
    card_box(c, T, 0, y, W, 10)  # resized below
    box_i = len(c.shapes) - 1
    for i, hname in enumerate(heads):
        c.text(gx + i * cw + 10, y + 18, hname, size=10.5, color="dim", bold=True)
    ry = y + 32
    weeks = calendar.Calendar(firstweekday=fw).monthdatescalendar(year, month)
    rh = 56
    stats = {"dry": 0, "wet": 0, "hi": [], "lo": []}
    for week in weeks:
        for i, d in enumerate(week):
            x = gx + i * cw
            inside = d.month == month
            if not inside:
                continue
            row = table.get(d.isoformat())
            is_today = d == today
            c.line([(x + 6, ry), (x + cw - 6, ry)], T["grid"], 1)
            if is_today:
                c.rect(x + 3, ry + 3, cw - 6, rh - 6, fill=None, radius=8, stroke=YELLOW, width=2)
            faded = row is None or row[4] == "lastyear"
            c.text(x + 10, ry + 14, str(d.day), size=10.5, color="dim" if faded else "dim", bold=is_today)
            if row and row[1] is not None:
                code, hi, lo, mm, kind = row
                g, col = glyph_for(code, True)
                c.glyph(x + 20, ry + 36, g, 18, col + ("66" if faded else ""), True)
                c.text(x + cw - 8, ry + 26, u.deg(hi), size=11.5, color="dim" if faded else "text", anchor="end", bold=not faded)
                c.text(x + cw - 8, ry + 43, u.deg(lo), size=10, color="dim", anchor="end")
                if kind != "lastyear":
                    stats["wet" if wet(code, mm) else "dry"] += 1
                    stats["hi"].append(hi)
                    stats["lo"].append(lo)
        ry += rh
    c.shapes[box_i] = fenn.rect(0, y, W, ry - y + 8, fill=T["card"], radius=14, stroke=T["rim"])
    ly = ry + 20
    c.text(14, ly, "Faded: the same day last year (beyond the 16-day forecast).", size=10, color="dim")
    # the summary ring
    oy = ly + 16
    oh = 120
    card_box(c, T, 0, oy, W, oh, "Weather overview")
    cx, cy, r = 70, oy + 68, 36
    total = stats["dry"] + stats["wet"]
    c.shapes.append(fenn.arc(cx, cy, r, 0, 360, color=T["track"], width=10))
    if total:
        cut = 360 * stats["dry"] / total
        if stats["dry"]:
            c.shapes.append(fenn.arc(cx, cy, r, 0, cut, color="#FFB547", width=10))
        if stats["wet"]:
            c.shapes.append(fenn.arc(cx, cy, r, cut, 360, color=BLUE, width=10))
    c.text(cx, cy - 7, str(year), size=9.5, color="dim", anchor="center")
    c.text(cx, cy + 8, calendar.month_abbr[month], size=15, color="text", anchor="center", bold=True)
    tx = 140
    col2 = tx + (W - tx) / 2
    c.circle(tx, oy + 46, 4, fill="#FFB547")
    c.text(tx + 10, oy + 46, "Dry days", size=10.5, color="dim")
    c.text(tx + 10, oy + 64, str(stats["dry"]), size=15, color="text", bold=True)
    c.circle(col2, oy + 46, 4, fill=BLUE)
    c.text(col2 + 10, oy + 46, "Rain or snow days", size=10.5, color="dim")
    c.text(col2 + 10, oy + 64, str(stats["wet"]), size=15, color="text", bold=True)
    avg = lambda v: u.deg(sum(v) / len(v)) if v else "–"
    c.text(tx + 10, oy + 88, "Average high", size=10.5, color="dim")
    c.text(tx + 10, oy + 105, avg(stats["hi"]), size=14, color="text", bold=True)
    c.text(col2 + 10, oy + 88, "Average low", size=10.5, color="dim")
    c.text(col2 + 10, oy + 105, avg(stats["lo"]), size=14, color="text", bold=True)
    c.text(W - 14, oy + 18, f"{total} days with data", size=10, color="dim", anchor="end")
    c.h = oy + oh
    return node(m, "pn:month", c)


# ---- trends

TREND_TABS = [("temp", "Temperature"), ("precip", "Precipitation"), ("humidity", "Humidity"), ("wind", "Wind")]


def trends(m):
    T = tones(m)
    W = m.page_w
    hist = m.hist_data
    c = Canvas(W)
    if not hist or not hist.get("daily"):
        c.h = 60
        card_box(c, T, 0, 0, W, 60)
        c.text(W / 2, 30, "Loading the past 12 months…" if m.extra_busy else "The past 12 months aren't available right now.",
               size=12, color="dim", anchor="center")
        return node(m, "pn:trends", c)
    tab = m.state.get("pn_trend", "temp")
    d = hist["daily"]
    times = [date.fromisoformat(t) for t in d["time"]]
    n = len(times)
    y = pills(c, T, 0, 0, W, TREND_TABS, tab, "pn_trend") + 10
    top = y
    ph = 190
    card_box(c, T, 0, top, W, ph + 56)
    x0, x1 = 40, W - 14
    py0, py1 = top + 20, top + 20 + ph
    # the past year, then the 16-day forecast after today
    md = m.month_data
    today = m.model.now().date()
    fdays = [date.fromisoformat(t) for t in md["daily"]["time"]] if md and md.get("daily") else []
    end = max([times[-1], today] + fdays)
    total = (end - times[0]).days or 1
    XD = lambda dd: x0 + (x1 - x0) * (dd - times[0]).days / total
    X = lambda i: XD(times[i])
    if tab == "temp":
        hi = [u.t(v) for v in d["temperature_2m_max"]]
        lo = [u.t(v) for v in d["temperature_2m_min"]]
        lines = [(hi, RED), (lo, BLUE)]
        fmt = lambda v: f"{round(v)}°"
    elif tab == "precip":
        lines = [([u.p(v) for v in d["precipitation_sum"]], BLUE)]
        fmt = lambda v: f"{v:.0f}" if v >= 1 or v == 0 else f"{v:.1f}"
    elif tab == "humidity":
        lines = [(d.get("relative_humidity_2m_mean") or [None] * n, "#7FD6FF")]
        fmt = lambda v: f"{round(v)}%"
    else:
        lines = [([u.w(v) for v in d["wind_speed_10m_max"]], TEAL)]
        fmt = lambda v: f"{round(v)}"
    vals = [v for vs, _ in lines for v in vs if v is not None]
    lo_v, hi_v, grid = nice_range(min(vals or [0]), max(vals or [1]), 4, floor_zero=tab != "temp")
    Y = lambda v: py1 - (v - lo_v) / ((hi_v - lo_v) or 1) * (py1 - py0)
    for g in grid:
        c.line([(x0, Y(g)), (x1, Y(g))], T["grid"], 1)
        c.text(x0 - 8, Y(g), fmt(g), size=9.5, color="dim", anchor="end")
    # month labels
    seen = set()
    for t in times + [dd for dd in fdays if dd > times[-1]]:
        key = (t.year, t.month)
        if t.day == 1 and key not in seen and XD(t) < x1 - 20:
            seen.add(key)
            c.line([(XD(t), py0), (XD(t), py1)], T["grid"], 1)
            c.text(XD(t) + 3, py1 + 14, calendar.month_abbr[t.month] + (f" '{t.year % 100}" if t.month == 1 else ""),
                   size=9.5, color="dim")
    base = Y(max(lo_v, 0)) if tab != "temp" else py1
    snow_days = d.get("snowfall_sum") or [0] * n
    for vs, col in lines:
        if tab == "precip":
            bw = max(1, (x1 - x0) / n)
            for i, v in enumerate(vs):
                if v:
                    fill = glossy.snow_color(m) if (snow_days[i] or 0) > 0 else col  # snow white, as in Sky
                    c.rect(X(i) - bw / 2, Y(v), bw, max(1, base - Y(v)), fill=fill)
            continue
        pts = [(X(i), Y(v)) for i, v in enumerate(vs) if v is not None]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            c.shapes.append(fenn.polygon([(ax, ay), (bx, by), (bx, base), (ax, base)], fill=col + "1A"))
        c.line(pts, col, 1.3)
    # the 16-day forecast after today, dotted
    if fdays and tab in ("temp", "precip"):
        fd = md["daily"]
        names = ["temperature_2m_max", "temperature_2m_min"] if tab == "temp" else ["precipitation_sum"]
        conv = u.t if tab == "temp" else u.p
        for name, col in zip(names, (RED, BLUE) if tab == "temp" else (BLUE,)):
            pts = [(XD(dd), Y(conv(v))) for dd, v in zip(fdays, fd[name]) if dd >= today and v is not None]
            if tab == "precip":
                fsnow = {dd: (sv or 0) > 0 for dd, sv in zip(fdays, fd.get("snowfall_sum") or [0] * len(fdays))}
                for (px, py), dd in zip(pts, [dd for dd, v in zip(fdays, fd[name]) if dd >= today and v is not None]):
                    c.rect(px - 1, py, 2, max(1, base - py), fill=(glossy.snow_color(m) if fsnow.get(dd) else col) + "88")
                continue
            for a, b in zip(pts, pts[1:]):
                steps = max(1, int((b[0] - a[0]) // 4))
                for j in range(0, steps, 2):
                    t0, t1 = j / steps, min(1, (j + 1) / steps)
                    c.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                            (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], col, 1.4)
    tx = XD(today)
    c.line([(tx, py0 - 6), (tx, py1)], T["line"], 1)
    tx = min(tx, W - 24)
    c.rect(tx - 20, py0 - 16, 40, 16, fill=T["on"], radius=8)
    c.text(tx, py0 - 8, "Today", size=9.5, color="text", anchor="center", bold=True)
    leg = {"temp": [("Daily high", RED), ("Daily low", BLUE)],
           "precip": [(f"Rain ({u.label('precip')})", BLUE), ("Snow", glossy.snow_color(m))],
           "humidity": [("Daily average", "#7FD6FF")], "wind": [(f"Daily maximum ({u.label('wind')})", TEAL)]}[tab]
    lx = 14
    for lab, col in leg:
        c.circle(lx + 4, top + ph + 46, 4, fill=col)
        c.text(lx + 12, top + ph + 46, lab, size=10.5, color="dim")
        lx += tw(lab, 10.5) + 30
    if tab in ("temp", "precip") and fdays:
        c.text(W - 14, top + ph + 46, "After today: the 16-day forecast", size=10, color="dim", anchor="end")
    y = top + ph + 66

    # the tables
    months = {}
    for i, t in enumerate(times):
        e = months.setdefault((t.year, t.month), {"hi": [], "lo": [], "mm": [], "wind": []})
        for key, col in (("hi", "temperature_2m_max"), ("lo", "temperature_2m_min"), ("mm", "precipitation_sum"),
                         ("wind", "wind_speed_10m_max")):
            v = d[col][i]
            if v is not None:
                e[key].append(v)
    full = {k: v for k, v in months.items() if len(v["hi"]) >= 20}
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    name = lambda k: calendar.month_name[k[1]]
    rows = []
    if full:
        rows = [("thermometer-hot", "#FF8A65", "Hottest month", name(max(full, key=lambda k: mean(full[k]["hi"])))),
                ("thermometer-cold", BLUE, "Coldest month", name(min(full, key=lambda k: mean(full[k]["lo"])))),
                ("drop", "#7FD6FF", "Wettest month", name(max(full, key=lambda k: sum(full[k]["mm"])))),
                ("wind", TEAL, "Windiest month", name(max(full, key=lambda k: mean(full[k]["wind"]))))]
    th = 30 + 26 * len(rows) + 8
    card_box(c, T, 0, y, W, th, "Past 12 months")
    for j, (g, col, lab, val) in enumerate(rows):
        ry = y + 46 + j * 26
        c.glyph(24, ry, g, 14, col, True)
        c.text(40, ry, lab, size=11.5, color="dim")
        c.text(W - 14, ry, val, size=11.5, color="text", anchor="end", bold=True)
        if j:
            c.line([(14, ry - 13), (W - 14, ry - 13)], T["grid"], 1)
    y += th + 8
    stats = [(f"High ({u.label('temp')})", [u.t(v) for v in d["temperature_2m_max"] if v is not None], 0),
             (f"Low ({u.label('temp')})", [u.t(v) for v in d["temperature_2m_min"] if v is not None], 0),
             (f"Precipitation ({u.label('precip')})", [u.p(v) for v in d["precipitation_sum"] if v is not None], 1),
             (f"Wind ({u.label('wind')})", [u.w(v) for v in d["wind_speed_10m_max"] if v is not None], 0)]
    th = 54 + 26 * len(stats)
    card_box(c, T, 0, y, W, th, "Daily summary")
    cols = [W - 190, W - 110, W - 30]
    for x, lab in zip(cols, ("Max", "Average", "Min")):
        c.text(x, y + 18, lab, size=10.5, color="dim", anchor="center", bold=True)
    for j, (lab, vs, digits) in enumerate(stats):
        ry = y + 46 + j * 26
        if j:
            c.line([(14, ry - 13), (W - 14, ry - 13)], T["grid"], 1)
        c.text(14, ry, lab, size=11.5, color="dim")
        if vs:
            show = (lambda v: f"{v:.{digits}f}") if digits else (lambda v: f"{round(v)}")
            for x, v in zip(cols, (max(vs), sum(vs) / len(vs), min(vs))):
                c.text(x, ry, show(v), size=11.5, color="text", anchor="center", bold=True)
    c.h = y + th
    return node(m, "pn:trends", c)


# ---- the page

def heading(text):
    return fenn.text(text, bold=True)


def view(m, footer):
    parts = [current(m), day_cards(m), chart(m),
             heading("Weather details"), details(m),
             heading("Monthly"), monthly(m),
             heading("Weather trends"), trends(m)]
    parts += glossy.places(m)
    parts += footer
    return fenn.column(parts, gap=10, scroll=True, id="panorama")



def click(m, head, arg, extra, x):
    """A click on one of Panorama's canvases ("pn_<head>:<arg>")."""
    st = m.state
    if head == "tab":
        st["pn_tab"] = arg
        st["pn_sel"] = None
    elif head == "pick":
        st["pn_sel"] = ui.pick_index(extra, x)
    elif head == "month":
        st["pn_month"] = int(arg)
    elif head == "trend":
        st["pn_trend"] = arg
