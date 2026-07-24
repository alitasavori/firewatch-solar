"""EPA AQS PM2.5 monitor catalog + nearest-monitor assignment for Western US sites."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from typing import Any

import requests

CACHE_FILE = "epa_pm25_monitors_cache.json"
CACHE_MAX_AGE_HOURS = 24 * 7  # weekly refresh is enough

# Process-local catalog so inventory / nearest lookups don't re-parse JSON.
_MONITORS_MEM: list[dict[str, Any]] | None = None

# Western US state postal → FIPS (matches USPVDB coverage)
STATE_FIPS = {
    "AZ": "04",
    "CA": "06",
    "CO": "08",
    "ID": "16",
    "MT": "30",
    "NV": "32",
    "NM": "35",
    "OR": "41",
    "UT": "49",
    "WA": "53",
    "WY": "56",
}

FIPS_TO_STATE = {v: k for k, v in STATE_FIPS.items()}

# Cap for assigning a real EPA monitor (not invented IDs).
MAX_EPA_DISTANCE_KM = 100.0

AQS_EMAIL = "test@aqs.api"
AQS_KEY = "test"
PARAM_PM25 = "88101"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cache_fresh() -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    return datetime.now() - mtime < timedelta(hours=CACHE_MAX_AGE_HOURS)


def _load_cache(*, allow_stale: bool = False) -> list[dict[str, Any]] | None:
    if not os.path.exists(CACHE_FILE):
        return None
    if not allow_stale and not _cache_fresh():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        monitors = data.get("monitors") if isinstance(data, dict) else data
        if isinstance(monitors, list) and monitors:
            return monitors
    except Exception:
        return None
    return None


def _save_cache(monitors: list[dict[str, Any]]) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "fetched_at": datetime.utcnow().isoformat() + "Z",
                "param": PARAM_PM25,
                "states": list(STATE_FIPS.keys()),
                "total": len(monitors),
                "monitors": monitors,
            },
            f,
        )


def _dedupe_monitors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per state/county/site (prefer named sites)."""
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        state = str(row.get("state_code") or "").zfill(2)
        county = str(row.get("county_code") or "").zfill(3)
        site = str(row.get("site_number") or "").zfill(4)
        lat, lon = row.get("latitude"), row.get("longitude")
        if not state or not county or not site or lat is None or lon is None:
            continue
        key = (state, county, site)
        name = row.get("local_site_name") or row.get("site_name") or ""
        cand = {
            "state_code": state,
            "county_code": county,
            "site_number": site,
            "latitude": float(lat),
            "longitude": float(lon),
            "name": name,
            "state": FIPS_TO_STATE.get(state, ""),
        }
        prev = best.get(key)
        if prev is None or (name and not prev.get("name")):
            best[key] = cand
    return list(best.values())


def fetch_western_pm25_monitors(
    use_cache: bool = True,
    allow_remote: bool = True,
) -> list[dict[str, Any]]:
    """Load Western US EPA AQS PM2.5 (88101) monitors.

    Request-path callers should pass allow_remote=False so inventory never blocks
    on EPA network I/O. Stale disk cache is preferred over an empty catalog.
    """
    global _MONITORS_MEM

    if use_cache and _MONITORS_MEM is not None:
        return _MONITORS_MEM

    if use_cache:
        cached = _load_cache(allow_stale=False)
        if cached is not None:
            _MONITORS_MEM = cached
            return cached

    if not allow_remote:
        # Prefer any on-disk catalog (even stale) rather than blocking or returning [].
        stale = _load_cache(allow_stale=True) if use_cache else None
        if stale is not None:
            _MONITORS_MEM = stale
            return stale
        return []

    # Recent calendar year window so AQS returns active-ish monitors.
    year = datetime.utcnow().year - 1
    bdate = f"{year}0101"
    edate = f"{year}1231"

    collected: list[dict[str, Any]] = []
    for postal, fips in STATE_FIPS.items():
        url = (
            "https://aqs.epa.gov/data/api/monitors/byState"
            f"?email={AQS_EMAIL}&key={AQS_KEY}&param={PARAM_PM25}"
            f"&bdate={bdate}&edate={edate}&state={fips}"
        )
        try:
            # Keep remote refresh bounded; inventory must not depend on this path.
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("Data") or []
            collected.extend(rows)
            print(f"[aq_monitors] {postal} ({fips}): {len(rows)} monitor rows")
        except Exception as exc:
            print(f"[aq_monitors] failed {postal}: {exc}")

    monitors = _dedupe_monitors(collected)
    if monitors:
        _save_cache(monitors)
        _MONITORS_MEM = monitors
        return monitors

    # Remote failed/partial — fall back to stale disk so enrichment still works.
    stale = _load_cache(allow_stale=True) if use_cache else None
    if stale is not None:
        _MONITORS_MEM = stale
        return stale
    return []


def nearest_pm25_monitor(
    latitude: float,
    longitude: float,
    monitors: list[dict[str, Any]] | None = None,
    max_km: float = MAX_EPA_DISTANCE_KM,
) -> dict[str, Any] | None:
    """
    Return nearest EPA PM2.5 monitor within max_km, or None if too far.
    Does not invent IDs — only returns real AQS state/county/site triples.
    """
    if monitors is None:
        monitors = fetch_western_pm25_monitors()
    if not monitors:
        return None

    best = None
    best_km = float("inf")
    for m in monitors:
        d = _haversine_km(latitude, longitude, m["latitude"], m["longitude"])
        if d < best_km:
            best_km = d
            best = m

    if best is None or best_km > max_km:
        return None

    return {
        "state_code": best["state_code"],
        "county_code": best["county_code"],
        "site_number": best["site_number"],
        "name": best.get("name") or "",
        "latitude": best["latitude"],
        "longitude": best["longitude"],
        "state": best.get("state") or FIPS_TO_STATE.get(best["state_code"], ""),
        "distance_km": round(best_km, 1),
    }


def resolve_pm25_source(
    latitude: float,
    longitude: float,
    monitors: list[dict[str, Any]] | None = None,
    max_km: float = MAX_EPA_DISTANCE_KM,
) -> dict[str, Any]:
    """
    Prefer real nearest EPA monitor within max_km; otherwise Open-Meteo by lat/lon.
    Always returns a usable PM2.5 strategy (inference-capable).
    """
    nearest = nearest_pm25_monitor(latitude, longitude, monitors=monitors, max_km=max_km)
    if nearest is not None:
        label = nearest["name"] or (
            f"EPA {nearest['state_code']}-{nearest['county_code']}-{nearest['site_number']}"
        )
        return {
            "pm25_source": "epa_nearest",
            "state_fips": nearest["state_code"],
            "county": nearest["county_code"],
            "site": nearest["site_number"],
            "pm25_monitor_name": label,
            "pm25_distance_km": nearest["distance_km"],
            "note": (
                f"PM2.5 from nearest EPA monitor {label} "
                f"({nearest['distance_km']} km away)."
            ),
        }

    return {
        "pm25_source": "openmeteo",
        "state_fips": None,
        "county": None,
        "site": None,
        "pm25_monitor_name": None,
        "pm25_distance_km": None,
        "note": (
            "PM2.5 from Open-Meteo air-quality API (lat/lon proxy); "
            f"no EPA PM2.5 monitor within {int(max_km)} km."
        ),
    }
