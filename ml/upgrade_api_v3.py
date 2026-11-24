with open("api_server.py", "r", encoding="utf-8") as f:
    src = f.read()

v3_block = '''
# --- AQUATWIN V3 NEXT-GEN MODELS ---
import joblib as _joblib

_ens_v3 = _joblib.load("aquatwin_ensemble_v3.pkl")
_anom_v3 = _joblib.load("aquatwin_anomaly_v3.pkl")
_st_ckpt = torch.load("aquatwin_st_attn_v3.pt", map_location="cpu", weights_only=False)

class _STQuantileNet(torch.nn.Module):
    def __init__(self, in_dim, d_model=64):
        super().__init__()
        self.proj = torch.nn.Linear(in_dim, d_model)
        self.attn = torch.nn.MultiheadAttention(embed_dim=d_model, num_heads=4, batch_first=True)
        self.gru = torch.nn.GRU(d_model, d_model, batch_first=True)
        self.head = torch.nn.Sequential(torch.nn.Linear(d_model, 48), torch.nn.GELU(), torch.nn.Linear(48, 9))
    def forward(self, x):
        h = torch.relu(self.proj(x))
        attn_out, _ = self.attn(h, h, h)
        _, last = self.gru(h + attn_out)
        return self.head(last.squeeze(0)).view(-1, 3, 3)

_st_model = _STQuantileNet(len(_st_ckpt["features"]))
_st_model.load_state_dict(_st_ckpt["state_dict"])
_st_model.eval()

def _run_stack_v3(stack_obj, vec):
    base = np.column_stack([
        stack_obj["xgb"].predict(vec),
        stack_obj["hgb"].predict(vec),
        stack_obj["et"].predict(vec)
    ])
    return float(np.clip(stack_obj["meta"].predict(base)[0], 15.0, 98.5))

@app.get("/anomalies")
def get_anomalies():
    cols = _anom_v3["cols"]
    iso = _anom_v3["iso"]
    min_s, max_s = _anom_v3["min_s"], _anom_v3["max_s"]
    alerts = []
    for dist, grp in df.groupby("district"):
        last = grp.iloc[-1]
        vec = np.array([[float(pd.to_numeric(last.get(c), errors="coerce") or 0.0) for c in cols]])
        raw = float(-iso.decision_function(vec)[0])
        score = round(float(np.clip((raw - min_s) / (max_s - min_s + 1e-6) * 100.0, 2.0, 99.0)), 1)
        alerts.append({
            "district": str(dist),
            "anomaly_score": score,
            "status": "Critical Alert" if score >= 75 else ("Watch" if score >= 48 else "Normal")
        })
    alerts.sort(key=lambda x: x["anomaly_score"], reverse=True)
    return {"top_alerts": alerts[:10], "all_districts": alerts}

@app.post("/predict-v3")
def predict_v3(req: SimRequest):
    key = _norm_district(req.district)
    grp = df[df["district"].apply(_norm_district) == key].sort_values("year_month").reset_index(drop=True)
    if grp.empty:
        raise HTTPException(status_code=404, detail="District not found")
    row = grp.iloc[-1].copy()
    if req.rainfall_mm is not None:
        row["rainfall_mm"] = float(req.rainfall_mm)
    if req.temp_c is not None:
        row["temp_c"] = float(req.temp_c)
    if req.pollution_idx is not None:
        row["pollution_idx"] = float(req.pollution_idx)

    feats = _ens_v3["features"]
    vec = np.array([[float(pd.to_numeric(row.get(c), errors="coerce") or 0.0) for c in feats]], dtype=np.float32)
    ens_1m = _run_stack_v3(_ens_v3["stack_1m"], vec)
    ens_6m = _run_stack_v3(_ens_v3["stack_6m"], vec)

    seq_len = _st_ckpt["seq_len"]
    raw_seq = grp[feats].tail(seq_len).apply(pd.to_numeric, errors="coerce").fillna(0.0).values.astype(np.float32)
    if len(raw_seq) < seq_len:
        raw_seq = np.vstack([np.repeat(raw_seq[:1], seq_len - len(raw_seq), axis=0), raw_seq])
    raw_seq[-1] = vec[0]
    norm_seq = (raw_seq - _st_ckpt["mean"]) / np.where(np.abs(_st_ckpt["scale"]) < 1e-6, 1.0, _st_ckpt["scale"])
    with torch.no_grad():
        q = _st_model(torch.tensor(norm_seq).unsqueeze(0)).squeeze(0).numpy()

    acols = _anom_v3["cols"]
    avec = np.array([[float(pd.to_numeric(row.get(c), errors="coerce") or 0.0) for c in acols]])
    araw = float(-_anom_v3["iso"].decision_function(avec)[0])
    ascore = round(float(np.clip((araw - _anom_v3["min_s"]) / (_anom_v3["max_s"] - _anom_v3["min_s"] + 1e-6) * 100.0, 2.0, 99.0)), 1)

    return {
        "district": str(row.get("district") or req.district),
        "ensemble_wqi_1m": round(ens_1m, 1),
        "ensemble_wqi_6m": round(ens_6m, 1),
        "quantile_forecast": {
            "wqi_1m": {"p10": round(float(q[0,0]), 1), "median": round(float(q[0,1]), 1), "p90": round(float(q[0,2]), 1)},
            "wqi_3m": {"p10": round(float(q[1,0]), 1), "median": round(float(q[1,1]), 1), "p90": round(float(q[1,2]), 1)},
            "wqi_6m": {"p10": round(float(q[2,0]), 1), "median": round(float(q[2,1]), 1), "p90": round(float(q[2,2]), 1)},
        },
        "anomaly_score": ascore,
        "anomaly_status": "Critical Alert" if ascore >= 75 else ("Watch" if ascore >= 48 else "Normal")
    }
'''

if "AQUATWIN V3 NEXT-GEN MODELS" not in src:
    src = src + "\n" + v3_block
    with open("api_server.py", "w", encoding="utf-8") as f:
        f.write(src)
    print("Added /predict-v3 and /anomalies to api_server.py!")
else:
    print("v3 endpoints already present.")
