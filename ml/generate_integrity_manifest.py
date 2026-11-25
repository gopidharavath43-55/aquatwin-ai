import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    "ml/data_3y/water_3y.csv",
    "ml/data_3y/groundwater_3y.csv",
    "ml/data_3y/reservoirs_3y.csv",
    "ml/data_3y/rainfall_3y.csv",
    "ml/data_3y/telangana_master_3y.csv",
    "ml/ml_predictions.json",
    "mobile-app/www/ml_data.js",
]

model_dir = ROOT / "ml" / "models_3y"
if model_dir.exists():
    for p in sorted(model_dir.glob("*")):
        if p.is_file():
            TARGETS.append(p.relative_to(ROOT).as_posix())

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

entries = {}
for rel in TARGETS:
    full = ROOT / rel
    if full.exists():
        entries[rel] = {
            "sha256": sha256_file(full),
            "bytes": full.stat().st_size,
        }

manifest = {
    "algorithm": "SHA-256",
    "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "protected_files": len(entries),
    "files": entries,
}

out_path = ROOT / "ml" / "data_3y" / "integrity_manifest.json"
out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"[PASS] Generated SHA-256 integrity manifest for {len(entries)} datasets, models & bundles")