"""Weather data: Open-Meteo forecasts and place search, the approximate
location from the IP address, and turning WMO weather codes into words and
icons. Standard library only."""

import json
import time
import urllib.parse
import urllib.request
import winreg
from datetime import datetime, timedelta, timezone

AGENT = "fenn-weather (+https://github.com/lucaslapos8-cloud/fenn-weather)"
FORECAST = "https://api.open-meteo.com/v1/forecast"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
IP_GEO = "https://get.geojs.io/v1/ip/geo.json"


def get_json(url, params=None, timeout=12):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---- places

def place_from_ip():
    """City-level location from the IP address (geojs.io, no key)."""
    d = get_json(IP_GEO)
    return {
        "name": d.get("city") or d.get("region") or "Your location",
        "region": d.get("region") or "",
        "country": d.get("country") or "",
        "lat": float(d["latitude"]),
        "lon": float(d["longitude"]),
    }


def search_places(query, language="en"):
    d = get_json(GEOCODE, {"name": query, "count": 6, "language": language, "format": "json"})
    out = []
    for r in d.get("results") or []:
        out.append({
            "name": r.get("name") or query,
            "region": r.get("admin1") or "",
            "country": r.get("country") or "",
            "lat": float(r["latitude"]),
            "lon": float(r["longitude"]),
        })
    return out


def place_line(p):
    """"Kyiv, Ukraine" (the region only when the country is missing)."""
    rest = p.get("country") or p.get("region") or ""
    return f"{p['name']}, {rest}" if rest and rest != p["name"] else p["name"]


# ---- forecast

HOURLY = ("temperature_2m,apparent_temperature,relative_humidity_2m,dew_point_2m,precipitation_probability,"
          "precipitation,rain,snowfall,weather_code,pressure_msl,surface_pressure,cloud_cover,visibility,"
          "wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index,is_day")
DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,"
         "sunrise,sunset,daylight_duration,uv_index_max,precipitation_sum,rain_sum,snowfall_sum,"
         "precipitation_hours,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,"
         "wind_direction_10m_dominant")
CURRENT = ("temperature_2m,apparent_temperature,relative_humidity_2m,dew_point_2m,is_day,weather_code,"
           "cloud_cover,pressure_msl,surface_pressure,visibility,wind_speed_10m,wind_direction_10m,"
           "wind_gusts_10m,precipitation,rain,snowfall,uv_index")


def forecast(place, *_):
    """Everything the page shows, always in metric (the page converts):
    yesterday and the next 10 days by hour and by day, and the next two
    hours in 15-minute steps."""
    d = get_json(FORECAST, {
        "latitude": round(place["lat"], 4),
        "longitude": round(place["lon"], 4),
        "current": CURRENT,
        "hourly": HOURLY,
        "daily": DAILY,
        "minutely_15": "precipitation,rain,snowfall",
        "forecast_minutely_15": 12,
        "past_minutely_15": 4,
        "timezone": "auto",
        "past_days": 1,
        "forecast_days": 10,
    })
    d["fetched"] = time.time()
    d["v"] = 3  # the fields above; older caches are fetched again
    d["place"] = place
    return d


AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"
POLLUTANTS = "pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide"


def air_quality(place):
    """European and US AQI with the pollutants, yesterday to 4 days ahead
    (Open-Meteo's CAMS model; a forecast, not a station measurement)."""
    d = get_json(AIR, {
        "latitude": round(place["lat"], 4),
        "longitude": round(place["lon"], 4),
        "current": "european_aqi,us_aqi," + POLLUTANTS,
        "hourly": "european_aqi,us_aqi," + POLLUTANTS,
        "timezone": "auto",
        "past_days": 1,
        "forecast_days": 4,
    })
    d["fetched"] = time.time()
    return d


def summaries(places):
    """Now, today's high and low, and the local time offset for several
    places in one request (for the places list)."""
    if not places:
        return []
    d = get_json(FORECAST, {
        "latitude": ",".join(str(round(p["lat"], 4)) for p in places),
        "longitude": ",".join(str(round(p["lon"], 4)) for p in places),
        "current": "temperature_2m,weather_code,is_day,precipitation",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 1,
    })
    return d if isinstance(d, list) else [d]


def local_now(fc):
    """The time where the place is (its UTC offset comes with the forecast)."""
    off = int(fc.get("utc_offset_seconds") or 0)
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=off)


def parse_local(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M")


# ---- WMO weather codes

CONDITIONS = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Heavy snow",
    95: "Thunderstorm", 96: "Storm and hail", 99: "Storm and hail",
}

ICONS = {
    0: "clear", 1: "mostly", 2: "partly", 3: "overcast", 45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "rain", 56: "sleet", 57: "sleet",
    61: "rain", 63: "rain", 65: "heavy-rain", 66: "sleet", 67: "sleet",
    71: "snow", 73: "snow", 75: "heavy-snow", 77: "snow",
    80: "showers", 81: "showers", 82: "heavy-rain", 85: "snow", 86: "heavy-snow",
    95: "thunder", 96: "hail", 99: "hail",
}


def condition(code, day=True):
    text = CONDITIONS.get(int(code or 0), "Cloudy")
    if day and code in (0, 1):
        return "Sunny" if code == 0 else "Mostly sunny"
    return text


def icon_name(code, day=True):
    base = ICONS.get(int(code or 0), "cloudy")
    if base in ("clear", "mostly", "partly", "showers"):
        return f"{base}-{'day' if day else 'night'}"
    return base


# ---- Windows' own preferences, for the first run

def windows_defaults():
    """24-hour clock and metric units, as set in Windows' region settings."""
    clock24, metric = True, True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\International") as k:
            short = winreg.QueryValueEx(k, "sShortTime")[0]
            clock24 = "H" in short
            metric = str(winreg.QueryValueEx(k, "iMeasure")[0]) != "1"
    except OSError:
        pass
    return clock24, metric
