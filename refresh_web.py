#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAISO / PACE Weather Dashboard — Web Refresh Script
Lehi City Power Department

Outputs:
  data.json     — complete dashboard snapshot for index.html
  normals.json  — cached ERA5 normals (fetched once, reused on every run)

Run locally or via GitHub Actions on a daily schedule.
No external dependencies — standard library only.
"""

import json, urllib.request, urllib.error
from collections import defaultdict
from datetime import date, timedelta, datetime
import os, sys, time

# ══════════════════════════════════════════════════════════════
# TUNABLE CONSTANTS
# ══════════════════════════════════════════════════════════════
GHI_CEILING        = 9.0
SPI_GHI_WEIGHT     = 0.7
SPI_CLOUD_WEIGHT   = 0.3
WIND_DAYTIME_HOURS = (7, 19)

NORMALS_FILE = "normals.json"
DATA_FILE    = "data.json"

# ══════════════════════════════════════════════════════════════
# CITY LISTS
# ══════════════════════════════════════════════════════════════
CITIES = [
    ("Lehi City",      "UT",  40.3916, -111.8508),
    ("Blythe",         "CA",  33.6103, -114.5961),
    ("San Diego",      "CA",  32.7157, -117.1611),
    ("Riverside",      "CA",  33.9533, -117.3962),
    ("Ontario",        "CA",  34.0633, -117.6509),
    ("Los Angeles",    "CA",  34.0522, -118.2437),
    ("Burbank",        "CA",  34.1808, -118.3090),
    ("Bakersfield",    "CA",  35.3733, -119.0187),
    ("Fresno",         "CA",  36.7378, -119.7871),
    ("Stockton",       "CA",  37.9577, -121.2908),
    ("Sacramento",     "CA",  38.5816, -121.4944),
    ("San Jose",       "CA",  37.3382, -121.8863),
    ("Red Bluff",      "CA",  40.1785, -122.2358),
    ("Oakland",        "CA",  37.8044, -122.2712),
    ("San Francisco",  "CA",  37.7749, -122.4194),
    ("Las Vegas",      "NV",  36.1699, -115.1398),
    ("Phoenix",        "AZ",  33.4484, -112.0740),
    ("Salt Lake City", "UT",  40.7608, -111.8910),
    ("Boise",          "ID",  43.6150, -116.2023),
]

SOLAR_CITIES = [
    ("Palm Springs", "CA",  33.8303, -116.5453),
    ("Blythe",       "CA",  33.6103, -114.5961),
    ("Fresno",       "CA",  36.7378, -119.7871),
    ("Bakersfield",  "CA",  35.3733, -119.0187),
]

WIND_CITIES = [
    ("Lancaster",  "CA",  34.6868, -118.1542),
    ("Tehachapi",  "CA",  35.1325, -118.4485),
]

# ══════════════════════════════════════════════════════════════
# NOAA 30-YEAR NORMALS (1991-2020)
# ══════════════════════════════════════════════════════════════
NOAA_NORMALS = {
    "Lehi City_UT":      [[38,21],[44,25],[54,32],[63,39],[73,47],[83,56],[93,63],[91,62],[80,52],[66,40],[50,30],[38,22]],
    "Blythe_CA":         [[67,43],[73,48],[81,54],[90,62],[100,70],[110,79],[115,85],[113,83],[105,76],[93,64],[77,50],[66,43]],
    "San Diego_CA":      [[65,49],[66,51],[67,53],[69,56],[71,60],[74,63],[77,66],[78,67],[77,65],[75,61],[70,55],[65,49]],
    "Riverside_CA":      [[68,42],[71,45],[75,48],[81,52],[88,57],[95,63],[101,68],[100,68],[96,64],[87,56],[76,47],[67,41]],
    "Ontario_CA":        [[68,43],[71,46],[75,49],[81,53],[87,58],[94,64],[100,69],[100,69],[96,65],[87,56],[76,48],[67,42]],
    "Los Angeles_CA":    [[68,48],[69,50],[70,52],[73,55],[75,59],[79,63],[84,67],[85,68],[83,66],[79,61],[73,54],[68,48]],
    "Burbank_CA":        [[67,45],[69,47],[72,50],[77,53],[82,57],[88,62],[95,67],[95,68],[91,65],[83,58],[74,50],[67,44]],
    "Bakersfield_CA":    [[57,37],[64,42],[71,47],[80,53],[89,61],[99,70],[105,76],[103,74],[96,67],[83,55],[68,43],[57,36]],
    "Fresno_CA":         [[55,38],[62,43],[69,47],[77,53],[86,61],[95,69],[101,75],[99,73],[92,66],[79,55],[64,43],[54,37]],
    "Stockton_CA":       [[55,38],[62,42],[68,46],[75,51],[83,57],[91,64],[97,68],[95,67],[89,62],[77,53],[63,43],[54,37]],
    "Sacramento_CA":     [[54,38],[61,42],[67,45],[74,49],[83,56],[91,63],[97,67],[95,66],[89,61],[76,52],[62,43],[53,37]],
    "San Jose_CA":       [[58,41],[63,44],[67,46],[72,49],[78,54],[84,59],[90,63],[89,63],[85,60],[76,55],[65,46],[57,40]],
    "Red Bluff_CA":      [[54,35],[62,39],[68,43],[76,48],[85,55],[95,63],[103,69],[101,68],[93,61],[79,50],[63,39],[53,34]],
    "Oakland_CA":        [[57,44],[60,46],[63,48],[65,50],[68,53],[71,56],[72,58],[72,59],[72,57],[68,53],[62,48],[57,43]],
    "San Francisco_CA":  [[57,46],[60,48],[62,49],[63,51],[64,53],[65,55],[65,56],[66,57],[68,57],[67,55],[62,50],[57,46]],
    "Las Vegas_NV":      [[57,37],[63,42],[71,48],[80,56],[90,65],[100,75],[105,81],[103,79],[94,70],[81,57],[66,45],[56,36]],
    "Phoenix_AZ":        [[67,44],[72,47],[80,53],[89,61],[99,70],[108,79],[106,84],[104,83],[98,76],[87,63],[75,51],[66,44]],
    "Salt Lake City_UT": [[38,23],[44,27],[54,34],[63,41],[73,50],[84,59],[94,67],[91,65],[80,54],[66,43],[49,31],[37,23]],
    "Boise_ID":          [[37,25],[45,30],[55,35],[63,40],[72,47],[82,56],[92,64],[91,63],[79,53],[64,42],[48,32],[37,24]],
}

STATE_TZ = {
    "CA": "America%2FLos_Angeles",
    "NV": "America%2FLos_Angeles",
    "AZ": "America%2FPhoenix",
    "UT": "America%2FDenver",
    "ID": "America%2FBoise",
}

CITY_META = {
    "Blythe":         {"geo": "Southern CA", "load_rank": 3},
    "San Diego":      {"geo": "Southern CA", "load_rank": 1},
    "Riverside":      {"geo": "Southern CA", "load_rank": 2},
    "Ontario":        {"geo": "Southern CA", "load_rank": 3},
    "Los Angeles":    {"geo": "Southern CA", "load_rank": 1},
    "Burbank":        {"geo": "Southern CA", "load_rank": 3},
    "Bakersfield":    {"geo": "Central CA",  "load_rank": 2},
    "Fresno":         {"geo": "Central CA",  "load_rank": 1},
    "Stockton":       {"geo": "Central CA",  "load_rank": 2},
    "Sacramento":     {"geo": "Central CA",  "load_rank": 1},
    "San Jose":       {"geo": "Northern CA", "load_rank": 1},
    "Red Bluff":      {"geo": "Northern CA", "load_rank": 3},
    "Oakland":        {"geo": "Northern CA", "load_rank": 2},
    "San Francisco":  {"geo": "Northern CA", "load_rank": 1},
    "Las Vegas":      {"geo": "Outside CA",  "load_rank": 2},
    "Phoenix":        {"geo": "Outside CA",  "load_rank": 1},
    "Salt Lake City": {"geo": "Outside CA",  "load_rank": 2},
    "Boise":          {"geo": "Outside CA",  "load_rank": 2},
    "Lehi City":      {"geo": "Outside CA",  "load_rank": 3},
}

# ══════════════════════════════════════════════════════════════
# FETCH — TEMPERATURE
# ══════════════════════════════════════════════════════════════
def fetch_weather(lat, lon):
    today      = date.today()
    past_start = today - timedelta(days=7)
    results    = {}
    arch_url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&start_date={past_start}&end_date={today}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&temperature_unit=fahrenheit&timezone=auto"
    )
    try:
        with urllib.request.urlopen(arch_url, timeout=30) as r:
            d = json.loads(r.read())
        for dt, hi, lo in zip(d["daily"]["time"],
                               d["daily"]["temperature_2m_max"],
                               d["daily"]["temperature_2m_min"]):
            if hi is not None and lo is not None:
                results[dt] = [round(hi), round(lo)]
    except Exception as e:
        print(f"    archive error: {e}")
    fc_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&temperature_unit=fahrenheit&timezone=auto&forecast_days=11"
    )
    try:
        with urllib.request.urlopen(fc_url, timeout=30) as r:
            d = json.loads(r.read())
        for dt, hi, lo in zip(d["daily"]["time"],
                               d["daily"]["temperature_2m_max"],
                               d["daily"]["temperature_2m_min"]):
            if hi is not None and lo is not None:
                results[dt] = [round(hi), round(lo)]
    except Exception as e:
        print(f"    forecast error: {e}")
    return results


# ══════════════════════════════════════════════════════════════
# FETCH — SOLAR
# ══════════════════════════════════════════════════════════════
def fetch_solar_day(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&hourly=shortwave_radiation,cloudcover"
        f"&past_days=7&forecast_days=11&timezone=auto"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            d = json.loads(r.read())
        dh_start, dh_end = WIND_DAYTIME_HOURS
        day_ghi   = defaultdict(float)
        day_cloud = defaultdict(list)
        for ts, sw, cc in zip(d["hourly"]["time"],
                               d["hourly"]["shortwave_radiation"],
                               d["hourly"]["cloudcover"]):
            if sw is None or cc is None: continue
            hour = int(ts[11:13])
            if dh_start <= hour < dh_end:
                day_ghi[ts[:10]]   += sw
                day_cloud[ts[:10]].append(cc)
        result = {}
        for dt, ghi_sum in day_ghi.items():
            clouds = day_cloud[dt]
            result[dt] = [round(ghi_sum / 1000.0, 2),
                          round(sum(clouds)/len(clouds), 1) if clouds else 0.0]
        return result
    except Exception as e:
        print(f"    solar fetch error: {e}")
        return {}


# ══════════════════════════════════════════════════════════════
# FETCH — WIND
# ══════════════════════════════════════════════════════════════
def fetch_wind_day(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&hourly=windspeed_80m&windspeed_unit=mph"
        f"&past_days=7&forecast_days=11&timezone=auto"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            d = json.loads(r.read())
        dh_start, dh_end = WIND_DAYTIME_HOURS
        day_wind = defaultdict(list)
        for ts, spd in zip(d["hourly"]["time"], d["hourly"]["windspeed_80m"]):
            if spd is None: continue
            if dh_start <= int(ts[11:13]) < dh_end:
                day_wind[ts[:10]].append(spd)
        return {dt: round(sum(v)/len(v), 1) for dt, v in day_wind.items()}
    except Exception as e:
        print(f"    wind fetch error: {e}")
        return {}


# ══════════════════════════════════════════════════════════════
# FETCH — HISTORICAL NORMALS
# ══════════════════════════════════════════════════════════════
def fetch_hist_normals(lat, lon, tz="America%2FLos_Angeles", retries=3):
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&start_date=2015-01-01&end_date=2024-12-31"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&temperature_unit=fahrenheit&timezone={tz}"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                d = json.loads(r.read())
            mh = {m: [] for m in range(1,13)}
            ml = {m: [] for m in range(1,13)}
            for dt, hi, lo in zip(d["daily"]["time"],
                                   d["daily"]["temperature_2m_max"],
                                   d["daily"]["temperature_2m_min"]):
                if hi is not None and lo is not None:
                    m = int(dt[5:7])
                    mh[m].append(hi); ml[m].append(lo)
            return [[round(sum(mh[m])/len(mh[m])), round(sum(ml[m])/len(ml[m]))]
                    if mh[m] else [None,None] for m in range(1,13)]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15*(attempt+1)
                print(f"    Rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                print(f"    hist normals error: {e}"); return None
        except Exception as e:
            print(f"    hist normals error: {e}"); return None
    return None


def fetch_3yr_normals(lat, lon, tz="America%2FLos_Angeles", retries=3):
    end = str(date.today() - timedelta(days=1))
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&start_date=2022-01-01&end_date={end}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&temperature_unit=fahrenheit&timezone={tz}"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                d = json.loads(r.read())
            mh = {m: [] for m in range(1,13)}
            ml = {m: [] for m in range(1,13)}
            for dt, hi, lo in zip(d["daily"]["time"],
                                   d["daily"]["temperature_2m_max"],
                                   d["daily"]["temperature_2m_min"]):
                if hi is not None and lo is not None:
                    m = int(dt[5:7])
                    mh[m].append(hi); ml[m].append(lo)
            return [[round(sum(mh[m])/len(mh[m])), round(sum(ml[m])/len(ml[m]))]
                    if mh[m] else [None,None] for m in range(1,13)]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15*(attempt+1)
                print(f"    Rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                print(f"    3yr normals error: {e}"); return None
        except Exception as e:
            print(f"    3yr normals error: {e}"); return None
    return None


def fetch_solar_normals(lat, lon, tz, start_date, end_date, retries=3):
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&hourly=shortwave_radiation&timezone={tz}"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                d = json.loads(r.read())
            dh_start, dh_end = WIND_DAYTIME_HOURS
            day_ghi = defaultdict(float)
            for ts, sw in zip(d["hourly"]["time"], d["hourly"]["shortwave_radiation"]):
                if sw is None: continue
                if dh_start <= int(ts[11:13]) < dh_end:
                    day_ghi[ts[:10]] += sw
            month_ghi = {m: [] for m in range(1,13)}
            for dt, ghi_sum in day_ghi.items():
                month_ghi[int(dt[5:7])].append(ghi_sum / 1000.0)
            return [round(sum(v)/len(v), 2) if v else None for v in month_ghi.values()]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15*(attempt+1); print(f"    Rate limited, waiting {wait}s...", flush=True); time.sleep(wait)
            else:
                print(f"    solar normals error: {e}"); return None
        except Exception as e:
            print(f"    solar normals error: {e}"); return None
    return None


def fetch_wind_normals(lat, lon, tz, start_date, end_date, retries=3):
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&hourly=windspeed_80m&windspeed_unit=mph&timezone={tz}"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                d = json.loads(r.read())
            dh_start, dh_end = WIND_DAYTIME_HOURS
            day_wind = defaultdict(list)
            for ts, spd in zip(d["hourly"]["time"], d["hourly"]["windspeed_80m"]):
                if spd is None: continue
                if dh_start <= int(ts[11:13]) < dh_end:
                    day_wind[ts[:10]].append(spd)
            month_wind = {m: [] for m in range(1,13)}
            for dt, vals in day_wind.items():
                month_wind[int(dt[5:7])].append(sum(vals)/len(vals))
            return [round(sum(v)/len(v), 1) if v else None for v in month_wind.values()]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15*(attempt+1); print(f"    Rate limited, waiting {wait}s...", flush=True); time.sleep(wait)
            else:
                print(f"    wind normals error: {e}"); return None
        except Exception as e:
            print(f"    wind normals error: {e}"); return None
    return None


# ══════════════════════════════════════════════════════════════
# NORMALS PERSISTENCE  (normals.json)
# ══════════════════════════════════════════════════════════════
def load_normals():
    if os.path.exists(NORMALS_FILE):
        with open(NORMALS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"temp_10yr": {}, "temp_3yr": {},
            "solar_10yr": {}, "solar_3yr": {},
            "wind_10yr": {}, "wind_3yr": {}}


def save_normals(normals):
    with open(NORMALS_FILE, "w", encoding="utf-8") as f:
        json.dump(normals, f, indent=2)


def ensure_normals(normals):
    """Fetch any missing normals entries. Returns (updated_normals, wrote_any)."""
    wrote_any = False
    end_3yr   = str(date.today() - timedelta(days=1))

    # ── Temperature normals ──────────────────────────────────
    for city_list, key, fetch_fn, kwargs in [
        (CITIES, "temp_10yr", fetch_hist_normals, {}),
        (CITIES, "temp_3yr",  fetch_3yr_normals,  {}),
    ]:
        missing = [c for c in city_list if f"{c[0]}_{c[1]}" not in normals[key]]
        if missing:
            print(f"  Fetching {key} for {len(missing)} city/cities...")
        for name, state, lat, lon in missing:
            tz = STATE_TZ.get(state, "America%2FLos_Angeles")
            print(f"    {name}, {state}...", flush=True)
            r = fetch_fn(lat, lon, tz=tz, **kwargs)
            if r:
                normals[key][f"{name}_{state}"] = r
                wrote_any = True
            time.sleep(2.0)

    # ── Solar normals ────────────────────────────────────────
    for (start, end), key in [
        (("2015-01-01", "2024-12-31"), "solar_10yr"),
        (("2022-01-01", end_3yr),      "solar_3yr"),
    ]:
        missing = [c for c in SOLAR_CITIES if f"{c[0]}_{c[1]}" not in normals[key]]
        if missing:
            print(f"  Fetching {key} for {len(missing)} city/cities (hourly ERA5 — may take several minutes)...")
        for name, state, lat, lon in missing:
            tz = STATE_TZ.get(state, "America%2FLos_Angeles")
            print(f"    {name}, {state}...", flush=True)
            r = fetch_solar_normals(lat, lon, tz, start, end)
            if r:
                normals[key][f"{name}_{state}"] = r
                wrote_any = True
            time.sleep(3.0)

    # ── Wind normals ─────────────────────────────────────────
    for (start, end), key in [
        (("2015-01-01", "2024-12-31"), "wind_10yr"),
        (("2022-01-01", end_3yr),      "wind_3yr"),
    ]:
        missing = [c for c in WIND_CITIES if f"{c[0]}_{c[1]}" not in normals[key]]
        if missing:
            print(f"  Fetching {key} for {len(missing)} city/cities (hourly ERA5)...")
        for name, state, lat, lon in missing:
            tz = STATE_TZ.get(state, "America%2FLos_Angeles")
            print(f"    {name}, {state}...", flush=True)
            r = fetch_wind_normals(lat, lon, tz, start, end)
            if r:
                normals[key][f"{name}_{state}"] = r
                wrote_any = True
            time.sleep(3.0)

    return normals, wrote_any


# ══════════════════════════════════════════════════════════════
# DATA.JSON WRITER
# ══════════════════════════════════════════════════════════════
def write_data_json(today, all_dates, city_weather, solar_weather, wind_weather, normals):
    data = {
        "last_refreshed": datetime.now().strftime("%A, %B %d %Y  at  %I:%M %p"),
        "today":  str(today),
        "dates":  [str(d) for d in all_dates],
        "cities": [
            {
                "key":  f"{n}_{s}",
                "full": f"{n}, {s}",
                "geo":  CITY_META.get(n, {}).get("geo", "Outside CA"),
                "load": CITY_META.get(n, {}).get("load_rank", 3),
            }
            for n, s, *_ in CITIES
        ],
        "solar_cities": [
            {"key": f"{n}_{s}", "full": f"{n}, {s}"}
            for n, s, *_ in SOLAR_CITIES
        ],
        "wind_cities": [
            {"key": f"{n}_{s}", "full": f"{n}, {s}"}
            for n, s, *_ in WIND_CITIES
        ],
        "city_weather":  city_weather,
        "solar_weather": solar_weather,
        "wind_weather":  wind_weather,
        "normals": {
            "temp_30yr":  NOAA_NORMALS,
            "temp_10yr":  normals.get("temp_10yr",  {}),
            "temp_3yr":   normals.get("temp_3yr",   {}),
            "solar_10yr": normals.get("solar_10yr", {}),
            "solar_3yr":  normals.get("solar_3yr",  {}),
            "wind_10yr":  normals.get("wind_10yr",  {}),
            "wind_3yr":   normals.get("wind_3yr",   {}),
        },
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    size_kb = os.path.getsize(DATA_FILE) // 1024
    print(f"  ✓  data.json written ({size_kb} KB)")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  CAISO / PACE Weather Dashboard — Web Refresh")
    print("  Lehi City Power Department")
    print("=" * 60)

    print("\n  Checking normals cache...")
    normals = load_normals()
    normals, wrote_any = ensure_normals(normals)
    if wrote_any:
        save_normals(normals)
        print("  normals.json updated.")
    else:
        print("  All normals present — skipping fetch.")

    today     = date.today()
    all_dates = [today - timedelta(days=7) + timedelta(days=i) for i in range(18)]

    print(f"\n  Fetching temperature data ({len(CITIES)} cities)...")
    city_weather = {}
    for i, (name, state, lat, lon) in enumerate(CITIES):
        key = f"{name}_{state}"
        print(f"  [{i+1:02d}/{len(CITIES)}] {name}, {state}...", flush=True)
        city_weather[key] = fetch_weather(lat, lon)
        time.sleep(0.15)

    print(f"\n  Fetching solar data ({len(SOLAR_CITIES)} cities)...")
    solar_weather = {}
    seen = set()
    for name, state, lat, lon in SOLAR_CITIES:
        key = f"{name}_{state}"
        if key in seen: continue
        seen.add(key)
        print(f"  {name}, {state}...", flush=True)
        solar_weather[key] = fetch_solar_day(lat, lon)
        time.sleep(0.15)

    print(f"\n  Fetching wind data ({len(WIND_CITIES)} cities)...")
    wind_weather = {}
    for name, state, lat, lon in WIND_CITIES:
        key = f"{name}_{state}"
        print(f"  {name}, {state}...", flush=True)
        wind_weather[key] = fetch_wind_day(lat, lon)
        time.sleep(0.15)

    print("\n  Writing data.json...")
    write_data_json(today, all_dates, city_weather, solar_weather, wind_weather, normals)

    print("\n  Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
