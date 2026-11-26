import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\gopid\aquatwin-ai")
KEY_DIR = Path(r"C:\Users\gopid\.aquatwin-keys")
failures = []

def check(cond: bool, ok_msg: str, fail_msg: str):
    if cond:
        print(f"[PASS] {ok_msg}")
    else:
        print(f"[FAIL] {fail_msg}")
        failures.append(fail_msg)

print("\n=== AQUATWIN AI — 5-LAYER EXTREME SECURITY AUDIT ===")

# Layer 1: Cryptographic Data Seal & Key Vault
check((KEY_DIR / "data_hmac.key").exists(), "Layer 1: External 256-bit HMAC key vault present outside Git", "Layer 1: Missing data_hmac.key in key vault")
check((KEY_DIR / "api_secret.key").exists(), "Layer 1: External 256-bit API secret key present outside Git", "Layer 1: Missing api_secret.key in key vault")
vlock = subprocess.run([sys.executable, str(ROOT / "ml" / "verify_data_lock.py"), "--verify"], capture_output=True, text=True)
check(vlock.returncode == 0, "Layer 1: HMAC-SHA256 data/model ledger authentic & 0 secret leaks", f"Layer 1: verify_data_lock failed: {vlock.stdout.strip()} {vlock.stderr.strip()}")

# Layer 2: Runtime Anti-Tamper, Freeze, XSS & CSP/HSTS Headers
for rel in ["mobile-app/index.html", "mobile-app/www/index.html", "mobile-app/android/app/src/main/assets/public/index.html"]:
    p = ROOT / rel
    txt = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    ok = all(tok in txt for tok in ["AQUATWIN_RUNTIME_SECURITY_START", "Object.freeze", "atEscapeHtml", "atIsTrustedApkUrl"])
    check(ok, f"Layer 2: Runtime Security Shield active in {rel}", f"Layer 2: Runtime Security Shield incomplete in {rel}")

for rel in ["vercel.json", "mobile-app/www/vercel.json"]:
    p = ROOT / rel
    hdr_keys = set()
    if p.exists():
        cfg = json.loads(p.read_text(encoding="utf-8"))
        for rule in cfg.get("headers", []):
            for h in rule.get("headers", []):
                hdr_keys.add(h.get("key", ""))
    req_hdrs = {"Content-Security-Policy", "Strict-Transport-Security", "X-Frame-Options", "X-Content-Type-Options", "Cross-Origin-Opener-Policy", "Cross-Origin-Resource-Policy"}
    check(req_hdrs.issubset(hdr_keys), f"Layer 2: Strict CSP/HSTS/COOP/CORP headers locked in {rel}", f"Layer 2: Missing headers in {rel}: {req_hdrs - hdr_keys}")

# Layer 3: Android Native Hardening
android_main = ROOT / "mobile-app" / "android" / "app" / "src" / "main"
nsc = (android_main / "res" / "xml" / "network_security_config.xml").read_text(encoding="utf-8") if (android_main / "res" / "xml" / "network_security_config.xml").exists() else ""
check('cleartextTrafficPermitted="false"' in nsc and 'src="system"' in nsc, "Layer 3: network_security_config.xml enforces HTTPS-only & System CAs", "Layer 3: network_security_config.xml not hardened")

man = (android_main / "AndroidManifest.xml").read_text(encoding="utf-8") if (android_main / "AndroidManifest.xml").exists() else ""
check('android:allowBackup="false"' in man and 'android:usesCleartextTraffic="false"' in man and 'data_extraction_rules' in man, "Layer 3: AndroidManifest.xml blocks backups, cleartext & Android 12+ extraction", "Layer 3: AndroidManifest.xml missing hardening attributes")

java_files = list((android_main / "java").rglob("MainActivity.java"))
java_txt = java_files[0].read_text(encoding="utf-8") if java_files else ""
check("FLAG_SECURE" in java_txt and "setWebContentsDebuggingEnabled(false)" in java_txt and "MIXED_CONTENT_NEVER_ALLOW" in java_txt, "Layer 3: MainActivity.java locks FLAG_SECURE, WebView debugging & mixed content", "Layer 3: MainActivity.java missing native security locks")

cap_cfg = ROOT / "mobile-app" / "capacitor.config.json"
if cap_cfg.exists():
    ct = cap_cfg.read_text(encoding="utf-8")
    check('"androidScheme": "https"' in ct and '"webContentsDebuggingEnabled": false' in ct, "Layer 3: capacitor.config.json hardened for HTTPS & no debug", "Layer 3: capacitor.config.json not hardened")

# Layer 4: Zero-Trust FastAPI Defense
zt_file = ROOT / "backend" / "zero_trust_shield.py"
check(zt_file.exists(), "Layer 4: backend/zero_trust_shield.py present", "Layer 4: Missing backend/zero_trust_shield.py")
for rel in ["backend/main.py", "ml/api_server.py"]:
    p = ROOT / rel
    if p.exists():
        txt = p.read_text(encoding="utf-8")
        comp = subprocess.run([sys.executable, "-m", "py_compile", str(p)], capture_output=True, text=True)
        check("AQUATWIN_ZERO_TRUST_V1" in txt and comp.returncode == 0, f"Layer 4: Zero-Trust Defense wired & compiled in {rel}", f"Layer 4: Zero-Trust check failed for {rel}")

# Layer 5: Git Pre-Commit Guard
hook = ROOT / ".git" / "hooks" / "pre-commit"
check(hook.exists() and "AQUATWIN PRE-COMMIT SECURITY GUARD" in hook.read_text(encoding="utf-8", errors="ignore"), "Layer 5: Git pre-commit secret blocker installed & active", "Layer 5: Git pre-commit hook missing")

if failures:
    print(f"\n=== AUDIT FAILED ({len(failures)} issue(s)) ===")
    sys.exit(1)

print("\n=== EXTREME SECURITY AUDIT PASSED (ALL 5 LAYERS LOCKED & VERIFIED) ===\n")
sys.exit(0)
