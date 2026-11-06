"""Reading the forecast: what it says now, which hours belong to which day,
and a short summary in words made from the hourly numbers. fc is the
Open-Meteo response from wx.forecast (metric)."""

from datetime import datetime, timedelta

import units as u
import wx


class Model:
    def __init__(self, fc, aq=None):
        self.fc = fc
        self.aq = aq
        h = fc["hourly"]
        self.times = [wx.parse_local(t) for t in h["time"]]
        self.days = fc["daily"]["time"]
        self.off = int(fc.get("utc_offset_seconds") or 0)

    # ---- time

    def now(self):
        return wx.local_now(self.fc)

    def to_utc(self, local):
        return local - timedelta(seconds=self.off)

    def to_local(self, utc):
        return None if utc is None else utc + timedelta(seconds=self.off)

    def today(self):
        d = self.now().strftime("%Y-%m-%d")
        return self.days.index(d) if d in self.days else 0

    def hour_now(self):
        key = self.now().strftime("%Y-%m-%dT%H")
        h = self.fc["hourly"]["time"]
        return next((i for i, t in enumerate(h) if t[:13] >= key), len(h) - 1)

    def day_hours(self, k):
        d = self.days[k]
        return [i for i, t in enumerate(self.fc["hourly"]["time"]) if t.startswith(d)]

    def h(self, name, i):
        col = self.fc["hourly"].get(name)
        return col[i] if col and 0 <= i < len(col) else None

    def d(self, name, k):
        col = self.fc["daily"].get(name)
        return col[k] if col and 0 <= k < len(col) else None

    def hs(self, name, idxs):
        col = self.fc["hourly"].get(name) or []
        return [col[i] if i < len(col) else None for i in idxs]

    # ---- now

    def cur(self, name):
        return self.fc["current"].get(name)

    def is_day(self):
        return bool(self.cur("is_day"))

    def condition(self):
        return wx.condition(self.cur("weather_code"), self.is_day())

    def day_date(self, k):
        return datetime.strptime(self.days[k], "%Y-%m-%d")

    def day_name(self, k, short=True):
        if k == self.today():
            return "Today"
        if k == self.today() + 1 and not short:
            return "Tomorrow"
        if k == self.today() - 1:
            return "Yesterday"
        return self.day_date(k).strftime("%a" if short else "%A")

    def sun(self, k):
        return wx.parse_local(self.d("sunrise", k)), wx.parse_local(self.d("sunset", k))

    # ---- air quality

    def aq_now(self, standard):
        if not self.aq:
            return None
        return self.aq.get("current", {}).get("us_aqi" if standard == "us" else "european_aqi")

    # ---- words

    def summary(self):
        """One or two sentences about the next hours, from the forecast."""
        start = self.hour_now()
        idx = list(range(start, min(start + 18, len(self.times))))
        if not idx:
            return ""
        prec = self.hs("precipitation", idx)
        prob = self.hs("precipitation_probability", idx)
        codes = self.hs("weather_code", idx)
        temps = self.hs("temperature_2m", idx)
        gusts = self.hs("wind_gusts_10m", idx)
        snow = self.hs("snowfall", idx)
        wet = [(p or 0) >= 0.2 or (q or 0) >= 60 for p, q in zip(prec, prob)]
        out = []
        noun = lambda i: "Snow" if (snow[i] or 0) > 0 else "Rain"
        if wet[0]:
            stop = next((k for k, w in enumerate(wet) if not w), None)
            if stop is None:
                out.append(f"{noun(0)} will continue for the rest of the period.")
            else:
                out.append(f"{noun(0)} should stop around {self.clock(self.times[idx[stop]])}.")
        else:
            begin = next((k for k, w in enumerate(wet) if w), None)
            if begin is not None:
                out.append(f"{noun(begin)} is expected around {self.clock(self.times[idx[begin]])}.")
            else:
                end_today = [k for k, i in enumerate(idx) if self.times[i].date() == self.times[idx[0]].date()]
                rest = [codes[k] for k in end_today] or codes[:6]
                if all(c in (0, 1) for c in rest):
                    out.append("Clear skies for the rest of the day." if self.is_day() else "Clear skies tonight.")
                elif all(c in (2,) or c in (0, 1) for c in rest):
                    out.append("Partly cloudy for the rest of the day.")
                elif all(c == 3 or c in (45, 48) for c in rest):
                    out.append("Cloudy conditions will continue for the rest of the day.")
                elif codes[0] in (2, 3) and any(c in (0, 1) for c in rest[3:]):
                    out.append(f"Clouds will clear around {self.clock(self.times[idx[next(k for k, c in enumerate(rest) if c in (0, 1) and k >= 3)]])}.")
        g = [x for x in gusts[:12] if x is not None]
        if g and max(g) >= 45:
            out.append(f"Wind gusts up to {u.wind(max(g))}.")
        else:
            t = [x for x in temps[:14] if x is not None]
            if t and t[0] - min(t) >= 6:
                k = t.index(min(t))
                when = "tonight" if self.times[idx[k]].hour >= 18 or self.times[idx[k]].hour < 6 else "later"
                out.append(f"Temperatures drop to {u.deg(min(t))} {when}.")
            elif t and max(t) - t[0] >= 5:
                out.append(f"Warming up to {u.deg(max(t))} by {self.clock(self.times[idx[t.index(max(t))]])}.")
        return " ".join(out[:2])

    clock = staticmethod(lambda dt: dt.strftime("%H:%M"))  # main.py swaps in the user's clock
