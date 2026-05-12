"""WorldMonitor map events aggregator.

Fetches real-time geospatial events from free public APIs:
- USGS GeoJSON (M4.5+ earthquakes, past 7 days)
- NASA EONET (open natural events: volcanoes, wildfires, storms, floods)
- GDACS GeoRSS (UN-coordinated global disaster alerts)
- Feodo Tracker JSON (active botnet C2 servers, grouped by country centroid)

Stores to Redis:
    wm:events:latest   — JSON list[300] of MapEvent dicts, newest-first
    wm:events:meta     — JSON: last_run, source_counts, duration_s
"""

from __future__ import annotations

import asyncio
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
import redis.asyncio as aioredis
import structlog

from .cache import CACHE_TIERS, fnv1a_hash, redis_key

log = structlog.get_logger(__name__)

KEY_EVENTS = redis_key("events", "latest")
KEY_EVENTS_META = redis_key("events", "meta")

_FETCH_TIMEOUT = 15.0

# ISO-2 country → (lat, lng) centroid (covers major countries for C2 geolocation)
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "US": (37.09, -95.71), "GB": (55.38, -3.44), "DE": (51.17, 10.45),
    "FR": (46.23, 2.21), "RU": (61.52, 105.32), "CN": (35.86, 104.20),
    "IN": (20.59, 78.96), "UA": (48.38, 31.17), "IL": (31.05, 34.85),
    "IR": (32.43, 53.69), "KP": (40.34, 127.51), "SY": (34.80, 38.99),
    "IQ": (33.22, 43.68), "AF": (33.93, 67.71), "PK": (30.38, 69.35),
    "NG": (9.08, 8.68), "SD": (12.86, 30.22), "SO": (5.15, 46.20),
    "YE": (15.55, 48.52), "LY": (26.34, 17.23), "ML": (17.57, -3.99),
    "CF": (6.61, 20.94), "CD": (-4.04, 21.76), "ET": (9.15, 40.49),
    "JP": (36.20, 138.25), "KR": (35.91, 127.77), "TR": (38.96, 35.24),
    "BR": (-14.24, -51.93), "MX": (23.63, -102.55), "EG": (26.82, 30.80),
    "SA": (23.89, 45.08), "AU": (-25.27, 133.78), "CA": (56.13, -106.35),
    "ID": (-0.79, 113.92), "PH": (12.88, 121.77), "VN": (14.06, 108.28),
    "TH": (15.87, 100.99), "MM": (21.91, 95.96), "BD": (23.68, 90.36),
    "IT": (41.87, 12.57), "ES": (40.46, -3.75), "PL": (51.92, 19.15),
    "NL": (52.13, 5.29), "BE": (50.50, 4.47), "CH": (46.82, 8.23),
    "AT": (47.52, 14.55), "SE": (60.13, 18.64), "NO": (60.47, 8.47),
    "FI": (61.92, 25.75), "DK": (56.26, 9.50), "GR": (39.07, 21.82),
    "RO": (45.94, 24.97), "HU": (47.16, 19.50), "CZ": (49.82, 15.47),
    "SK": (48.67, 19.70), "BG": (42.73, 25.49), "HR": (45.10, 15.20),
    "RS": (44.02, 21.01), "BA": (44.16, 17.68), "UA": (48.38, 31.17),
    "BY": (53.71, 27.95), "MD": (47.41, 28.37), "LT": (55.17, 23.88),
    "LV": (56.88, 24.60), "EE": (58.60, 25.01), "KZ": (48.02, 66.92),
    "UZ": (41.38, 64.59), "TM": (38.97, 59.56), "TJ": (38.86, 71.28),
    "KG": (41.20, 74.77), "AZ": (40.14, 47.58), "GE": (42.32, 43.36),
    "AM": (40.07, 45.04), "TN": (33.89, 9.54), "MA": (31.79, -7.09),
    "DZ": (28.03, 1.66), "LB": (33.85, 35.86), "JO": (30.59, 36.24),
    "KW": (29.31, 47.49), "QA": (25.35, 51.18), "AE": (23.42, 53.85),
    "OM": (21.51, 55.92), "BH": (26.00, 50.55), "ZA": (-30.56, 22.94),
    "KE": (-1.29, 36.82), "TZ": (-6.37, 34.89), "UG": (1.37, 32.29),
    "RW": (-1.94, 29.87), "CI": (7.54, -5.55), "GH": (7.95, -1.02),
    "SN": (14.50, -14.45), "CM": (3.85, 11.50), "MZ": (-18.67, 35.53),
    "ZW": (-19.02, 29.15), "ZM": (-13.13, 27.85), "AO": (-11.20, 17.87),
    "NE": (17.61, 8.08), "TD": (15.45, 18.73), "BF": (12.36, -1.56),
    "GN": (9.95, -11.79), "SL": (8.46, -11.78), "LR": (6.43, -9.43),
    "TG": (8.62, 0.82), "BJ": (9.31, 2.32), "MG": (-18.77, 46.87),
    "MW": (-13.25, 34.30), "NP": (28.39, 84.12), "LK": (7.87, 80.77),
    "MN": (46.86, 103.85), "KH": (12.57, 104.99), "LA": (19.86, 102.50),
    "PE": (-9.19, -75.02), "CO": (4.57, -74.30), "VE": (6.42, -66.59),
    "CL": (-35.68, -71.54), "AR": (-38.42, -63.62), "BO": (-16.29, -63.59),
    "EC": (-1.83, -78.18), "PY": (-23.44, -58.44), "UY": (-32.52, -55.77),
    "CU": (21.52, -77.78), "HT": (18.97, -72.29), "DO": (18.74, -70.16),
    "GT": (15.78, -90.23), "HN": (15.20, -86.24), "SV": (13.79, -88.90),
    "NI": (12.86, -85.21), "CR": (9.75, -83.75), "PA": (8.54, -80.78),
    "NZ": (-40.90, 174.89), "PG": (-6.31, 143.96), "FJ": (-16.58, 179.41),
    "NG": (9.08, 8.68), "TW": (23.70, 120.96), "HK": (22.35, 114.18),
    "SG": (1.35, 103.82),
}


def _severity_from_magnitude(mag: float) -> str:
    if mag >= 6.5:
        return "high"
    if mag >= 5.0:
        return "medium"
    return "low"


async def _fetch_usgs_earthquakes(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """USGS GeoJSON Feed: M4.5+ earthquakes past 7 days."""
    try:
        resp = await client.get(
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson",
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": "WorldMonitor/1.0 (geopolitical-dashboard)"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("usgs_fetch_failed", error=str(exc))
        return []

    events: list[dict[str, Any]] = []
    for feature in data.get("features", [])[:100]:
        props = feature.get("properties", {})
        coords = (feature.get("geometry") or {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        lng, lat = coords[0], coords[1]
        mag = props.get("mag") or 0.0
        title = props.get("title") or f"M{mag} earthquake"
        ts_ms = props.get("time") or 0
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()

        events.append({
            "id": fnv1a_hash(f"usgs_{feature.get('id', title)}"),
            "layer": "disaster",
            "lat": round(float(lat), 4),
            "lng": round(float(lng), 4),
            "title": title,
            "severity": _severity_from_magnitude(float(mag)),
            "timestamp": ts,
            "source": "USGS",
        })

    log.debug("usgs_fetched", count=len(events))
    return events


async def _fetch_nasa_eonet(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """NASA EONET API v3: open natural events (volcanoes, wildfires, storms, floods)."""
    try:
        resp = await client.get(
            "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=60",
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": "WorldMonitor/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("eonet_fetch_failed", error=str(exc))
        return []

    LAYER_MAP = {
        "Wildfires": "energy",
        "Volcanoes": "disaster",
        "Severe Storms": "crisis",
        "Floods": "crisis",
        "Earthquakes": "disaster",
        "Landslides": "disaster",
        "Sea and Lake Ice": "crisis",
        "Dust and Haze": "crisis",
        "Drought": "crisis",
        "Temperature Extremes": "crisis",
        "Manmade": "energy",
        "Water Color": "crisis",
        "Snow": "crisis",
    }
    SEVERITY_MAP = {
        "Wildfires": "medium",
        "Volcanoes": "high",
        "Severe Storms": "high",
        "Floods": "medium",
        "Earthquakes": "high",
        "Landslides": "medium",
    }

    events: list[dict[str, Any]] = []
    for event in data.get("events", []):
        title = event.get("title", "Unknown event")
        categories = event.get("categories", [])
        cat_title = categories[0].get("title", "Unknown") if categories else "Unknown"
        layer = LAYER_MAP.get(cat_title, "crisis")
        severity = SEVERITY_MAP.get(cat_title, "medium")

        geometries = event.get("geometry", [])
        if not geometries:
            continue

        latest_geo = geometries[-1]
        coords = latest_geo.get("coordinates")
        if not coords:
            continue

        # Can be [lng, lat] point or polygon [[lng, lat], ...]
        if isinstance(coords[0], list):
            lng, lat = float(coords[0][0]), float(coords[0][1])
        else:
            lng, lat = float(coords[0]), float(coords[1])

        ts = latest_geo.get("date") or datetime.now(tz=timezone.utc).isoformat()

        events.append({
            "id": fnv1a_hash(f"eonet_{event.get('id', title)}"),
            "layer": layer,
            "lat": round(lat, 4),
            "lng": round(lng, 4),
            "title": f"{cat_title}: {title}",
            "severity": severity,
            "timestamp": ts,
            "source": "NASA EONET",
        })

    log.debug("eonet_fetched", count=len(events))
    return events


async def _fetch_gdacs(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """GDACS GeoRSS: UN-coordinated disaster alerts with severity and coordinates."""
    try:
        resp = await client.get(
            "https://www.gdacs.org/xml/rss.xml",
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": "WorldMonitor/1.0"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as exc:
        log.warning("gdacs_fetch_failed", error=str(exc))
        return []

    NS_GEO = "http://www.w3.org/2003/01/geo/wgs84_pos#"
    NS_GEORSS = "http://www.georss.org/georss"
    NS_GDACS = "http://www.gdacs.org"

    SEVERITY_MAP = {"Red": "high", "Orange": "medium", "Green": "low"}
    LAYER_MAP = {
        "EQ": "disaster", "TC": "crisis", "FL": "crisis",
        "VO": "disaster", "DR": "crisis", "WF": "energy", "TS": "crisis",
    }

    events: list[dict[str, Any]] = []
    channel = root.find("channel")
    if channel is None:
        return events

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        pub_date_raw = item.findtext("pubDate") or ""

        lat: float | None = None
        lng: float | None = None

        # Try georss:point first
        geo_point = item.findtext(f"{{{NS_GEORSS}}}point")
        if geo_point:
            parts = geo_point.strip().split()
            if len(parts) == 2:
                try:
                    lat, lng = float(parts[0]), float(parts[1])
                except ValueError:
                    pass

        # Fallback: geo:lat / geo:long
        if lat is None:
            lat_el = item.find(f"{{{NS_GEO}}}lat")
            lng_el = item.find(f"{{{NS_GEO}}}long")
            if lat_el is not None and lng_el is not None:
                try:
                    lat = float(lat_el.text or "")
                    lng = float(lng_el.text or "")
                except ValueError:
                    pass

        if lat is None or lng is None:
            continue

        alert_level = item.findtext(f"{{{NS_GDACS}}}alertlevel") or "Green"
        severity = SEVERITY_MAP.get(alert_level, "low")
        event_type = item.findtext(f"{{{NS_GDACS}}}eventtype") or ""
        layer = LAYER_MAP.get(event_type, "crisis")

        try:
            ts = parsedate_to_datetime(pub_date_raw).astimezone(timezone.utc).isoformat()
        except Exception:
            ts = datetime.now(tz=timezone.utc).isoformat()

        events.append({
            "id": fnv1a_hash(f"gdacs_{title}_{ts}"),
            "layer": layer,
            "lat": round(lat, 4),
            "lng": round(lng, 4),
            "title": title,
            "severity": severity,
            "timestamp": ts,
            "source": "GDACS",
        })

    log.debug("gdacs_fetched", count=len(events))
    return events


async def _fetch_feodo_tracker(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Feodo Tracker: active botnet C2 servers grouped by country centroid."""
    try:
        resp = await client.get(
            "https://feodotracker.abuse.ch/downloads/ipblocklist.json",
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": "WorldMonitor/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("feodo_fetch_failed", error=str(exc))
        return []

    # Group by country to avoid thousands of individual markers
    country_counts: dict[str, int] = {}
    country_families: dict[str, set[str]] = {}

    for entry in data:
        country = entry.get("country") or "XX"
        family = entry.get("malware_family") or "Unknown"
        country_counts[country] = country_counts.get(country, 0) + 1
        country_families.setdefault(country, set()).add(family)

    events: list[dict[str, Any]] = []
    now_ts = datetime.now(tz=timezone.utc).isoformat()

    for country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
        coords = COUNTRY_CENTROIDS.get(country)
        if not coords:
            continue
        lat, lng = coords
        families_str = ", ".join(sorted(country_families[country])[:3])
        severity: str = "high" if count >= 10 else "medium" if count >= 3 else "low"

        # Small deterministic jitter so overlapping country markers don't stack
        jitter_lat = (fnv1a_hash(country) and int(fnv1a_hash(country), 16) % 50) * 0.015
        jitter_lng = (fnv1a_hash(country + "x") and int(fnv1a_hash(country + "x"), 16) % 50) * 0.015

        events.append({
            "id": fnv1a_hash(f"feodo_{country}"),
            "layer": "cyber",
            "lat": round(lat + jitter_lat, 4),
            "lng": round(lng + jitter_lng, 4),
            "title": f"Active C2 servers — {country} ({count} hosts) [{families_str}]",
            "severity": severity,
            "timestamp": now_ts,
            "source": "Feodo Tracker",
        })

    log.debug("feodo_fetched", country_count=len(events))
    return events


# ── Static hotspot datasets ────────────────────────────────────────────────────

_CONFLICT_ZONES: list[dict[str, Any]] = [
    {"id": "conflict-ukraine",      "title": "Russia-Ukraine War",                       "lat": 49.0,  "lng": 31.5,   "severity": "critical"},
    {"id": "conflict-gaza",         "title": "Gaza-Israel Conflict",                      "lat": 31.4,  "lng": 34.3,   "severity": "critical"},
    {"id": "conflict-red-sea",      "title": "Red Sea — Houthi Attacks on Shipping",      "lat": 15.0,  "lng": 42.5,   "severity": "critical"},
    {"id": "conflict-west-bank",    "title": "West Bank Operations",                      "lat": 32.0,  "lng": 35.3,   "severity": "high"},
    {"id": "conflict-kashmir",      "title": "Kashmir Line of Control Tensions",          "lat": 34.1,  "lng": 74.8,   "severity": "high"},
    {"id": "conflict-taiwan-strait","title": "Taiwan Strait Military Tensions",           "lat": 24.0,  "lng": 120.5,  "severity": "high"},
    {"id": "conflict-iran-israel",  "title": "Iran-Israel Shadow War",                    "lat": 32.0,  "lng": 37.0,   "severity": "high"},
    {"id": "conflict-sudan",        "title": "Sudan Civil War (RSF vs SAF)",              "lat": 15.5,  "lng": 32.5,   "severity": "high"},
    {"id": "conflict-myanmar",      "title": "Myanmar Civil War",                         "lat": 21.0,  "lng": 96.5,   "severity": "high"},
    {"id": "conflict-yemen",        "title": "Yemen Conflict",                            "lat": 15.5,  "lng": 48.5,   "severity": "high"},
    {"id": "conflict-somalia",      "title": "Somalia — Al-Shabaab",                      "lat":  5.2,  "lng": 46.2,   "severity": "high"},
    {"id": "conflict-drc",          "title": "DRC Eastern Conflict (M23/Rwanda)",         "lat": -1.5,  "lng": 29.5,   "severity": "high"},
    {"id": "conflict-sahel",        "title": "Sahel — BF/Mali/Niger Jihadist Insurgency", "lat": 14.0,  "lng": -1.5,   "severity": "high"},
    {"id": "conflict-nigeria",      "title": "Nigeria — ISWAP / Boko Haram",              "lat": 12.0,  "lng": 14.5,   "severity": "high"},
    {"id": "conflict-haiti",        "title": "Haiti Gang Violence",                       "lat": 18.9,  "lng": -72.3,  "severity": "high"},
    {"id": "conflict-syria",        "title": "Syria Post-Assad Instability",              "lat": 34.8,  "lng": 38.8,   "severity": "medium"},
    {"id": "conflict-ethiopia",     "title": "Ethiopia — Amhara Conflict",                "lat": 11.5,  "lng": 40.5,   "severity": "medium"},
    {"id": "conflict-mozambique",   "title": "Mozambique — Cabo Delgado Insurgency",      "lat": -12.0, "lng": 40.5,   "severity": "medium"},
    {"id": "conflict-iraq-pmf",     "title": "Iraq — PMF / ISIS Activity",                "lat": 33.3,  "lng": 44.4,   "severity": "medium"},
    {"id": "conflict-colombia",     "title": "Colombia — ELN / FARC Dissidents",          "lat":  4.5,  "lng": -74.3,  "severity": "medium"},
]

_MILITARY_HOTSPOTS: list[dict[str, Any]] = [
    {"id": "mil-ukraine-front",     "title": "Ukraine-Russia Front Lines",                "lat": 48.5,  "lng": 37.5,   "severity": "critical"},
    {"id": "mil-red-sea-us",        "title": "US CTF-153 Red Sea / Gulf of Aden",         "lat": 13.5,  "lng": 44.0,   "severity": "high"},
    {"id": "mil-kashmir-loc",       "title": "India-Pakistan LoC — Active Artillery",     "lat": 33.5,  "lng": 73.5,   "severity": "high"},
    {"id": "mil-black-sea",         "title": "Black Sea Naval Operations",                "lat": 43.0,  "lng": 34.0,   "severity": "high"},
    {"id": "mil-strait-hormuz",     "title": "Strait of Hormuz Tensions",                 "lat": 26.6,  "lng": 56.3,   "severity": "high"},
    {"id": "mil-south-china-sea",   "title": "South China Sea PLA Navy Activity",         "lat": 12.0,  "lng": 115.0,  "severity": "high"},
    {"id": "mil-taiwan-strait-ops", "title": "Taiwan Strait Military Exercises",          "lat": 24.5,  "lng": 121.0,  "severity": "high"},
    {"id": "mil-levant",            "title": "Eastern Mediterranean (US/Israel/Syria)",   "lat": 33.5,  "lng": 35.5,   "severity": "high"},
    {"id": "mil-persian-gulf",      "title": "Persian Gulf Naval Deployments",            "lat": 26.5,  "lng": 53.0,   "severity": "high"},
    {"id": "mil-korea-peninsula",   "title": "Korean Peninsula Joint Exercises",          "lat": 37.5,  "lng": 127.0,  "severity": "medium"},
    {"id": "mil-nato-east",         "title": "NATO Eastern Flank — Baltic/Poland",        "lat": 54.0,  "lng": 23.0,   "severity": "medium"},
    {"id": "mil-baltics-naval",     "title": "Baltic Sea NATO Naval Ops",                 "lat": 58.0,  "lng": 20.0,   "severity": "medium"},
    {"id": "mil-arctic",            "title": "Arctic Military Activity",                  "lat": 75.0,  "lng": 20.0,   "severity": "medium"},
    {"id": "mil-indian-ocean",      "title": "Indian Ocean Carrier Strike Group",         "lat":  5.0,  "lng": 68.0,   "severity": "medium"},
    {"id": "mil-sahel-africa",      "title": "Africa Sahel Military Operations",          "lat": 15.0,  "lng":  2.0,   "severity": "medium"},
    {"id": "mil-japan-sea",         "title": "Sea of Japan — DPRK Missile Test Zone",     "lat": 40.0,  "lng": 135.0,  "severity": "medium"},
]

_NUCLEAR_SITES: list[dict[str, Any]] = [
    {"id": "nuc-zaporizhzhia",    "title": "Zaporizhzhia NPP (Active War Zone)",           "lat": 47.5,  "lng": 34.6,   "severity": "critical"},
    {"id": "nuc-iran-natanz",     "title": "Iran Natanz Enrichment Facility",              "lat": 33.7,  "lng": 51.7,   "severity": "critical"},
    {"id": "nuc-iran-fordow",     "title": "Iran Fordow Underground Facility",             "lat": 34.9,  "lng": 51.0,   "severity": "critical"},
    {"id": "nuc-kp-yongbyon",     "title": "DPRK Yongbyon Nuclear Complex",               "lat": 39.8,  "lng": 125.8,  "severity": "critical"},
    {"id": "nuc-kp-punggye-ri",   "title": "DPRK Punggye-ri Test Site",                   "lat": 41.3,  "lng": 129.1,  "severity": "critical"},
    {"id": "nuc-iran-arak",       "title": "Iran Arak Heavy Water Reactor",               "lat": 34.1,  "lng": 49.3,   "severity": "high"},
    {"id": "nuc-israel-dimona",   "title": "Israel Dimona Reactor (Suspected Weapons)",   "lat": 31.0,  "lng": 35.1,   "severity": "high"},
    {"id": "nuc-pakistan-khushab","title": "Pakistan Khushab Plutonium Reactor",          "lat": 32.1,  "lng": 71.8,   "severity": "high"},
    {"id": "nuc-china-jiuquan",   "title": "China Jiuquan Atomic Energy Complex",         "lat": 40.0,  "lng": 100.0,  "severity": "high"},
    {"id": "nuc-russia-novaya",   "title": "Russia Novaya Zemlya Test Site",              "lat": 73.3,  "lng": 55.1,   "severity": "high"},
    {"id": "nuc-chernobyl",       "title": "Chernobyl Exclusion Zone",                    "lat": 51.4,  "lng": 30.1,   "severity": "medium"},
    {"id": "nuc-fukushima",       "title": "Fukushima Daiichi (Decommissioning)",         "lat": 37.4,  "lng": 141.0,  "severity": "medium"},
    {"id": "nuc-sellafield",      "title": "UK Sellafield Reprocessing Site",             "lat": 54.4,  "lng": -3.5,   "severity": "medium"},
    {"id": "nuc-la-hague",        "title": "France La Hague Reprocessing",                "lat": 49.7,  "lng": -1.9,   "severity": "medium"},
    {"id": "nuc-hanford",         "title": "US Hanford Nuclear Reservation",              "lat": 46.5,  "lng": -119.5, "severity": "medium"},
    {"id": "nuc-savannah",        "title": "US Savannah River Site",                      "lat": 33.3,  "lng": -81.7,  "severity": "medium"},
]

_INTEL_HOTSPOTS: list[dict[str, Any]] = [
    {"id": "intel-ru-gru",        "title": "Russia GRU / SVR Cyber Ops (Moscow)",         "lat": 55.7,  "lng": 37.6,   "severity": "critical"},
    {"id": "intel-ru-sandworm",   "title": "Russia Sandworm ICS Targeting",               "lat": 55.9,  "lng": 37.9,   "severity": "critical"},
    {"id": "intel-cn-apt-bj",     "title": "China PLA Cyber Unit (Beijing)",              "lat": 39.9,  "lng": 116.4,  "severity": "critical"},
    {"id": "intel-cn-apt-sh",     "title": "China APT Infrastructure (Shanghai)",         "lat": 31.2,  "lng": 121.5,  "severity": "critical"},
    {"id": "intel-ir-apt",        "title": "Iran MOIS / IRGC Cyber Ops (Tehran)",         "lat": 35.7,  "lng": 51.4,   "severity": "high"},
    {"id": "intel-kp-lazarus",    "title": "DPRK Lazarus Group",                          "lat": 39.0,  "lng": 125.8,  "severity": "high"},
    {"id": "intel-israel-8200",   "title": "Israel Unit 8200 Signals Intelligence",       "lat": 32.1,  "lng": 34.9,   "severity": "high"},
    {"id": "intel-ru-ransomware", "title": "Eastern Europe Ransomware Hubs",              "lat": 50.5,  "lng": 30.5,   "severity": "high"},
    {"id": "intel-nato-cyber",    "title": "NATO CCDCOE (Tallinn)",                       "lat": 59.4,  "lng": 24.7,   "severity": "medium"},
    {"id": "intel-us-cyber-cmd",  "title": "US Cyber Command (Fort Meade)",               "lat": 39.1,  "lng": -76.7,  "severity": "medium"},
]


def _static_events(hotspots: list[dict[str, Any]], layer: str, source: str) -> list[dict[str, Any]]:
    ts = datetime.now(tz=timezone.utc).isoformat()
    return [
        {"id": h["id"], "layer": layer, "lat": h["lat"], "lng": h["lng"],
         "title": h["title"], "severity": h["severity"], "timestamp": ts, "source": source}
        for h in hotspots
    ]


async def _fetch_world_nuclear_news(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """World Nuclear News RSS → nuclear layer events with country-centroid coords."""
    _COORD_HINTS: list[tuple[list[str], float, float]] = [
        (["iran", "natanz", "fordow", "arak"],            33.7,   51.7),
        (["ukraine", "zaporizhzhia", "zaporizhzhya"],     47.5,   34.6),
        (["russia", "rosatom", "russian"],                55.7,   37.6),
        (["north korea", "dprk", "pyongyang"],            39.0,  125.8),
        (["china", "chinese"],                            35.9,  104.2),
        (["pakistan"],                                    30.4,   69.3),
        (["india", "indian"],                             20.6,   79.0),
        (["japan", "fukushima"],                          36.2,  138.3),
        (["france", "french"],                            46.2,    2.2),
        (["uk", "united kingdom", "sellafield"],          54.4,   -3.5),
        (["usa", "united states", "american", "nrc"],     37.1,  -95.7),
        (["finland", "olkiluoto"],                        61.2,   21.4),
        (["south korea", "korean"],                       35.9,  127.8),
        (["taiwan"],                                      23.7,  121.0),
    ]
    try:
        resp = await client.get(
            "https://www.world-nuclear-news.org/rss",
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": "WorldMonitor/1.0"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception as exc:
        log.warning("wnn_fetch_failed", error=str(exc))
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    events: list[dict[str, Any]] = []
    for item in channel.findall("item")[:25]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_str = item.findtext("pubDate") or ""
        try:
            ts = parsedate_to_datetime(pub_str).isoformat()
        except Exception:
            ts = datetime.now(tz=timezone.utc).isoformat()

        text_lower = (title + " " + (item.findtext("description") or "")).lower()
        lat, lng = 0.0, 0.0
        for keywords, klat, klng in _COORD_HINTS:
            if any(kw in text_lower for kw in keywords):
                lat, lng = klat, klng
                break
        if lat == 0.0:
            continue

        severity = (
            "critical" if any(w in text_lower for w in ["weapon", "warhead", "attack", "crisis", "emergency"])
            else "high" if any(w in text_lower for w in ["enrich", "uranium", "plutonium", "sanction", "proliferat"])
            else "medium"
        )
        events.append({
            "id": fnv1a_hash(f"wnn_{link}"),
            "layer": "nuclear",
            "lat": round(lat, 4), "lng": round(lng, 4),
            "title": title,
            "severity": severity,
            "timestamp": ts,
            "source": "World Nuclear News",
        })

    log.debug("wnn_fetched", count=len(events))
    return events


async def _fetch_acled(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """ACLED conflict data — requires ACLED_API_KEY + ACLED_API_EMAIL env vars."""
    import os
    api_key = os.getenv("ACLED_API_KEY", "")
    api_email = os.getenv("ACLED_API_EMAIL", "")
    if not api_key or not api_email:
        return []

    try:
        resp = await client.get(
            "https://api.acleddata.com/acled/read.php",
            params={
                "key": api_key, "email": api_email,
                "limit": 100,
                "fields": "event_id_cnty|event_date|event_type|country|latitude|longitude|notes|fatalities",
                "event_date": "2025-01-01", "event_date_where": ">=",
            },
            timeout=_FETCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as exc:
        log.warning("acled_fetch_failed", error=str(exc))
        return []

    _MILITARY_TYPES = {"Battles", "Explosions/Remote violence", "Strategic developments"}
    events: list[dict[str, Any]] = []
    for row in data:
        try:
            lat, lng = float(row.get("latitude") or 0), float(row.get("longitude") or 0)
        except (ValueError, TypeError):
            continue
        if lat == 0.0 and lng == 0.0:
            continue
        event_type = row.get("event_type", "")
        fatalities = int(row.get("fatalities") or 0)
        events.append({
            "id": fnv1a_hash(f"acled_{row.get('event_id_cnty', '')}"),
            "layer": "military" if event_type in _MILITARY_TYPES else "conflict",
            "lat": round(lat, 4), "lng": round(lng, 4),
            "title": f"[{event_type}] {row.get('country', '')} — {(row.get('notes') or '')[:80]}",
            "severity": "critical" if fatalities >= 50 else "high" if fatalities >= 10 else "medium" if fatalities >= 1 else "low",
            "timestamp": row.get("event_date", datetime.now(tz=timezone.utc).isoformat()),
            "source": "ACLED",
        })

    log.debug("acled_fetched", count=len(events))
    return events


async def run_events_aggregation(redis: aioredis.Redis) -> dict[str, Any]:
    """Fetch all event sources and persist to Redis. Returns stats dict."""
    started_at = time.time()

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _fetch_usgs_earthquakes(client),
            _fetch_nasa_eonet(client),
            _fetch_gdacs(client),
            _fetch_feodo_tracker(client),
            _fetch_world_nuclear_news(client),
            _fetch_acled(client),
            return_exceptions=True,
        )

    all_events: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    # Always include static hotspot datasets
    for static_batch, layer, source in [
        (_CONFLICT_ZONES,   "conflict", "OSINT Static"),
        (_MILITARY_HOTSPOTS,"military", "OSINT Static"),
        (_NUCLEAR_SITES,    "nuclear",  "OSINT Static"),
        (_INTEL_HOTSPOTS,   "intel",    "OSINT Static"),
    ]:
        batch = _static_events(static_batch, layer, source)
        source_counts[f"static_{layer}"] = len(batch)
        all_events.extend(batch)

    for result in results:
        if isinstance(result, Exception):
            log.error("events_aggregation_task_error", error=str(result))
            continue
        for ev in result:  # type: ignore[union-attr]
            src = ev.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
        all_events.extend(result)  # type: ignore[arg-type]

    # Deduplicate by id
    seen_ids: set[str] = set()
    unique_events: list[dict[str, Any]] = []
    for ev in all_events:
        if ev["id"] not in seen_ids:
            seen_ids.add(ev["id"])
            unique_events.append(ev)

    unique_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Persist to Redis (replace entire list atomically)
    pipe = redis.pipeline()
    pipe.delete(KEY_EVENTS)
    for ev in unique_events[:500]:
        pipe.rpush(KEY_EVENTS, json.dumps(ev, default=str))
    pipe.expire(KEY_EVENTS, CACHE_TIERS["fast"] * 4)  # 20-min TTL

    meta: dict[str, Any] = {
        "last_run": datetime.now(tz=timezone.utc).isoformat(),
        "duration_s": round(time.time() - started_at, 2),
        "total_events": len(unique_events),
        "source_counts": source_counts,
    }
    pipe.setex(KEY_EVENTS_META, CACHE_TIERS["fast"] * 4, json.dumps(meta))
    await pipe.execute()

    log.info("events_aggregation_complete", **{k: v for k, v in meta.items() if k != "source_counts"})
    return meta
