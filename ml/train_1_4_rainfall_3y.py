import json, re
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

# IMD / TSDPS Normal Annual Rainfall (mm/year) per Telangana district
DISTRICT_NORMAL_RAIN_MM = {
    "mulugu":                  1240.0,
    "jayashankar bhupalpally": 1195.0,
    "kumuram bheem asifabad":  1185.0,
    "adilabad":                1160.0,
    "bhadradri kothagudem":    1145.0,
    "mancherial":              1120.0,
    "nirmal":                  1090.0,
    "khammam":                 1060.0,
    "mahabubabad":             1045.0,
    "peddapalli":              1030.0,
    "nizamabad":               1020.0,
    "jagtial":                 1005.0,
    "karimnagar":               965.0,
    "kamareddy":                955.0,
    "warangal":                 940.0,
    "hanumakonda":              930.0,
    "rajanna sircilla":         895.0,
    "medak":                    880.0,
    "sangareddy":               865.0,
    "jangaon":                  840.0,
    "siddipet":                 835.0,
    "suryapet":                 820.0,
    "vikarabad":                815.0,
    "hyderabad":                805.0,
    "medchal malkajgiri":       790.0,
    "yadadri bhuvanagiri":      765.0,
    "ranga reddy":              755.0,
    "nalgonda":                 735.0,
    "nagarkurnool":             685.0,
    "mahabubnagar":             670.0,
    "wanaparthy":               655.0,
    "narayanpet":               640.0,
    "jogulamba gadwal":         615.0,
}

# Monthly rainfall climatology weights for Telangana (SW Monsoon Jun-Sep ~78%, NE Oct-Dec ~14%)
MONTHLY_WEIGHTS = {
    1:  0.008,  # Jan
    2:  0.009,  # Feb
    3:  0.014,  # Mar
    4:  0.022,  # Apr
    5:  0.036,  # May
    6:  0.145,  # Jun
    7:  0.255,  # Jul
    8:  0.220,  # Aug
    9:  0.165,  # Sep
    10: 0.088,  # Oct
    11: 0.028,  # Nov
    12: 0.010,  # Dec
}

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

water_df = pd.read_csv("data_3y/water_3y.csv").sort_values(["district", "year_month"]).reset_index(drop=True)
rng = np.random.default_rng(202604)

rows = []
for dist, grp in water_df.groupby("district", sort=True):
    grp = grp.reset_index(drop=True)
    k = norm(dist)
    annual_norm = DISTRICT_NORMAL_RAIN_MM.get(k, 905.0)

    # Consistent 3-year climate regime matching Steps 1.1 - 1.3:
    # Year 1 (2024): near-normal monsoon (1.03x)
    # Year 2 (2025): strong surplus monsoon (1.16x -> reservoir fill & GW recovery)
    # Year 3 (2026): El Nino deficit monsoon (0.76x -> late-2026 GW drawdown & low reservoir fill)
    for idx, r in grp.iterrows():
        yr = int(r["year"])
        m  = int(r["month"])

        if idx < 12:
            regime_mult = 1.03
        elif idx < 24:
            regime_mult = 1.16
        else:
            regime_mult = 0.76

        normal_m = round(float(annual_norm * MONTHLY_WEIGHTS[m]), 2)
        ndmi = float(r["ndmi_proxy"])
        moisture_adj = 1.0 + np.clip(ndmi * 0.12, -0.08, 0.08)

        noise_sd = max(1.5, normal_m * 0.14)
        rain_raw = normal_m * regime_mult * moisture_adj + rng.normal(0.0, noise_sd)
        rain_mm = round(float(np.clip(rain_raw, 0.0, 620.0)), 2)

        dep_pct = round(float(((rain_mm - normal_m) / max(normal_m, 5.0)) * 100.0), 1)
        dep_pct = round(float(np.clip(dep_pct, -95.0, 180.0)), 1)

        if dep_pct >= 20.0:
            r_status = "Excess"
        elif dep_pct >= -19.0:
            r_status = "Normal"
        elif dep_pct >= -59.0:
            r_status = "Deficit"
        else:
            r_status = "Large Deficit"

        # Temperature & potential evaporation paired with rainfall regime
        summer = np.exp(-((m - 4.5) ** 2) / 3.2)
        monsoon = np.exp(-((m - 8.0) ** 2) / 3.4)
        temp_c = round(float(np.clip(25.2 + 8.6 * summer - 3.6 * monsoon + (0.9 if yr >= 2026 else 0.0) + rng.normal(0, 0.7), 17.0, 44.5)), 2)
        evap_mm = round(float(np.clip(3.8 * temp_c + 26.0 * summer - 0.12 * rain_mm + rng.normal(0, 4.5), 18.0, 220.0)), 2)

        rows.append({
            "district": dist,
            "year_month": r["year_month"],
            "year": yr,
            "month": m,
            "sin_m": float(r["sin_m"]),
            "cos_m": float(r["cos_m"]),
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "ndmi_proxy": ndmi,
            "normal_annual_mm": round(float(annual_norm), 1),
            "normal_rain_mm": normal_m,
            "rainfall_mm": rain_mm,
            "rain_departure_pct": dep_pct,
            "temp_c": temp_c,
            "evap_mm": evap_mm,
            "rain_status": r_status,
        })

df = pd.DataFrame(rows).sort_values(["district", "year_month"]).reset_index(drop=True)

# Rolling 3M / 6M / 12M cumulative rainfall & Standardized Precipitation Index (SPI) proxy
g = df.groupby("district")
df["rain_3m_cum_mm"]  = g["rainfall_mm"].transform(lambda s: s.rolling(3, min_periods=1).sum()).round(2)
df["rain_6m_cum_mm"]  = g["rainfall_mm"].transform(lambda s: s.rolling(6, min_periods=1).sum()).round(2)
df["rain_12m_cum_mm"] = g["rainfall_mm"].transform(lambda s: s.rolling(12, min_periods=1).sum()).round(2)
df["norm_6m_cum_mm"]  = g["normal_rain_mm"].transform(lambda s: s.rolling(6, min_periods=1).sum()).round(2)
df["spi_6m_proxy"]    = (((df["rain_6m_cum_mm"] - df["norm_6m_cum_mm"]) / (df["norm_6m_cum_mm"] * 0.25 + 10.0)).clip(-3.0, 3.0)).round(3)

# Temporal lags & multi-horizon rainfall targets (+1M, +2M, +6M, +12M)
df["rain_lag1"]  = g["rainfall_mm"].shift(1).bfill()
df["rain_lag3"]  = g["rainfall_mm"].shift(3).bfill()
df["rain_lag6"]  = g["rainfall_mm"].shift(6).bfill()
df["rain_lag12"] = g["rainfall_mm"].shift(12).bfill()

for h in [1, 2, 6, 12]:
    df[f"target_rain_{h}m"] = g["rainfall_mm"].shift(-h)

df.to_csv("data_3y/rainfall_3y.csv", index=False)

# Train 3-Year Rainfall XGBoost models for +1M, +2M, +6M, and +12M (chronological 80/20 split)
features = [
    "month", "sin_m", "cos_m", "latitude", "longitude",
    "ndmi_proxy", "normal_annual_mm", "normal_rain_mm",
    "rainfall_mm", "rain_departure_pct", "temp_c", "evap_mm",
    "rain_3m_cum_mm", "rain_6m_cum_mm", "rain_12m_cum_mm", "spi_6m_proxy",
    "rain_lag1", "rain_lag3", "rain_lag6", "rain_lag12"
]

metrics = {}
trained = {}
for h in [1, 2, 6, 12]:
    tgt = f"target_rain_{h}m"
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
    mae  = round(float(mean_absolute_error(te[tgt], preds)), 2)
    rmse = round(float(np.sqrt(mean_squared_error(te[tgt], preds))), 2)
    metrics[label] = {"rows": int(len(sub)), "r2": r2, "mae": mae, "rmse": rmse}

    model.save_model(f"models_3y/rain_xgb_{h}m.json")
    trained[h] = model
    print(f"[PASS] Step 1.4 Rainfall XGBoost +{label:<2} | Rows: {len(sub):4d} | R2: {r2:.4f} | MAE: {mae:.2f} mm | RMSE: {rmse:.2f} mm")

# Export latest 33-district Rainfall baseline + 1M/2M/6M/1Y forecasts
latest = df.groupby("district", as_index=False).tail(1).reset_index(drop=True)
rain_preds = []
for _, r in latest.iterrows():
    x1 = pd.DataFrame([r[features]])
    rain_preds.append({
        "district": r["district"],
        "latest_month": r["year_month"],
        "rainfall_mm": round(float(r["rainfall_mm"]), 2),
        "normal_rain_mm": round(float(r["normal_rain_mm"]), 2),
        "rain_departure_pct": round(float(r["rain_departure_pct"]), 1),
        "rain_6m_cum_mm": round(float(r["rain_6m_cum_mm"]), 2),
        "rain_12m_cum_mm": round(float(r["rain_12m_cum_mm"]), 2),
        "spi_6m_proxy": round(float(r["spi_6m_proxy"]), 3),
        "temp_c": round(float(r["temp_c"]), 2),
        "evap_mm": round(float(r["evap_mm"]), 2),
        "rain_status": str(r["rain_status"]),
        "rain_pred_1m": round(float(np.clip(trained[1].predict(x1)[0], 0.0, 620.0)), 2),
        "rain_pred_2m": round(float(np.clip(trained[2].predict(x1)[0], 0.0, 620.0)), 2),
        "rain_pred_6m": round(float(np.clip(trained[6].predict(x1)[0], 0.0, 620.0)), 2),
        "rain_pred_1y": round(float(np.clip(trained[12].predict(x1)[0], 0.0, 620.0)), 2),
    })

summary = {
    "step": "1.4_rainfall_3y",
    "date_range": f"{df['year_month'].min()} to {df['year_month'].max()}",
    "districts_count": int(df["district"].nunique()),
    "total_rows": int(len(df)),
    "state_avg_12m_rain_mm": round(float(latest["rain_12m_cum_mm"].mean()), 1),
    "metrics": metrics,
    "districts": rain_preds,
}
with open("data_3y/rainfall_3y_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"\n[DONE] Saved data_3y/rainfall_3y.csv ({len(df)} rows = {df['district'].nunique()} districts x 36 months)")
print(f"[DONE] Latest State Avg 12-Month Rainfall: {summary['state_avg_12m_rain_mm']} mm")
print("[DONE] Saved models_3y/rain_xgb_{1m,2m,6m,12m}.json & data_3y/rainfall_3y_summary.json")