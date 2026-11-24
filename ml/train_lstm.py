import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error

torch.manual_seed(42)
np.random.seed(42)

df = pd.read_csv("telangana_36m_timeseries.csv").sort_values(["district", "year_month"]).reset_index(drop=True)

feat_cols = [
    "month", "latitude", "longitude", "rainfall_mm", "temp_c",
    "pollution_idx", "ndwi_mean", "turbidity_index", "water_coverage_pct", "prev_wqi"
]
target_col = "wqi_score"
seq_len = 6  # Use 6 past months to predict next month's WQI

X_seqs, y_seqs = [], []
for _, grp in df.groupby("district"):
    grp = grp.reset_index(drop=True)
    vals = grp[feat_cols].values.astype(np.float32)
    tgts = grp[target_col].values.astype(np.float32)
    for i in range(seq_len, len(grp)):
        X_seqs.append(vals[i - seq_len:i])
        y_seqs.append(tgts[i])

X_all = np.array(X_seqs)
y_all = np.array(y_seqs)

split_idx = int(len(X_all) * 0.8)
X_tr_raw, X_te_raw = X_all[:split_idx], X_all[split_idx:]
y_tr, y_te = y_all[:split_idx], y_all[split_idx:]

scaler = StandardScaler()
X_tr = scaler.fit_transform(X_tr_raw.reshape(-1, len(feat_cols))).reshape(X_tr_raw.shape)
X_te = scaler.transform(X_te_raw.reshape(-1, len(feat_cols))).reshape(X_te_raw.shape)

train_loader = DataLoader(
    TensorDataset(torch.tensor(X_tr), torch.tensor(y_tr).unsqueeze(1)),
    batch_size=32,
    shuffle=True,
)

class AquaLSTM(nn.Module):
    def __init__(self, input_size, hidden_size=64):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=2, batch_first=True, dropout=0.1)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])

model = AquaLSTM(input_size=len(feat_cols), hidden_size=64)
opt = torch.optim.Adam(model.parameters(), lr=0.003)
loss_fn = nn.MSELoss()

model.train()
for epoch in range(80):
    for bx, by in train_loader:
        opt.zero_grad()
        pred = model(bx)
        loss = loss_fn(pred, by)
        loss.backward()
        opt.step()

model.eval()
with torch.no_grad():
    te_preds = model(torch.tensor(X_te)).squeeze(1).numpy()

r2 = r2_score(y_te, te_preds)
mae = mean_absolute_error(y_te, te_preds)
rmse = root_mean_squared_error(y_te, te_preds)

# Roll out 6-month forecast for Hyderabad from latest 6 months
hyd = df[df["district"].str.lower() == "hyderabad"].tail(seq_len).copy()
if len(hyd) == 0:
    hyd = df[df["district"] == df["district"].iloc[0]].tail(seq_len).copy()

roll_vals = hyd[feat_cols].values.astype(np.float32).copy()
last_wqi = float(hyd[target_col].iloc[-1])
forecast_6m = []

with torch.no_grad():
    for step in range(1, 7):
        scaled_win = scaler.transform(roll_vals.reshape(-1, len(feat_cols))).reshape(1, seq_len, len(feat_cols))
        pred_wqi = float(np.clip(model(torch.tensor(scaled_win)).item(), 15.0, 98.0))
        forecast_6m.append({"step": f"+{step}M", "wqi": round(pred_wqi, 1)})

        next_row = roll_vals[-1].copy()
        next_row[0] = ((int(next_row[0]) % 12) + 1)  # next month 1..12
        next_row[9] = pred_wqi  # prev_wqi
        roll_vals = np.vstack([roll_vals[1:], next_row])

torch.save({
    "model_state": model.state_dict(),
    "scaler_mean": scaler.mean_.tolist(),
    "scaler_scale": scaler.scale_.tolist(),
    "features": feat_cols,
    "seq_len": seq_len,
}, "aquatwin_lstm.pt")

with open("model_benchmark.json", "w") as f:
    json.dump({
        "lstm_r2": round(float(r2), 4),
        "lstm_mae": round(float(mae), 3),
        "lstm_rmse": round(float(rmse), 3),
        "sample_district": str(hyd["district"].iloc[0]),
        "forecast_6m": forecast_6m,
    }, f, indent=2)

print(f"LSTM Test R2: {r2:.4f} | MAE: {mae:.3f} | RMSE: {rmse:.3f}")
print("Sample 6-Month LSTM Forecast (" + str(hyd["district"].iloc[0]) + "):", forecast_6m)
print("Saved model: aquatwin_lstm.pt")
