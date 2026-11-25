$ErrorActionPreference = "Stop"
$root   = "C:\Users\gopid\aquatwin-ai"
$mlDir  = Join-Path $root "ml"
$logDir = Join-Path $mlDir "logs"
$logFile = Join-Path $logDir "retrain_history.log"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line
}

$pyExe = (Get-Command python -ErrorAction Stop).Source
Set-Location $mlDir
Write-Log "=== START AquaTwin AI Weekly 3-Year Multi-Modal Retrain ==="

try {
    $steps = @(
        "train_1_1_water_3y.py",
        "train_1_2_groundwater_3y.py",
        "train_1_3_reservoirs_3y.py",
        "train_1_4_rainfall_3y.py",
        "train_2_1_multimodal_forecast.py",
        "generate_integrity_manifest.py",
        "verify_integrity.py",
        "run_final_audit.py"
    )

    foreach ($s in $steps) {
        if (-not (Test-Path $s)) {
            throw "Required pipeline script missing: $s"
        }
        Write-Log "Running $s ..."
        & $pyExe $s 2>&1 | Out-String | ForEach-Object {
            if ($_.Trim()) { Add-Content -Path $logFile -Value $_.TrimEnd() -Encoding UTF8 }
        }
        if ($LASTEXITCODE -ne 0) {
            throw "$s failed with exit code $LASTEXITCODE"
        }
        Write-Log "[PASS] $s"
    }

    # Keep mobile-app/ml_data.js synced with mobile-app/www/ml_data.js
    $wwwMl = Join-Path $root "mobile-app\www\ml_data.js"
    $appMl = Join-Path $root "mobile-app\ml_data.js"
    if (Test-Path $wwwMl) {
        Copy-Item $wwwMl $appMl -Force
        Write-Log "[PASS] Synced ml_data.js across mobile-app & mobile-app\www"
    }

    Write-Log "=== SUCCESS: 3-Year Models, Forecasts & SHA-256 Integrity Updated ==="
} catch {
    Write-Log "[ERROR] Pipeline aborted: $($_.Exception.Message)"
    exit 1
}