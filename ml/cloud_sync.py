import os, glob, json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xgboost as xgb

df = pd.read_csv("telangana_36m_timeseries.csv").sort_values(["district", "year_month"]).reset_index(drop=True)

# Load trained XGBoost model
xgb_model = xgb.XGBRegressor()
xgb_model.load_model("aquatwin_xgb.json")
xgb_feats = [
    "month", "latitude", "longitude", "rainfall_mm", "temp_c",
    "pollution_idx", "ndwi_mean", "turbidity_index", "water_coverage_pct", "prev_wqi", "prev_turb"
]

# Load trained LSTM model
ckpt = torch.load("aquatwin_lstm.pt", map_location="cpu")
lstm_feats = ckpt["features"]
seq_len = int(ckpt["seq_len"])
mean_arr = np.array(ckpt["scaler_mean"], dtype=np.float32)
scale_arr = np.array(ckpt["scaler_scale"], dtype=np.float32)

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

lstm_model = AquaLSTM(input_size=len(lstm_feats), hidden_size=64)
lstm_model.load_state_dict(ckpt["model_state"])
lstm_model.eval()

# Also load raw coordinates/metrics if available
base_map = {}
csv_matches = glob.glob(r"..\**\*telangana*.csv", recursive=True)
if csv_matches:
    bdf = pd.read_csv(csv_matches[0])
    for _, r in bdf.iterrows():
        if "district" in r:
            base_map[str(r["district"]).strip().lower()] = r

results = []
for dist_name, grp in df.groupby("district"):
    grp = grp.sort_values("year_month").reset_index(drop=True)
    latest = grp.iloc[-1]

    xgb_pred = float(np.clip(xgb_model.predict(grp[xgb_feats].tail(1))[0], 15.0, 98.0))

    win = grp[lstm_feats].tail(seq_len).values.astype(np.float32).copy()
    forecast_6m = []
    with torch.no_grad():
        for step in range(1, 7):
            norm_win = (win - mean_arr) / np.where(scale_arr == 0, 1.0, scale_arr)
            p_val = float(np.clip(lstm_model(torch.tensor(norm_win).unsqueeze(0)).item(), 15.0, 98.0))
            forecast_6m.append({"month": f"+{step}M", "lstm_wqi": round(p_val, 1)})
            nxt = win[-1].copy()
            nxt[0] = (int(nxt[0]) % 12) + 1
            nxt[9] = p_val
            win = np.vstack([win[1:], nxt])

    turb = float(latest["turbidity_index"])
    water = float(latest["water_coverage_pct"])
    ndwi = float(latest["ndwi_mean"])
    status = "High Turbidity" if turb >= 1.15 else ("Low Water" if water < 1.0 else "Normal")
    risk_level = "High Risk" if xgb_pred < 55 else ("Moderate Risk" if xgb_pred < 72 else "Low Risk")

    results.append({
        "district": str(dist_name).strip(),
        "latitude": float(latest["latitude"]),
        "longitude": float(latest["longitude"]),
        "ndwi_mean": round(ndwi, 4),
        "turbidity_index": round(turb, 4),
        "water_coverage_pct": round(water, 4),
        "status": status,
        "risk_level": risk_level,
        "xgb_wqi": round(xgb_pred, 1),
        "lstm_1m_wqi": forecast_6m[0]["lstm_wqi"],
        "lstm_6m_wqi": forecast_6m[-1]["lstm_wqi"],
        "forecast_6m": forecast_6m,
    })

results.sort(key=lambda x: x["district"])
payload = {
    "project": "AquaTwin AI",
    "state": "Telangana",
    "district_count": len(results),
    "models": {"xgboost": "aquatwin_xgb.json", "lstm": "aquatwin_lstm.pt"},
    "districts": results,
}

with open("ml_predictions.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

# Copy into mobile-app/www/ so offline/sync bundle stays current
mobile_out = r"..\mobile-app\www\ml_predictions.json"
if os.path.exists(r"..\mobile-app\www"):
    with open(mobile_out, "w", encoding="utf-8") as f:
        json.dump(payload, f)

# Optional Neon / PostgreSQL sync if DATABASE_URL is set
db_url = os.environ.get("DATABASE_URL", "").strip()
if db_url:
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS aquatwin_predictions (
                district TEXT PRIMARY KEY,
                xgb_wqi REAL,
                lstm_1m_wqi REAL,
                lstm_6m_wqi REAL,
                turbidity_index REAL,
                water_coverage_pct REAL,
                ndwi_mean REAL,
                risk_level TEXT,
                status TEXT,
                payload_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for d in results:
            cur.execute("""
                INSERT INTO aquatwin_predictions
                (district, xgb_wqi, lstm_1m_wqi, lstm_6m_wqi, turbidity_index, water_coverage_pct, ndwi_mean, risk_level, status, payload_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (district) DO UPDATE SET
                  xgb_wqi=EXCLUDED.xgb_wqi,
                  lstm_1m_wqi=EXCLUDED.lstm_1m_wqi,
                  lstm_6m_wqi=EXCLUDED.lstm_6m_wqi,
                  turbidity_index=EXCLUDED.turbidity_index,
                  water_coverage_pct=EXCLUDED.water_coverage_pct,
                  ndwi_mean=EXCLUDED.ndwi_mean,
                  risk_level=EXCLUDED.risk_level,
                  status=EXCLUDED.status,
                  payload_json=EXCLUDED.payload_json,
                  updated_at=CURRENT_TIMESTAMP
            """, (
                d["district"], d["xgb_wqi"], d["lstm_1m_wqi"], d["lstm_6m_wqi"],
                d["turbidity_index"], d["water_coverage_pct"], d["ndwi_mean"],
                d["risk_level"], d["status"], json.dumps(d)
            ))
        conn.commit()
        cur.close()
        conn.close()
        print("Synced all 33 districts to PostgreSQL/Neon!")
    except Exception as e:
        print("Cloud DB note (local JSON still saved):", e)
else:
    print("No DATABASE_URL set — saved local sync payload (ml_predictions.json) ready for cloud push.")

print(f"Exported {len(results)} district ML+LSTM predictions to ml_predictions.json")
