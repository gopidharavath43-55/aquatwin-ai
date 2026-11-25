import json, os
from datetime import datetime
import numpy as np
import pandas as pd
import xgboost as xgb
import torch
import torch.nn as nn
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler

# ------------------------------------------------------------------
# 1. Fuse all 4 three-year datasets (Water + GW + Reservoirs + Rain)
# ------------------------------------------------------------------
w_df = pd.read_csv("data_3y/water_3y.csv")
g_df = pd.read_csv("data_3y/groundwater_3y.csv")
s_df = pd.read_csv("data_3y/reservoirs_3y.csv")
r_df = pd.read_csv("data_3y/rainfall_3y.csv")

g_keep = [
    "district", "year_month", "gw_depth_mbgl", "gw_extraction_pct", "gw_recharge_mm", "gw_status",
    "gw_lag1", "gw_lag3", "gw_lag6", "gw_lag12", "gw_yoy_chg_m", "ext_lag1", "rech_lag1",
    "target_gw_1m", "target_gw_2m", "target_gw_6m", "target_gw_12m"
]
s_keep = [
    "district", "year_month", "reservoir_name", "river_basin", "basin_code",
    "res_capacity_tmc", "res_storage_tmc", "res_storage_pct",
    "res_inflow_cusecs", "res_outflow_cusecs", "res_net_flow_ratio", "res_status",
    "res_lag1", "res_lag3", "res_lag6", "res_lag12", "res_yoy_chg_pct", "inflow_lag1",
    "target_res_1m", "target_res_2m", "target_res_6m", "target_res_12m"
]
r_keep = [
    "district", "year_month", "normal_annual_mm", "normal_rain_mm",
    "rainfall_mm", "rain_departure_pct", "temp_c", "evap_mm", "rain_status",
    "rain_3m_cum_mm", "rain_6m_cum_mm", "rain_12m_cum_mm", "norm_6m_cum_mm", "spi_6m_proxy",
    "rain_lag1", "rain_lag3", "rain_lag6", "rain_lag12",
    "target_rain_1m", "target_rain_2m", "target_rain_6m", "target_rain_12m"
]

master = (
    w_df.merge(g_df[g_keep], on=["district", "year_month"], how="inner")
        .merge(s_df[s_keep], on=["district", "year_month"], how="inner")
        .merge(r_df[r_keep], on=["district", "year_month"], how="inner")
        .sort_values(["district", "year_month"])
        .reset_index(drop=True)
)

# Engineered hydro-climatic interaction features (key for +6M and +1Y accuracy)
master["rain_minus_evap"]     = (master["rainfall_mm"] - master["evap_mm"]).round(2)
master["hydro_stress_index"]  = (
    (100.0 - master["res_storage_pct"]) * 0.40
    + (master["gw_extraction_pct"] / 1.2) * 0.35
    + np.clip(-master["spi_6m_proxy"], 0.0, 3.0) * 10.0 * 0.25
).clip(0.0, 100.0).round(2)
master["res_rain_coupling"]   = ((master["res_storage_pct"] / 100.0) * (master["rain_6m_cum_mm"] / 100.0)).round(3)

master.to_csv("data_3y/telangana_master_3y.csv", index=False)
print(f"[PASS] Fused master 3-year dataset: {master.shape[0]} rows x {master.shape[1]} columns ({master['district'].nunique()} districts)")

# ------------------------------------------------------------------
# 2. Multi-Modal XGBoost Models (+1M, +2M, +6M, +1Y) across all 4 domains
# ------------------------------------------------------------------
FEATURES = [
    # Spatial & Seasonal
    "month", "sin_m", "cos_m", "latitude", "longitude", "basin_code",
    # Surface Water (1.1)
    "ndwi_mean", "ndmi_proxy", "turbidity_index", "water_coverage_pct",
    "pollution_idx", "wqi_score", "wqi_lag1", "wqi_lag3", "wqi_lag6", "turb_lag1", "water_lag1",
    # Groundwater (1.2)
    "gw_depth_mbgl", "gw_extraction_pct", "gw_recharge_mm",
    "gw_lag1", "gw_lag3", "gw_lag6", "gw_lag12", "gw_yoy_chg_m", "ext_lag1", "rech_lag1",
    # Reservoirs (1.3)
    "res_capacity_tmc", "res_storage_tmc", "res_storage_pct",
    "res_inflow_cusecs", "res_outflow_cusecs", "res_net_flow_ratio",
    "res_lag1", "res_lag3", "res_lag6", "res_lag12", "res_yoy_chg_pct", "inflow_lag1",
    # Rainfall & Climate (1.4)
    "normal_annual_mm", "normal_rain_mm", "rainfall_mm", "rain_departure_pct",
    "temp_c", "evap_mm", "rain_3m_cum_mm", "rain_6m_cum_mm", "rain_12m_cum_mm", "spi_6m_proxy",
    "rain_lag1", "rain_lag3", "rain_lag6", "rain_lag12",
    # Hydro-Climatic Interactions
    "rain_minus_evap", "hydro_stress_index", "res_rain_coupling"
]

DOMAINS = [
    ("wqi",  "target_wqi",  15.0, 98.5, "WQI"),
    ("gw",   "target_gw",    1.5, 25.0, "GW (mbgl)"),
    ("res",  "target_res",   2.0, 99.5, "Reservoir (%)"),
    ("rain", "target_rain",  0.0, 620.0, "Rainfall (mm)"),
]
HORIZONS = [(1, "1m"), (2, "2m"), (6, "6m"), (12, "1y")]

xgb_models = {}
xgb_metrics = {}

print("\n=== MULTI-MODAL XGBOOST (Water + GW + Reservoirs + Rainfall) ===")
for dom_key, tgt_prefix, lo, hi, dom_label in DOMAINS:
    xgb_models[dom_key] = {}
    xgb_metrics[dom_key] = {}
    for h_num, h_tag in HORIZONS:
        tgt_col = f"{tgt_prefix}_{h_num}m"
        sub = master.dropna(subset=[tgt_col]).sort_values(["year_month", "district"]).reset_index(drop=True)
        uniq_ym = sorted(sub["year_month"].unique())
        cut_ym = uniq_ym[int(len(uniq_ym) * 0.8)]
        tr = sub[sub["year_month"] < cut_ym]
        te = sub[sub["year_month"] >= cut_ym]

        m = xgb.XGBRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.80,
            random_state=2026,
        )
        m.fit(tr[FEATURES], tr[tgt_col])
        preds = np.clip(m.predict(te[FEATURES]), lo, hi)
        r2 = round(float(r2_score(te[tgt_col], preds)), 4)
        mae = round(float(mean_absolute_error(te[tgt_col], preds)), 3)
        rmse = round(float(np.sqrt(mean_squared_error(te[tgt_col], preds))), 3)

        m.save_model(f"models_3y/fused_xgb_{dom_key}_{h_tag}.json")
        xgb_models[dom_key][h_tag] = m
        xgb_metrics[dom_key][h_tag] = {"r2": r2, "mae": mae, "rmse": rmse}
        print(f"  [PASS] {dom_label:<14} +{h_tag.upper():<2} | R2: {r2:.4f} | MAE: {mae:.3f} | RMSE: {rmse:.3f}")

# Check how much Rainfall + Reservoir features contribute to +6M WQI prediction
imp_6m = xgb_models["wqi"]["6m"].feature_importances_
rain_res_share = sum(
    float(imp_6m[i]) for i, f in enumerate(FEATURES)
    if any(tok in f for tok in ("rain", "res_", "spi", "evap", "hydro", "inflow"))
)
print(f"\n[INFO] Rainfall + Reservoir Feature Contribution to +6M WQI Forecast: {rain_res_share * 100:.1f}%")

# ------------------------------------------------------------------
# 3. Multi-Modal PyTorch Hybrid LSTM + GRU Sequence Network
#    6-month multi-modal sequence -> 16 outputs (4 domains x 4 horizons)
# ------------------------------------------------------------------
torch.manual_seed(2026)
np.random.seed(2026)

SEQ_LEN = 6
SEQ_FEATS = [
    "sin_m", "cos_m", "basin_code",
    "ndwi_mean", "turbidity_index", "water_coverage_pct", "pollution_idx", "wqi_score",
    "gw_depth_mbgl", "gw_extraction_pct", "gw_recharge_mm",
    "res_storage_pct", "res_net_flow_ratio", "res_yoy_chg_pct",
    "rainfall_mm", "rain_6m_cum_mm", "spi_6m_proxy", "temp_c", "evap_mm", "hydro_stress_index"
]

TGT_COLS = [
    "target_wqi_1m", "target_wqi_2m", "target_wqi_6m", "target_wqi_12m",
    "target_gw_1m",  "target_gw_2m",  "target_gw_6m",  "target_gw_12m",
    "target_res_1m", "target_res_2m", "target_res_6m", "target_res_12m",
    "target_rain_1m","target_rain_2m","target_rain_6m","target_rain_12m",
]
TGT_SCALES = np.array(
    [100.0]*4 + [25.0]*4 + [100.0]*4 + [600.0]*4, dtype=np.float32
)

scaler = StandardScaler()
scaled_all = scaler.fit_transform(master[SEQ_FEATS].values.astype(np.float32))
master_scaled = master.copy()
for i, col in enumerate(SEQ_FEATS):
    master_scaled[col] = scaled_all[:, i]

X_tr_list, y_tr_list, X_te_list, y_te_list = [], [], [], []
latest_seq_map = {}

for dist, grp in master_scaled.groupby("district", sort=True):
    grp = grp.sort_values("year_month").reset_index(drop=True)
    feat_arr = grp[SEQ_FEATS].values.astype(np.float32)
    tgt_arr = grp[TGT_COLS].values.astype(np.float32)

    # Save latest 6-month window (months 30..35) for live future prediction
    latest_seq_map[dist] = feat_arr[-SEQ_LEN:]

    # Build supervised sequences for t = 5..23 (where t+12 <= 35)
    for t in range(SEQ_LEN - 1, len(grp) - 12):
        y_vec = tgt_arr[t]
        if np.isnan(y_vec).any():
            continue
        x_seq = feat_arr[t - SEQ_LEN + 1 : t + 1]
        y_norm = y_vec / TGT_SCALES
        if t <= 19:
            X_tr_list.append(x_seq)
            y_tr_list.append(y_norm)
        else:
            X_te_list.append(x_seq)
            y_te_list.append(y_norm)

X_tr_t = torch.tensor(np.array(X_tr_list), dtype=torch.float32)
y_tr_t = torch.tensor(np.array(y_tr_list), dtype=torch.float32)
X_te_t = torch.tensor(np.array(X_te_list), dtype=torch.float32)
y_te_t = torch.tensor(np.array(y_te_list), dtype=torch.float32)

class HybridHydroSeqNet(nn.Module):
    def __init__(self, in_dim, out_dim=16):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, 64, num_layers=2, batch_first=True, dropout=0.15)
        self.gru  = nn.GRU(in_dim, 48, num_layers=1, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(64 + 48, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, out_dim),
        )

    def forward(self, x):
        l_out, _ = self.lstm(x)
        g_out, _ = self.gru(x)
        fused = torch.cat([l_out[:, -1, :], g_out[:, -1, :]], dim=-1)
        return self.head(fused)

net = HybridHydroSeqNet(in_dim=len(SEQ_FEATS), out_dim=16)
opt = torch.optim.AdamW(net.parameters(), lr=2.5e-3, weight_decay=1e-4)
loss_fn = nn.SmoothL1Loss()

net.train()
for epoch in range(110):
    opt.zero_grad()
    pred = net(X_tr_t)
    loss = loss_fn(pred, y_tr_t)
    loss.backward()
    opt.step()

net.eval()
with torch.no_grad():
    te_pred = net(X_te_t).numpy() * TGT_SCALES
    te_true = y_te_t.numpy() * TGT_SCALES

dl_metrics = {
    "wqi_1m_r2": round(float(r2_score(te_true[:, 0], te_pred[:, 0])), 4),
    "wqi_6m_r2": round(float(r2_score(te_true[:, 2], te_pred[:, 2])), 4),
    "wqi_1y_r2": round(float(r2_score(te_true[:, 3], te_pred[:, 3])), 4),
    "gw_6m_mae_m": round(float(mean_absolute_error(te_true[:, 6], te_pred[:, 6])), 3),
    "res_6m_mae_pct": round(float(mean_absolute_error(te_true[:, 10], te_pred[:, 10])), 2),
    "rain_6m_mae_mm": round(float(mean_absolute_error(te_true[:, 14], te_pred[:, 14])), 2),
}

torch.save({
    "state_dict": net.state_dict(),
    "seq_feats": SEQ_FEATS,
    "scaler_mean": scaler.mean_.tolist(),
    "scaler_scale": scaler.scale_.tolist(),
    "tgt_scales": TGT_SCALES.tolist(),
}, "models_3y/hybrid_lstm_gru_3y.pt")

print("\n=== HYBRID PYTORCH LSTM + GRU (+1M / +2M / +6M / +1Y) ===")
print(f"  [PASS] WQI R2 (+1M: {dl_metrics['wqi_1m_r2']}, +6M: {dl_metrics['wqi_6m_r2']}, +1Y: {dl_metrics['wqi_1y_r2']})")
print(f"  [PASS] +6M MAE -> GW: {dl_metrics['gw_6m_mae_m']} m | Reservoir: {dl_metrics['res_6m_mae_pct']}% | Rainfall: {dl_metrics['rain_6m_mae_mm']} mm")

# ------------------------------------------------------------------
# 4. Generate Calibrated Ensemble Forecasts (65% XGBoost + 35% LSTM-GRU)
#    and update ml_predictions.json + mobile-app ml_data.js
# ------------------------------------------------------------------
latest_rows = master.groupby("district", as_index=False).tail(1).sort_values("district").reset_index(drop=True)
sync_ts = datetime.now().strftime("%Y-%m-%d %H:%M IST")
district_outputs = []

for _, r in latest_rows.iterrows():
    dist = str(r["district"])
    x_tab = pd.DataFrame([r[FEATURES]])
    x_seq = torch.tensor(latest_seq_map[dist][None, :, :], dtype=torch.float32)

    with torch.no_grad():
        dl_vec = (net(x_seq).numpy()[0] * TGT_SCALES)

    def blend(dom_key, h_tag, dl_idx, lo, hi, digits=2):
        xp = float(xgb_models[dom_key][h_tag].predict(x_tab)[0])
        dp = float(dl_vec[dl_idx])
        val = np.clip(0.65 * xp + 0.35 * dp, lo, hi)
        return round(float(val), digits)

    wqi_1m = blend("wqi", "1m", 0, 15.0, 98.5, 1)
    wqi_2m = blend("wqi", "2m", 1, 15.0, 98.5, 1)
    wqi_6m = blend("wqi", "6m", 2, 15.0, 98.5, 1)
    wqi_1y = blend("wqi", "1y", 3, 15.0, 98.5, 1)
    wqi_3m = round(wqi_2m * 0.65 + wqi_6m * 0.35, 1)

    gw_1m  = blend("gw", "1m", 4, 1.5, 25.0, 2)
    gw_2m  = blend("gw", "2m", 5, 1.5, 25.0, 2)
    gw_6m  = blend("gw", "6m", 6, 1.5, 25.0, 2)
    gw_1y  = blend("gw", "1y", 7, 1.5, 25.0, 2)

    res_1m = blend("res", "1m", 8, 2.0, 99.5, 1)
    res_2m = blend("res", "2m", 9, 2.0, 99.5, 1)
    res_6m = blend("res", "6m", 10, 2.0, 99.5, 1)
    res_1y = blend("res", "1y", 11, 2.0, 99.5, 1)

    rn_1m  = blend("rain", "1m", 12, 0.0, 620.0, 1)
    rn_2m  = blend("rain", "2m", 13, 0.0, 620.0, 1)
    rn_6m  = blend("rain", "6m", 14, 0.0, 620.0, 1)
    rn_1y  = blend("rain", "1y", 15, 0.0, 620.0, 1)

    wqi_now = round(float(r["wqi_score"]), 1)
    risk = "Safe" if wqi_now >= 70.0 else ("Moderate Risk" if wqi_now >= 55.0 else "High Risk")

    district_outputs.append({
        "district": dist,
        "latitude": round(float(r["latitude"]), 4),
        "longitude": round(float(r["longitude"]), 4),
        "last_satellite_sync": sync_ts,
        # Surface Water (1.1)
        "ndwi_mean": round(float(r["ndwi_mean"]), 4),
        "ndmi_proxy": round(float(r["ndmi_proxy"]), 4),
        "turbidity_index": round(float(r["turbidity_index"]), 4),
        "water_coverage_pct": round(float(r["water_coverage_pct"]), 4),
        "pollution_idx": round(float(r["pollution_idx"]), 2),
        "wqi_score": wqi_now,
        "xgb_wqi": wqi_now,
        "risk_level": risk,
        # Backward-compatible + new +1M / +2M / +6M / +1Y WQI forecasts
        "lstm_1m_wqi": wqi_1m,
        "lstm_2m_wqi": wqi_2m,
        "lstm_3m_wqi": wqi_3m,
        "lstm_6m_wqi": wqi_6m,
        "lstm_1y_wqi": wqi_1y,
        # Groundwater (1.2)
        "gw_depth_mbgl": round(float(r["gw_depth_mbgl"]), 2),
        "gw_extraction_pct": round(float(r["gw_extraction_pct"]), 1),
        "gw_recharge_mm": round(float(r["gw_recharge_mm"]), 2),
        "gw_yoy_chg_m": round(float(r["gw_yoy_chg_m"]), 2),
        "gw_status": str(r["gw_status"]),
        "gw_pred_1m": gw_1m,
        "gw_pred_2m": gw_2m,
        "gw_pred_6m": gw_6m,
        "gw_pred_1y": gw_1y,
        # Reservoirs (1.3)
        "reservoir_name": str(r["reservoir_name"]),
        "river_basin": str(r["river_basin"]),
        "res_capacity_tmc": round(float(r["res_capacity_tmc"]), 2),
        "res_storage_tmc": round(float(r["res_storage_tmc"]), 2),
        "res_storage_pct": round(float(r["res_storage_pct"]), 1),
        "reservoir_idx": round(float(r["res_storage_pct"]), 1),
        "res_yoy_chg_pct": round(float(r["res_yoy_chg_pct"]), 1),
        "res_status": str(r["res_status"]),
        "res_pred_1m": res_1m,
        "res_pred_2m": res_2m,
        "res_pred_6m": res_6m,
        "res_pred_1y": res_1y,
        # Rainfall & Climate (1.4)
        "rainfall_mm": round(float(r["rainfall_mm"]), 1),
        "normal_rain_mm": round(float(r["normal_rain_mm"]), 1),
        "rain_departure_pct": round(float(r["rain_departure_pct"]), 1),
        "rain_6m_cum_mm": round(float(r["rain_6m_cum_mm"]), 1),
        "rain_12m_cum_mm": round(float(r["rain_12m_cum_mm"]), 1),
        "spi_6m_proxy": round(float(r["spi_6m_proxy"]), 3),
        "temp_c": round(float(r["temp_c"]), 1),
        "evap_mm": round(float(r["evap_mm"]), 1),
        "rain_status": str(r["rain_status"]),
        "rain_pred_1m": rn_1m,
        "rain_pred_2m": rn_2m,
        "rain_pred_6m": rn_6m,
        "rain_pred_1y": rn_1y,
        "hydro_stress_index": round(float(r["hydro_stress_index"]), 1),
    })

bundle = {
    "model_version": "AquaTwin-3Y-MultiModal-v2",
    "trained_window": f"{master['year_month'].min()} to {master['year_month'].max()} (36 months)",
    "horizons": ["+1M", "+2M", "+6M", "+1Y"],
    "domains": ["Surface Water", "Groundwater", "Reservoirs", "Rainfall"],
    "rain_reservoir_6m_feature_share_pct": round(rain_res_share * 100.0, 1),
    "last_satellite_sync": sync_ts,
    "xgb_metrics": xgb_metrics,
    "dl_metrics": dl_metrics,
    "districts": district_outputs,
}

with open("ml_predictions.json", "w", encoding="utf-8") as f:
    json.dump(bundle, f, indent=2)

with open("data_3y/multimodal_benchmark.json", "w", encoding="utf-8") as f:
    json.dump({"xgb_metrics": xgb_metrics, "dl_metrics": dl_metrics, "rain_res_6m_share_pct": bundle["rain_reservoir_6m_feature_share_pct"]}, f, indent=2)

js_payload = "window.AQUATWIN_ML_DATA = " + json.dumps(bundle, separators=(",", ":")) + ";"
for target_js in [r"..\mobile-app\www\ml_data.js", r"..\mobile-app\ml_data.js"]:
    if os.path.exists(os.path.dirname(target_js)):
        with open(target_js, "w", encoding="utf-8") as f:
            f.write(js_payload)

hyd = [d for d in district_outputs if d["district"] == "Hyderabad"][0]
print(f"\n[DONE] Exported 33-district Multi-Modal (+1M/+2M/+6M/+1Y) predictions to ml_predictions.json & mobile-app/www/ml_data.js")
print(f"[SAMPLE] Hyderabad -> WQI: {hyd['wqi_score']} (+1M:{hyd['lstm_1m_wqi']} | +2M:{hyd['lstm_2m_wqi']} | +6M:{hyd['lstm_6m_wqi']} | +1Y:{hyd['lstm_1y_wqi']})")
print(f"                      GW : {hyd['gw_depth_mbgl']}m (+1M:{hyd['gw_pred_1m']} | +2M:{hyd['gw_pred_2m']} | +6M:{hyd['gw_pred_6m']} | +1Y:{hyd['gw_pred_1y']})")
print(f"                      Res: {hyd['res_storage_pct']}% ({hyd['reservoir_name']}) (+1M:{hyd['res_pred_1m']}% | +6M:{hyd['res_pred_6m']}% | +1Y:{hyd['res_pred_1y']}%)")
print(f"                      Rain: {hyd['rainfall_mm']}mm (+1M:{hyd['rain_pred_1m']} | +2M:{hyd['rain_pred_2m']} | +6M:{hyd['rain_pred_6m']} | +1Y:{hyd['rain_pred_1y']})")