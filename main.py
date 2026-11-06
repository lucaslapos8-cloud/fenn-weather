"""Weather for Fenn: the temperature and sky on the tile, and a page in one
of two looks. Glossy (the default): today with sunrise and sunset, rain,
humidity and wind, and the next 7 days or hours. Sky: a full dashboard of
cards (hourly, 10 days, rain, air quality, wind, sun, moon, UV and more),
each opening a detail view with a chart. Forecasts from Open-Meteo (free,
no key); sun and moon computed locally.

This file keeps the settings and view state, fetches in the background and
handles clicks; glossy.py and sky.py draw."""

import os
import sys
import threading
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

import data
import fenn
import glossy
import sky
import ui
import units as u
import wx

HERE = os.path.dirname(os.path.abspath(__file__))
app = fenn.Plugin()

RETRY = 60

clock24, _metric = wx.windows_defaults()
DEFAULTS = {
    "place": None,          # the place shown: {"name", "region", "country", "lat", "lon"}
    "auto": True,           # show "my location" (the IP address's city)
    "auto_place": None,     # where "my location" was last found
    "places": [],           # saved places, in order
    "temp": None, "wind": None, "precip": None, "pressure": None, "dist": None,  # None: by the place
    "clock24": clock24,
    "look": "glossy",       # "glossy" or "sky"
    "strip": "days",        # Glossy's bottom row: "days" or "hours"
    "aqi": "auto",          # "auto" (US AQI in the US, else European), "eu" or "us"
    "refresh": 15,          # minutes
    "hour_mode": "conditions",
    "cards_hidden": [],
    "cards_order": [],
    "animate": True,        # move the Sky look's clouds, rain and snow
    "sky_bg": 100,          # Sky look: background opacity, %
    "sky_fx": 100,          # Sky look: clouds, sun, rain... opacity, %
}
settings = {**DEFAULTS, **(app.load("settings", {}) or {})}
if settings.get("recent") and not settings["places"]:
    settings["places"] = settings.pop("recent")
settings.pop("recent", None)
u.settings = settings

fc = app.load("forecast")
aq = app.load("air")
if fc and fc.get("v") != 3:
    fc = None  # an older format; fetch again
model = None

view = "main"               # "main", "settings" or "places"
state = {"hour_mode": settings["hour_mode"], "hour_page": 0, "hour_sel": None, "detail": None, "edit_places": False}
results = None
search_gen = int(time.time()) % 100000  # a fresh id, so Fenn doesn't keep old text in the box
error = ""
busy = False
last_try = 0.0
page_w, page_h = 536, 312
tile = ("wide", 104, 36)
canvases = {}               # canvas id -> ui.Canvas, for clicks
summ = {}                   # place key -> Open-Meteo summary (places view)
summ_time = 0.0
summaries_busy = False


def save_settings():
    app.save("settings", settings)


def clock(dt):
    if dt is None:
        return "–"
    if settings["clock24"]:
        return f"{dt.hour}:{dt.minute:02d}"
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'am' if dt.hour < 12 else 'pm'}"


def hour_label(dt):
    if settings["clock24"]:
        return f"{dt.hour:02d}:00"
    return f"{dt.hour % 12 or 12} {'am' if dt.hour < 12 else 'pm'}"


data.Model.clock = staticmethod(clock)


def rebuild():
    global model
    model = data.Model(fc, aq) if fc else None


rebuild()


# ---- the animated sky

T0 = time.monotonic()


def anim_time():
    return time.monotonic() - T0


def system_animations():
    """Windows' "Animation effects" setting (off = reduced motion)."""
    try:
        import ctypes
        on = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(on), 0)
        return bool(on.value)
    except Exception:
        return True


anim = {"template": None, "last": 0.0, "system": system_animations(), "checked": time.monotonic()}


def dash_view(c, shapes):
    return fenn.column([fenn.canvas(c.h, shapes, width=c.w, id="dash")], scroll=True, id="dash")


def anim_tick():
    """Redraws only the sky behind the header, 6 to 15 times a second, while
    the Sky dashboard is open. The rest of the page is serialized once and
    reused, so a frame costs little."""
    if time.monotonic() - anim["checked"] > 30:
        anim.update(system=system_animations(), checked=time.monotonic())
    c = canvases.get("dash")
    if not (app.page_open and view == "main" and settings["look"] == "sky" and not state["detail"]
            and settings["animate"] and anim["system"] and c is not None and getattr(c, "scene", None)):
        return
    now = time.monotonic()
    if now - anim["last"] < 1 / c.scene["fps"] - 0.01:
        return
    anim["last"] = now
    if anim["template"] is None:
        msg = fenn._clean({"type": "page", "view": dash_view(c, c.below + ["@@SKY@@"] + c.above), "actions": actions()})
        anim["template"] = fenn.json.dumps(msg, separators=(",", ":"), ensure_ascii=False)
    sky_json = fenn.json.dumps(sky.sky_shapes(c, anim_time()), separators=(",", ":"), ensure_ascii=False)[1:-1]
    line = anim["template"].replace('"@@SKY@@"', sky_json or '{"type":"rect","x":0,"y":0,"w":0,"h":0}')
    with fenn._out_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def aqi_standard():
    if settings["aqi"] in ("eu", "us"):
        return settings["aqi"]
    p = settings["place"] or {}
    return "us" if p.get("country") in ("United States", "United States of America") else "eu"


def card_order():
    order = [k for k in settings["cards_order"] if k in sky.SMALL]
    return order + [k for k in sky.SMALL if k not in order]


# ---- fetching (worker threads; results come back through the inbox)

def refresh(force=False):
    global busy, last_try
    if busy:
        return
    age = time.time() - (fc or {}).get("fetched", 0)
    fresh = fc and age < settings["refresh"] * 60 and (aq is not None or age < 120)
    if fresh:  # but is the cache for the place being shown?
        if settings["auto"] or not settings["place"]:
            fresh = not settings["auto_place"] or same(fc.get("place"), settings["auto_place"])
        else:
            fresh = same(fc.get("place"), settings["place"])
    if not force and fresh:
        return
    if not force and time.time() - last_try < RETRY:
        return
    busy, last_try = True, time.time()
    auto = settings["auto"] or not settings["place"]
    want = settings["place"]

    def work():
        try:
            place = want
            if auto:
                try:
                    place = wx.place_from_ip()
                except Exception:
                    place = settings.get("auto_place") or want
                    if not place:
                        raise
            forecast = wx.forecast(place)
            try:
                air = wx.air_quality(place)
            except Exception:
                air = None
            app._inbox.put({"type": "weather", "place": place, "auto": auto, "data": forecast, "air": air})
        except Exception as e:
            app._inbox.put({"type": "weather", "error": f"{type(e).__name__}: {e}"})

    threading.Thread(target=work, daemon=True).start()


@app.on_message("weather")
def on_weather(msg):
    global fc, aq, busy, error
    busy = False
    if msg.get("error"):
        error = "Can't reach the weather service"
        app.log(msg["error"], "warn")
    else:
        if msg["auto"] != (settings["auto"] or not settings["place"]):
            refresh(force=True)  # the place changed while fetching
            return
        error = ""
        fc, aq = msg["data"], msg["air"]
        if msg["auto"]:
            settings["auto_place"] = msg["place"]
            settings["place"] = msg["place"]
            save_settings()
        app.save("forecast", fc)
        app.save("air", aq)
        rebuild()
    draw()


def load_summaries(force=False):
    global summaries_busy, summ_time
    if summaries_busy or (not force and time.time() - summ_time < 600):
        return
    entries = ([("auto", settings["auto_place"])] if settings["auto_place"] else []) + \
        [(str(n), p) for n, p in enumerate(settings["places"])]
    if not entries:
        return
    summaries_busy = True

    def work():
        try:
            found = wx.summaries([p for _, p in entries])
            app._inbox.put({"type": "summaries", "data": {k: s for (k, _), s in zip(entries, found)}})
        except Exception as e:
            app._inbox.put({"type": "summaries", "data": None, "error": str(e)})

    threading.Thread(target=work, daemon=True).start()


@app.on_message("summaries")
def on_summaries(msg):
    global summ, summaries_busy, summ_time
    summaries_busy = False
    if msg.get("data") is not None:
        summ, summ_time = msg["data"], time.time()
    draw()


def summary_for(key):
    return summ.get(key)


def search(query):
    def work():
        try:
            found = wx.search_places(query)
            app._inbox.put({"type": "places", "results": found, "query": query})
        except Exception:
            app._inbox.put({"type": "places", "results": [], "query": query})

    threading.Thread(target=work, daemon=True).start()


@app.on_message("places")
def on_places(msg):
    global results
    results = msg
    draw()


def same(a, b):
    return a and b and round(a["lat"], 3) == round(b["lat"], 3) and round(a["lon"], 3) == round(b["lon"], 3)


def show_place(p):
    """Open a place (saved or not) on the dashboard."""
    global fc, aq, view
    settings["auto"] = p is None
    if p is not None:
        settings["place"] = p
    elif settings["auto_place"]:
        settings["place"] = settings["auto_place"]
    save_settings()
    fc = aq = None
    rebuild()
    view = "main"
    state.update(detail=None, hour_page=0, hour_sel=None, edit_places=False)
    refresh(force=True)


def add_place(p):
    global summ_time
    if not any(same(p, q) for q in settings["places"]):
        settings["places"].append(p)
        summ_time = 0
    show_place(p)


# ---- views

def loading_view():
    msg = "Finding the weather…" if busy or not error else error
    parts = [fenn.spacer(30), fenn.icon("cloud-sun", size=34, color="dim"), fenn.text(msg, color="dim")]
    if error and not busy:
        parts.append(fenn.button("retry", label="Try again", icon="arrow-clockwise"))
    return fenn.column(parts, gap=10, align="center")


def footer():
    if error:
        age = time.time() - (fc or {}).get("fetched", 0)
        text = f"{error}, showing the forecast from {int(age // 60)} min ago"
    elif busy:
        text = "Updating…"
    else:
        text = f"Updated {clock(datetime.fromtimestamp(fc.get('fetched', 0)))} · Open-Meteo"
    return [fenn.text(text, size="small", color="faint")]


def canvas_node(cid, c):
    canvases[cid] = c
    return c.node(cid)


def main_view():
    if not model:
        return loading_view()
    if settings["look"] == "sky":
        me = sys.modules[__name__]
        if state["detail"]:
            c = sky.detail(me, page_w)
            return fenn.column([canvas_node("detail", c)], scroll=True, id=f"detail:{state['detail']['kind']}")
        c = sky.dashboard(me, page_w)
        canvases["dash"] = c
        anim["template"] = None
        return dash_view(c, c.shapes)
    me = sys.modules[__name__]
    if state["detail"]:
        return fenn.column([glossy.detail(me)], scroll=True, id=f"gdetail:{state['detail']['kind']}")
    return glossy.view(me, footer())


def places_view():
    load_summaries()
    parts = [fenn.text_input(f"search:{search_gen}", hint="Search a city or town and press Enter")]
    if results is not None:
        found = results["results"]
        if found:
            parts.append(fenn.list_view([fenn.item(f"add:{k}", p["name"], ", ".join(x for x in (p["region"], p["country"]) if x),
                                                   icon="plus") for k, p in enumerate(found)]))
        else:
            parts.append(fenn.text(f"Nothing found for “{results['query']}”.", size="small", color="faint"))
    parts.append(canvas_node("places", sky.places(sys.modules[__name__], page_w)))
    if not settings["places"]:
        parts.append(fenn.text("Search above to save more places.", size="small", color="faint"))
    return fenn.column(parts, gap=8, scroll=True, id="places")


def chips_row(label, cid, options, selected):
    return fenn.row([fenn.text(label, color="dim"), fenn.chips(cid, options, selected)], gap=8)


def settings_view():
    parts = [chips_row("Look", "look", ["Glossy", "Sky"], 1 if settings["look"] == "sky" else 0)]
    for kind, label in (("temp", "Temperature"), ("wind", "Wind"), ("precip", "Precipitation"),
                        ("pressure", "Pressure"), ("dist", "Distance")):
        codes = [c for c, _ in u.CHOICES[kind]]
        parts.append(chips_row(label, f"u:{kind}", [lab for _, lab in u.CHOICES[kind]], codes.index(u.unit(kind))))
    parts += [
        chips_row("Clock", "clock", ["24-hour", "12-hour"], 0 if settings["clock24"] else 1),
        chips_row("Air quality", "aqi", ["Automatic", "European", "US"], ["auto", "eu", "us"].index(settings["aqi"])),
        chips_row("Refresh every", "refresh_every", ["15 min", "30 min", "1 hour"], [15, 30, 60].index(settings["refresh"])
                  if settings["refresh"] in (15, 30, 60) else 0),
        chips_row("Hourly shows", "hour_mode", ["Conditions", "Rain", "Wind"],
                  ["conditions", "precip", "wind"].index(settings["hour_mode"])),
        fenn.row([fenn.text("Sky background", color="dim"),
                  fenn.slider("sky_bg", settings["sky_bg"], min=0, max=100, step=5,
                              tooltip="0% is see-through like Glossy, 100% the full sky color")], gap=8),
        fenn.row([fenn.text("Sky effects", color="dim"),
                  fenn.slider("sky_fx", settings["sky_fx"], min=0, max=100, step=5,
                              tooltip="Clouds, sun, stars, rain, snow and lightning")], gap=8),
        fenn.toggle("animate", settings["animate"], label="Animated sky (drifting clouds, rain, snow, lightning)"),
        fenn.text("Units left as they were follow the place (°F, mph and inches in the US).", size="small", color="faint"),
        fenn.divider(),
        fenn.text("Sky cards", size="small", color="dim", bold=True),
    ]
    for n, key in enumerate(card_order()):
        parts.append(fenn.row([
            fenn.toggle(f"card:{key}", key not in settings["cards_hidden"], label=sky.CARD_NAMES[key]),
            fenn.spacer(),
            fenn.button(f"cardup:{key}", icon="caret-up", tooltip="Move up") if n else fenn.spacer(28),
        ], gap=6))
    parts += [
        fenn.button("cards_reset", label="Reset cards", icon="arrow-counter-clockwise"),
        fenn.divider(),
        fenn.text("Forecasts by Open-Meteo.com (CC BY 4.0); air quality from Copernicus CAMS via Open-Meteo. "
                  "Sun and moon are computed on this PC.", size="small", color="faint", wrap=True),
    ]
    return fenn.column(parts, gap=8, scroll=True, id="settings")


def actions():
    if view == "settings":
        return [{"id": "done", "icon": "check", "tooltip": "Done"}]
    if view == "places":
        return [{"id": "edit", "icon": "check" if state["edit_places"] else "pencil-simple",
                 "tooltip": "Done editing" if state["edit_places"] else "Remove or reorder places"},
                {"id": "done", "icon": "x", "tooltip": "Close"}]
    if state["detail"]:
        return [{"id": "back", "icon": "squares-four", "tooltip": "Back"}]
    if settings["look"] == "sky":
        return [{"id": "places", "icon": "list", "tooltip": "Places"},
                {"id": "refresh", "icon": "arrows-clockwise", "tooltip": "Refresh now"},
                {"id": "settings", "icon": "gear-six", "tooltip": "Look, units and cards"}]
    other = "Next 7 hours" if settings["strip"] == "days" else "Next 7 days"
    return [{"id": "strip", "icon": "clock" if settings["strip"] == "days" else "calendar-dots", "tooltip": other},
            {"id": "places", "icon": "list", "tooltip": "Places"},
            {"id": "settings", "icon": "gear-six", "tooltip": "Look, units and cards"}]


def tile_view():
    size, w, h = tile
    if not model:
        return fenn.column([fenn.icon("cloud-sun", size=22, color="dim"),
                            fenn.text("Loading" if busy or not error else "Offline", size="small", color="dim")],
                           gap=2, align="center", justify="center")
    if settings["look"] == "sky" and size == "wide" and w and h:
        return sky.tile(sys.modules[__name__], w, h)
    return glossy.tile(sys.modules[__name__], size)


page_sent = False


def draw():
    """The tile always; the page while it's open, and once before, because
    Fenn opens a plugin's page on a tile click only after it has one."""
    global page_sent
    sky.BG, sky.FX = settings["sky_bg"] / 100, settings["sky_fx"] / 100
    try:
        app.tile(tile_view())
    except Exception as e:
        app.log(f"tile: {type(e).__name__}: {e}", "error")
    if app.page_open or not page_sent:
        canvases.clear()
        body = {"settings": settings_view, "places": places_view}.get(view, main_view)()
        app.page(body, actions())
        page_sent = True


# ---- clicks on canvases

def open_detail(kind, day=None):
    k0 = model.today()
    state["detail"] = {"kind": kind, "day": k0 if day is None else day, "sel": None, "sub": 0}
    if kind == "aqi" and state["detail"]["day"] > k0 + 3:
        state["detail"]["day"] = k0


def on_canvas(cid, x, y):
    global summ_time
    c = canvases.get(cid)
    if not c:
        return
    action, extra = c.hit(x, y)
    if not action:
        return
    head, _, arg = action.partition(":")
    d = state["detail"]
    if head == "gtoday":
        state.update(g_day=None, ov_sel=0)
    elif head == "ovtab":
        state["ov_tab"] = arg
    elif head == "ovrange":
        if state.get("ov_range", "24h") != arg:
            state["ov_sel"] = 0
        state["ov_range"] = arg
    elif head == "ovpick":
        state["ov_sel"] = ui.pick_index(extra, x)
    elif head == "gsel":
        state["g_sel"] = int(arg)
    elif head == "ghour":
        i = int(arg)
        open_detail("temp", model.days.index(model.times[i].strftime("%Y-%m-%d")))
        state["detail"]["sel"] = i
    elif head == "detail":
        kind, _, day = arg.partition(":")
        open_detail(kind, int(day) if day else None)
    elif head == "mode":
        state.update(hour_mode=arg, hour_page=0)
    elif head == "hpage":
        state["hour_page"] = max(0, state["hour_page"] + int(arg))
    elif head == "hour":
        i = int(arg)
        state["hour_sel"] = None if state["hour_sel"] == i else i
    elif head == "day" and d:
        d.update(day=int(arg), sel=None, sel_aq=None, sel_sun=None)
    elif head == "sub" and d:
        d["sub"] = int(arg)
    elif head == "pick" and d:
        d["sel"] = model.day_hours(d["day"])[ui.pick_index(extra, x)]
    elif head == "pick_aq" and d:
        d["sel_aq"] = ui.pick_index(extra, x)
    elif head == "pick_sun" and d:
        d["sel_sun"] = ui.pick_index(extra, x)
    elif head == "moon" and d:
        d["moon_day"] = 0 if arg == "0" else d.get("moon_day", 0) + int(arg)
    elif head == "moonday" and d:
        d["moon_day"] = int(arg)
    elif head == "popen":
        show_place(None if arg == "auto" else settings["places"][int(arg)])
    elif head == "premove":
        settings["places"].pop(int(arg))
        summ_time = 0
        save_settings()
        load_summaries(True)
    elif head == "pup":
        n = int(arg)
        if n > 0:
            pl = settings["places"]
            pl[n - 1], pl[n] = pl[n], pl[n - 1]
            summ_time = 0
            save_settings()
            load_summaries(True)


# ---- events

@app.on_message("event")
def on_event(e):
    global view, results, search_gen
    eid, value, kind = e.get("id", ""), e.get("value"), e.get("kind")
    if eid in canvases and kind == "click" and isinstance(value, dict):
        on_canvas(eid, value.get("x", 0), value.get("y", 0))
    elif eid.startswith(("gday:", "ghour:")) and model:
        kind, n = eid.split(":")[0], int(eid.split(":")[1])
        if kind == "gday":
            state["g_day"] = n
            if state.get("ov_range", "24h") == "7d":
                state["ov_sel"] = n - model.today()
            else:  # today starts at now; another day at its warmest hour
                state["ov_sel"] = 0 if n == model.today() else \
                    max(range(24), key=lambda h: model.h("temperature_2m", model.day_hours(n)[h]) or -99)
        else:
            state.update(g_day=None, ov_range="24h", ov_sel=n)
    elif eid.startswith("city:"):
        key = eid[5:]
        if key == "auto":
            show_place(None)
        elif key.isdigit() and int(key) < len(settings["places"]):
            show_place(settings["places"][int(key)])
    elif eid == "settings":
        view, results = "settings", None
    elif eid == "places":
        view, results = "places", None
        load_summaries(True)
    elif eid == "done":
        view, results = "main", None
        state["edit_places"] = False
    elif eid == "edit":
        state["edit_places"] = not state["edit_places"]
    elif eid == "back":
        state["detail"] = None
    elif eid == "refresh":
        refresh(force=True)
    elif eid == "strip":
        settings["strip"] = "hours" if settings["strip"] == "days" else "days"
        state.update(g_day=None, ov_sel=0)
        save_settings()
    elif eid == "retry":
        refresh(force=True)
    elif eid.startswith("search:") and kind == "submit":
        q = (value or "").strip()
        if q:
            search(q)
    elif eid.startswith("add:") and results:
        k = int(eid[4:])
        if k < len(results["results"]):
            search_gen += 1
            p = results["results"][k]
            results = None
            add_place(p)
            save_settings()
    elif eid == "look":
        settings["look"] = "sky" if value["index"] == 1 else "glossy"
        state["detail"] = None
        save_settings()
    elif eid.startswith("u:"):
        k = eid[2:]
        settings[k] = u.CHOICES[k][value["index"]][0]
        save_settings()
    elif eid in ("sky_bg", "sky_fx"):
        settings[eid] = int(value or 0)
        if kind == "commit":
            save_settings()
    elif eid == "animate":
        settings["animate"] = bool(value)
        save_settings()
    elif eid == "clock":
        settings["clock24"] = value["index"] == 0
        save_settings()
    elif eid == "aqi":
        settings["aqi"] = ["auto", "eu", "us"][value["index"]]
        save_settings()
    elif eid == "refresh_every":
        settings["refresh"] = [15, 30, 60][value["index"]]
        save_settings()
    elif eid == "hour_mode":
        settings["hour_mode"] = state["hour_mode"] = ["conditions", "precip", "wind"][value["index"]]
        save_settings()
    elif eid.startswith("card:"):
        key = eid[5:]
        hidden = set(settings["cards_hidden"])
        hidden.discard(key) if value else hidden.add(key)
        settings["cards_hidden"] = sorted(hidden)
        save_settings()
    elif eid.startswith("cardup:"):
        order = card_order()
        n = order.index(eid[7:])
        if n > 0:
            order[n - 1], order[n] = order[n], order[n - 1]
        settings["cards_order"] = order
        save_settings()
    elif eid == "cards_reset":
        settings["cards_order"], settings["cards_hidden"] = [], []
        save_settings()
    draw()


@app.on_message("layout")
def on_layout(msg):
    global page_w, page_h, tile
    if msg.get("target") == "page":
        page_w, page_h = int(msg.get("width") or page_w), int(msg.get("height") or page_h)
    elif msg.get("target") == "tile":
        tile = (msg.get("size") or "wide", msg.get("width"), msg.get("height"))
    draw()


@app.on_message("page_open")
def on_open(_):
    refresh()
    draw()


@app.on_message("page_close")
def on_close(_):
    global view, results
    view, results = "main", None
    state.update(detail=None, edit_places=False)


@app.on_message("theme")
def on_theme(_):
    draw()


@app.on_message("hello")
def on_hello(_):
    draw()
    refresh()


# ---- timers

def tick():
    refresh()
    draw()  # clocks, "Updating..."


_stamps = {f: os.path.getmtime(os.path.join(HERE, f)) for f in os.listdir(HERE) if f.endswith(".py")}


def check_code():
    """Restart (Fenn starts the plugin again 2 s after it exits) when its
    code changes, e.g. after a git pull."""
    for f, t in _stamps.items():
        try:
            if os.path.getmtime(os.path.join(HERE, f)) != t:
                # Fenn gives up after 3 restarts in a minute: leave 25 s between them.
                mark = os.path.join(app.data_dir, "reloaded")
                if os.path.exists(mark) and time.time() - os.path.getmtime(mark) < 25:
                    return
                open(mark, "w").close()
                app.stop()
                return
        except OSError:
            pass


app.every(30, tick)
app.every(1 / 15, anim_tick)
app.every(2, check_code)
draw()
refresh()
app.run()
