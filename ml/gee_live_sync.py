import json, os, re
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xgboost as xgb
import ee

IST = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(IST)
ym_now = now_ist.strftime("%Y-%m")

# 1. Connect to Google Earth Engine using saved Project ID
proj_id = ""
if os.path.exists("gee_project.txt"):
    with open("gee_project.txt", "r", encoding="utf-8-sig") as f:
        proj_id = f.read().strip()

if proj_id:
    ee.Initialize(project=proj_id)
else:
    ee.Initialize()

print(f"[{now_ist.strftime('%Y-%m-%d %H:%M IST')}] Connected to GEE (project: {proj_id or 'default'})")

# 2. Load current 33-district dataset
df = pd.read_csv("telangana_upgraded_dataset.csv").sort_values(["district", "year_month"]).reset_index(drop=True)
latest = df.groupby("district", as_index=False).tail(1).reset_index(drop=True)

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
    }
    return aliases.get(s, s)

# 3. Fetch latest cloud-free Sentinel-2 water metrics for all 33 districts in one batch
features = [
    ee.Feature(
        ee.Geometry.Point([float(r["longitude"]), float(r["latitude"])]).buffer(12000),
        {"district": str(r["district"])}
    )
    for _, r in latest.iterrows()
]
fc = ee.FeatureCollection(features)

def mask_s2(img):
    scl = img.select("SCL")
    mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return img.updateMask(mask)

end_dt = datetime.now(timezone.utc)
start_dt = end_dt - timedelta(days=45)
col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(fc)
    .filterDate(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
    .map(mask_s2)
)
if col.size().getInfo() == 0:
    start_dt = end_dt - timedelta(days=90)
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(fc)
        .filterDate(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 55))
        .map(mask_s2)
    )

s2 = col.median()
b3 = s2.select("B3").toFloat()
b4 = s2.select("B4").toFloat()
b8 = s2.select("B8").toFloat()
b11 = s2.select("B11").toFloat()

ndwi = b3.subtract(b8).divide(b3.add(b8).add(1e-6)).rename("ndwi_mean")
ndmi = b8.subtract(b11).divide(b8.add(b11).add(1e-6)).rename("ndmi_proxy")
turb = b4.divide(b3.add(1.0)).rename("turbidity_index")
water_pct = ndwi.gt(0.0).multiply(100.0).rename("water_coverage_pct")

metrics_img = ee.Image.cat([ndwi, ndmi, turb, water_pct])
print("Pulling live Sentinel-2 pass for all 33 Telangana districts...")
reduced = metrics_img.reduceRegions(
    collection=fc,
    reducer=ee.Reducer.mean(),
    scale=100,
    tileScale=4
).getInfo()

sat_map = {}
for feat in reduced.get("features", []):
    props = feat.get("properties", {})
    dname = props.get("district")
    if dname:
        sat_map[norm(dname)] = props

# 4. Update dataset with latest live satellite reading
new_rows = []
live_hits = 0
for _, prev in latest.iterrows():
    r = prev.copy()
    r["year_month"] = ym_now
    r["month"] = int(now_ist.month)
    r["prev_wqi"] = float(prev["wqi_score"])
    r["prev_turb"] = float(prev["turbidity_index"])
    r["prev_water"] = float(prev["water_coverage_pct"])

    s = sat_map.get(norm(r["district"]), {})
    if s.get("ndwi_mean") is not None:
        live_hits += 1
        r["ndwi_mean"] = round(float(np.clip(s["ndwi_mean"], -0.8, 0.8)), 4)
    if s.get("ndmi_proxy") is not None:
        r["ndmi_proxy"] = round(float(np.clip(s["ndmi_proxy"], -0.8, 0.8)), 4)
    if s.get("turbidity_index") is not None:
        r["turbidity_index"] = round(float(np.clip(s["turbidity_index"], 0.4, 3.5)), 4)
    if s.get("water_coverage_pct") is not None:
        r["water_coverage_pct"] = round(float(np.clip(s["water_coverage_pct"], 0.05, 45.0)), 4)

    # Recompute current WQI score from updated satellite readings
    turb_pen = max(0.0, (float(r["turbidity_index"]) - 0.85) * 18.0)
    water_bonus = min(14.0, float(r["water_coverage_pct"]) * 1.4)
    pol_pen = float(r.get("pollution_idx", 45.0)) * 0.25
    r["wqi_score"] = round(float(np.clip(84.0 + water_bonus - turb_pen - pol_pen, 18.0, 96.5)), 2)
    r["anomaly_flag"] = 1 if abs(float(r["wqi_score"]) - float(r["prev_wqi"])) >= 8.0 else 0
    new_rows.append(r)

df = df[df["year_month"] != ym_now]
df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True).sort_values(["district", "year_month"]).reset_index(drop=True)
df.to_csv("telangana_upgraded_dataset.csv", index=False)

# 5. Run XGBoost, Hybrid DL (LSTM+GRU), and Groundwater ML models
xgb_1m = xgb.XGBRegressor(); xgb_1m.load_model("aquatwin_xgb_1m.json")
xgb_6m = xgb.XGBRegressor(); xgb_6m.load_model("aquatwin_xgb_6m.json")
gw_1m = xgb.XGBRegressor(); gw_1m.load_model("aquatwin_gw_1m.json")
gw_6m = xgb.XGBRegressor(); gw_6m.load_model("aquatwin_gw_6m.json")

try:
    ckpt = torch.load("aquatwin_dl_v2.pt", map_location="cpu", weights_only=False)
except TypeError:
    ckpt = torch.load("aquatwin_dl_v2.pt", map_location="cpu")

dl_feats = ckpt["features"]
seq_len = int(ckpt["seq_len"])
mean_arr = np.array(ckpt["scaler_mean"], dtype=np.float32)
scale_arr = np.array(ckpt["scaler_scale"], dtype=np.float32)

class HybridSeqNet(nn.Module):
    def __init__(self, in_dim, hidden=64):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, num_layers=2, batch_first=True, dropout=0.1)
        self.gru = nn.GRU(in_dim, hidden, num_layers=1, batch_first=True)
        self.fc = nn.Sequential(nn.Linear(hidden * 2, 64), nn.ReLU(), nn.Linear(64, 3))
    def forward(self, x):
        l_out, _ = self.lstm(x)
        g_out, _ = self.gru(x)
        return self.fc(torch.cat([l_out[:, -1, :], g_out[:, -1, :]], dim=-1))

dl_model = HybridSeqNet(len(dl_feats), hidden=64)
dl_model.load_state_dict(ckpt["state_dict"])
dl_model.eval()

xgb_cols = [
    "month", "latitude", "longitude", "rainfall_mm", "temp_c", "evap_mm",
    "pollution_idx", "reservoir_idx", "ndwi_mean", "ndmi_proxy",
    "turbidity_index", "water_coverage_pct", "anomaly_flag",
    "prev_wqi", "prev_turb", "prev_water", "wqi_score"
]
gw_feats = [
    "month", "latitude", "longitude", "rainfall_mm", "temp_c", "evap_mm",
    "reservoir_idx", "ndwi_mean", "water_coverage_pct",
    "gw_depth_mbgl", "gw_extraction_pct", "gw_recharge_mm"
]

with open("ml_predictions.json", "r", encoding="utf-8") as f:
    pred_data = json.load(f)

pred_data["last_satellite_sync"] = now_ist.strftime("%Y-%m-%d %H:%M IST")
pred_data["satellite_source"] = "Sentinel-2 L2A (GEE Live)"
pred_data["satellite_window"] = f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}"

for item in pred_data.get("districts", []):
    key = norm(item["district"])
    grp = df[df["district"].apply(norm) == key].sort_values("year_month").reset_index(drop=True)
    if grp.empty:
        continue
    row = grp.iloc[-1]

    x_df = pd.DataFrame([{c: float(pd.to_numeric(row.get(c), errors="coerce") or 0.0) for c in xgb_cols}])[xgb_cols]
    p1_xgb = float(np.clip(xgb_1m.predict(x_df)[0], 15.0, 98.5))
    p6_xgb = float(np.clip(xgb_6m.predict(x_df)[0], 15.0, 98.5))

    win = grp[dl_feats].tail(seq_len).apply(pd.to_numeric, errors="coerce").fillna(0.0).values.astype(np.float32)
    if len(win) < seq_len:
        win = np.vstack([np.repeat(win[:1], seq_len - len(win), axis=0), win])
    denom = np.where(np.abs(scale_arr) < 1e-6, 1.0, scale_arr)
    with torch.no_grad():
        dl_out = dl_model(torch.tensor((win - mean_arr) / denom, dtype=torch.float32).unsqueeze(0)).squeeze(0).numpy()

    g_df = pd.DataFrame([{c: float(pd.to_numeric(row.get(c), errors="coerce") or 0.0) for c in gw_feats}])[gw_feats]
    gp1 = float(np.clip(gw_1m.predict(g_df)[0], 1.5, 25.0))
    gp6 = float(np.clip(gw_6m.predict(g_df)[0], 1.5, 25.0))

    wqi_now = round(float(row["wqi_score"]), 1)
    item.update({
        "xgb_wqi": round((wqi_now + p1_xgb) / 2.0, 1),
        "lstm_1m_wqi": round(float(np.clip(dl_out[0], 15.0, 98.5)), 1),
        "lstm_3m_wqi": round(float(np.clip(dl_out[1], 15.0, 98.5)), 1),
        "lstm_6m_wqi": round(float(np.clip(dl_out[2], 15.0, 98.5)), 1),
        "turbidity_index": round(float(row["turbidity_index"]), 4),
        "water_coverage_pct": round(float(row["water_coverage_pct"]), 4),
        "ndwi_mean": round(float(row["ndwi_mean"]), 4),
        "gw_depth_mbgl": round(float(row["gw_depth_mbgl"]), 2),
        "gw_extraction_pct": round(float(row["gw_extraction_pct"]), 1),
        "gw_recharge_mm": round(float(row["gw_recharge_mm"]), 2),
        "gw_status": str(row["gw_status"]),
        "gw_pred_1m": round(gp1, 2),
        "gw_pred_6m": round(gp6, 2),
        "risk_level": "Safe" if wqi_now >= 70 else ("Moderate Risk" if wqi_now >= 50 else "High Risk"),
        "last_satellite_sync": pred_data["last_satellite_sync"],
    })

with open("ml_predictions.json", "w", encoding="utf-8") as f:
    json.dump(pred_data, f, indent=2)

# 6. Mirror refreshed data to mobile-app bundle
ml_js = "window.AQUATWIN_ML_DATA = " + json.dumps(pred_data) + ";"
for target in [r"..\mobile-app\www\ml_data.js", r"..\mobile-app\ml_data.js"]:
    if os.path.exists(os.path.dirname(target)):
        with open(target, "w", encoding="utf-8") as f:
            f.write(ml_js)

print(f"SUCCESS: Live Sentinel-2 sync complete for {live_hits}/33 districts at {pred_data['last_satellite_sync']}!")
