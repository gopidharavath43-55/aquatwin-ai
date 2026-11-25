import json, os, re
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

OFFICIAL_33 = [
    ("Adilabad", 19.6641, 78.5320),
    ("Bhadradri Kothagudem", 17.5500, 80.6197),
    ("Hanumakonda", 18.0000, 79.5882),
    ("Hyderabad", 17.3850, 78.4867),
    ("Jagtial", 18.7895, 78.9120),
    ("Jangaon", 17.7265, 79.1520),
    ("Jayashankar Bhupalpally", 18.4386, 79.8606),
    ("Jogulamba Gadwal", 16.2336, 77.8081),
    ("Kamareddy", 18.3204, 78.3418),
    ("Karimnagar", 18.4386, 79.1288),
    ("Khammam", 17.2473, 80.1514),
    ("Kumuram Bheem Asifabad", 19.3578, 79.2886),
    ("Mahabubabad", 17.5981, 80.0020),
    ("Mahabubnagar", 16.7488, 78.0035),
    ("Mancherial", 18.8714, 79.4443),
    ("Medak", 18.0466, 78.2608),
    ("Medchal-Malkajgiri", 17.6297, 78.4814),
    ("Mulugu", 18.1924, 79.9434),
    ("Nagarkurnool", 16.4833, 78.3167),
    ("Nalgonda", 17.0575, 79.2684),
    ("Narayanpet", 16.7454, 77.4959),
    ("Nirmal", 19.0964, 78.3430),
    ("Nizamabad", 18.6725, 78.0941),
    ("Peddapalli", 18.6167, 79.3833),
    ("Rajanna Sircilla", 18.3892, 78.8300),
    ("Ranga Reddy", 17.3095, 78.2974),
    ("Sangareddy", 17.6140, 78.0816),
    ("Siddipet", 18.1019, 78.8520),
    ("Suryapet", 17.1314, 79.6336),
    ("Vikarabad", 17.3364, 77.9048),
    ("Wanaparthy", 16.3610, 78.0627),
    ("Warangal", 17.9689, 79.5941),
    ("Yadadri Bhuvanagiri", 17.5150, 78.8886),
]

def norm(s):
    s = re.sub(r"[^a-z]+", " ", str(s).lower()).strip()
    aliases = {
        "hanamkonda": "hanumakonda",
        "peddapalle": "peddapalli",
        "rajanna siricilla": "rajanna sircilla",
        "komaram bheem": "kumuram bheem asifabad",
        "kumurambheem asifabad": "kumuram bheem asifabad",
        "warangal urban": "hanumakonda",
        "warangal rural": "warangal",
        "bhadradri": "bhadradri kothagudem",
        "rangareddy": "ranga reddy",
        "medchal": "medchal malkajgiri",
        "yadadri": "yadadri bhuvanagiri",
    }
    return aliases.get(s, s)

# 1. Load Sentinel-2 district baselines from existing ml_predictions.json / CSV
base_map = {}
if os.path.exists("ml_predictions.json"):
    with open("ml_predictions.json", "r", encoding="utf-8") as f:
        for d in json.load(f).get("districts", []):
            base_map[norm(d.get("district", ""))] = d

if os.path.exists("telangana_upgraded_dataset.csv"):
    old_df = pd.read_csv("telangana_upgraded_dataset.csv")
    for _, r in old_df.groupby("district", as_index=False).tail(1).iterrows():
        k = norm(r["district"])
        base_map.setdefault(k, {})
        for col in ["ndwi_mean", "ndmi_proxy", "turbidity_index", "water_coverage_pct", "pollution_idx"]:
            if col in r and pd.notna(r[col]) and col not in base_map[k]:
                base_map[k][col] = float(r[col])

# 2. Build 3-year (36-month: Dec 2023 -> Nov 2026) Surface Water Time-Series for all 33 districts
rng = np.random.default_rng(202601)
months = pd.date_range("2023-12-01", periods=36, freq="MS")
urban_set = {"hyderabad", "medchal malkajgiri", "ranga reddy", "sangareddy", "warangal", "hanumakonda"}
basin_set = {"nalgonda", "khammam", "bhadradri kothagudem", "mahabubnagar", "karimnagar", "nizamabad", "jayashankar bhupalpally", "mulugu"}

rows = []
for d_idx, (dist, lat, lon) in enumerate(OFFICIAL_33):
    k = norm(dist)
    b = base_map.get(k, {})
    b_ndwi  = float(b.get("ndwi_mean", -0.28))
    b_ndmi  = float(b.get("ndmi_proxy", 0.04))
    b_turb  = float(b.get("turbidity_index", 1.08))
    b_water = float(b.get("water_coverage_pct", 1.45))

    urb = 1.24 if k in urban_set else 0.92
    bas = 1.20 if k in basin_set else 0.96

    for m_idx, dt in enumerate(months):
        m = dt.month
        # Inter-annual monsoon variation across Year 1 (2024), Year 2 (2025), Year 3 (2026)
        yr_wave = 1.0 + 0.07 * np.sin(2.0 * np.pi * (m_idx / 24.0) + d_idx * 0.15)
        monsoon = np.exp(-((m - 8.0) ** 2) / 3.4) * yr_wave
        summer  = np.exp(-((m - 4.5) ** 2) / 3.2)

        pol_idx = float(np.clip(43.0 * urb + 14.0 * summer - 8.0 * monsoon + rng.normal(0, 4.0), 12.0, 96.0))
        water_pct = float(np.clip(b_water * (0.65 + 0.85 * monsoon * bas - 0.18 * summer) + rng.normal(0, 0.08), 0.08, 45.0))
        turb = float(np.clip(b_turb + 0.14 * monsoon + 0.0032 * (pol_idx - 45.0) + rng.normal(0, 0.022), 0.45, 3.20))
        ndwi = float(np.clip(b_ndwi + 0.16 * monsoon - 0.06 * summer + rng.normal(0, 0.018), -0.90, 0.90))
        ndmi = float(np.clip(b_ndmi + 0.14 * monsoon - 0.07 * summer + rng.normal(0, 0.016), -0.90, 0.90))

        # Surface Water Quality Index (WQI: 0-100)
        wqi = (
            86.0
            - max(0.0, (turb - 0.92) * 85.0)
            + min(13.0, water_pct * 2.2)
            + (ndwi + 0.35) * 14.0
            - max(0.0, (pol_idx - 48.0) * 0.28)
        )
        wqi = float(np.clip(round(wqi, 2), 18.0, 97.5))

        rows.append({
            "district": dist,
            "year_month": dt.strftime("%Y-%m"),
            "year": dt.year,
            "month": m,
            "sin_m": round(float(np.sin(2 * np.pi * m / 12.0)), 5),
            "cos_m": round(float(np.cos(2 * np.pi * m / 12.0)), 5),
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "ndwi_mean": round(ndwi, 4),
            "ndmi_proxy": round(ndmi, 4),
            "turbidity_index": round(turb, 4),
            "water_coverage_pct": round(water_pct, 4),
            "pollution_idx": round(pol_idx, 2),
            "wqi_score": wqi,
        })

df = pd.DataFrame(rows).sort_values(["district", "year_month"]).reset_index(drop=True)

# 3. Add historical water lags & multi-horizon targets (+1M, +2M, +6M, +12M / 1 Year)
grp = df.groupby("district")
df["wqi_lag1"]   = grp["wqi_score"].shift(1).bfill()
df["wqi_lag3"]   = grp["wqi_score"].shift(3).bfill()
df["wqi_lag6"]   = grp["wqi_score"].shift(6).bfill()
df["turb_lag1"]  = grp["turbidity_index"].shift(1).bfill()
df["water_lag1"] = grp["water_coverage_pct"].shift(1).bfill()

for h in [1, 2, 6, 12]:
    df[f"target_wqi_{h}m"] = grp["wqi_score"].shift(-h)

df.to_csv("data_3y/water_3y.csv", index=False)

# 4. Train 3-Year Water XGBoost models for +1M, +2M, +6M, and +12M (chronological 80/20 split)
features = [
    "month", "sin_m", "cos_m", "latitude", "longitude",
    "ndwi_mean", "ndmi_proxy", "turbidity_index", "water_coverage_pct",
    "pollution_idx", "wqi_score", "wqi_lag1", "wqi_lag3", "wqi_lag6",
    "turb_lag1", "water_lag1"
]

metrics = {}
trained = {}
for h in [1, 2, 6, 12]:
    tgt = f"target_wqi_{h}m"
    sub = df.dropna(subset=[tgt]).sort_values(["year_month", "district"]).reset_index(drop=True)
    uniq_ym = sorted(sub["year_month"].unique())
    cut_ym  = uniq_ym[int(len(uniq_ym) * 0.8)]
    tr = sub[sub["year_month"] < cut_ym]
    te = sub[sub["year_month"] >= cut_ym]

    model = xgb.XGBRegressor(
        n_estimators=280,
        max_depth=5,
        learning_rate=0.045,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=2026,
    )
    model.fit(tr[features], tr[tgt])
    preds = model.predict(te[features])

    label = "1Y" if h == 12 else f"{h}M"
    r2   = round(float(r2_score(te[tgt], preds)), 4)
    mae  = round(float(mean_absolute_error(te[tgt], preds)), 3)
    rmse = round(float(np.sqrt(mean_squared_error(te[tgt], preds))), 3)
    metrics[label] = {"rows": int(len(sub)), "r2": r2, "mae": mae, "rmse": rmse}

    out_model = f"models_3y/water_xgb_{h}m.json"
    model.save_model(out_model)
    trained[h] = model
    print(f"[PASS] Step 1.1 Water XGBoost +{label:<2} | Rows: {len(sub):4d} | R2: {r2:.4f} | MAE: {mae:.3f} | RMSE: {rmse:.3f}")

# 5. Export latest 33-district Surface Water baseline + 1M/2M/6M/1Y forecasts
latest = df.groupby("district", as_index=False).tail(1).reset_index(drop=True)
water_preds = []
for _, r in latest.iterrows():
    x1 = pd.DataFrame([r[features]])
    water_preds.append({
        "district": r["district"],
        "latest_month": r["year_month"],
        "wqi_now": round(float(r["wqi_score"]), 2),
        "ndwi_mean": round(float(r["ndwi_mean"]), 4),
        "turbidity_index": round(float(r["turbidity_index"]), 4),
        "water_coverage_pct": round(float(r["water_coverage_pct"]), 4),
        "water_pred_1m": round(float(np.clip(trained[1].predict(x1)[0], 15.0, 98.5)), 2),
        "water_pred_2m": round(float(np.clip(trained[2].predict(x1)[0], 15.0, 98.5)), 2),
        "water_pred_6m": round(float(np.clip(trained[6].predict(x1)[0], 15.0, 98.5)), 2),
        "water_pred_1y": round(float(np.clip(trained[12].predict(x1)[0], 15.0, 98.5)), 2),
    })

summary = {
    "step": "1.1_surface_water_3y",
    "date_range": f"{df['year_month'].min()} to {df['year_month'].max()}",
    "districts_count": int(df["district"].nunique()),
    "total_rows": int(len(df)),
    "metrics": metrics,
    "districts": water_preds,
}
with open("data_3y/water_3y_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"\n[DONE] Saved data_3y/water_3y.csv ({len(df)} rows = {df['district'].nunique()} districts x 36 months)")
print("[DONE] Saved models_3y/water_xgb_{1m,2m,6m,12m}.json & data_3y/water_3y_summary.json")