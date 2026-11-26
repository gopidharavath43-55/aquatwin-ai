import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AquaTwin AI Intelligence API", version="2.0")

# AQUATWIN_ZERO_TRUST_V1
try:
    import sys as _at_sys
    from pathlib import Path as _at_Path
    _at_root = str(_at_Path(__file__).resolve().parent.parent)
    if _at_root not in _at_sys.path:
        _at_sys.path.insert(0, _at_root)
    from backend.zero_trust_shield import attach_zero_trust as _attach_zero_trust
    _attach_zero_trust(app)
except Exception as _at_zt_err:
    import logging as _at_log
    _at_log.getLogger("aquatwin.zero_trust").warning("Zero-trust shield skipped: %s", _at_zt_err)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df = pd.read_csv("telangana_upgraded_dataset.csv").sort_values(["district", "year_month"]).reset_index(drop=True)
with open("ml_predictions.json", encoding="utf-8") as f:
    base_predictions = json.load(f)

xgb_1m = xgb.XGBRegressor()
xgb_1m.load_model("aquatwin_xgb_1m.json")
xgb_6m = xgb.XGBRegressor()
xgb_6m.load_model("aquatwin_xgb_6m.json")

ckpt = torch.load("aquatwin_dl_v2.pt", map_location="cpu")
dl_feats = ckpt["features"]
seq_len = int(ckpt["seq_len"])
mean_arr = np.array(ckpt["scaler_mean"], dtype=np.float32)
scale_arr = np.array(ckpt["scaler_scale"], dtype=np.float32)

class HybridSeqNet(nn.Module):
    def __init__(self, in_dim, hidden=64):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, num_layers=2, batch_first=True, dropout=0.1)
        self.gru = nn.GRU(in_dim, hidden, num_layers=1, batch_first=True)
        self.fc = nn.Sequential(nn.Linear(hidden * 2, 64), nn.ReLU(), nn.Linear(64, 3))
    def forward(self, x):
        l_out, _ = self.lstm(x)
        g_out, _ = self.gru(x)
        return self.fc(torch.cat([l_out[:, -1, :], g_out[:, -1, :]], dim=-1))

dl_model = HybridSeqNet(len(dl_feats), hidden=64)
dl_model.load_state_dict(ckpt["state_dict"])
dl_model.eval()


def _norm_district(name: str) -> str:
    s = re.sub(r"\s*(digital\s*twin|twin|district)\s*$", "", str(name or ""), flags=re.I)
    return re.sub(r"\s+", " ", s).strip().lower()


class SimRequest(BaseModel):
    district: str
    rainfall_mm: float | None = None
    temp_c: float | None = None
    pollution_idx: float | None = None

@app.get("/health")
def health():
    return {"status": "online", "service": "AquaTwin AI FastAPI", "districts": len(base_predictions.get("districts", []))}

@app.get("/districts")
def all_districts():
    return base_predictions

@app.get("/districts/{name}")
def district_detail(name: str):
    key = _norm_district(name)
    for item in base_predictions.get("districts", []):
        if _norm_district(item["district"]) == key:
            history = df[df["district"].apply(_norm_district) == key].tail(12).to_dict(orient="records")
            return {"prediction": item, "recent_history": history}
    raise HTTPException(status_code=404, detail="District not found")

@app.post("/simulate")
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
@app.get("/forecast/{district}")
def get_multimodal_forecast(district: str):
    key = district.strip().lower()
    with open("ml_predictions.json", encoding="utf-8") as f:
        latest_bundle = json.load(f)
    for item in latest_bundle.get("districts", []):
        if item["district"].lower() == key:
            return {
                "district": item["district"],
                "model_version": latest_bundle.get("model_version", "AquaTwin-3Y-MultiModal-v2"),
                "trained_window": latest_bundle.get("trained_window", "36 months"),
                "horizons": {
                    "now": {
                        "wqi": item.get("wqi_score"),
                        "gw_depth_mbgl": item.get("gw_depth_mbgl"),
                        "res_storage_pct": item.get("res_storage_pct"),
                        "rainfall_mm": item.get("rainfall_mm"),
                    },
                    "+1M": {
                        "wqi": item.get("lstm_1m_wqi"),
                        "gw_depth_mbgl": item.get("gw_pred_1m"),
                        "res_storage_pct": item.get("res_pred_1m"),
                        "rainfall_mm": item.get("rain_pred_1m"),
                    },
                    "+2M": {
                        "wqi": item.get("lstm_2m_wqi"),
                        "gw_depth_mbgl": item.get("gw_pred_2m"),
                        "res_storage_pct": item.get("res_pred_2m"),
                        "rainfall_mm": item.get("rain_pred_2m"),
                    },
                    "+6M": {
                        "wqi": item.get("lstm_6m_wqi"),
                        "gw_depth_mbgl": item.get("gw_pred_6m"),
                        "res_storage_pct": item.get("res_pred_6m"),
                        "rainfall_mm": item.get("rain_pred_6m"),
                    },
                    "+1Y": {
                        "wqi": item.get("lstm_1y_wqi"),
                        "gw_depth_mbgl": item.get("gw_pred_1y"),
                        "res_storage_pct": item.get("res_pred_1y"),
                        "rainfall_mm": item.get("rain_pred_1y"),
                    },
                },
                "reservoir_name": item.get("reservoir_name"),
                "river_basin": item.get("river_basin"),
                "hydro_stress_index": item.get("hydro_stress_index"),
            }
    raise HTTPException(status_code=404, detail="District not found")
# AQUATWIN_ML_STRONG_SECURITY
import hmac as _at_hmac
import os as _at_os
import re as _at_re
from fastapi import Request as _AtRequest
from fastapi.responses import JSONResponse as _AtJSONResponse
from verify_integrity import verify_all as _at_verify_integrity

_AT_CLIENT_TOKEN = _at_os.environ.get("AQUATWIN_CLIENT_TOKEN", "aquatwin-v1")
_AT_DISTRICT_RE = _at_re.compile(r"^[A-Za-z0-9\s\-]{2,40}$")

@app.middleware("http")
async def _at_strong_security_middleware(request: _AtRequest, call_next):
    # 1. Block oversized payload floods (> 16 KB)
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > 16384:
        return _AtJSONResponse(
            status_code=413,
            content={"ok": False, "code": "PAYLOAD_TOO_LARGE", "message": "Payload exceeds 16 KB limit."},
        )

    # 2. Enforce X-App-Client token on protected endpoints (/simulate, /forecast)
    path = request.url.path or ""
    if request.method != "OPTIONS" and (path.startswith("/simulate") or path.startswith("/forecast")):
        supplied = request.headers.get("X-App-Client", "")
        if not _at_hmac.compare_digest(supplied, _AT_CLIENT_TOKEN):
            return _AtJSONResponse(
                status_code=403,
                content={"ok": False, "code": "UNAUTHORIZED_CLIENT", "message": "Valid X-App-Client header required."},
            )

    # 3. Validate district name path parameter against injection / traversal
    if path.startswith("/forecast/") or path.startswith("/districts/"):
        seg = path.rsplit("/", 1)[-1].replace("%20", " ")
        if not _AT_DISTRICT_RE.match(seg):
            return _AtJSONResponse(
                status_code=400,
                content={"ok": False, "code": "INVALID_DISTRICT", "message": "Invalid district parameter format."},
            )

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    return response

@app.get("/security/status")
def security_integrity_status():
    res = _at_verify_integrity()
    return {
        "ok": res["ok"],
        "integrity_verified": res["ok"],
        "protected_artifacts": res["checked"],
        "headers_enforced": True,
        "client_guard": True,
    }
