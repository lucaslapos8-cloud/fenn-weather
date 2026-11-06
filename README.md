# Weather for Fenn

The weather on a Fenn tile, and a page in one of two looks.

## Glossy (the default)

3D icons on Fenn's own glass. At the top: today (condition, temperature,
place, high and low, feels like), the sunrise / day length / sunset bar,
rain, humidity and wind, and the next 7 days or 7 hours (the clock button in
the page header switches). Below, scrolling:

- **Overview:** one chart with Temperature, Rain, Humidity and Wind tabs, for
  the next 24 hours or 7 days (highs and lows, rain chance bars, wind with
  gusts and direction arrows). Click any point: its value shows in a bubble
  and what it means beside the tabs. Clicking today's card or the rain,
  humidity and wind numbers switches the chart to that. Click anywhere on a day above
  to see that day's 24 hours, or on an hour to pick
  it; "× Today" goes back.
- **Today's highlights:** wind, humidity and dew point, UV and when to
  protect your skin, visibility, feels like, rain today, cloud cover, and
  the next sunrise and sunset with how long until them, each with a 3D icon.
- **Should I go outside?:** a verdict for the next 8 hours, plus umbrella,
  sun protection, what to wear and how walking outside will be.
- **Air quality:** the index on its color scale with advice, the next 24
  hours as a colored line, and PM2.5, PM10, ozone and NO2 now.
- **Your places:** your location and saved places with their weather; the
  arrow opens one.

## Sky

A dashboard of glass cards on a sky-colored background (blue by day, grey
when cloudy or raining, warm around sunrise and sunset, deep blue at night),
with flat multicolor symbols. Behind the place and temperature there's a
live sky that follows the weather and the time of day: the sun with its glow
and halo moving from sunrise to sunset, warm light around sunrise and sunset,
soft clouds (more or fewer with the cloud cover) drifting with the wind, an
overcast ceiling, stars and the moon at night, rain with drops on the glass,
snow, fog and lightning. It fades out before the first card. Clouds, rain and
snow move while the page is open (turn it off under Settings, or with
Windows' "Animation effects"). Two sliders in Settings make the sky's
background see-through (down to Fenn's own glass) and set how strong the
clouds, sun, stars, rain and snow are. The page scrolls, and almost everything is
clickable:

- **Header:** place, temperature, condition, high and low. Click it for the
  temperature detail.
- **Rain forecast** (only when rain or snow is falling or coming within two
  hours): 15-minute bars and when it starts or stops.
- **Hourly forecast:** a one-line summary made from the forecast ("Rain is
  expected around 17:00."), the next 24 hours in pages of 8, with sunrise and
  sunset slotted in. Switch between Conditions, Rain (amount and chance) and
  Wind (direction arrows, speed and gusts). Click an hour for its details.
- **10-day forecast:** symbol, chance of rain, and temperature bars on one
  shared scale, with a dot for the temperature now. Click a day.
- **Air quality** (European or US AQI), **wind** (compass), **sunrise and
  sunset** (the sun's real path today), **moon** (phase, illumination,
  moonrise or moonset), **UV index**, **precipitation** (last and next 24 h),
  **feels like**, **humidity** (dew point), **visibility** and **pressure**
  (gauge and trend).

Each card opens a detail view: pick a day (today and the next 9), click the
chart to read any hour, and see the day's numbers with a short explanation:

- Temperature (with feels like), precipitation (amount or chance, and totals
  for the next days), wind (speed, gusts, direction through the day, Beaufort),
  air quality (by hour, plus PM2.5, PM10, ozone, NO2, SO2 and CO), UV (with the
  protection window), humidity or dew point, visibility, and pressure
  (from yesterday on).
- Sun: altitude through the day with civil, nautical and astronomical
  twilight, and how much longer or shorter the day is than the day before.
- Moon: phase, illumination, rise and set, next full and new moon, and a
  clickable month of moon phases to step through.

**Places:** the list button opens your places as small sky cards (local time,
temperature, condition, high and low). Search to add one, click to open it,
and use the pencil to remove or reorder.

**Settings** (gear): look, units (°C/°F; km/h, mph, m/s, knots or Beaufort;
mm or inches; hPa, inHg or mmHg; km or miles), 24- or 12-hour clock, the air
quality index, how often to refresh, what the hourly card shows first, and
which Sky cards to show and in what order. Units you leave alone follow the
place (°F, mph and inches in the US).

## What it doesn't do

Fenn pages can't do hover or drag and drop, and there's no map:
Fenn can't lay a weather overlay over map tiles. There are no weather alerts
or historical averages either, because Open-Meteo doesn't provide alerts and
the climate data would need another large download.

## Requirements

Windows and Python 3 (standard library only; Fenn can install Python for you).

## Install

```powershell
git clone https://github.com/lucaslapos8-cloud/fenn-weather "$env:APPDATA\Fenn\plugins\weather"
```

Fenn picks the new folder up on its own; restart Fenn once so the page gets
its full height.

## Privacy and network

- **Forecasts:** `api.open-meteo.com` gets the place's coordinates (rounded to
  about 10 m) once per refresh interval (15 minutes by default) while Fenn
  runs, and when you change places or press refresh.
- **Air quality:** `air-quality-api.open-meteo.com`, the same coordinates, with
  each forecast.
- **Places list:** one `api.open-meteo.com` request for all saved places when
  you open it (at most every 10 minutes).
- **City search:** `geocoding-api.open-meteo.com` gets what you type.
- **"My location"** asks `get.geojs.io` for the city of your internet
  connection's IP address, with each forecast refresh while it's selected.
- Sun and moon times are computed on your PC. No account, no key, no tracking.

Kept in the plugin's data folder (`FENN_DATA_DIR`): `settings.json` (places,
units, look, cards), `forecast.json` and `air.json` (the last data, shown when
you're offline), and an empty `reloaded` marker (the plugin restarts itself
when its files change, at most every 25 seconds).

## Files

`main.py` (state, fetching, clicks), `wx.py` (Open-Meteo), `data.py`
(reading the forecast, the summary sentence), `units.py`, `astro.py` (sun and
moon, after SunCalc by Vladimir Agafonkin, BSD-2-Clause), `glossy.py` and
`sky.py` (the two looks), `ambient.py` (the animated sky), `ui.py` (canvas cards and charts), `symbols.py` (the
flat symbols), `icons/` (the 3D icons, drawn by `tools/make_icons.ps1`).

## License

MIT, see [LICENSE](LICENSE). Weather and air quality data by
[Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0), air quality from
Copernicus Atmosphere Monitoring Service.

## Changelog

**1.0.1**
- Sky look: two new sliders in Settings, Sky background (from the full sky
  color down to see-through on Fenn's glass) and Sky effects (how strong the
  clouds, sun, stars, rain and snow are).

**1.0.0**
- First release: the Glossy and Sky looks, places, units, air quality, sun and
  moon, and the animated sky.
