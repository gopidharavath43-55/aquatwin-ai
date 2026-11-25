import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors = []

def check(cond, ok_msg, fail_msg):
    if cond:
        print(f"[PASS] {ok_msg}")
    else:
        print(f"[FAIL] {fail_msg}")
        errors.append(fail_msg)

# A. Verify 3-year datasets exist
for ds in ["water_3y.csv", "groundwater_3y.csv", "reservoirs_3y.csv", "rainfall_3y.csv", "telangana_master_3y.csv"]:
    dp = ROOT / "ml" / "data_3y" / ds
    check(dp.exists() and dp.stat().st_size > 100, f"3Y dataset present: ml/data_3y/{ds}", f"Missing 3Y dataset: ml/data_3y/{ds}")

# B. Verify 33-district +1M / +2M / +6M / +1Y (12M) forecasts across all 4 domains
pred_path = ROOT / "ml" / "ml_predictions.json"
if pred_path.exists():
    bundle = json.loads(pred_path.read_text(encoding="utf-8"))
    dists = bundle.get("districts", [])
    req_keys = [
        "lstm_1m_wqi", "lstm_2m_wqi", "lstm_6m_wqi", "lstm_1y_wqi",
        "gw_pred_1m", "gw_pred_2m", "gw_pred_6m", "gw_pred_1y",
        "res_pred_1m", "res_pred_2m", "res_pred_6m", "res_pred_1y",
        "rain_pred_1m", "rain_pred_2m", "rain_pred_6m", "rain_pred_1y",
    ]
    ok_33 = len(dists) == 33 and all(all(k in d and d[k] is not None for k in req_keys) for d in dists)
    check(ok_33, "33/33 districts have +1M/+2M/+6M/+1Y(12M) forecasts for Water, GW, Reservoirs & Rainfall", "Incomplete forecast keys or district count in ml/ml_predictions.json")
else:
    check(False, "", "ml/ml_predictions.json missing")

# C. Verify frontend bundle & forecast/security blocks
for rel_html in ["mobile-app/index.html", "mobile-app/www/index.html"]:
    hp = ROOT / rel_html
    if hp.exists():
        ht = hp.read_text(encoding="utf-8", errors="ignore")
        check("MULTIMODAL_3Y_FORECAST_START" in ht, f"{rel_html} has 3Y multi-modal forecast UI", f"Missing 3Y forecast UI in {rel_html}")
        check("RUNTIME_INTEGRITY_LOCK_START" in ht, f"{rel_html} has runtime integrity lock", f"Missing runtime lock in {rel_html}")
    else:
        check(False, "", f"Missing {rel_html}")

# D. Verify Vercel security headers
for rel_vj in ["mobile-app/www/vercel.json", "vercel.json"]:
    vjp = ROOT / rel_vj
    if vjp.exists():
        vjt = vjp.read_text(encoding="utf-8", errors="ignore")
        check("Content-Security-Policy" in vjt and "Strict-Transport-Security" in vjt,
              f"{rel_vj} enforces CSP & HSTS headers", f"Missing CSP/HSTS in {rel_vj}")

# E. Verify Android hardening files if present in checkout
manifest_candidates = [
    ROOT / "mobile-app" / "android" / "app" / "src" / "main" / "AndroidManifest.xml",
    ROOT / "mobile-app" / "android" / "app" / "AndroidManifest.xml",
]
manifest_path = next((m for m in manifest_candidates if m.exists()), None)
if manifest_path:
    mtxt = manifest_path.read_text(encoding="utf-8", errors="ignore")
    check('allowBackup="false"' in mtxt and 'usesCleartextTraffic="false"' in mtxt,
          "AndroidManifest.xml hardened (allowBackup=false, usesCleartextTraffic=false)",
          "AndroidManifest.xml missing security flags")

# F. Compile Python backend/API files
for rel_py in ["backend/main.py", "ml/api_server.py"]:
    pp = ROOT / rel_py
    if pp.exists():
        c = subprocess.run([sys.executable, "-m", "py_compile", str(pp)], capture_output=True, text=True)
        check(c.returncode == 0, f"{rel_py} compiles cleanly", f"{rel_py} compile error: {c.stderr}")

# G. Verify SHA-256 manifest at the end
vres = subprocess.run([sys.executable, str(ROOT / "ml" / "verify_integrity.py")], capture_output=True, text=True)
check(vres.returncode == 0, f"SHA-256 manifest check passed: {vres.stdout.strip()}", f"SHA-256 check failed: {vres.stdout.strip()} {vres.stderr.strip()}")

print("\n" + ("=== ALL 3-YEAR MODEL, FORECAST & SECURITY CHECKS PASSED ===" if not errors else f"=== {len(errors)} CHECK(S) FAILED ==="))
sys.exit(1 if errors else 0)
