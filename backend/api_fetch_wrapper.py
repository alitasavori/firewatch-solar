# api_fetch_wrapper.py

import json
import threading
from datetime import datetime, timedelta

from db import (
    get_panel_data,
    upsert_panel_days,
    load_lstm_cache,
    save_lstm_cache,
)
from inference_function import run_inference
from sri import compute_daily_sri_hsu

PANELS_FILE = "panels.json"

# In-flight inference locks so concurrent /data + /sri (or double-clicks)
# share one cold fetch instead of racing two NASA/EPA round-trips.
_INFERENCE_LOCKS: dict[tuple, threading.Lock] = {}
_INFERENCE_LOCKS_GUARD = threading.Lock()


def _inference_lock(panel_id: str, start_date: str, end_date: str) -> threading.Lock:
    key = (panel_id, start_date, end_date)
    with _INFERENCE_LOCKS_GUARD:
        lock = _INFERENCE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _INFERENCE_LOCKS[key] = lock
        return lock


def load_panels():
    with open(PANELS_FILE, "r") as f:
        return json.load(f)


def generate_dates(start, end):
    start_dt = datetime.strptime(start, "%Y%m%d").date()
    end_dt = datetime.strptime(end, "%Y%m%d").date()

    days = []
    cur = start_dt
    while cur <= end_dt:
        days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    return days


def _resolve_panel(site):
    """Prefer enriched inventory (Utah + USPVDB); fall back to panels.json."""
    try:
        from panels_inventory import find_panel

        panel = find_panel(site)
        if panel is not None:
            return panel
    except Exception:
        pass

    panels = load_panels()
    return next((p for p in panels if p["panel_id"] == site), None)


def _persist_inference(panel_id, date_list, full_rows):
    """Write raw weather/PM2.5 + prediction cache from one inference pass."""
    upsert_panel_days(panel_id, full_rows)
    simplified = [
        {
            "date": r["date"],
            "lstm_pred": r["lstm_pred"],
            "baseline": r["baseline"],
        }
        for r in full_rows
    ]
    save_lstm_cache(panel_id, date_list[0], date_list[-1], simplified)
    return simplified


# ------------------------------------------------------------
# FETCH PANEL DATA ENDPOINT LOGIC
# ------------------------------------------------------------
def fetch_data_panel(site, start_date, end_date):
    panel = _resolve_panel(site)

    if panel is None:
        return []

    panel_id = panel["panel_id"]
    date_list = generate_dates(start_date, end_date)

    raw = get_panel_data(panel_id, date_list[0], date_list[-1])
    raw_by_date = {r["date"]: r for r in raw}
    missing_raw = [d for d in date_list if d not in raw_by_date]
    lstm_cache = load_lstm_cache(panel_id, date_list[0], date_list[-1])

    if missing_raw or lstm_cache is None:
        lock = _inference_lock(panel_id, start_date, end_date)
        with lock:
            # Re-check after acquiring lock (another request may have filled caches).
            raw = get_panel_data(panel_id, date_list[0], date_list[-1])
            raw_by_date = {r["date"]: r for r in raw}
            missing_raw = [d for d in date_list if d not in raw_by_date]
            lstm_cache = load_lstm_cache(panel_id, date_list[0], date_list[-1])

            if missing_raw or lstm_cache is None:
                # ONE inference pass fills both raw + prediction caches.
                # Previously missing_raw and missing lstm each called run_inference
                # separately (~2× NASA POWER + PM2.5 latency on cold load).
                full_rows = run_inference(panel, start_date, end_date)
                lstm_cache = _persist_inference(panel_id, date_list, full_rows)
                raw = get_panel_data(panel_id, date_list[0], date_list[-1])
                raw_by_date = {r["date"]: r for r in raw}

    lstm_by_date = {r["date"]: r for r in lstm_cache}

    final = []
    for d in date_list:
        row = dict(raw_by_date[d])
        row.update(lstm_by_date[d])
        final.append(row)

    # Attach SRI so the frontend only needs /api/panel/data (no second round-trip).
    if final:
        sri_df = compute_daily_sri_hsu(
            [float(r.get("pm25") or 0) for r in final],
            [float(r.get("prectotcorr") or 0) for r in final],
        )
        for i, row in enumerate(final):
            row["SRI"] = float(sri_df["SRI"].iloc[i])

    return final


# ------------------------------------------------------------
# SRI ENDPOINT
# ------------------------------------------------------------
def compute_sri_dict(panel, start_date, end_date):
    rows = fetch_data_panel(panel["panel_id"], start_date, end_date)
    return [{"date": r["date"], "SRI": float(r["SRI"])} for r in rows]
