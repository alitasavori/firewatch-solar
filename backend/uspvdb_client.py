"""Fetch large-scale solar PV facilities from USGS USPVDB (Western US)."""
from urllib.parse import urlencode
import json
import os
from datetime import datetime, timedelta

import httpx

USPVDB_BASE = "https://energy.usgs.gov/api/uspvdb/v1/projects"
CACHE_FILE = "uspvdb_western_cache.json"
CACHE_MAX_AGE_HOURS = 24

WESTERN_STATE_CODES = (
    "AZ", "CA", "CO", "ID", "MT", "NV", "NM", "OR", "UT", "WA", "WY"
)


class UspvdbError(Exception):
    pass


def _state_filter_param(state: str) -> str:
    code = state.upper()
    if code == "ALL":
        joined = ",".join(WESTERN_STATE_CODES)
        return f"p_state=in.({joined})"
    return f"p_state=eq.{code}"


def _cache_fresh() -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    return datetime.now() - mtime < timedelta(hours=CACHE_MAX_AGE_HOURS)


def _load_cache() -> list | None:
    if not _cache_fresh():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "sites" in data:
            return data["sites"]
        if isinstance(data, list):
            return data
    except Exception:
        return None
    return None


def _save_cache(sites: list) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "fetched_at": datetime.utcnow().isoformat() + "Z",
                "coverage": "Western US (AZ CA CO ID MT NV NM OR UT WA WY)",
                "total": len(sites),
                "sites": sites,
            },
            f,
        )


def fetch_solar_projects(state: str = "ALL", use_cache: bool = True) -> list:
    """Retrieve solar facilities for a state or all Western US states."""
    if use_cache:
        cached = _load_cache()
        if cached is not None and state.upper() == "ALL":
            return cached

    filter_param = _state_filter_param(state)
    select = "case_id,eia_id,p_name,p_state,p_county,ylat,xlong,p_cap_ac,p_cap_dc,p_year,p_axis,p_tech_pri"
    query = f"{filter_param}&{urlencode({'select': select})}"
    url = f"{USPVDB_BASE}?{query}"

    with httpx.Client(timeout=90.0) as client:
        response = client.get(url)

    if response.status_code != 200:
        raise UspvdbError(f"USPVDB error ({response.status_code}): {response.text[:200]}")

    raw = response.json()
    if not isinstance(raw, list):
        raise UspvdbError("Unexpected USPVDB response format")

    sites = []
    for row in raw:
        lat = row.get("ylat")
        lon = row.get("xlong")
        if lat is None or lon is None:
            continue
        sites.append({
            "case_id": row.get("case_id"),
            "eia_id": row.get("eia_id"),
            "name": row.get("p_name") or "Unknown",
            "state": row.get("p_state") or "",
            "county": row.get("p_county") or "",
            "latitude": float(lat),
            "longitude": float(lon),
            "capacity_ac_mw": float(row.get("p_cap_ac") or 0),
            "capacity_dc_mw": float(row.get("p_cap_dc") or 0),
            "year_online": row.get("p_year"),
            "axis_type": row.get("p_axis") or "",
            "tech": row.get("p_tech_pri") or "PV",
        })

    if state.upper() == "ALL":
        _save_cache(sites)

    return sites
