"""Sun and moon: sunrise, sunset and twilight, moon phase, illumination,
moonrise and moonset, and the next full and new moon. Computed locally
(the formulas of Vladimir Agafonkin's SunCalc, BSD-2-Clause), no network.
All times in and out are UTC datetimes without tzinfo."""

import math
from datetime import datetime, timedelta

RAD = math.pi / 180
E = RAD * 23.4397  # obliquity of the Earth
J1970, J2000 = 2440588, 2451545
EPOCH = datetime(1970, 1, 1)


def _julian(dt):
    return (dt - EPOCH).total_seconds() / 86400 - 0.5 + J1970


def _from_julian(j):
    if j != j:  # NaN: no such event that day
        return None
    return EPOCH + timedelta(days=j + 0.5 - J1970)


def _days(dt):
    return _julian(dt) - J2000


def _ra(l, b):
    return math.atan2(math.sin(l) * math.cos(E) - math.tan(b) * math.sin(E), math.cos(l))


def _dec(l, b):
    return math.asin(math.sin(b) * math.cos(E) + math.cos(b) * math.sin(E) * math.sin(l))


def _altitude(H, phi, dec):
    return math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(H))


def _sidereal(d, lw):
    return RAD * (280.16 + 360.9856235 * d) - lw


def _refraction(h):
    h = max(h, 0)
    return 0.0002967 / math.tan(h + 0.00312536 / (h + 0.08901179))


def _mean_anomaly(d):
    return RAD * (357.5291 + 0.98560028 * d)


def _ecliptic_longitude(M):
    C = RAD * (1.9148 * math.sin(M) + 0.02 * math.sin(2 * M) + 0.0003 * math.sin(3 * M))
    return M + C + RAD * 102.9372 + math.pi


def _sun_coords(d):
    L = _ecliptic_longitude(_mean_anomaly(d))
    return _ra(L, 0), _dec(L, 0)


J0 = 0.0009


def _transit(ds, M, L):
    return J2000 + ds + 0.0053 * math.sin(M) - 0.0069 * math.sin(2 * L)


def _hour_angle(h, phi, d):
    x = (math.sin(h) - math.sin(phi) * math.sin(d)) / (math.cos(phi) * math.cos(d))
    return math.acos(x) if -1 <= x <= 1 else float("nan")


TWILIGHTS = [(-0.833, "sunrise", "sunset"), (-6, "dawn", "dusk"),
             (-12, "nautical_dawn", "nautical_dusk"), (-18, "astro_dawn", "astro_dusk"),
             (6, "golden_end", "golden_start")]


def sun_times(day_utc_noon, lat, lon):
    """Sunrise, sunset, the three twilights and solar noon for the day
    around `day_utc_noon` (use the place's local noon in UTC)."""
    lw, phi = RAD * -lon, RAD * lat
    d = _days(day_utc_noon)
    n = round(d - J0 - lw / (2 * math.pi))
    ds = J0 + lw / (2 * math.pi) + n
    M = _mean_anomaly(ds)
    L = _ecliptic_longitude(M)
    dec = _dec(L, 0)
    noon = _transit(ds, M, L)
    out = {"noon": _from_julian(noon)}
    for angle, rise, set_ in TWILIGHTS:
        w = _hour_angle(angle * RAD, phi, dec)
        j_set = _transit(J0 + (w + lw) / (2 * math.pi) + n, M, L)
        out[rise] = _from_julian(noon - (j_set - noon))
        out[set_] = _from_julian(j_set)
    return out


def sun_altitude(dt, lat, lon):
    lw, phi = RAD * -lon, RAD * lat
    d = _days(dt)
    ra, dec = _sun_coords(d)
    return _altitude(_sidereal(d, lw) - ra, phi, dec) / RAD


# ---- moon

def _moon_coords(d):
    L = RAD * (218.316 + 13.176396 * d)
    M = RAD * (134.963 + 13.064993 * d)
    F = RAD * (93.272 + 13.229350 * d)
    l = L + RAD * 6.289 * math.sin(M)
    b = RAD * 5.128 * math.sin(F)
    return _ra(l, b), _dec(l, b), 385001 - 20905 * math.cos(M)


def moon_altitude(dt, lat, lon):
    lw, phi = RAD * -lon, RAD * lat
    d = _days(dt)
    ra, dec, _ = _moon_coords(d)
    H = _sidereal(d, lw) - ra
    h = _altitude(H, phi, dec)
    return h + _refraction(h)


def moon_illumination(dt):
    """fraction lit (0..1) and phase (0 new, 0.25 first quarter, 0.5 full,
    0.75 last quarter)."""
    d = _days(dt)
    s_ra, s_dec = _sun_coords(d)
    m_ra, m_dec, m_dist = _moon_coords(d)
    sdist = 149598000
    phi = math.acos(max(-1, min(1, math.sin(s_dec) * math.sin(m_dec) + math.cos(s_dec) * math.cos(m_dec) * math.cos(s_ra - m_ra))))
    inc = math.atan2(sdist * math.sin(phi), m_dist - sdist * math.cos(phi))
    angle = math.atan2(math.cos(s_dec) * math.sin(s_ra - m_ra),
                       math.sin(s_dec) * math.cos(m_dec) - math.cos(s_dec) * math.sin(m_dec) * math.cos(s_ra - m_ra))
    return (1 + math.cos(inc)) / 2, 0.5 + 0.5 * inc * (-1 if angle < 0 else 1) / math.pi


def moon_times(midnight_utc, lat, lon):
    """Moonrise and moonset in the 24 hours after the place's local midnight
    (given in UTC); either may be None."""
    hc = 0.133 * RAD

    def alt(h):
        return moon_altitude(midnight_utc + timedelta(hours=h), lat, lon) - hc

    h0 = alt(0)
    rise = set_ = None
    for i in range(1, 25, 2):
        h1, h2 = alt(i), alt(i + 1)
        a = (h0 + h2) / 2 - h1
        b = (h2 - h0) / 2
        if a == 0:
            h0 = h2
            continue
        xe = -b / (2 * a)
        ye = (a * xe + b) * xe + h1
        disc = b * b - 4 * a * h1
        roots = 0
        x1 = x2 = 0
        if disc >= 0:
            dx = math.sqrt(disc) / (abs(a) * 2)
            x1, x2 = xe - dx, xe + dx
            roots = (abs(x1) <= 1) + (abs(x2) <= 1)
            if x1 < -1:
                x1 = x2
        if roots == 1:
            if h0 < 0:
                rise = i + x1
            else:
                set_ = i + x1
        elif roots == 2:
            rise = i + (x2 if ye < 0 else x1)
            set_ = i + (x1 if ye < 0 else x2)
        if rise is not None and set_ is not None:
            break
        h0 = h2
    conv = lambda h: None if h is None else midnight_utc + timedelta(hours=h)
    return conv(rise), conv(set_)


PHASES = [(0.0333, "New moon"), (0.2167, "Waxing crescent"), (0.2833, "First quarter"),
          (0.4667, "Waxing gibbous"), (0.5333, "Full moon"), (0.7167, "Waning gibbous"),
          (0.7833, "Last quarter"), (0.9667, "Waning crescent"), (1.01, "New moon")]


def phase_name(phase):
    return next(name for limit, name in PHASES if phase < limit)


def next_phase(dt, target):
    """The next time after dt when the phase reaches target (0 = new, 0.5 = full)."""
    def dist(t):
        p = moon_illumination(t)[1]
        return (p - target) % 1.0  # how far past the target
    # walk in 6-hour steps until it wraps (passes the target), then refine
    t = dt
    prev = dist(t)
    for _ in range(4 * 31):
        nt = t + timedelta(hours=6)
        cur = dist(nt)
        if cur < prev and prev > 0.5:  # wrapped around the target
            lo, hi = t, nt
            for _ in range(20):
                mid = lo + (hi - lo) / 2
                if dist(mid) > 0.5:
                    lo = mid
                else:
                    hi = mid
            return hi
        t, prev = nt, cur
    return None
