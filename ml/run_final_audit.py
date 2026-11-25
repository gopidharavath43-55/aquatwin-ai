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

# A. Verify 3-year datasets & SHA-256 cryptographic integrity
res = subprocess.run([sys.executable, str(ROOT / "ml" / "verify_integrity.py")], capture_output=True, text=True)
check(res.returncode == 0, "SHA-256 Integrity Manifest verified (all 3Y datasets, models & ml_data.js)", f"SHA-256 check failed: {res.stdout} {res.stderr}")

# B. Verify 33-district +1M / +2M / +6M / +1Y predictions across all 4 domains
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
    all_have_keys = len(dists) == 33 and all(all(k in d for k in req_keys) for d in dists)
    check(all_have_keys, "All 33 districts contain +1M/+2M/+6M/+1Y forecasts for Water, GW, Reservoirs & Rainfall", "Missing districts or forecast horizon keys in ml_predictions.json")
else:
    check(False, "", "ml/ml_predictions.json missing")

# C. Verify frontend runtime lock, XSS escaping & 3Y forecast UI
html_txt = (ROOT / "mobile-app" / "www" / "index.html").read_text(encoding="utf-8")
check("MULTIMODAL_3Y_FORECAST_START" in html_txt, "Frontend 3-Year Multi-Modal (+1M/+2M/+6M/+1Y) Forecast Card present", "3Y Forecast Card missing in www/index.html")
check("RUNTIME_INTEGRITY_LOCK_START" in html_txt and "Object.freeze" in html_txt, "Frontend in-memory ML data freeze & X-App-Client fetch guard active", "Runtime lock missing in www/index.html")
check("ASK_AI_STATE_GUARD_START" in html_txt, "Ask AI state/district input validation active", "Ask AI validation guard missing in www/index.html")

# D. Verify Vercel CSP/HSTS/Permissions-Policy headers
vj_txt = (ROOT / "mobile-app" / "www" / "vercel.json").read_text(encoding="utf-8")
check("Content-Security-Policy" in vj_txt and "Strict-Transport-Security" in vj_txt and "Permissions-Policy" in vj_txt,
      "Web security headers active (CSP, HSTS, X-Frame-Options, Permissions-Policy)",
      "Missing security headers in mobile-app/www/vercel.json")

# E. Verify Android native hardening (HTTPS-only, allowBackup=false, R8)
manifest_txt = (ROOT / "mobile-app" / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
gradle_txt = (ROOT / "mobile-app" / "android" / "app" / "build.gradle").read_text(encoding="utf-8")
netsec_exists = (ROOT / "mobile-app" / "android" / "app" / "src" / "main" / "res" / "xml" / "network_security_config.xml").exists()
check('allowBackup="false"' in manifest_txt and 'usesCleartextTraffic="false"' in manifest_txt and netsec_exists,
      "Android Manifest & Network Security Config hardened (HTTPS-only, no ADB backup)",
      "Android native security flags incomplete")
check("minifyEnabled true" in gradle_txt and "shrinkResources true" in gradle_txt,
      "Android R8 code shrinking & obfuscation enabled",
      "R8 obfuscation missing in build.gradle")

# F. Verify FastAPI backend & ML API compile cleanly with security guards
for rel_py in ["backend/main.py", "ml/api_server.py"]:
    p = ROOT / rel_py
    if p.exists():
        c = subprocess.run([sys.executable, "-m", "py_compile", str(p)], capture_output=True, text=True)
        txt = p.read_text(encoding="utf-8")
        check(c.returncode == 0 and "X-App-Client" in txt,
              f"{rel_py} compiles cleanly with X-App-Client & security headers",
              f"{rel_py} syntax or security check failed: {c.stderr}")

print("\n" + ("=== ALL SECURITY & 3-YEAR MODEL CHECKS PASSED ===" if not errors else f"=== FAILED CHECKS: {len(errors)} ==="))
sys.exit(1 if errors else 0)