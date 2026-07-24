from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from api_fetch_wrapper import fetch_data_panel, compute_sri_dict
from panels_inventory import build_panel_inventory, find_panel, clear_inventory_cache
import os

app = FastAPI(
    title="FireWatch Solar",
    description="PV smoke-impact forecasting (MLP/SRI) with Western US PV map inventory",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "solarsense-firewatch-shell"}


@app.get("/api/panel/sri")
def get_sri(site: str, start_date: str, end_date: str):
    panel = find_panel(site)
    if panel is None:
        raise HTTPException(status_code=404, detail=f"Panel with site '{site}' not found")

    if not panel.get("inference_capable"):
        raise HTTPException(
            status_code=422,
            detail=(
                "SRI/MLP inference unavailable for this site — no PM2.5 source could "
                "be resolved (nearest EPA monitor or Open-Meteo)."
            ),
        )

    try:
        return compute_sri_dict(panel, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/panel/data")
def get_data_panel(site: str, start_date: str, end_date: str):
    if int(start_date) > 20250701:
        raise HTTPException(
            status_code=400,
            detail="Invalid date, please choose a date earlier than July 2, 2025.",
        )
    if int(start_date) < 20170101:
        raise HTTPException(
            status_code=400,
            detail="Invalid date, please choose a date later than December 31, 2016.",
        )

    panel = find_panel(site)
    if panel is None:
        raise HTTPException(status_code=404, detail=f"Panel with site '{site}' not found")

    if not panel.get("inference_capable"):
        raise HTTPException(
            status_code=422,
            detail=(
                "Generation / weather inference unavailable — no PM2.5 source could "
                "be resolved for this plant."
            ),
        )

    try:
        return fetch_data_panel(site, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/panels")
def get_all_panels():
    """Merged SolarSense Utah + Western US USPVDB inventory (list of panels)."""
    inv = build_panel_inventory()
    # Frontend expects an array (SolarSense parity). Metadata on separate route.
    return inv["panels"]


@app.get("/api/panels/meta")
def get_panels_meta():
    inv = build_panel_inventory()
    # Do not mutate the in-process inventory cache.
    return {k: v for k, v in inv.items() if k != "panels"}


@app.delete("/api/cache/reset")
def reset_cache():
    removed = []
    for name in (
        "weather_cache.json",
        "uspvdb_western_cache.json",
        "epa_pm25_monitors_cache.json",
        "panel_inventory_cache.json",
    ):
        if os.path.exists(name):
            os.remove(name)
            removed.append(name)
    clear_inventory_cache()
    if removed:
        return {"status": "cache cleared", "removed": removed}
    return {"status": "no cache found", "inventory_cleared": True}
