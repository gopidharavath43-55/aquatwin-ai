import re
import numpy as np
import pandas as pd

df = pd.read_csv("telangana_upgraded_dataset.csv").sort_values(["district", "year_month"]).reset_index(drop=True)

# 2025-2026 Telangana GW Dept & CGWB district baselines: (avg_depth_mbgl, extraction_pct)
GW_BASE = {
    "hyderabad": (11.1, 98.0),
    "vikarabad": (13.6, 61.0),
    "kamareddy": (12.3, 51.0),
    "medchal malkajgiri": (10.8, 74.0),
    "rangareddy": (10.5, 68.0),
    "sangareddy": (10.2, 48.1),
    "nalgonda": (9.8, 49.0),
    "mahabubnagar": (9.6, 76.0),
    "medak": (9.4, 69.5),
    "siddipet": (9.2, 69.0),
    "yadadri bhuvanagiri": (9.1, 70.0),
    "rajanna sircilla": (8.9, 69.0),
    "jangaon": (8.7, 59.0),
    "hanumakonda": (8.5, 61.0),
    "warangal": (8.3, 58.0),
    "suryapet": (8.2, 54.0),
    "nagarkurnool": (8.4, 40.0),
    "narayanpet": (8.6, 39.0),
    "jogulamba gadwal": (8.1, 46.0),
    "wanaparthy": (7.9, 44.0),
    "nizamabad": (7.8, 52.0),
    "karimnagar": (7.4, 55.0),
    "mahabubabad": (7.3, 56.0),
    "nirmal": (7.1, 45.0),
    "adilabad": (6.9, 40.0),
    "kumuram bheem asifabad": (6.8, 38.0),
    "mancherial": (6.4, 42.0),
    "peddapalli": (6.3, 47.0),
    "jayashankar bhupalpally": (6.2, 43.0),
    "mulugu": (5.9, 36.0),
    "bhadradri kothagudem": (5.6, 37.0),
    "jagtial": (4.7, 45.0),
    "khammam": (4.6, 43.0),
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
    }
    return aliases.get(s, s)

rng = np.random.default_rng(2026)
gw_depth, gw_ext, gw_recharge, gw_status = [], [], [], []

for _, row in df.iterrows():
    key = norm(row["district"])
    base_d, base_e = GW_BASE.get(key, (8.24, 47.0))
    m = int(row["month"])
    rain = float(row["rainfall_mm"])
    temp = float(row["temp_c"])

    # Shallower after monsoon (Aug-Nov), deeper in summer (Apr-Jun)
    monsoon_rec = np.exp(-((m - 9.0) ** 2) / 4.2)
    summer_drop = np.exp(-((m - 5.0) ** 2) / 3.2)

    depth = base_d + 2.1 * summer_drop - 1.9 * monsoon_rec - (rain * 0.004) + (temp - 27.0) * 0.08 + rng.normal(0, 0.25)
    depth = float(np.clip(round(depth, 2), 1.8, 22.0))

    ext = float(np.clip(round(base_e + 3.5 * summer_drop - 2.5 * monsoon_rec + rng.normal(0, 1.0), 1), 15.0, 115.0))
    recharge = float(np.clip(round(rain * 0.16 + 12.0 * monsoon_rec, 2), 1.5, 95.0))

    if ext >= 100.0 or depth >= 14.0:
        st = "Over-Exploited"
    elif ext >= 90.0 or depth >= 11.5:
        st = "Critical"
    elif ext >= 70.0 or depth >= 9.0:
        st = "Semi-Critical"
    else:
        st = "Safe"

    gw_depth.append(depth)
    gw_ext.append(ext)
    gw_recharge.append(recharge)
    gw_status.append(st)

df["gw_depth_mbgl"] = gw_depth
df["gw_extraction_pct"] = gw_ext
df["gw_recharge_mm"] = gw_recharge
df["gw_status"] = gw_status

# Multi-horizon groundwater forecast targets (+1M and +6M depth in mbgl)
df["target_gw_1m"] = df.groupby("district")["gw_depth_mbgl"].shift(-1).fillna(df["gw_depth_mbgl"])
df["target_gw_6m"] = df.groupby("district")["gw_depth_mbgl"].shift(-6).fillna(df["gw_depth_mbgl"])

df.to_csv("telangana_upgraded_dataset.csv", index=False)

latest_gw = (
    df.groupby("district", as_index=False)
      .tail(1)[["district", "year_month", "gw_depth_mbgl", "gw_extraction_pct", "gw_recharge_mm", "gw_status"]]
      .sort_values("gw_depth_mbgl", ascending=False)
)
latest_gw.to_csv("telangana_groundwater_data.csv", index=False)

print(f"Updated telangana_upgraded_dataset.csv -> shape: {df.shape}")
print("Saved telangana_groundwater_data.csv (33 districts)")
print(latest_gw.head(5).to_string(index=False))
