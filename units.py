"""Unit choices and conversions. Forecasts are kept in metric (°C, km/h,
mm, hPa, m); everything shown goes through here. A unit left at None
follows the place: the US and a few others get °F, mph, inches and inHg."""

IMPERIAL = {"United States", "United States of America", "Liberia", "Myanmar", "Bahamas", "Belize",
            "Cayman Islands", "Palau", "Puerto Rico", "Guam"}

CHOICES = {
    "temp": [("c", "°C"), ("f", "°F")],
    "wind": [("kmh", "km/h"), ("mph", "mph"), ("ms", "m/s"), ("kn", "kn"), ("bft", "Bft")],
    "precip": [("mm", "mm"), ("in", "in")],
    "pressure": [("hpa", "hPa"), ("inhg", "inHg"), ("mmhg", "mmHg")],
    "dist": [("km", "km"), ("mi", "mi")],
}

settings = {}  # main.py hands its settings dict over


def _imperial():
    p = settings.get("place") or {}
    return p.get("country") in IMPERIAL


def unit(kind):
    chosen = settings.get(kind)
    if chosen:
        return chosen
    imp = _imperial()
    uk = (settings.get("place") or {}).get("country") == "United Kingdom"
    return {"temp": "f" if imp else "c", "wind": "mph" if imp or uk else "kmh",
            "precip": "in" if imp else "mm", "pressure": "inhg" if imp else "hpa",
            "dist": "mi" if imp or uk else "km"}[kind]


def label(kind):
    return dict(CHOICES[kind])[unit(kind)]


# ---- temperature

def t(c):
    if c is None:
        return None
    return c * 1.8 + 32 if unit("temp") == "f" else c


def t_delta(dc):
    return dc * 1.8 if unit("temp") == "f" else dc


def deg(c):
    return "–" if c is None else f"{round(t(c))}°"


# ---- wind

BEAUFORT = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]
BEAUFORT_NAMES = ["Calm", "Light air", "Light breeze", "Gentle breeze", "Moderate breeze", "Fresh breeze",
                  "Strong breeze", "Near gale", "Gale", "Strong gale", "Storm", "Violent storm", "Hurricane force"]


def beaufort(kmh):
    return next((i for i, lim in enumerate(BEAUFORT) if kmh < lim), 12)


def w(kmh):
    """The number in the chosen unit."""
    if kmh is None:
        return None
    u = unit("wind")
    return {"kmh": kmh, "mph": kmh / 1.609344, "ms": kmh / 3.6, "kn": kmh / 1.852}.get(u, beaufort(kmh))


def wind(kmh, with_unit=True):
    if kmh is None:
        return "–"
    v = w(kmh)
    num = f"{v:.1f}" if unit("wind") == "ms" and v < 10 else f"{round(v)}"
    return f"{num} {label('wind')}" if with_unit else num


DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(deg_from):
    return "–" if deg_from is None else DIRS[round(deg_from / 22.5) % 16]


# ---- precipitation, pressure, distance

def p(mm):
    if mm is None:
        return None
    return mm / 25.4 if unit("precip") == "in" else mm


def precip(mm, with_unit=True):
    if mm is None:
        return "–"
    v = p(mm)
    if unit("precip") == "in":
        num = "0" if v < 0.005 else f"{v:.2f}".lstrip("0") if v < 1 else f"{v:.1f}"
        return num + ("″" if with_unit else "")
    num = "0" if v < 0.05 else f"{v:.1f}" if v < 10 else f"{round(v)}"
    return f"{num} mm" if with_unit else num


def pr(hpa):
    if hpa is None:
        return None
    return {"hpa": hpa, "inhg": hpa * 0.02953, "mmhg": hpa * 0.750062}[unit("pressure")]


def pressure(hpa, with_unit=True):
    if hpa is None:
        return "–"
    v = pr(hpa)
    num = f"{v:.2f}" if unit("pressure") == "inhg" else f"{round(v)}"
    return f"{num} {label('pressure')}" if with_unit else num


def dist(m):
    if m is None:
        return "–"
    v = m / 1609.344 if unit("dist") == "mi" else m / 1000
    num = f"{v:.1f}" if v < 10 else f"{round(v)}"
    return f"{num} {label('dist')}"
