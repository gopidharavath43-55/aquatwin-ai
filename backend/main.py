import csv
import math
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AquaTwin AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent


class SimulationRequest(BaseModel):
    district: str
    rainfall_change_pct: float = 0.0   # -50% to +50%
    temp_change_c: float = 0.0         # -3°C to +5°C
    pollution_load_pct: float = 0.0    # -30% to +50%


def find_csv():
    data_dirs = [BASE_DIR.parent / "data", BASE_DIR / "data", Path.cwd() / "data"]
    for d in data_dirs:
        if d.exists():
            for f in sorted(d.rglob("*.csv")):
                if "telangana" in f.name.lower():
                    return f
    other_dirs = [BASE_DIR.parent, BASE_DIR, Path.cwd(), Path.home() / "Downloads"]
    for d in other_dirs:
        if d.exists():
            for f in sorted(d.glob("*.csv")):
                if "telangana" in f.name.lower():
                    return f
    return None


def to_value(val):
    if val is None or val.strip() == "":
        return None
    try:
        num = float(val)
        return round(num, 4) if math.isfinite(num) else None
    except ValueError:
        return val.strip()


def get_status(turbidity, water_pct):
    if turbidity is None:
        return "Unknown"
    if turbidity >= 1.15:
        return "High Turbidity"
    if water_pct is not None and water_pct < 1.0:
        return "Low Water"
    return "Normal"


def compute_ai_metrics(turbidity, water_pct, ndwi):
    t = turbidity if turbidity is not None else 1.0
    w = water_pct if water_pct is not None else 1.5
    n = ndwi if ndwi is not None else -0.45

    # AI Water Quality Index (0-100)
    score = 88.0 - max(0.0, (t - 0.95) * 110.0) + min(10.0, w * 2.2) + (n + 0.5) * 20.0
    wqi_score = round(max(15.0, min(98.0, score)), 1)

    if wqi_score < 55:
        risk = "High Risk"
        action = "Deploy sediment filtration & inspect runoff sources immediately."
    elif wqi_score < 72:
        risk = "Moderate Risk"
        action = "Increase weekly monitoring & optimize local reservoir inflow."
    else:
        risk = "Low Risk"
        action = "Water clarity and storage levels are within safe targets."

    if w < 1.0:
        action = "Trigger drought conservation plan & prioritize groundwater recharge."

    return {
        "wqi_score": wqi_score,
        "risk_level": risk,
        "ai_recommendation": action,
    }


def load_all_districts():
    csv_path = find_csv()
    if not csv_path:
        return []

    records = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            row.pop("system:index", None)
            row.pop(".geo", None)
            item = {k: to_value(v) for k, v in row.items() if k}
            item["status"] = get_status(
                item.get("turbidity_index"),
                item.get("water_coverage_pct"),
            )
            item.update(
                compute_ai_metrics(
                    item.get("turbidity_index"),
                    item.get("water_coverage_pct"),
                    item.get("ndwi_mean"),
                )
            )
            records.append(item)
    return records


@app.get("/")
def home():
    return {"message": "AquaTwin AI backend is running!"}


@app.get("/districts")
def get_districts():
    records = load_all_districts()
    if not records:
        return {"error": "No Telangana CSV found"}
    return {"count": len(records), "districts": records}


@app.post("/simulate")
def simulate_digital_twin(req: SimulationRequest):
    records = load_all_districts()
    target = next(
        (d for d in records if str(d.get("district", "")).lower() == req.district.lower()),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail=f"District '{req.district}' not found")

    base_turb = target.get("turbidity_index") or 1.05
    base_water = target.get("water_coverage_pct") or 1.5
    base_ndwi = target.get("ndwi_mean") or -0.45

    # Digital Twin projection model
    water_factor = 1.0 + (req.rainfall_change_pct * 0.009) - (req.temp_change_c * 0.045)
    sim_water = round(max(0.1, base_water * water_factor), 4)

    runoff_turb = max(0.0, req.rainfall_change_pct) * 0.0018
    pollution_turb = req.pollution_load_pct * 0.0045
    evap_turb = max(0.0, req.temp_change_c) * 0.015
    sim_turb = round(max(0.5, base_turb + runoff_turb + pollution_turb + evap_turb), 4)

    sim_ndwi = round(max(-1.0, min(1.0, base_ndwi + (sim_water - base_water) * 0.04)), 4)
    sim_status = get_status(sim_turb, sim_water)
    sim_ai = compute_ai_metrics(sim_turb, sim_water, sim_ndwi)

    # 6-month forecast curve
    forecast_6m = []
    for m in range(1, 7):
        ratio = m / 6.0
        m_turb = round(base_turb + (sim_turb - base_turb) * ratio, 4)
        m_water = round(base_water + (sim_water - base_water) * ratio, 4)
        m_ndwi = round(base_ndwi + (sim_ndwi - base_ndwi) * ratio, 4)
        m_ai = compute_ai_metrics(m_turb, m_water, m_ndwi)
        forecast_6m.append({
            "month": f"Month +{m}",
            "turbidity_index": m_turb,
            "water_coverage_pct": m_water,
            "wqi_score": m_ai["wqi_score"],
        })

    return {
        "district": target["district"],
        "inputs": req.model_dump(),
        "baseline": {
            "turbidity_index": base_turb,
            "water_coverage_pct": base_water,
            "status": target["status"],
            "wqi_score": target["wqi_score"],
        },
        "simulated": {
            "turbidity_index": sim_turb,
            "water_coverage_pct": sim_water,
            "ndwi_mean": sim_ndwi,
            "status": sim_status,
            **sim_ai,
        },
        "forecast_6m": forecast_6m,
    }