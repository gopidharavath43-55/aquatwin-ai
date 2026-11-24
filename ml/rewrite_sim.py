import re

with open("api_server.py", "r", encoding="utf-8") as f:
    src = f.read()

marker = "@app.post(\"/simulate\")"
idx = src.find(marker)
if idx == -1:
    marker = "@app.post('/simulate')"
    idx = src.find(marker)

new_sim = '''@app.post("/simulate")
def simulate(req: SimRequest):
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
        old_pol = float(pd.to_numeric(grp.iloc[-1].get("pollution_idx"), errors="coerce") or 45.0)
        new_pol = float(req.pollution_idx)
        old_turb = float(pd.to_numeric(row.get("turbidity_index"), errors="coerce") or 1.0)
        row["pollution_idx"] = new_pol
        row["turbidity_index"] = max(0.4, old_turb + (new_pol - old_pol) * 0.003)

    xgb_cols = [
        "month", "latitude", "longitude", "rainfall_mm", "temp_c", "evap_mm",
        "pollution_idx", "reservoir_idx", "ndwi_mean", "ndmi_proxy",
        "turbidity_index", "water_coverage_pct", "anomaly_flag",
        "prev_wqi", "prev_turb", "prev_water", "wqi_score"
    ]

    def _num(val, default=0.0):
        v = pd.to_numeric(val, errors="coerce")
        return float(default) if pd.isna(v) else float(v)

    safe_row = {c: _num(row.get(c), 0.0) for c in xgb_cols}
    safe_row["month"] = int(round(safe_row["month"]))
    safe_row["anomaly_flag"] = int(round(safe_row["anomaly_flag"]))
    x_df = pd.DataFrame([safe_row])[xgb_cols]

    p_1m = float(np.clip(xgb_1m.predict(x_df)[0], 15.0, 98.5))
    p_6m = float(np.clip(xgb_6m.predict(x_df)[0], 15.0, 98.5))

    win = grp[dl_feats].tail(seq_len).apply(pd.to_numeric, errors="coerce").fillna(0.0).values.astype(np.float32).copy()
    if len(win) == 0:
        win = np.zeros((seq_len, len(dl_feats)), dtype=np.float32)
    elif len(win) < seq_len:
        win = np.vstack([np.repeat(win[:1], seq_len - len(win), axis=0), win])
    win[-1] = np.array([_num(row.get(c), 0.0) for c in dl_feats], dtype=np.float32)

    denom = np.where(np.abs(scale_arr) < 1e-6, 1.0, scale_arr)
    norm_win = (win - mean_arr) / denom
    with torch.no_grad():
        dl_out = dl_model(torch.tensor(norm_win, dtype=torch.float32).unsqueeze(0)).squeeze(0).numpy()

    return {
        "district": str(row.get("district") or req.district),
        "simulated_inputs": {
            "rainfall_mm": round(_num(row.get("rainfall_mm"), 0.0), 2),
            "temp_c": round(_num(row.get("temp_c"), 0.0), 2),
            "pollution_idx": round(_num(row.get("pollution_idx"), 0.0), 2),
        },
        "xgb_wqi_1m": round(p_1m, 1),
        "xgb_wqi_6m": round(p_6m, 1),
        "dl_forecast": {
            "wqi_1m": round(float(np.clip(dl_out[0], 15.0, 98.5)), 1),
            "wqi_3m": round(float(np.clip(dl_out[1], 15.0, 98.5)), 1),
            "wqi_6m": round(float(np.clip(dl_out[2], 15.0, 98.5)), 1),
        },
    }
'''

if idx != -1:
    src = src[:idx] + new_sim
    with open("api_server.py", "w", encoding="utf-8") as f:
        f.write(src)
    print("Replaced /simulate cleanly.")
else:
    print("Could not locate @app.post('/simulate') in api_server.py")
