import json, os, re
import pandas as pd

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

with open("ml_predictions.json", "r", encoding="utf-8") as f:
    pred = json.load(f)

df = pd.read_csv("telangana_upgraded_dataset.csv").sort_values(["district", "year_month"]).reset_index(drop=True)
latest_map = {norm(r["district"]): r for _, r in df.groupby("district", as_index=False).tail(1).iterrows()}

num_cols = [
    "latitude", "longitude", "rainfall_mm", "temp_c", "evap_mm",
    "pollution_idx", "reservoir_idx", "ndwi_mean", "ndmi_proxy",
    "turbidity_index", "water_coverage_pct", "wqi_score",
    "gw_depth_mbgl", "gw_extraction_pct", "gw_recharge_mm"
]

for item in pred.get("districts", []):
    k = norm(item.get("district", ""))
    row = latest_map.get(k)
    if row is not None:
        for c in num_cols:
            if c in row and pd.notna(row[c]):
                val = float(row[c])
                item[c] = round(val, 4) if c in ("latitude", "longitude", "ndwi_mean", "ndmi_proxy", "turbidity_index", "water_coverage_pct") else round(val, 2)
        if "gw_status" in row and pd.notna(row["gw_status"]):
            item["gw_status"] = str(row["gw_status"])

with open("ml_predictions.json", "w", encoding="utf-8") as f:
    json.dump(pred, f, indent=2)

js_out = "window.AQUATWIN_ML_DATA = " + json.dumps(pred) + ";"
for p in [r"..\mobile-app\www\ml_data.js", r"..\mobile-app\ml_data.js"]:
    if os.path.exists(os.path.dirname(p)):
        with open(p, "w", encoding="utf-8") as f:
            f.write(js_out)

names = [d.get("district") for d in pred.get("districts", [])]
print(f"Packed {len(names)} districts with GPS + Satellite + Water + GW. Hyderabad present: {'Hyderabad' in names}")
