import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures = []

def check(cond, ok_msg, fail_msg):
    if cond:
        print(f"[PASS] {ok_msg}")
    else:
        print(f"[FAIL] {fail_msg}")
        failures.append(fail_msg)

# 1. Check 3-year datasets (1.1 - 1.4 + fused master)
for ds in ["water_3y.csv", "groundwater_3y.csv", "reservoirs_3y.csv", "rainfall_3y.csv", "telangana_master_3y.csv"]:
    dp = ROOT / "ml" / "data_3y" / ds
    check(dp.exists() and dp.stat().st_size > 50, f"3Y dataset present: ml/data_3y/{ds}", f"Missing 3Y dataset: ml/data_3y/{ds}")

# 2. Check +1M, +2M, +6M & +1Y (12M) forecasts across all 33 districts
pred_path = ROOT / "ml" / "ml_predictions.json"
if pred_path.exists():
    data = json.loads(pred_path.read_text(encoding="utf-8", errors="ignore"))
    dists = data.get("districts", [])
    req_keys = [
        "lstm_1m_wqi", "lstm_2m_wqi", "lstm_6m_wqi", "lstm_1y_wqi",
        "gw_pred_1m", "gw_pred_2m", "gw_pred_6m", "gw_pred_1y",
        "res_pred_1m", "res_pred_2m", "res_pred_6m", "res_pred_1y",
        "rain_pred_1m", "rain_pred_2m", "rain_pred_6m", "rain_pred_1y",
    ]
    ok_33 = len(dists) == 33 and all(all(k in d and d[k] is not None for k in req_keys) for d in dists)
    check(ok_33, "33/33 districts have +1M/+2M/+6M/+1Y(12M) forecasts across Water, GW, Reservoirs & Rainfall", "Missing districts or forecast keys in ml/ml_predictions.json")
else:
    check(False, "", "ml/ml_predictions.json missing")

# 3. Check frontend HTML & ML bundle if present
for rel_html in ["mobile-app/www/index.html", "mobile-app/index.html"]:
    hp = ROOT / rel_html
    if hp.exists():
        ht = hp.read_text(encoding="utf-8", errors="ignore")
        check("MULTIMODAL_3Y_FORECAST_START" in ht, f"{rel_html} has 3Y multi-modal forecast UI", f"Missing 3Y forecast UI in {rel_html}")

for rel_js in ["mobile-app/www/ml_data.js", "mobile-app/ml_data.js"]:
    jp = ROOT / rel_js
    if jp.exists():
        jt = jp.read_text(encoding="utf-8", errors="ignore")
        check("AQUATWIN_ML_DATA" in jt and "lstm_1y_wqi" in jt, f"{rel_js} has 12M (1Y) multi-modal bundle", f"Missing 12M/1Y bundle in {rel_js}")

# 4. Check web security headers if vercel.json exists
for rel_vj in ["mobile-app/www/vercel.json", "vercel.json"]:
    vjp = ROOT / rel_vj
    if vjp.exists():
        vjt = vjp.read_text(encoding="utf-8", errors="ignore")
        check("Content-Security-Policy" in vjt and "Strict-Transport-Security" in vjt,
              f"{rel_vj} has CSP & HSTS headers", f"Missing CSP/HSTS in {rel_vj}")

# 5. Compile backend & ML API scripts if present
for rel_py in ["backend/main.py", "ml/api_server.py"]:
    pp = ROOT / rel_py
    if pp.exists():
        c = subprocess.run([sys.executable, "-m", "py_compile", str(pp)], capture_output=True, text=True)
        check(c.returncode == 0, f"{rel_py} compiles cleanly", f"{rel_py} syntax error: {c.stderr.strip()}")

# 6. Verify SHA-256 manifest if present
ver_py = ROOT / "ml" / "verify_integrity.py"
man_json = ROOT / "ml" / "data_3y" / "integrity_manifest.json"
if ver_py.exists() and man_json.exists():
    vr = subprocess.run([sys.executable, str(ver_py)], capture_output=True, text=True)
    check(vr.returncode == 0, f"SHA-256 integrity verified ({vr.stdout.strip()})", f"SHA-256 mismatch: {vr.stdout.strip()} {vr.stderr.strip()}")

print("\n" + ("=== AUDIT PASSED ===" if not failures else f"=== AUDIT FAILED ({len(failures)}) ==="))
sys.exit(1 if failures else 0)
