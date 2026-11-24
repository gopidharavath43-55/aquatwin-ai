param([string]$Notes = "• Latest signed AquaTwin AI improvements, security hardening & telemetry")
$ErrorActionPreference = "Stop"
cd C:\Users\gopid\aquatwin-ai\mobile-app

powershell -ExecutionPolicy Bypass -File .\update-app.ps1
powershell -ExecutionPolicy Bypass -File .\make-friend-release.ps1 -Notes $Notes

# Deploy latest hardened web build to Vercel
Push-Location "www"
try {
  npx vercel --prod
} finally {
  Pop-Location
}

# Push synced code & version.json to GitHub (never stages private keys)
cd C:\Users\gopid\aquatwin-ai
git config core.autocrlf false
git config core.safecrlf false

$meta = Get-Content .\version.json | ConvertFrom-Json
$v = $meta.version
$tag = "v$v"

git add version.json mobile-app/index.html mobile-app/www/index.html mobile-app/www/vercel.json mobile-app/www/ml_data.js mobile-app/ml_data.js mobile-app/android/app/build.gradle backend/main.py 2>$null
git commit -m "Release signed AquaTwin AI $tag" --allow-empty
git tag -f $tag
git push origin main
git push origin "refs/tags/$tag" --force

Start-Process explorer.exe (Resolve-Path "release").Path
Start-Process "https://github.com/gopidharavath43-55/aquatwin-ai/releases/new?tag=$tag&title=AquaTwin+AI+$tag"
Write-Host "`nPushed $tag & deployed Vercel. Drag release\AquaTwin-AI.apk onto the GitHub Release page and click Publish release." -ForegroundColor Green