# backend/sri.py

import numpy as np
import pandas as pd

def compute_daily_sri_hsu(pm25_series, precip_series, init_sri=1.0, cleaning_threshold=1.0,
                           v_settle=0.09, k_optical=0.05):
    """
    Simplified daily HSU-like soiling model.
    Inputs:
      pm25_series : iterable of PM2.5 values [µg/m³]
      precip_series : iterable of precipitation [mm/day]
      init_sri : initial soiling ratio (1.0 = perfectly clean)
      cleaning_threshold : rainfall (mm) needed to reset to clean
      v_settle : settling velocity (m/s) for PM2.5
      k_optical : optical attenuation coefficient used in e^{-k*M}
    Returns:
      pandas.DataFrame with columns [day, pm25, precip, dep_mass_gm2, cum_mass, SRI]
    """

    n = len(pm25_series)
    pm25_gm3 = np.array(pm25_series, dtype=float) * 1e-6  # µg/m³ → g/m³
    precip_mm = np.array(precip_series, dtype=float)
    sec_per_day = 86400.0

    dep_mass = v_settle * pm25_gm3 * sec_per_day  # g/m²/day
    cum_mass = np.zeros(n)
    sri = np.zeros(n)

    # initial condition
    running_mass = ( -np.log(init_sri) / max(k_optical,1e-9) )  # invert e^{-kM} = SRI
    for i in range(n):
        # accumulate
        running_mass += dep_mass[i]

        # check cleaning threshold
        if precip_mm[i] >= cleaning_threshold:
            running_mass = 0.0  # full cleaning event

        cum_mass[i] = running_mass
        sri[i] = np.exp(-k_optical * running_mass)

    return pd.DataFrame({
        "day": np.arange(1, n+1),
        "pm25": pm25_series,
        "precip_mm": precip_series,
        "dep_mass_gm2": dep_mass,
        "cum_mass_gm2": cum_mass,
        "SRI": sri
    })
