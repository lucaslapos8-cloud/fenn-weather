"""The "Brief" look: the answer first, in a typewriter font. Is today
colder, warmer or about the same as yesterday (or tomorrow than today)?
Then the morning, noon, evening and night temperatures with the change
from the day before. The header arrow switches between today and
tomorrow; Settings choose whether to compare the real or the feels-like
temperature, and how big a change counts.

`m` is main.py. Clicks come back as "brief:" button events."""

import fenn
import mono as mono_look
import units as u

PERIODS = [("Morning", 8), ("Noon", 13), ("Evening", 18), ("Night", 22)]
COLD, WARM = "#5A8CFF", "#FF5A4E"


def field(m):
    return "apparent_temperature" if m.settings.get("brief_feels") else "temperature_2m"


def at(M, k, hour, name):
    """The day's value at that hour (None outside the forecast)."""
    hours = M.day_hours(k)
    if not hours:
        return None
    i = next((i for i in hours if M.times[i].hour == hour), None)
    return M.h(name, i) if i is not None else None


def compare(m, k):
    """[(period, temp, code, is_day, change)] for day k against day k-1, and
    the average change (°C)."""
    M = m.model
    name = field(m)
    rows, changes = [], []
    for label, hour in PERIODS:
        t, before = at(M, k, hour, name), at(M, k - 1, hour, name) if k > 0 else None
        code, day = at(M, k, hour, "weather_code"), at(M, k, hour, "is_day")
        change = None if t is None or before is None else t - before
        if change is not None:
            changes.append(change)
        rows.append((label, t, code, bool(day), change))
    return rows, (sum(changes) / len(changes) if changes else None)


def verdict(m, change):
    limit = float(m.settings.get("brief_threshold", 1))
    limit_c = limit / 1.8 if u.unit("temp") == "f" else limit
    if change is None:
        return "UNKNOWN", "dim"
    if change <= -limit_c:
        return "COLDER", COLD
    if change >= limit_c:
        return "WARMER", WARM
    return "ABOUT THE SAME", "text"


def mono(text, size=None, color=None, bold=None):
    return fenn.text(text, size=size, color=color, bold=bold, mono=True)


def signed(change):
    if change is None:
        return "–"
    v = round(u.t_delta(change))
    return f"{'+' if v > 0 else '±' if v == 0 else '−'}{abs(v)}{u.label('temp')}"


def view(m, footer):
    M = m.model
    tomorrow = m.state.get("brief_day") == 1
    k = M.today() + (1 if tomorrow else 0)
    k = min(k, len(M.days) - 1)
    rows, change = compare(m, k)
    word, color = verdict(m, change)
    place = (m.settings.get("place") or {}).get("name", "")
    what = "feels-like temperature" if m.settings.get("brief_feels") else "weather"
    if tomorrow:
        lead, tail = f"Tomorrow's {what} will be", "than today"
    else:
        lead, tail = f"Today's {what} is", "than yesterday"
    if word == "ABOUT THE SAME":
        tail = "as today" if tomorrow else "as yesterday"
    table = []
    for label, t, code, day, ch in rows:
        temp = f"{u.deg(t)}{u.label('temp')[-1]}" if t is not None else "–"
        table += [mono(label, color="dim"), mono(temp), fenn.icon(mono_look.outline(code, day), size=16, color="text"),
                  mono(signed(ch), color="dim")]
    parts = [
        mono(f"*{place}*", color="dim"),
        fenn.spacer(26),
        mono(lead, size="title"),
        mono(word, size="huge", color=color),
        mono(tail, size="title"),
        fenn.spacer(18),
        mono("*****", color="faint"),
        fenn.spacer(6),
        fenn.grid(4, table, gap=10),
        fenn.spacer(14),
        fenn.row([fenn.button("brief:0", label="Today", icon="sun", primary=not tomorrow),
                  fenn.button("brief:1", label="Tomorrow", icon="arrow-right", primary=tomorrow)], gap=8),
    ]
    if change is not None:
        parts.insert(5, mono(f"{signed(change)} on average", size="small", color="faint"))
    return fenn.column(parts + [fenn.spacer(6)] + footer, gap=4, scroll=True, id="brief")

