import glob, json
import numpy as np
import pandas as pd

csv_matches = glob.glob(r"..\**\*telangana*.csv", recursive=True)
if csv_matches:
    base_df = pd.read_csv(csv_matches[0])
else:
    raw = open(r"..\mobile-app\www\data.js", encoding="utf-8").read()
    base_df = pd.DataFrame(json.loads(raw.split("=", 1)[1].strip().rstrip(";")))

base_df = base_df.drop(columns=[c for c in ["system:index", ".geo"] if c in base_df.columns])
for col in ["latitude", "longitude", "ndwi_mean", "turbidity_index", "water_coverage_pct"]:
    base_df[col] = pd.to_numeric(base_df[col], errors="coerce")
base_df = base_df.dropna(subset=["district"]).reset_index(drop=True)

rng = np.random.default_rng(2026)
months = pd.date_range("2023-12-01", periods=36, freq="MS")
records = []

for idx_d, d in base_df.iterrows():
    dist = str(d["district"]).strip()
    lat = float(d["latitude"]) if pd.notna(d["latitude"]) else 17.9
    lon = float(d["longitude"]) if pd.notna(d["longitude"]) else 79.1
    b_ndwi = float(d["ndwi_mean"]) if pd.notna(d["ndwi_mean"]) else -0.45
    b_turb = float(d["turbidity_index"]) if pd.notna(d["turbidity_index"]) else 1.05
    b_water = float(d["water_coverage_pct"]) if pd.notna(d["water_coverage_pct"]) else 1.5

    # District-specific structural sensitivity (urban runoff vs agricultural/reservoir districts)
    urban_factor = 1.25 if dist.lower() in {"hyderabad", "medchal-malkajgiri", "rangareddy", "sangareddy", "warangal"} else 0.92
    reservoir_factor = 1.18 if dist.lower() in {"nalgonda", "khammam", "bhadradri kothagudem", "mahabubnagar", "karimnagar", "nizamabad"} else 0.95

    prev_wqi = None
    prev_turb = None
    prev_water = None

    for m_idx, dt in enumerate(months):
        m = dt.month
        monsoon = np.exp(-((m - 7.5) ** 2) / 3.0)
        summer = np.exp(-((m - 4.5) ** 2) / 3.4)
        trend_drift = (m_idx / 36.0) * 0.04

        rainfall_mm = max(1.0, (255.0 * monsoon * reservoir_factor) + 16.0 + rng.normal(0, 24.0))
        temp_c = 24.8 + 8.8 * summer - 3.4 * monsoon + rng.normal(0, 1.0)
        evap_mm = max(15.0, 4.2 * temp_c + 28.0 * summer - 18.0 * monsoon + rng.normal(0, 8.0))
        pollution_idx = np.clip((44.0 * urban_factor) + 15.0 * summer - 7.5 * monsoon + rng.normal(0, 6.5), 12.0, 98.0)

        # Inject realistic extreme events (flash runoff / dry spell spikes) ~8% of records
        is_anomaly = int(rng.random() < 0.08)
        anomaly_boost = rng.choice([-1, 1]) * rng.uniform(0.08, 0.18) if is_anomaly else 0.0

        water_pct = max(0.05, b_water * (0.62 + 0.92 * monsoon * reservoir_factor - 0.18 * summer + trend_drift + anomaly_boost) + rng.normal(0, 0.10))
        turb = max(0.40, b_turb + 0.13 * monsoon + 0.0035 * (pollution_idx - 45.0) + max(0.0, anomaly_boost * 0.6) + rng.normal(0, 0.025))
        ndwi = float(np.clip(b_ndwi + 0.15 * monsoon - 0.05 * summer + anomaly_boost * 0.35 + rng.normal(0, 0.02), -0.95, 0.95))
        ndmi_proxy = float(np.clip(ndwi * 0.78 + 0.08 * monsoon - 0.04 * summer + rng.normal(0, 0.015), -0.95, 0.95))
        reservoir_idx = float(np.clip(45.0 + water_pct * 11.5 + rainfall_mm * 0.08 - evap_mm * 0.12 + rng.normal(0, 3.0), 5.0, 100.0))

        wqi = 87.5 - max(0.0, (turb - 0.95) * 98.0) + min(12.5, water_pct * 2.5) + (ndwi + 0.4) * 17.0 - max(0.0, (pollution_idx - 50.0) * 0.26) - (4.5 if is_anomaly else 0.0)
        wqi = float(np.clip(round(wqi, 2), 15.0, 98.5))

        if prev_wqi is None:
            prev_wqi = wqi
        if prev_turb is None:
            prev_turb = turb
        if prev_water is None:
            prev_water = water_pct

        records.append({
            "district": dist,
            "year_month": dt.strftime("%Y-%m"),
            "month": m,
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "rainfall_mm": round(float(rainfall_mm), 2),
            "temp_c": round(float(temp_c), 2),
            "evap_mm": round(float(evap_mm), 2),
            "pollution_idx": round(float(pollution_idx), 2),
            "reservoir_idx": round(reservoir_idx, 2),
            "ndwi_mean": round(ndwi, 4),
            "ndmi_proxy": round(ndmi_proxy, 4),
            "turbidity_index": round(float(turb), 4),
            "water_coverage_pct": round(float(water_pct), 4),
            "anomaly_flag": is_anomaly,
            "prev_wqi": round(float(prev_wqi), 2),
            "prev_turb": round(float(prev_turb), 4),
            "prev_water": round(float(prev_water), 4),
            "wqi_score": wqi,
        })
        prev_wqi, prev_turb, prev_water = wqi, turb, water_pct

df = pd.DataFrame(records).sort_values(["district", "year_month"]).reset_index(drop=True)
# Add multi-horizon targets (+1M, +3M, +6M WQI)
for h in [1, 3, 6]:
    df[f"target_wqi_{h}m"] = df.groupby("district")["wqi_score"].shift(-h)

df = df.dropna(subset=["target_wqi_1m", "target_wqi_3m", "target_wqi_6m"]).reset_index(drop=True)
df.to_csv("telangana_upgraded_dataset.csv", index=False)
print(f"Saved telangana_upgraded_dataset.csv -> shape: {df.shape}, columns: {len(df.columns)}")
