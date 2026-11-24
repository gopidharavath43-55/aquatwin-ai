import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error
import xgboost as xgb

torch.manual_seed(2026)
np.random.seed(2026)

df = pd.read_csv("telangana_upgraded_dataset.csv").sort_values(["district", "year_month"]).reset_index(drop=True)

features = [
    "month", "latitude", "longitude", "rainfall_mm", "temp_c", "evap_mm",
    "pollution_idx", "reservoir_idx", "ndwi_mean", "ndmi_proxy",
    "turbidity_index", "water_coverage_pct", "anomaly_flag",
    "prev_wqi", "prev_turb", "prev_water", "wqi_score"
]

# 1. Train XGBoost models for +1M, +3M, and +6M horizons
xgb_metrics = {}
xgb_models = {}
for h in [1, 3, 6]:
    target = f"target_wqi_{h}m"
    X = df[features]
    y = df[target]
    split = int(len(df) * 0.8)
    X_tr, X_te, y_tr, y_te = X.iloc[:split], X.iloc[split:], y.iloc[:split], y.iloc[split:]

    m = xgb.XGBRegressor(
        n_estimators=260,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=2026,
    )
    m.fit(X_tr, y_tr)
    preds = m.predict(X_te)
    xgb_metrics[f"{h}m"] = {
        "r2": round(float(r2_score(y_te, preds)), 4),
        "mae": round(float(mean_absolute_error(y_te, preds)), 3),
        "rmse": round(float(root_mean_squared_error(y_te, preds)), 3),
    }
    fname = f"aquatwin_xgb_{h}m.json"
    m.save_model(fname)
    xgb_models[h] = fname

# 2. Train Multi-Horizon LSTM + GRU sequence model (6-month window -> [1M, 3M, 6M])
seq_len = 6
targets = ["target_wqi_1m", "target_wqi_3m", "target_wqi_6m"]
X_seqs, y_seqs = [], []
for _, grp in df.groupby("district"):
    grp = grp.reset_index(drop=True)
    f_arr = grp[features].values.astype(np.float32)
    t_arr = grp[targets].values.astype(np.float32)
    for i in range(seq_len, len(grp)):
        X_seqs.append(f_arr[i - seq_len:i])
        y_seqs.append(t_arr[i])

X_all = np.array(X_seqs)
y_all = np.array(y_seqs)
s_idx = int(len(X_all) * 0.8)
X_tr_r, X_te_r = X_all[:s_idx], X_all[s_idx:]
y_tr, y_te = y_all[:s_idx], y_all[s_idx:]

scaler = StandardScaler()
X_tr = scaler.fit_transform(X_tr_r.reshape(-1, len(features))).reshape(X_tr_r.shape)
X_te = scaler.transform(X_te_r.reshape(-1, len(features))).reshape(X_te_r.shape)

loader = DataLoader(TensorDataset(torch.tensor(X_tr), torch.tensor(y_tr)), batch_size=32, shuffle=True)

class HybridSeqNet(nn.Module):
    def __init__(self, in_dim, hidden=64):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, num_layers=2, batch_first=True, dropout=0.1)
        self.gru = nn.GRU(in_dim, hidden, num_layers=1, batch_first=True)
        self.fc = nn.Sequential(
            nn.Linear(hidden * 2, 64),
            nn.ReLU(),
            nn.Linear(64, 3),
        )
    def forward(self, x):
        l_out, _ = self.lstm(x)
        g_out, _ = self.gru(x)
        comb = torch.cat([l_out[:, -1, :], g_out[:, -1, :]], dim=-1)
        return self.fc(comb)

dl_model = HybridSeqNet(len(features), hidden=64)
opt = torch.optim.Adam(dl_model.parameters(), lr=0.0025)
loss_fn = nn.MSELoss()

dl_model.train()
for _ in range(90):
    for bx, by in loader:
        opt.zero_grad()
        loss = loss_fn(dl_model(bx), by)
        loss.backward()
        opt.step()

dl_model.eval()
with torch.no_grad():
    te_p = dl_model(torch.tensor(X_te)).numpy()

dl_metrics = {}
for idx_h, h in enumerate([1, 3, 6]):
    dl_metrics[f"{h}m"] = {
        "r2": round(float(r2_score(y_te[:, idx_h], te_p[:, idx_h])), 4),
        "mae": round(float(mean_absolute_error(y_te[:, idx_h], te_p[:, idx_h])), 3),
        "rmse": round(float(root_mean_squared_error(y_te[:, idx_h], te_p[:, idx_h])), 3),
    }

torch.save({
    "state_dict": dl_model.state_dict(),
    "scaler_mean": scaler.mean_.tolist(),
    "scaler_scale": scaler.scale_.tolist(),
    "features": features,
    "seq_len": seq_len,
}, "aquatwin_dl_v2.pt")

summary = {
    "dataset": "telangana_upgraded_dataset.csv",
    "rows": int(len(df)),
    "feature_count": len(features),
    "xgboost_models": xgb_models,
    "xgboost_metrics": xgb_metrics,
    "dl_hybrid_lstm_gru_metrics": dl_metrics,
}
with open("ensemble_v2_report.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("XGBoost +1M/+3M/+6M R2:", {k: v["r2"] for k, v in xgb_metrics.items()})
print("Hybrid LSTM+GRU +1M/+3M/+6M R2:", {k: v["r2"] for k, v in dl_metrics.items()})
print("Saved aquatwin_dl_v2.pt & ensemble_v2_report.json")
