import glob, json, os, joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingRegressor, ExtraTreesRegressor, IsolationForest
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error
import xgboost as xgb

# 1. Auto-locate district time-series dataset
csv_files = [f for f in glob.glob("*.csv") if "pred" not in f.lower()]
if not csv_files:
    raise FileNotFoundError("No training CSV found in C:\\Users\\gopid\\aquatwin-ai\\ml")
data_path = max(csv_files, key=os.path.getsize)
print(f"Loading dataset: {data_path}")
df = pd.read_csv(data_path)

FEATURES = [
    "month", "latitude", "longitude", "rainfall_mm", "temp_c", "evap_mm",
    "pollution_idx", "reservoir_idx", "ndwi_mean", "ndmi_proxy",
    "turbidity_index", "water_coverage_pct", "anomaly_flag",
    "prev_wqi", "prev_turb", "prev_water", "wqi_score"
]
for col in FEATURES:
    if col not in df.columns:
        df[col] = 0.0
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

sort_cols = ["district", "year_month"] if "year_month" in df.columns else ["district", "month"]
df = df.sort_values(sort_cols).reset_index(drop=True)

# Create multi-horizon targets (+1M, +3M, +6M)
df["target_1m"] = df.groupby("district")["wqi_score"].shift(-1).fillna(df["wqi_score"])
df["target_3m"] = df.groupby("district")["wqi_score"].shift(-3).fillna(df["target_1m"])
df["target_6m"] = df.groupby("district")["wqi_score"].shift(-6).fillna(df["target_3m"])

X = df[FEATURES].values.astype(np.float32)
y1 = df["target_1m"].values.astype(np.float32)
y6 = df["target_6m"].values.astype(np.float32)

split = int(len(df) * 0.8)
X_tr, X_va = X[:split], X[split:]
y1_tr, y1_va = y1[:split], y1[split:]
y6_tr, y6_va = y6[:split], y6[split:]

# 2. Model 4: Stacking Ensemble (XGBoost + HistGBM + ExtraTrees -> Ridge)
print("Training Model 4: Multi-Model Stacking Ensemble...")
def fit_stack(X_train, y_train, X_val, y_val):
    m_xgb = xgb.XGBRegressor(n_estimators=180, max_depth=5, learning_rate=0.05, subsample=0.85, random_state=42)
    m_hgb = HistGradientBoostingRegressor(max_iter=180, max_depth=6, learning_rate=0.05, random_state=42)
    m_et  = ExtraTreesRegressor(n_estimators=120, max_depth=10, random_state=42, n_jobs=-1)
    m_xgb.fit(X_train, y_train)
    m_hgb.fit(X_train, y_train)
    m_et.fit(X_train, y_train)

    val_meta = np.column_stack([m_xgb.predict(X_val), m_hgb.predict(X_val), m_et.predict(X_val)])
    meta = Ridge(alpha=1.0).fit(val_meta, y_val)
    mae = mean_absolute_error(y_val, meta.predict(val_meta))
    return {"xgb": m_xgb, "hgb": m_hgb, "et": m_et, "meta": meta, "val_mae": round(float(mae), 3)}

stack_1m = fit_stack(X_tr, y1_tr, X_va, y1_va)
stack_6m = fit_stack(X_tr, y6_tr, X_va, y6_va)
print(f"Stacking Ensemble Validation MAE -> +1M: {stack_1m['val_mae']} | +6M: {stack_6m['val_mae']}")

joblib.dump({"features": FEATURES, "stack_1m": stack_1m, "stack_6m": stack_6m}, "aquatwin_ensemble_v3.pkl")

# 3. Model 3: Spatio-Temporal Multi-Head Attention + Quantile Network
print("Training Model 3: Spatio-Temporal Quantile Attention Network...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X).astype(np.float32)

SEQ_LEN = 6
seqs, targets = [], []
for _, grp in df.groupby("district"):
    arr = scaler.transform(grp[FEATURES].values.astype(np.float32))
    t_arr = grp[["target_1m", "target_3m", "target_6m"]].values.astype(np.float32)
    if len(arr) >= SEQ_LEN:
        for i in range(len(arr) - SEQ_LEN + 1):
            seqs.append(arr[i:i+SEQ_LEN])
            targets.append(t_arr[i+SEQ_LEN-1])

seqs = np.array(seqs, dtype=np.float32)
targets = np.array(targets, dtype=np.float32)

class SpatioTemporalQuantileNet(nn.Module):
    def __init__(self, in_dim, d_model=64):
        super().__init__()
        self.proj = nn.Linear(in_dim, d_model)
        self.attn = nn.MultiheadAttention(embed_dim=d_model, num_heads=4, batch_first=True)
        self.gru = nn.GRU(d_model, d_model, batch_first=True)
        # Outputs 3 horizons x 3 quantiles (q10, q50, q90) = 9 outputs
        self.head = nn.Sequential(nn.Linear(d_model, 48), nn.GELU(), nn.Linear(48, 9))

    def forward(self, x):
        h = torch.relu(self.proj(x))
        attn_out, _ = self.attn(h, h, h)
        _, last = self.gru(h + attn_out)
        return self.head(last.squeeze(0)).view(-1, 3, 3)

def pinball_loss(preds, y_true, quantiles=(0.1, 0.5, 0.9)):
    loss = 0.0
    for idx, q in enumerate(quantiles):
        err = y_true - preds[:, :, idx]
        loss += torch.mean(torch.maximum(q * err, (q - 1.0) * err))
    return loss

st_model = SpatioTemporalQuantileNet(len(FEATURES))
opt = torch.optim.AdamW(st_model.parameters(), lr=2e-3, weight_decay=1e-4)
ds_t = torch.utils.data.TensorDataset(torch.tensor(seqs), torch.tensor(targets))
loader = torch.utils.data.DataLoader(ds_t, batch_size=32, shuffle=True)

st_model.train()
for epoch in range(28):
    for bx, by in loader:
        opt.zero_grad()
        loss = pinball_loss(st_model(bx), by)
        loss.backward()
        opt.step()

torch.save({
    "state_dict": st_model.state_dict(),
    "features": FEATURES,
    "seq_len": SEQ_LEN,
    "mean": scaler.mean_.astype(np.float32),
    "scale": scaler.scale_.astype(np.float32)
}, "aquatwin_st_attn_v3.pt")

# 4. Model 5: Isolation Forest Anomaly & Contamination Detector
print("Training Model 5: Contamination & Bloom Anomaly Detector...")
ANOM_COLS = ["pollution_idx", "turbidity_index", "ndwi_mean", "ndmi_proxy", "water_coverage_pct", "rainfall_mm", "evap_mm", "wqi_score"]
iso = IsolationForest(n_estimators=150, contamination=0.12, random_state=42)
iso.fit(df[ANOM_COLS].values)
raw_scores = -iso.decision_function(df[ANOM_COLS].values)
min_s, max_s = float(raw_scores.min()), float(raw_scores.max())
joblib.dump({"iso": iso, "cols": ANOM_COLS, "min_s": min_s, "max_s": max_s}, "aquatwin_anomaly_v3.pkl")

# 5. Export enriched ml_predictions.json with v3 fields while preserving v2 keys
st_model.eval()
existing = {}
if os.path.exists("ml_predictions.json"):
    with open("ml_predictions.json", "r", encoding="utf-8") as f:
        old_data = json.load(f)
        for item in old_data.get("districts", []):
            existing[item["district"].lower()] = item

def predict_stack(stack_obj, row_vec):
    base = np.column_stack([
        stack_obj["xgb"].predict(row_vec),
        stack_obj["hgb"].predict(row_vec),
        stack_obj["et"].predict(row_vec)
    ])
    return float(np.clip(stack_obj["meta"].predict(base)[0], 15.0, 98.5))

def top_driver(row):
    if row["pollution_idx"] > 65:
        return "Industrial/Urban Pollution Load"
    if row["turbidity_index"] > 1.35:
        return "High Turbidity & Sediment Runoff"
    if row["rainfall_mm"] < 35 and row["evap_mm"] > 140:
        return "Low Monsoon Recharge & High Evap"
    if row["ndwi_mean"] < 0.05:
        return "Surface Water Shrinkage (NDWI)"
    return "Balanced Basin Hydrology"

districts_out = []
for dist, grp in df.groupby("district"):
    last = grp.iloc[-1]
    row_vec = last[FEATURES].values.astype(np.float32).reshape(1, -1)
    ens_1m = predict_stack(stack_1m, row_vec)
    ens_6m = predict_stack(stack_6m, row_vec)

    win = scaler.transform(grp[FEATURES].tail(SEQ_LEN).values.astype(np.float32))
    if len(win) < SEQ_LEN:
        win = np.vstack([np.repeat(win[:1], SEQ_LEN - len(win), axis=0), win])
    with torch.no_grad():
        q_out = st_model(torch.tensor(win).unsqueeze(0)).squeeze(0).numpy()  # (3, 3)

    a_raw = float(-iso.decision_function(last[ANOM_COLS].values.reshape(1, -1))[0])
    anom_score = round(float(np.clip((a_raw - min_s) / (max_s - min_s + 1e-6) * 100.0, 2.0, 99.0)), 1)
    anom_status = "Critical Alert" if anom_score >= 75 else ("Watch" if anom_score >= 48 else "Normal")

    base_rec = existing.get(str(dist).lower(), {})
    rec = {
        **base_rec,
        "district": str(dist),
        "xgb_wqi": round(float(base_rec.get("xgb_wqi", ens_1m)), 1),
        "lstm_1m_wqi": round(float(np.clip(q_out[0, 1], 15.0, 98.5)), 1),
        "lstm_6m_wqi": round(float(np.clip(q_out[2, 1], 15.0, 98.5)), 1),
        "ensemble_1m_wqi": round(ens_1m, 1),
        "ensemble_6m_wqi": round(ens_6m, 1),
        "ci_1m": [round(float(np.clip(q_out[0, 0], 10.0, 98.5)), 1), round(float(np.clip(q_out[0, 2], 12.0, 99.5)), 1)],
        "ci_6m": [round(float(np.clip(q_out[2, 0], 10.0, 98.5)), 1), round(float(np.clip(q_out[2, 2], 12.0, 99.5)), 1)],
        "anomaly_score": anom_score,
        "anomaly_status": anom_status,
        "top_driver": top_driver(last),
        "turbidity_index": round(float(last["turbidity_index"]), 2),
        "water_coverage_pct": round(float(last["water_coverage_pct"]), 2),
        "risk_level": "High Risk" if ens_1m < 55 else ("Moderate Risk" if ens_1m < 75 else "Low Risk")
    }
    districts_out.append(rec)

with open("ml_predictions.json", "w", encoding="utf-8") as f:
    json.dump({"model_version": "v3-spatiotemporal-ensemble", "count": len(districts_out), "districts": districts_out}, f, indent=2)

print(f"Saved v3 models & updated ml_predictions.json for {len(districts_out)} districts!")
