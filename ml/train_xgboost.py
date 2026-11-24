import glob, os, json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error
import xgboost as xgb

# 1. Load real 33-district Telangana CSV (or fallback to packed mobile data.js)
csv_matches = glob.glob(r"..\**\*telangana*.csv", recursive=True)
if csv_matches:
    base_df = pd.read_csv(csv_matches[0])
    print("Loaded base CSV:", csv_matches[0])
else:
    js_path = r"..\mobile-app\www\data.js"
    raw = open(js_path, encoding="utf-8").read()
    json_str = raw.split("=", 1)[1].strip().rstrip(";")
    base_df = pd.DataFrame(json.loads(json_str))
    print("Loaded base data from mobile-app/www/data.js")

base_df = base_df.drop(columns=[c for c in ["system:index", ".geo"] if c in base_df.columns])
for col in ["latitude", "longitude", "ndwi_mean", "turbidity_index", "water_coverage_pct"]:
    base_df[col] = pd.to_numeric(base_df[col], errors="coerce")
base_df = base_df.dropna(subset=["district"]).reset_index(drop=True)

# 2. Build 36-month realistic time-series anchored to each district's Sentinel-2 baseline
rng = np.random.default_rng(42)
rows = []
months = pd.date_range("2023-12-01", periods=36, freq="MS")

for _, d in base_df.iterrows():
    b_ndwi = float(d.get("ndwi_mean") if pd.notna(d.get("ndwi_mean")) else -0.45)
    b_turb = float(d.get("turbidity_index") if pd.notna(d.get("turbidity_index")) else 1.05)
    b_water = float(d.get("water_coverage_pct") if pd.notna(d.get("water_coverage_pct")) else 1.5)
    lat = float(d.get("latitude") if pd.notna(d.get("latitude")) else 17.9)
    lon = float(d.get("longitude") if pd.notna(d.get("longitude")) else 79.1)

    for idx, dt in enumerate(months):
        m = dt.month
        monsoon = np.exp(-((m - 7.5) ** 2) / 3.2)
        summer = np.exp(-((m - 4.5) ** 2) / 3.5)

        rainfall_mm = max(2.0, 240.0 * monsoon + 18.0 + rng.normal(0, 22.0))
        temp_c = 24.5 + 8.5 * summer - 3.2 * monsoon + rng.normal(0, 1.1)
        pollution_idx = np.clip(42.0 + 14.0 * summer - 8.0 * monsoon + rng.normal(0, 6.0), 10, 95)

        water_pct = max(0.05, b_water * (0.65 + 0.85 * monsoon - 0.15 * summer) + rng.normal(0, 0.12))
        turb = max(0.45, b_turb + 0.12 * monsoon + 0.003 * (pollution_idx - 45) + rng.normal(0, 0.03))
        ndwi = float(np.clip(b_ndwi + 0.14 * monsoon - 0.05 * summer + rng.normal(0, 0.025), -0.95, 0.95))

        # Target Water Quality Index (WQI 0-100)
        wqi = 86.0 - max(0.0, (turb - 0.95) * 95.0) + min(12.0, water_pct * 2.4) + (ndwi + 0.4) * 18.0 - max(0.0, (pollution_idx - 50) * 0.25)
        wqi = float(np.clip(round(wqi, 2), 15.0, 98.0))

        rows.append({
            "district": d["district"],
            "year_month": dt.strftime("%Y-%m"),
            "month": m,
            "latitude": lat,
            "longitude": lon,
            "rainfall_mm": round(float(rainfall_mm), 2),
            "temp_c": round(float(temp_c), 2),
            "pollution_idx": round(float(pollution_idx), 2),
            "ndwi_mean": round(ndwi, 4),
            "turbidity_index": round(float(turb), 4),
            "water_coverage_pct": round(float(water_pct), 4),
            "wqi_score": wqi,
        })

df = pd.DataFrame(rows)
df = df.sort_values(["district", "year_month"]).reset_index(drop=True)
df["prev_wqi"] = df.groupby("district")["wqi_score"].shift(1).bfill()
df["prev_turb"] = df.groupby("district")["turbidity_index"].shift(1).bfill()
df.to_csv("telangana_36m_timeseries.csv", index=False)

features = ["month", "latitude", "longitude", "rainfall_mm", "temp_c", "pollution_idx", "ndwi_mean", "turbidity_index", "water_coverage_pct", "prev_wqi", "prev_turb"]
X = df[features]
y = df["wqi_score"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = xgb.XGBRegressor(
    n_estimators=220,
    max_depth=5,
    learning_rate=0.06,
    subsample=0.85,
    colsample_bytree=0.85,
    random_state=42,
)
model.fit(X_train, y_train)
preds = model.predict(X_test)

r2 = r2_score(y_test, preds)
mae = mean_absolute_error(y_test, preds)
rmse = root_mean_squared_error(y_test, preds)

model.save_model("aquatwin_xgb.json")
imp = pd.Series(model.feature_importances_, index=features).sort_values(ascending=False)

print(f"Dataset saved: telangana_36m_timeseries.csv ({len(df)} rows)")
print(f"XGBoost Test R2: {r2:.4f} | MAE: {mae:.3f} | RMSE: {rmse:.3f}")
print("Top 4 Important Features:")
for k, v in imp.head(4).items():
    print(f"  - {k}: {v:.3f}")
