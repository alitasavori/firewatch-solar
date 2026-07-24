"""Merge SolarSense Utah EPA panels with FireWatch/USPVDB Western US PV units."""
from __future__ import annotations

import json
import math
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from api_fetch_wrapper import load_panels
from aq_monitors import MAX_EPA_DISTANCE_KM, fetch_western_pm25_monitors, resolve_pm25_source
from uspvdb_client import UspvdbError, fetch_solar_projects, WESTERN_STATE_CODES

# Match radius: if a USPVDB plant is this close to a SolarSense site, keep SolarSense.
MATCH_KM = 2.5

INVENTORY_CACHE_FILE = "panel_inventory_cache.json"
INVENTORY_DISK_TTL_HOURS = 24


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
_INV_LOCK = threading.Lock()
_ENRICH_STARTED = False


def _openmeteo_aq() -> dict[str, Any]:
    return {
        "pm25_source": "openmeteo",
        "state_fips": None,
        "county": None,
        "site": None,
        "pm25_monitor_name": None,
        "pm25_distance_km": None,
        "note": (
            "PM2.5 from Open-Meteo air-quality API (lat/lon proxy); "
            "EPA catalog not yet applied."
        ),
    }


def _meta_counts(panels: list[dict[str, Any]], monitors: list[dict[str, Any]]) -> dict[str, Any]:
    utah = [p for p in panels if p.get("source") == "solarsense"]
    western = [p for p in panels if p.get("source") != "solarsense"]
    return {
        "total": len(panels),
        "solarsense_count": len(utah),
        "uspvdb_count": len(western),
        "inference_capable_count": sum(1 for p in panels if p.get("inference_capable")),
        "pm25_epa_nearest_count": sum(
            1 for p in western if p.get("pm25_source") == "epa_nearest"
        ),
        "pm25_openmeteo_count": sum(
            1 for p in western if p.get("pm25_source") == "openmeteo"
        ),
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
    }


def _load_disk_inventory() -> dict[str, Any] | None:
    if not os.path.exists(INVENTORY_CACHE_FILE):
        return None
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(INVENTORY_CACHE_FILE))
        stale = datetime.now() - mtime >= timedelta(hours=INVENTORY_DISK_TTL_HOURS)
        with open(INVENTORY_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        panels = data.get("panels") if isinstance(data, dict) else None
        if not isinstance(panels, list) or not panels:
            return None
        inv = dict(data)
        if stale:
            inv["aq_error"] = (
                (inv.get("aq_error") or "")
                + (" " if inv.get("aq_error") else "")
                + "Serving disk inventory cache older than TTL; background refresh may update."
            ).strip()
        return inv
    except Exception:
        return None


def _save_disk_inventory(inv: dict[str, Any]) -> None:
    try:
        payload = dict(inv)
        payload["cached_at"] = datetime.utcnow().isoformat() + "Z"
        with open(INVENTORY_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as exc:
        print(f"[panels_inventory] disk cache write failed: {exc}")


def _set_mem_cache(inv: dict[str, Any]) -> dict[str, Any]:
    global _INV_CACHE, _INV_CACHE_TS
    _INV_CACHE = inv
    _INV_CACHE_TS = time.time()
    return inv


def _enrich_with_epa(inv: dict[str, Any]) -> dict[str, Any]:
    """Assign nearest EPA monitors when a local catalog is available (no remote wait)."""
    aq_error = None
    try:
        # Disk/memory only — never block the request path on EPA network I/O.
        monitors = fetch_western_pm25_monitors(use_cache=True, allow_remote=False)
    except Exception as exc:
        aq_error = f"EPA monitor catalog unavailable ({exc}); using Open-Meteo only."
        monitors = []

    if not monitors:
        meta = _meta_counts(inv["panels"], [])
        out = {**inv, **meta, "aq_error": aq_error or inv.get("aq_error")}
        return out

    panels: list[dict[str, Any]] = []
    for p in inv["panels"]:
        if p.get("source") != "uspvdb":
            panels.append(p)
            continue
        aq = resolve_pm25_source(
            float(p["latitude"]),
            float(p["longitude"]),
            monitors=monitors,
            max_km=MAX_EPA_DISTANCE_KM,
        )
        updated = dict(p)
        updated.update(
            {
                "county": aq.get("county"),
                "site": aq.get("site"),
                "state_fips": aq.get("state_fips"),
                "pm25_source": aq.get("pm25_source"),
                "pm25_monitor_name": aq.get("pm25_monitor_name"),
                "pm25_distance_km": aq.get("pm25_distance_km"),
                "note": aq.get("note") or "",
                "inference_capable": True,
            }
        )
        panels.append(updated)

    meta = _meta_counts(panels, monitors)
    out = {
        **inv,
        **meta,
        "panels": panels,
        "aq_error": aq_error,
    }
    return out


def _build_base_inventory() -> dict[str, Any]:
    """Build Utah + USPVDB rows quickly using caches; EPA enrichment is optional/lazy."""
    utah = [_solarsense_row(p) for p in load_panels()]
    utah_coords = [(p["latitude"], p["longitude"]) for p in utah]

    uspvdb_error = None
    western: list[dict[str, Any]] = []

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
            western.append(_uspvdb_row(s, _openmeteo_aq()))
    except UspvdbError as exc:
        uspvdb_error = str(exc)
    except Exception as exc:
        uspvdb_error = str(exc)

    panels = utah + western
    if not panels:
        # Last resort: serve whatever is on disk even if stale/empty build failed.
        disk = _load_disk_inventory()
        if disk and disk.get("panels"):
            disk = dict(disk)
            disk["uspvdb_error"] = uspvdb_error or disk.get("uspvdb_error")
            return disk
        raise RuntimeError(
            uspvdb_error or "Panel inventory empty (no Utah panels and USPVDB unavailable)."
        )

    inv = {
        "panels": panels,
        **_meta_counts(panels, []),
        "uspvdb_error": uspvdb_error,
        "aq_error": None,
    }
    return _enrich_with_epa(inv)


def _background_refresh() -> None:
    """Refresh EPA catalog remotely (if needed) and rebuild inventory off the request path."""
    global _ENRICH_STARTED
    try:
        try:
            fetch_western_pm25_monitors(use_cache=True, allow_remote=True)
        except Exception as exc:
            print(f"[panels_inventory] background EPA refresh skipped: {exc}")
        inv = _build_base_inventory()
        with _INV_LOCK:
            _set_mem_cache(inv)
            _save_disk_inventory(inv)
        print(f"[panels_inventory] background refresh complete: {inv.get('total')} sites")
    except Exception as exc:
        print(f"[panels_inventory] background refresh failed: {exc}")
    finally:
        _ENRICH_STARTED = False


def _ensure_background_refresh() -> None:
    global _ENRICH_STARTED
    with _INV_LOCK:
        if _ENRICH_STARTED:
            return
        _ENRICH_STARTED = True
    t = threading.Thread(target=_background_refresh, name="inventory-enrich", daemon=True)
    t.start()


def build_panel_inventory(force: bool = False) -> dict[str, Any]:
    """Return merged inventory for /api/panels (memory + disk cached; EPA never blocks)."""
    global _INV_CACHE, _INV_CACHE_TS

    now = time.time()
    if (
        not force
        and _INV_CACHE is not None
        and (now - _INV_CACHE_TS) < _INV_TTL_SEC
    ):
        return _INV_CACHE

    kick_refresh = False
    with _INV_LOCK:
        now = time.time()
        if (
            not force
            and _INV_CACHE is not None
            and (now - _INV_CACHE_TS) < _INV_TTL_SEC
        ):
            return _INV_CACHE

        if not force:
            disk = _load_disk_inventory()
            if disk is not None:
                # Prefer disk snapshot for instant startup; enrich/refresh in background.
                inv = _set_mem_cache(disk)
                kick_refresh = True
            else:
                inv = None
        else:
            inv = None

        if inv is None:
            inv = _build_base_inventory()
            _set_mem_cache(inv)
            _save_disk_inventory(inv)
            kick_refresh = True

    if kick_refresh:
        _ensure_background_refresh()
    return inv


def find_panel(panel_id: str) -> dict[str, Any] | None:
    inv = build_panel_inventory()
    return next((p for p in inv["panels"] if p["panel_id"] == panel_id), None)


def clear_inventory_cache() -> None:
    global _INV_CACHE, _INV_CACHE_TS
    with _INV_LOCK:
        _INV_CACHE = None
        _INV_CACHE_TS = 0.0
    if os.path.exists(INVENTORY_CACHE_FILE):
        try:
            os.remove(INVENTORY_CACHE_FILE)
        except OSError:
            pass
