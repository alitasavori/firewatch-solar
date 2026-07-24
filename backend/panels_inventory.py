"""Merge SolarSense Utah EPA panels with FireWatch/USPVDB Western US PV units."""
from __future__ import annotations

import math
from typing import Any

from api_fetch_wrapper import load_panels
from aq_monitors import MAX_EPA_DISTANCE_KM, fetch_western_pm25_monitors, resolve_pm25_source
from uspvdb_client import UspvdbError, fetch_solar_projects, WESTERN_STATE_CODES

# Match radius: if a USPVDB plant is this close to a SolarSense site, keep SolarSense.
MATCH_KM = 2.5


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _solarsense_row(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "panel_id": p["panel_id"],
        "site_name": p.get("site_name") or p["panel_id"],
        "latitude": float(p["latitude"]),
        "longitude": float(p["longitude"]),
        "county": p.get("county"),
        "site": p.get("site"),
        "county_name": p.get("county_name") or "",
        "capacity": float(p.get("capacity") or 0),
        "state": "UT",
        "state_fips": "49",
        "source": "solarsense",
        "inference_capable": True,
        "pm25_source": "epa",
        "pm25_monitor_name": p.get("site_name"),
        "pm25_distance_km": 0.0,
        "year_online": None,
        "case_id": None,
        "eia_id": None,
        "tech": "PV",
        "note": "Full MLP/SRI inference (on-site EPA county/site metadata).",
    }


def _uspvdb_row(s: dict[str, Any], aq: dict[str, Any]) -> dict[str, Any]:
    case_id = s.get("case_id")
    capacity = float(s.get("capacity_ac_mw") or 0)
    if capacity <= 0:
        capacity = float(s.get("capacity_dc_mw") or 0)

    return {
        "panel_id": f"uspvdb-{case_id}",
        "site_name": s.get("name") or f"USPVDB {case_id}",
        "latitude": float(s["latitude"]),
        "longitude": float(s["longitude"]),
        "county": aq.get("county"),
        "site": aq.get("site"),
        "county_name": s.get("county") or "",
        "capacity": capacity,
        "state": s.get("state") or "",
        "state_fips": aq.get("state_fips"),
        "source": "uspvdb",
        "inference_capable": True,
        "pm25_source": aq.get("pm25_source"),
        "pm25_monitor_name": aq.get("pm25_monitor_name"),
        "pm25_distance_km": aq.get("pm25_distance_km"),
        "year_online": s.get("year_online"),
        "case_id": case_id,
        "eia_id": s.get("eia_id"),
        "tech": s.get("tech") or "PV",
        "note": aq.get("note") or "",
    }


_INV_CACHE: dict[str, Any] | None = None
_INV_CACHE_TS: float = 0.0
_INV_TTL_SEC = 3600.0


def build_panel_inventory(force: bool = False) -> dict[str, Any]:
    """Return merged inventory for /api/panels (cached in-process)."""
    import time

    global _INV_CACHE, _INV_CACHE_TS
    now = time.time()
    if (
        not force
        and _INV_CACHE is not None
        and (now - _INV_CACHE_TS) < _INV_TTL_SEC
    ):
        return _INV_CACHE

    utah = [_solarsense_row(p) for p in load_panels()]
    utah_coords = [(p["latitude"], p["longitude"]) for p in utah]

    uspvdb_error = None
    aq_error = None
    western: list[dict[str, Any]] = []
    epa_nearest_count = 0
    openmeteo_count = 0

    monitors: list[dict[str, Any]] = []
    try:
        monitors = fetch_western_pm25_monitors()
    except Exception as exc:
        aq_error = f"EPA monitor catalog unavailable ({exc}); using Open-Meteo only."
        monitors = []

    try:
        western_raw = fetch_solar_projects("ALL")
        for s in western_raw:
            lat, lon = float(s["latitude"]), float(s["longitude"])
            near_utah = any(
                _haversine_km(lat, lon, ulat, ulon) <= MATCH_KM
                for ulat, ulon in utah_coords
            )
            if near_utah:
                continue

            aq = resolve_pm25_source(lat, lon, monitors=monitors, max_km=MAX_EPA_DISTANCE_KM)
            if aq.get("pm25_source") == "epa_nearest":
                epa_nearest_count += 1
            else:
                openmeteo_count += 1
            western.append(_uspvdb_row(s, aq))
    except UspvdbError as exc:
        uspvdb_error = str(exc)
    except Exception as exc:
        uspvdb_error = str(exc)

    panels = utah + western
    inv = {
        "panels": panels,
        "total": len(panels),
        "solarsense_count": len(utah),
        "uspvdb_count": len(western),
        "inference_capable_count": sum(1 for p in panels if p.get("inference_capable")),
        "pm25_epa_nearest_count": epa_nearest_count,
        "pm25_openmeteo_count": openmeteo_count,
        "pm25_monitor_count": len(monitors),
        "pm25_max_epa_distance_km": MAX_EPA_DISTANCE_KM,
        "coverage": (
            "Western US USGS USPVDB "
            f"({', '.join(WESTERN_STATE_CODES)}) plus Utah EPA monitoring sites"
        ),
        "coverage_note": (
            "Not full CONUS — FireWatch/USPVDB inventory used here is Western US only. "
            "MLP/SRI inference uses NASA POWER weather + PM2.5 from the nearest EPA "
            f"AQS monitor within {int(MAX_EPA_DISTANCE_KM)} km when available, otherwise "
            "Open-Meteo air-quality by lat/lon. Capacity for nominal scaling comes from "
            "USPVDB (AC MW). No fake EPA IDs are invented."
        ),
        "uspvdb_error": uspvdb_error,
        "aq_error": aq_error,
    }
    _INV_CACHE = inv
    _INV_CACHE_TS = now
    return inv


def find_panel(panel_id: str) -> dict[str, Any] | None:
    inv = build_panel_inventory()
    return next((p for p in inv["panels"] if p["panel_id"] == panel_id), None)


def clear_inventory_cache() -> None:
    global _INV_CACHE, _INV_CACHE_TS
    _INV_CACHE = None
    _INV_CACHE_TS = 0.0
