param(
  [string]$Notes = "• All 33 Telangana districts with full official names`n• Smooth Satellite Map & Apple Liquid Glass Dock`n• Live Ask AI water quality, Sentinel-2 & groundwater telemetry"
)
$ErrorActionPreference = "Stop"
cd C:\Users\gopid\aquatwin-ai\mobile-app

$gradleTxt = [System.IO.File]::ReadAllText((Resolve-Path "android\app\build.gradle").Path)
$ver  = ([regex]::Match($gradleTxt, 'versionName\s+"([^"]+)"')).Groups[1].Value
$code = [int]([regex]::Match($gradleTxt, 'versionCode\s+(\d+)')).Groups[1].Value
$apkUrl = "https://github.com/gopidharavath43-55/aquatwin-ai/releases/latest/download/AquaTwin-AI.apk"

$relDir = "..\release"
if (!(Test-Path $relDir)) { New-Item -ItemType Directory -Path $relDir | Out-Null }

$srcApk = (Resolve-Path "android\app\build\outputs\apk\debug\app-debug.apk").Path
$dstApk = Join-Path (Resolve-Path $relDir).Path "AquaTwin-AI.apk"
Copy-Item $srcApk $dstApk -Force

$verObj = [ordered]@{
  version      = $ver
  version_code = $code
  apk_url      = $apkUrl
  notes        = $Notes
  force        = $false
  updated_at   = (Get-Date -Format "yyyy-MM-dd HH:mm IST")
}
$verPath = Join-Path (Resolve-Path "..").Path "version.json"
[System.IO.File]::WriteAllText($verPath, ($verObj | ConvertTo-Json -Depth 4), [System.Text.UTF8Encoding]::new($false))

Write-Host "`n=== RELEASE READY: v$ver (code $code) ===" -ForegroundColor Green
Write-Host "APK     : $dstApk" -ForegroundColor Cyan
Write-Host "Manifest: $verPath" -ForegroundColor Cyan
