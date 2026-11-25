import hashlib, hmac, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "ml" / "data_3y" / "integrity_manifest.json"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_all() -> dict:
    if not MANIFEST_PATH.exists():
        return {"ok": False, "checked": 0, "failed": ["integrity_manifest.json missing"]}
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failed = []
    checked = 0
    for rel, meta in manifest.get("files", {}).items():
        full = ROOT / rel
        checked += 1
        if not full.exists():
            failed.append(f"{rel} (missing)")
            continue
        actual = sha256_file(full)
        if not hmac.compare_digest(actual, str(meta.get("sha256", ""))):
            failed.append(f"{rel} (hash mismatch)")
    return {"ok": len(failed) == 0, "checked": checked, "failed": failed}

if __name__ == "__main__":
    res = verify_all()
    if res["ok"]:
        print(f"[PASS] SHA-256 Integrity Verified: {res['checked']}/{res['checked']} files intact")
        sys.exit(0)
    else:
        print(f"[FAIL] Integrity Tamper Detected: {res['failed']}")
        sys.exit(1)