param(
    [string]$RenderUrl = "https://aquatwin-ai-api.onrender.com",
    [string]$WebUrl    = "https://www-gold-five.vercel.app"
)

$ErrorActionPreference = "Stop"
$root = "C:\Users\gopid\aquatwin-ai"
Set-Location $root

Write-Host "=== 1. Local SHA-256 Integrity & 3Y Model Audit ===" -ForegroundColor Cyan
python ml\verify_integrity.py
if ($LASTEXITCODE -ne 0) { throw "SHA-256 integrity check failed." }

python ml\run_final_audit.py
if ($LASTEXITCODE -ne 0) { throw "Final 3Y model & security audit failed." }

Write-Host "`n=== 2. Live Web & Cloud API Reachability Check ===" -ForegroundColor Cyan
try {
    $wResp = Invoke-WebRequest -Uri $WebUrl -UseBasicParsing -TimeoutSec 12
    Write-Host "[PASS] Web Frontend reachable ($WebUrl) -> HTTP $($wResp.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Web check skipped/timed out ($WebUrl): $($_.Exception.Message)" -ForegroundColor Yellow
}

try {
    $hResp = Invoke-RestMethod -Uri "$RenderUrl/health" -TimeoutSec 12
    Write-Host "[PASS] Cloud API /health online -> $($hResp | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "[INFO] Cloud API /health not reachable right now (cold start or offline mode active): $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n=== SMOKE CHECK COMPLETE ===" -ForegroundColor Green