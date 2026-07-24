import requests
import pandas as pd
from collections import defaultdict
from datetime import datetime


def fetch_api_data(api_url):
    try:
        response = requests.get(api_url, timeout=90)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None


def get_weather_data(start_date, end_date, latitude, longitude):
    weather_api_url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?start={start_date}&end={end_date}&latitude={latitude}&longitude={longitude}"
        "&community=re&parameters=ALLSKY_KT%2CPRECTOTCORR%2CT2M%2CWS10M%2CWS50M&header=true"
    )
    weather_data_json = fetch_api_data(weather_api_url)
    weather_data_dict = weather_data_json["properties"]["parameter"]
    weather_data_df = pd.DataFrame(weather_data_dict)
    return weather_data_df


def get_pm25_data(start_date, end_date, county, site, state="49"):
    """EPA AQS daily PM2.5 (88101) for a real state/county/site triple."""
    state_fips = str(state).zfill(2)
    county_fips = str(county).zfill(3)
    site_id = str(site).zfill(4)
    pm25_api_url = (
        "https://aqs.epa.gov/data/api/dailyData/bySite"
        f"?email=test@aqs.api&key=test&param=88101"
        f"&bdate={start_date}&edate={end_date}"
        f"&state={state_fips}&county={county_fips}&site={site_id}"
    )
    payload = fetch_api_data(pm25_api_url)
    if not payload:
        return pd.DataFrame(columns=["date_local", "max_arithmetic_mean"])

    pm25_data = payload.get("Data", []) or []
    merged = defaultdict(list)
    for entry in pm25_data:
        date = entry["date_local"]
        merged[date].append(entry)

    merged_data = []
    for date, entries in merged.items():
        valid_means = [
            e["arithmetic_mean"] for e in entries if e.get("arithmetic_mean") is not None
        ]
        if not valid_means:
            continue
        merged_data.append(
            {
                "date_local": date,
                "max_arithmetic_mean": max(valid_means),
            }
        )
    return pd.DataFrame(merged_data)


def get_pm25_data_openmeteo(start_date, end_date, latitude, longitude):
    """
    Daily PM2.5 from Open-Meteo air-quality API by lat/lon.
    Aggregates hourly pm2_5 to daily max (comparable to EPA max-of-means merge).
    Dates are YYYYMMDD (same as NASA POWER / EPA helpers).
    """
    start_iso = datetime.strptime(str(start_date), "%Y%m%d").strftime("%Y-%m-%d")
    end_iso = datetime.strptime(str(end_date), "%Y%m%d").strftime("%Y-%m-%d")
    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={latitude}&longitude={longitude}"
        f"&hourly=pm2_5&start_date={start_iso}&end_date={end_iso}"
        "&timezone=auto"
    )
    payload = fetch_api_data(url)
    if not payload or "hourly" not in payload:
        return pd.DataFrame(columns=["date_local", "max_arithmetic_mean"])

    times = payload["hourly"].get("time") or []
    values = payload["hourly"].get("pm2_5") or []
    by_day = defaultdict(list)
    for t, v in zip(times, values):
        if v is None:
            continue
        day = str(t)[:10]  # YYYY-MM-DD
        by_day[day].append(float(v))

    rows = [
        {"date_local": day, "max_arithmetic_mean": max(vals)}
        for day, vals in sorted(by_day.items())
        if vals
    ]
    return pd.DataFrame(rows)


def get_final_df(weather_df, pm25_df):
    """Align PM2.5 to NASA POWER weather dates (YYYYMMDD index)."""
    df = weather_df.copy()
    if pm25_df is None or len(pm25_df) == 0:
        df["PM25"] = 0.0
        return df

    pm = pm25_df.copy()
    # Normalize date keys to YYYYMMDD strings
    date_keys = []
    for d in pm["date_local"]:
        s = str(d).replace("-", "")[:8]
        date_keys.append(s)
    pm = pm.assign(_key=date_keys).set_index("_key")["max_arithmetic_mean"]

    weather_keys = [str(i).replace("-", "")[:8] for i in df.index]
    aligned = [float(pm[k]) if k in pm.index else float("nan") for k in weather_keys]
    series = pd.Series(aligned, index=df.index)
    # Fill gaps so MLP windows stay valid; prefer nearby days then 0
    series = series.ffill().bfill().fillna(0.0)
    df["PM25"] = series
    return df


if __name__ == "__main__":
    """
    Yellow Lake Wildfire:
    Started 09/28/2024
    Fire stopped 10/18/2024
    Contained 11/8/2024
    """
    start_date = "20240928"
    end_date = "20241008"

    fire_latitude = "40.4647097224075"
    fire_longitude = "-109.561471504638"
    fire_county = "047"
    fire_site = "1004"

    normal_latitude = "37.74743"
    normal_longitude = "-113.055525"
    normal_county = "021"
    normal_site = "0005"

    normal_weather = get_weather_data(start_date, end_date, normal_latitude, normal_longitude)
    normal_pm25 = get_pm25_data(start_date, end_date, normal_county, normal_site, state="49")
    normal_df = get_final_df(normal_weather, normal_pm25)

    fire_weather = get_weather_data(start_date, end_date, fire_latitude, fire_longitude)
    fire_pm25 = get_pm25_data(start_date, end_date, fire_county, fire_site, state="49")
    fire_df = get_final_df(fire_weather, fire_pm25)

    print("Normal Monitoring Station:")
    print(normal_df)
    print("Fire Monitoring Station")
    print(fire_df)

    om = get_pm25_data_openmeteo(start_date, end_date, 34.2158, -118.5004)
    print("Open-Meteo LA sample:")
    print(om.head())
