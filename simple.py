"""The "Simple" look: one card like a home-screen widget. The place, the
temperature, today's high and low, the condition and a big 3D icon, then
the next six days or hours (the Daily / Hourly switch, or the header
button). `m` is main.py; clicks come back as "sm_" actions."""

import fenn
import glossy
import units as u
import wx
from ui import Canvas, fit, tw

DAYS, HOURS = "days", "hours"


def node(m, cid, c):
    m.canvases[cid] = c
    return fenn.canvas(c.h, c.shapes, width=c.w, id=cid)


def mode(m):
    return HOURS if m.settings.get("simple_mode") == HOURS else DAYS


def switch(m, W):
    """The Daily / Hourly switch, centered."""
    T = glossy.tones(m)
    c = Canvas(W)
    c.h = 28
    items = [(DAYS, "Daily"), (HOURS, "Hourly")]
    widths = [tw(lab, 11.5, True) + 26 for _, lab in items]
    x = (W - sum(widths) - 6) / 2
    c.rect(x, 1, sum(widths) + 6, 26, fill=T["well"], radius=13)
    px = x + 3
    for (key, lab), wd in zip(items, widths):
        on = key == mode(m)
        if on:
            c.rect(px, 4, wd, 20, fill=T["on"], radius=10)
        c.text(px + wd / 2, 14, lab, size=11.5, color="text" if on else "dim", anchor="center", bold=True)
        c.region(px, 0, px + wd, 28, f"sm_mode:{key}")
        px += wd
    return node(m, "sm:switch", c)


def strip(m, W):
    """Six days or hours: name, 3D icon, temperature."""
    M = m.model
    cells = []
    cw = W / 6
    if mode(m) == HOURS:
        n = glossy.now_info(M)
        start = M.hour_now()
        for k, i in enumerate(range(start, min(start + 6, len(M.times)))):
            temp, code, day = (n["temp"], n["code"], n["day"]) if k == 0 else \
                (M.h("temperature_2m", i), M.h("weather_code", i), bool(M.h("is_day", i)))
            rain = M.h("precipitation_probability", i) or 0
            cells.append(cell(cw, "Now" if k == 0 else m.hour_label(M.times[i]),
                              glossy.icon(wx.icon_name(code, day), True), u.deg(temp), f"{rain}%" if rain >= 20 else ""))
    else:
        k0 = M.today()
        for k in range(k0, min(k0 + 6, len(M.days))):
            name = "Today" if k == k0 else M.day_date(k).strftime("%a")
            cells.append(cell(cw, name, glossy.icon(wx.icon_name(M.d("weather_code", k), True), True),
                              u.deg(M.d("temperature_2m_max", k)), u.deg(M.d("temperature_2m_min", k))))
    return fenn.grid(len(cells) or 1, cells, gap=0)


def cell(cw, top, image, big, small):
    head = fenn.canvas(22, [fenn.label(cw / 2, 11, top, size=14, color="dim", anchor="center")], width=cw)
    foot = fenn.canvas(38, [fenn.label(cw / 2, 11, big, size=17, color="text", anchor="center", bold=True),
                            fenn.label(cw / 2, 30, small, size=11, color="dim", anchor="center")], width=cw)
    return fenn.column([head, fenn.image(image, width=42, height=42), foot], gap=2, align="center")


def view(m, footer):
    M = m.model
    n = glossy.now_info(M)
    k = M.today()
    W = m.page_w
    inner = W - 36
    img = 104
    lw = inner - img - 6
    c = Canvas(lw)
    c.h = 118
    place = (m.settings.get("place") or {}).get("name", "")
    c.glyph(9, 15, "map-pin", 17, "text", True)
    c.text(24, 15, fit(place, 17, lw - 30), size=17, color="text")
    temp = u.deg(n["temp"])
    c.text(-3, 72, temp, size=66, color="text")
    tx = tw(temp, 66) + 14
    hi, lo = u.deg(M.d("temperature_2m_max", k)), u.deg(M.d("temperature_2m_min", k))
    c.text(tx, 58, f"H: {hi}   L: {lo}", size=16, color="dim")
    words = m.model.summary().split(".")[0] if (M.cur("weather_code") or 0) >= 51 else n["text"]
    c.text(tx, 84, fit(words or n["text"], 16, lw - tx), size=16, color="text")
    c.region(0, 0, lw, c.h, "sm_mode:" + (HOURS if mode(m) == DAYS else DAYS))
    top = fenn.row([node(m, "sm:top", c), fenn.image(glossy.icon(n["icon"]), width=img, height=img)], gap=6)
    card = fenn.card([top, strip(m, inner), switch(m, inner)], padding=18, gap=10)
    return fenn.column([card] + footer, gap=10, scroll=True, id="simple")


def click(m, head, arg, extra, x):
    if head == "mode" and arg in (DAYS, HOURS):
        m.settings["simple_mode"] = arg
        m.save_settings()
