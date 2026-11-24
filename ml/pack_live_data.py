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

gw_map = {}
if os.path.exists("telangana_groundwater_data.csv"):
    gdf = pd.read_csv("telangana_groundwater_data.csv")
    gw_map = {norm(r["district"]): r for _, r in gdf.iterrows()}

num_cols = [
    "rainfall_mm", "temp_c", "evap_mm", "pollution_idx", "reservoir_idx",
    "ndwi_mean", "ndmi_proxy", "turbidity_index", "water_coverage_pct",
    "wqi_score", "gw_depth_mbgl", "gw_extraction_pct", "gw_recharge_mm"
]

for item in pred.get("districts", []):
    k = norm(item.get("district", ""))
    row = latest_map.get(k)
    if row is not None:
        for c in num_cols:
            if c in row and pd.notna(row[c]):
                val = float(row[c])
                if c in ("ndwi_mean", "ndmi_proxy", "turbidity_index", "water_coverage_pct"):
                    item[c] = round(val, 4)
                else:
                    item[c] = round(val, 2)
        if "gw_status" in row and pd.notna(row["gw_status"]):
            item["gw_status"] = str(row["gw_status"])
        if "year_month" in row and pd.notna(row["year_month"]):
            item["data_month"] = str(row["year_month"])
    grow = gw_map.get(k)
    if grow is not None:
        if "gw_depth_mbgl" not in item and pd.notna(grow.get("gw_depth_mbgl")):
            item["gw_depth_mbgl"] = round(float(grow["gw_depth_mbgl"]), 2)
        if "gw_extraction_pct" not in item and pd.notna(grow.get("gw_extraction_pct")):
            item["gw_extraction_pct"] = round(float(grow["gw_extraction_pct"]), 1)
        if "gw_recharge_mm" not in item and pd.notna(grow.get("gw_recharge_mm")):
            item["gw_recharge_mm"] = round(float(grow["gw_recharge_mm"]), 2)
        if "gw_status" not in item and pd.notna(grow.get("gw_status")):
            item["gw_status"] = str(grow["gw_status"])

with open("ml_predictions.json", "w", encoding="utf-8") as f:
    json.dump(pred, f, indent=2)

js_out = "window.AQUATWIN_ML_DATA = " + json.dumps(pred) + ";"
for p in [r"..\mobile-app\www\ml_data.js", r"..\mobile-app\ml_data.js"]:
    if os.path.exists(os.path.dirname(p)):
        with open(p, "w", encoding="utf-8") as f:
            f.write(js_out)

print(f"Packed Satellite + Water + Groundwater for {len(pred.get('districts', []))} districts!")
