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
    ("Palm Springs",   "CA",  33.8303, -116.5453),
    ("Desert Center",  "CA",  33.7157, -115.4017),
    ("El Centro",      "CA",  32.7920, -115.5630),
    ("Blythe",         "CA",  33.6103, -114.5961),
    ("Fresno",         "CA",  36.7378, -119.7871),
    ("Bakersfield",    "CA",  35.3733, -119.0187),
]

WIND_CITIES = [
    ("Lancaster",  "CA",  34.6868, -118.1542),
    ("Tehachapi",  "CA",  35.1325, -118.4485),
]

UAMPS_CITIES = [
    ("Bountiful City",      "UT",  40.8894, -111.8808),
    ("Brigham City",        "UT",  41.5100, -112.0158),
    ("Hyrum City",          "UT",  41.6313, -111.8549),
    ("Kaysville City",      "UT",  41.0352, -111.9388),
    ("Lehi City",           "UT",  40.3916, -111.8508),
    ("Logan City",          "UT",  41.7370, -111.8338),
    ("Morgan City",         "UT",  41.0361, -111.6769),
    ("Murray City",         "UT",  40.6669, -111.8879),
    ("Payson City",         "UT",  40.0444, -111.7324),
    ("Springville City",    "UT",  40.1699, -111.6113),
    ("Heber Light & Power", "UT",  40.5069, -111.4133),
    ("S. Utah Valley ESD",  "UT",  40.1149, -111.6549),
    ("Weber Basin WCD",     "UT",  41.2230, -111.9740),
    ("Ephraim City",        "UT",  39.3594, -111.5877),
    ("Fairview City",       "UT",  39.6252, -111.4341),
    ("Fillmore City",       "UT",  38.9691, -112.3235),
    ("Helper City",         "UT",  39.6860, -110.8549),
    ("Holden Town",         "UT",  39.0902, -112.2780),
    ("Kanosh Town",         "UT",  38.7969, -112.4363),
    ("Meadow Town",         "UT",  38.8994, -112.3988),
    ("Monroe City",         "UT",  38.6327, -112.1174),
    ("Mt. Pleasant City",   "UT",  39.5474, -111.4538),
    ("Town of Oak City",    "UT",  39.3655, -112.3369),
    ("Price City",          "UT",  39.5993, -110.8107),
    ("Spring City",         "UT",  39.4821, -111.4949),
    ("Central Valley WRF",  "UT",  40.6977, -112.0605),
    ("Beaver City",         "UT",  38.2736, -112.6413),
    ("Blanding City",       "UT",  37.6249, -109.4785),
    ("City of Enterprise",  "UT",  37.5732, -113.7193),
    ("Hurricane City",      "UT",  37.1753, -113.2897),
    ("Town of Paragonah",   "UT",  37.8894, -112.7874),
    ("Parowan City",        "UT",  37.8427, -112.8274),
    ("Santa Clara",         "UT",  37.1316, -113.6538),
    ("St. George",          "UT",  37.0965, -113.5684),
    ("Washington City",     "UT",  37.1302, -113.5080),
    ("Ticaboo UID",         "UT",  37.4949, -110.7430),
    ("City of Fallon",      "NV",  39.4735, -118.7774),
    ("Wells Rural EC",      "NV",  41.1135, -114.9630),
    ("Gallup City",         "NM",  35.5281, -108.7426),
    ("Los Alamos County",   "NM",  35.8800, -106.3031),
    ("Navajo TUA",          "AZ",  36.1500, -109.5500),
    ("Idaho Energy Auth.",  "ID",  43.4917, -112.0339),
    ("Idaho Falls Power",   "ID",  43.4917, -112.0339),
    ("Lost River EC",       "ID",  43.9135, -113.6125),
    ("Salmon River EC",     "ID",  45.1769, -113.8958),
    ("Lassen MUD",          "CA",  40.4152, -120.6529),
    ("Plumas-Sierra REC",   "CA",  39.9350, -120.9470),
    ("Truckee Donner PUD",  "CA",  39.3280, -120.1833),
    ("Lower Valley Energy", "WY",  42.7252, -110.9305),
]

UAMPS_CITY_META = {
    "Bountiful City":      {"geo": "Northern Utah", "load_rank": 1},
    "Brigham City":        {"geo": "Northern Utah", "load_rank": 2},
    "Hyrum City":          {"geo": "Northern Utah", "load_rank": 2},
    "Kaysville City":      {"geo": "Northern Utah", "load_rank": 1},
    "Lehi City":           {"geo": "Northern Utah", "load_rank": 1},
    "Logan City":          {"geo": "Northern Utah", "load_rank": 1},
    "Morgan City":         {"geo": "Northern Utah", "load_rank": 2},
    "Murray City":         {"geo": "Northern Utah", "load_rank": 1},
    "Payson City":         {"geo": "Northern Utah", "load_rank": 1},
    "Springville City":    {"geo": "Northern Utah", "load_rank": 1},
    "Heber Light & Power": {"geo": "Northern Utah", "load_rank": 1},
    "S. Utah Valley ESD":  {"geo": "Northern Utah", "load_rank": 1},
    "Weber Basin WCD":     {"geo": "Northern Utah", "load_rank": 1},
    "Ephraim City":        {"geo": "Central Utah",  "load_rank": 2},
    "Fairview City":       {"geo": "Central Utah",  "load_rank": 2},
    "Fillmore City":       {"geo": "Central Utah",  "load_rank": 2},
    "Helper City":         {"geo": "Central Utah",  "load_rank": 2},
    "Holden Town":         {"geo": "Central Utah",  "load_rank": 3},
    "Kanosh Town":         {"geo": "Central Utah",  "load_rank": 3},
    "Meadow Town":         {"geo": "Central Utah",  "load_rank": 3},
    "Monroe City":         {"geo": "Central Utah",  "load_rank": 3},
    "Mt. Pleasant City":   {"geo": "Central Utah",  "load_rank": 2},
    "Town of Oak City":    {"geo": "Central Utah",  "load_rank": 3},
    "Price City":          {"geo": "Central Utah",  "load_rank": 2},
    "Spring City":         {"geo": "Central Utah",  "load_rank": 3},
    "Central Valley WRF":  {"geo": "Central Utah",  "load_rank": 2},
    "Beaver City":         {"geo": "Southern Utah", "load_rank": 2},
    "Blanding City":       {"geo": "Southern Utah", "load_rank": 3},
    "City of Enterprise":  {"geo": "Southern Utah", "load_rank": 3},
    "Hurricane City":      {"geo": "Southern Utah", "load_rank": 2},
    "Town of Paragonah":   {"geo": "Southern Utah", "load_rank": 3},
    "Parowan City":        {"geo": "Southern Utah", "load_rank": 2},
    "Santa Clara":         {"geo": "Southern Utah", "load_rank": 2},
    "St. George":          {"geo": "Southern Utah", "load_rank": 1},
    "Washington City":     {"geo": "Southern Utah", "load_rank": 1},
    "Ticaboo UID":         {"geo": "Southern Utah", "load_rank": 3},
    "City of Fallon":      {"geo": "Nevada",        "load_rank": 2},
    "Wells Rural EC":      {"geo": "Nevada",        "load_rank": 2},
    "Gallup City":         {"geo": "New Mexico",    "load_rank": 1},
    "Los Alamos County":   {"geo": "New Mexico",    "load_rank": 1},
    "Navajo TUA":          {"geo": "Arizona",       "load_rank": 1},
    "Idaho Energy Auth.":  {"geo": "Idaho",         "load_rank": 3},
    "Idaho Falls Power":   {"geo": "Idaho",         "load_rank": 1},
    "Lost River EC":       {"geo": "Idaho",         "load_rank": 2},
    "Salmon River EC":     {"geo": "Idaho",         "load_rank": 2},
    "Lassen MUD":          {"geo": "California",    "load_rank": 2},
    "Plumas-Sierra REC":   {"geo": "California",    "load_rank": 2},
    "Truckee Donner PUD":  {"geo": "California",    "load_rank": 1},
    "Lower Valley Energy": {"geo": "Wyoming",       "load_rank": 2},
}

UAMPS_GEO_GROUP_ORDER = [
    "Northern Utah", "Central Utah", "Southern Utah",
    "Nevada", "New Mexico", "Arizona", "Idaho", "California", "Wyoming",
]

UAMPS_SOLAR_CITIES = [
    ("Red Mesa Solar", "UT",  37.1160, -109.4037),
    ("Steel Solar",    "UT",  41.8785, -112.1461),
]

UAMPS_WIND_CITIES = [
    ("Horse Butte Wind", "ID",  43.3923, -111.7395),
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
    "NM": "America%2FDenver",
    "WY": "America%2FDenver",
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
    past_start = today - timedelta(days=14)
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
        f"&past_days=14&forecast_days=11&timezone=auto"
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
        f"&past_days=14&forecast_days=11&timezone=auto"
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
        f"&hourly=windspeed_100m&windspeed_unit=mph&timezone={tz}"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                d = json.loads(r.read())
            dh_start, dh_end = WIND_DAYTIME_HOURS
            day_wind = defaultdict(list)
            for ts, spd in zip(d["hourly"]["time"], d["hourly"]["windspeed_100m"]):
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
    all_temp_cities = CITIES + UAMPS_CITIES
    for city_list, key, fetch_fn, kwargs in [
        (all_temp_cities, "temp_10yr", fetch_hist_normals, {}),
        (all_temp_cities, "temp_3yr",  fetch_3yr_normals,  {}),
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
    all_solar_cities = SOLAR_CITIES + UAMPS_SOLAR_CITIES
    for (start, end), key in [
        (("2015-01-01", "2024-12-31"), "solar_10yr"),
        (("2022-01-01", end_3yr),      "solar_3yr"),
    ]:
        missing = [c for c in all_solar_cities if f"{c[0]}_{c[1]}" not in normals[key]]
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
    all_wind_cities = WIND_CITIES + UAMPS_WIND_CITIES
    for (start, end), key in [
        (("2015-01-01", "2024-12-31"), "wind_10yr"),
        (("2022-01-01", end_3yr),      "wind_3yr"),
    ]:
        missing = [c for c in all_wind_cities if f"{c[0]}_{c[1]}" not in normals[key]]
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
def write_data_json(today, all_dates, city_weather, solar_weather, wind_weather, normals,
                    uamps_city_weather, uamps_solar_weather, uamps_wind_weather):
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
        "uamps_cities": [
            {
                "key":  f"{n}_{s}",
                "full": f"{n}, {s}",
                "geo":  UAMPS_CITY_META.get(n, {}).get("geo", "Northern Utah"),
                "load": UAMPS_CITY_META.get(n, {}).get("load_rank", 3),
            }
            for n, s, *_ in UAMPS_CITIES
        ],
        "uamps_solar_cities": [
            {"key": f"{n}_{s}", "full": f"{n}, {s}"}
            for n, s, *_ in UAMPS_SOLAR_CITIES
        ],
        "uamps_wind_cities": [
            {"key": f"{n}_{s}", "full": f"{n}, {s}"}
            for n, s, *_ in UAMPS_WIND_CITIES
        ],
        "city_weather":        city_weather,
        "solar_weather":       solar_weather,
        "wind_weather":        wind_weather,
        "uamps_city_weather":  uamps_city_weather,
        "uamps_solar_weather": uamps_solar_weather,
        "uamps_wind_weather":  uamps_wind_weather,
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
    all_dates = [today - timedelta(days=14) + timedelta(days=i) for i in range(25)]

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

    print(f"\n  Fetching UAMPS temperature data ({len(UAMPS_CITIES)} cities)...")
    uamps_city_weather = {}
    seen_uamps = set()
    for name, state, lat, lon in UAMPS_CITIES:
        key = f"{name}_{state}"
        if key in seen_uamps:
            continue
        seen_uamps.add(key)
        print(f"  {name}, {state}...", flush=True)
        uamps_city_weather[key] = fetch_weather(lat, lon)
        time.sleep(0.15)

    print(f"\n  Fetching UAMPS solar data ({len(UAMPS_SOLAR_CITIES)} sites)...")
    uamps_solar_weather = {}
    for name, state, lat, lon in UAMPS_SOLAR_CITIES:
        key = f"{name}_{state}"
        print(f"  {name}, {state}...", flush=True)
        uamps_solar_weather[key] = fetch_solar_day(lat, lon)
        time.sleep(0.15)

    print(f"\n  Fetching UAMPS wind data ({len(UAMPS_WIND_CITIES)} sites)...")
    uamps_wind_weather = {}
    for name, state, lat, lon in UAMPS_WIND_CITIES:
        key = f"{name}_{state}"
        print(f"  {name}, {state}...", flush=True)
        uamps_wind_weather[key] = fetch_wind_day(lat, lon)
        time.sleep(0.15)

    print("\n  Writing data.json...")
    write_data_json(today, all_dates, city_weather, solar_weather, wind_weather, normals,
                    uamps_city_weather, uamps_solar_weather, uamps_wind_weather)

    print("\n  Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
