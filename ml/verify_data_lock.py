import hashlib, hmac, json, os, re, secrets, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\gopid\aquatwin-ai")
KEY_DIR = Path(r"C:\Users\gopid\.aquatwin-keys")
KEY_FILE = KEY_DIR / "data_hmac.key"
LEDGER_FILE = ROOT / "ml" / "data_integrity_ledger.json"

TARGET_GLOBS = [
    "data/*.csv",
    "ml/*.csv",
    "ml/*.json",
    "ml/*.pt",
    "ml/api_server.py",
    "backend/main.py",
    "backend/zero_trust_shield.py",
    "mobile-app/index.html",
    "mobile-app/data.js",
    "mobile-app/ml_data.js",
    "mobile-app/www/index.html",
    "mobile-app/www/data.js",
    "mobile-app/www/ml_data.js",
    "mobile-app/www/sw.js",
    "mobile-app/www/vercel.json",
    "vercel.json",
]

SECRET_PATTERNS = [
    ("Private Key Block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{30,}\b")),
    ("Generic Bearer/SK Secret", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
]

FORBIDDEN_PUBLIC_EXTS = {".jks", ".keystore", ".key", ".pem", ".p12", ".pfx", ".env"}

def get_hmac_key() -> bytes:
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    if not KEY_FILE.exists():
        KEY_FILE.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
    return bytes.fromhex(KEY_FILE.read_text(encoding="utf-8").strip())

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def collect_protected_files():
    found = {}
    for pattern in TARGET_GLOBS:
        for p in ROOT.glob(pattern):
            if p.is_file() and p.resolve() != LEDGER_FILE.resolve():
                rel = p.relative_to(ROOT).as_posix()
                found[rel] = p
    return dict(sorted(found.items()))

def compute_ledger_signature(key: bytes, files_map: dict) -> str:
    canonical = json.dumps(files_map, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()

def scan_for_secret_leaks():
    issues = []
    # Check public web directory for any forbidden secret files
    www_dir = ROOT / "mobile-app" / "www"
    if www_dir.exists():
        for p in www_dir.rglob("*"):
            if p.is_file() and (p.suffix.lower() in FORBIDDEN_PUBLIC_EXTS or p.name.lower().startswith(".env")):
                issues.append(f"Forbidden file in public www/: {p.relative_to(ROOT).as_posix()}")

    # Check git-tracked files for forbidden extensions
    try:
        tracked = subprocess.check_output(["git", "ls-files"], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL).splitlines()
        for rel in tracked:
            p = Path(rel)
            if p.suffix.lower() in FORBIDDEN_PUBLIC_EXTS or p.name.lower().startswith(".env") or "keystore-backup" in p.name.lower():
                issues.append(f"Sensitive file tracked in Git: {rel}")
    except Exception:
        pass

    # Scan code & JSON files for hardcoded credentials
    skip_dirs = {".git", "node_modules", "venv", ".venv", "backups", "release", "build", ".gradle"}
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.suffix.lower() not in {".py", ".js", ".json", ".html", ".ps1", ".yml", ".yaml"}:
            continue
        if p.stat().st_size > 2_500_000:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, pat in SECRET_PATTERNS:
            if pat.search(txt):
                issues.append(f"Potential {label} found in {p.relative_to(ROOT).as_posix()}")
    return issues

def seal():
    key = get_hmac_key()
    files = collect_protected_files()
    files_map = {}
    for rel, path in files.items():
        files_map[rel] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    sig = compute_ledger_signature(key, files_map)
    ledger = {
        "schema": "aquatwin-hmac-sha256-v1",
        "sealed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_count": len(files_map),
        "hmac_sha256": sig,
        "files": files_map,
    }
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_FILE.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"[PASS] Sealed {len(files_map)} protected data, model & app files with HMAC-SHA256 -> ml/data_integrity_ledger.json")

def verify():
    if not LEDGER_FILE.exists():
        print("[FAIL] Ledger missing. Run with --seal first.")
        return 1
    key = get_hmac_key()
    ledger = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    files_map = ledger.get("files", {})
    expected_sig = ledger.get("hmac_sha256", "")
    actual_sig = compute_ledger_signature(key, files_map)
    if not hmac.compare_digest(expected_sig, actual_sig):
        print("[FAIL] TAMPER ALERT: Ledger HMAC-SHA256 signature mismatch!")
        return 1

    tampered = []
    for rel, meta in files_map.items():
        p = ROOT / rel
        if not p.exists():
            tampered.append(f"MISSING: {rel}")
        else:
            cur_hash = sha256_file(p)
            if not hmac.compare_digest(cur_hash, meta["sha256"]):
                tampered.append(f"MODIFIED: {rel}")

    if tampered:
        print("[FAIL] TAMPER ALERT in protected files:")
        for t in tampered:
            print("  -", t)
        return 1

    leaks = scan_for_secret_leaks()
    if leaks:
        print("[FAIL] SECRET LEAK ALERT:")
        for l in leaks:
            print("  -", l)
        return 1

    print(f"[PASS] Cryptographic Verification OK: {len(files_map)}/{len(files_map)} files authentic (HMAC-SHA256 valid) & 0 secret leaks")
    return 0

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--verify"
    if mode == "--seal":
        seal()
        sys.exit(verify())
    else:
        sys.exit(verify())
