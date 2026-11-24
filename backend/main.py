import csv
import logging
import math
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

logger = logging.getLogger("aquatwin.security")
IS_PROD = os.getenv("ENV", "development").lower() == "production"

# 1. Disable public Swagger/OpenAPI docs in production
app = FastAPI(
    title="AquaTwin AI Backend",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)

# 2. Strict CORS allowlist (no wildcard "*")
ALLOWED_ORIGINS = [
    "https://www-gold-five.vercel.app",
    "https://aquatwin-ai.vercel.app",
    "https://localhost",
    "capacitor://localhost",
    "http://localhost",
    "http://127.0.0.1:5500",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-App-Client"],
)

# 3. Burst & DDoS rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

BASE_DIR = Path(__file__).resolve().parent

@app.middleware("http")
async def security_headers_and_size_guard(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > 16384:
        return JSONResponse(
            status_code=413,
            content={"ok": False, "code": "PAYLOAD_TOO_LARGE", "message": "Request payload exceeds 16 KB limit."},
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response



# 4. Convert all unexpected/unwanted errors into clean, expected JSON
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "ok": False,
            "code": "RATE_LIMITED",
            "message": "Too many requests. Please wait a minute and try again.",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "code": "INVALID_INPUT",
            "message": "One or more input fields are invalid or outside allowed limits.",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "code": "SERVER_ERROR",
            "message": "Something went wrong. Please try again later.",
        },
    )


# 5. Strict input validation & numeric bounds
class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    district: str = Field(..., min_length=2, max_length=60, pattern=r"^[A-Za-z0-9\s\-]+$")
    rainfall_change_pct: float = Field(0.0, ge=-50.0, le=50.0)
    temp_change_c: float = Field(0.0, ge=-3.0, le=5.0)
    pollution_load_pct: float = Field(0.0, ge=-30.0, le=50.0)


def find_csv():
    # Restricted strictly to project data directories (never scan user Downloads)
    data_dirs = [BASE_DIR.parent / "data", BASE_DIR / "data"]
    for d in data_dirs:
        if d.exists():
            for f in sorted(d.rglob("*.csv")):
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
@limiter.limit("60/minute")
def home(request: Request):
    return {"ok": True, "message": "AquaTwin AI backend is running!"}


@app.get("/health")
@limiter.limit("60/minute")
def health(request: Request):
    return {"ok": True, "status": "online", "service": "AquaTwin AI FastAPI"}


@app.get("/districts")
@limiter.limit("30/minute")
def get_districts(request: Request):
    records = load_all_districts()
    if not records:
        raise HTTPException(status_code=503, detail="District data temporarily unavailable.")
    return {"ok": True, "count": len(records), "districts": records}


@app.post("/simulate")
@limiter.limit("20/minute")
def simulate_digital_twin(request: Request, req: SimulationRequest):
    records = load_all_districts()
    target = next(
        (d for d in records if str(d.get("district", "")).lower() == req.district.strip().lower()),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail="Requested district was not found.")

    base_turb = target.get("turbidity_index") or 1.05
    base_water = target.get("water_coverage_pct") or 1.5
    base_ndwi = target.get("ndwi_mean") or -0.45

    water_factor = 1.0 + (req.rainfall_change_pct * 0.009) - (req.temp_change_c * 0.045)
    sim_water = round(max(0.1, base_water * water_factor), 4)

    runoff_turb = max(0.0, req.rainfall_change_pct) * 0.0018
    pollution_turb = req.pollution_load_pct * 0.0045
    evap_turb = max(0.0, req.temp_change_c) * 0.015
    sim_turb = round(max(0.5, base_turb + runoff_turb + pollution_turb + evap_turb), 4)

    sim_ndwi = round(max(-1.0, min(1.0, base_ndwi + (sim_water - base_water) * 0.04)), 4)
    sim_status = get_status(sim_turb, sim_water)
    sim_ai = compute_ai_metrics(sim_turb, sim_water, sim_ndwi)

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
        "ok": True,
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