# inference_function.py

from concurrent.futures import ThreadPoolExecutor

from MLPRegressor import MLPRegressor
import torch
import joblib
import numpy as np
from datetime import datetime, timedelta

from api_fetch import (
    get_weather_data,
    get_pm25_data,
    get_pm25_data_openmeteo,
    get_final_df,
)

MODEL_PATH = "pv_mlp_model.pt"
SCALER_PATH = "scaler_mlp.pkl"

# --------------------------------------------
# Load model + scaler once
# --------------------------------------------
model = MLPRegressor(input_dim=30, hidden_dim=64)

model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
model.eval()
scaler = joblib.load(SCALER_PATH)


def parse_yyyymmdd(s):
    return datetime.strptime(s, "%Y%m%d").date()


def _fetch_pm25(panel, start_yyyymmdd, end_yyyymmdd):
    """Resolve PM2.5 via EPA (site IDs) or Open-Meteo (lat/lon)."""
    source = (panel.get("pm25_source") or "epa").lower()
    lat = panel["latitude"]
    lon = panel["longitude"]

    if source == "openmeteo" or not panel.get("county") or not panel.get("site"):
        return get_pm25_data_openmeteo(start_yyyymmdd, end_yyyymmdd, lat, lon)

    state = panel.get("state_fips") or panel.get("state_code") or "49"
    return get_pm25_data(
        start_yyyymmdd,
        end_yyyymmdd,
        panel["county"],
        panel["site"],
        state=state,
    )


# ------------------------------------------------------------
# MAIN INFERENCE ENGINE (with 4-day lookback)
# ------------------------------------------------------------
def run_inference(panel, start_date, end_date):
    """
    Returns predictions for the EXACT requested window [start_date, end_date],
    but uses 4 days of extension before start_date so ALL days have valid
    MLP predictions (no leading None values).

    Example:
        Requested → 20250701–20250730
        Model Input → 20250627–20250730
        Output → predictions ONLY for 7/1–7/30
    """

    # Parse user range
    start_dt = parse_yyyymmdd(start_date)
    end_dt = parse_yyyymmdd(end_date)

    # Extend start backwards by 4 days for 5-day windowing
    extended_start = start_dt - timedelta(days=4)
    extended_start_s = extended_start.strftime("%Y%m%d")

    # Compute total lengths
    requested_days = (end_dt - start_dt).days + 1

    # Extract panel metadata
    latitude = panel["latitude"]
    longitude = panel["longitude"]
    capacity = float(panel.get("capacity") or 0)
    if capacity <= 0:
        capacity = 1.5  # safe default MW if missing

    nominal = capacity * 11  # scale factor used in training

    # --------------------------------------------------------
    # Fetch extended weather + PM2.5 in parallel
    # --------------------------------------------------------
    with ThreadPoolExecutor(max_workers=2) as pool:
        weather_fut = pool.submit(
            get_weather_data,
            extended_start_s,
            end_date,
            latitude,
            longitude,
        )
        pm25_fut = pool.submit(_fetch_pm25, panel, extended_start_s, end_date)
        weather = weather_fut.result()
        pm25 = pm25_fut.result()

    df = get_final_df(weather, pm25)

    # df now contains (extended_days) rows
    mlp_input = df.to_numpy(dtype=np.float64)
    n = len(mlp_input)

    # --------------------------------------------------------
    # Batched sliding windows of size 5 → (N, 30) for the MLP
    # --------------------------------------------------------
    windows = np.stack(
        [mlp_input[i : i + 5].reshape(-1) for i in range(n - 4)],
        axis=0,
    )

    pm25_all = mlp_input[:, -1]
    max_pm = max(float(pm25_all.max()), 1.0)
    pm25_last = windows[:, -1]  # PM2.5 of last day in each window

    X_scaled = scaler.transform(windows)
    with torch.no_grad():
        raw_pred = (
            model(torch.tensor(X_scaled, dtype=torch.float32))
            .cpu()
            .numpy()
            .reshape(-1)
        )

    mlp_pred = nominal * raw_pred
    # Deterministic baseline (was np.random per day — broke cache stability).
    rand_factor = 0.2
    baseline = mlp_pred * (1.0 + rand_factor * (pm25_last / max_pm))
    baseline = np.maximum(baseline, mlp_pred * 1.01)

    preds = [None] * n
    for i in range(len(windows)):
        preds[i + 4] = (float(mlp_pred[i]), float(baseline[i]))

    # --------------------------------------------------------
    # Drop the first 4 prep-only days
    # --------------------------------------------------------
    start_idx = 4
    end_idx = start_idx + requested_days

    df_requested = df.iloc[start_idx:end_idx]
    preds_requested = preds[start_idx:end_idx]

    # Sanity check: should match requested_days
    assert len(df_requested) == requested_days, "Prediction slicing mismatch"

    # --------------------------------------------------------
    # Build final results for user range
    # --------------------------------------------------------
    results = []
    for offset, (feat, pred_pair) in enumerate(zip(df_requested.values, preds_requested)):
        date = start_dt + timedelta(days=offset)
        date_iso = date.strftime("%Y-%m-%d")

        row = {
            "date": date_iso,
            "ALLSKY_KT": float(feat[0]),
            "PRECTOTCORR": float(feat[1]),
            "T2M": float(feat[2]),
            "WS10M": float(feat[3]),
            "WS50M": float(feat[4]),
            "PM25": float(feat[5]),
            "lstm_pred": float(pred_pair[0]) if pred_pair else None,
            "baseline": float(pred_pair[1]) if pred_pair else None,
        }

        results.append(row)

    return results
