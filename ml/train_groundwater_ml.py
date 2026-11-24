import json, re
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import r2_score, mean_absolute_error

df = pd.read_csv("telangana_upgraded_dataset.csv").sort_values(["district", "year_month"]).reset_index(drop=True)

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

gw_feats = [
    "month", "latitude", "longitude", "rainfall_mm", "temp_c", "evap_mm",
    "reservoir_idx", "ndwi_mean", "water_coverage_pct",
    "gw_depth_mbgl", "gw_extraction_pct", "gw_recharge_mm"
]

split = int(len(df) * 0.8)
X_tr, X_te = df[gw_feats].iloc[:split], df[gw_feats].iloc[split:]

models = {}
for h in [1, 6]:
    y = df[f"target_gw_{h}m"]
    m = xgb.XGBRegressor(n_estimators=220, max_depth=4, learning_rate=0.05, subsample=0.85, random_state=2026)
    m.fit(X_tr, y.iloc[:split])
    preds = m.predict(X_te)
    print(f"GW XGBoost +{h}M -> R2: {r2_score(y.iloc[split:], preds):.4f}, MAE: {mean_absolute_error(y.iloc[split:], preds):.3f} m")
    m.save_model(f"aquatwin_gw_{h}m.json")
    models[h] = m

# Build lookup for all 33 districts using latest month
latest = df.groupby("district", as_index=False).tail(1).reset_index(drop=True)
gw_map = {}
summary_rows = []
for _, r in latest.iterrows():
    x_one = pd.DataFrame([r[gw_feats]])
    p1 = float(np.clip(models[1].predict(x_one)[0], 1.5, 25.0))
    p6 = float(np.clip(models[6].predict(x_one)[0], 1.5, 25.0))
    rec = {
        "gw_depth_mbgl": round(float(r["gw_depth_mbgl"]), 2),
        "gw_extraction_pct": round(float(r["gw_extraction_pct"]), 1),
        "gw_recharge_mm": round(float(r["gw_recharge_mm"]), 2),
        "gw_status": str(r["gw_status"]),
        "gw_pred_1m": round(p1, 2),
        "gw_pred_6m": round(p6, 2),
    }
    gw_map[norm(r["district"])] = rec
    summary_rows.append({"district": r["district"], **rec})

# Merge groundwater fields into ml_predictions.json
with open("ml_predictions.json", "r", encoding="utf-8") as f:
    pred_data = json.load(f)

matched = 0
for item in pred_data.get("districts", []):
    g = gw_map.get(norm(item["district"]))
    if g:
        item.update(g)
        matched += 1

with open("ml_predictions.json", "w", encoding="utf-8") as f:
    json.dump(pred_data, f, indent=2)

out_df = pd.DataFrame(summary_rows).sort_values("gw_depth_mbgl", ascending=False).reset_index(drop=True)
out_df.index = out_df.index + 1
print(f"\nMerged groundwater predictions into {matched}/33 districts in ml_predictions.json:\n")
print(out_df[["district", "gw_depth_mbgl", "gw_pred_1m", "gw_pred_6m", "gw_extraction_pct", "gw_status"]].to_string())
