param([string]$Notes = "Latest AquaTwin AI improvements and fixes")

$ErrorActionPreference = "Stop"
cd C:\Users\gopid\aquatwin-ai

$vPath = Join-Path (Get-Location) "version.json"
$meta = Get-Content $vPath -Raw | ConvertFrom-Json
$newCode = [int]($meta.versionCode) + 1
$newVer = "1.$newCode"
$newTag = "v$newVer"
$exactApkUrl = "https://github.com/gopidharavath43-55/aquatwin-ai/releases/download/$newTag/AquaTwin-AI.apk"

$verObj = [ordered]@{
    version     = $newVer
    versionCode = $newCode
    tag         = $newTag
    downloadUrl = $exactApkUrl
    notes       = $Notes
    updatedAt   = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($vPath, ($verObj | ConvertTo-Json -Depth 4), $utf8NoBom)

$gradlePath = (Resolve-Path "mobile-app\android\app\build.gradle").Path
$gTxt = [System.IO.File]::ReadAllText($gradlePath)
$gTxt = [regex]::Replace($gTxt, 'versionCode\s+\d+', "versionCode $newCode")
$gTxt = [regex]::Replace($gTxt, 'versionName\s+"[^"]+"', "versionName `"$newVer`"")
[System.IO.File]::WriteAllText($gradlePath, $gTxt, $utf8NoBom)

foreach ($rel in @("mobile-app\index.html", "mobile-app\www\index.html")) {
    if (Test-Path $rel) {
        $p = (Resolve-Path $rel).Path
        $h = [System.IO.File]::ReadAllText($p)
        $h = [regex]::Replace($h, '(BAKED_VERSION\s*=\s*")1\.\d+(")', "`${1}$newVer`${2}")
        $h = [regex]::Replace($h, '(BAKED_CODE\s*=\s*)\d+', "`${1}$newCode")
        $h = [regex]::Replace($h, '(APP_VERSION\s*=\s*["''])1\.\d+(["''])', "`${1}$newVer`${2}")
        $h = [regex]::Replace($h, 'https://github\.com/gopidharavath43-55/aquatwin-ai/releases/(?:latest/download|download/v1\.\d+)/AquaTwin-AI\.apk', $exactApkUrl)
        [System.IO.File]::WriteAllText($p, $h, $utf8NoBom)
    }
}

cd C:\Users\gopid\aquatwin-ai\mobile-app
Copy-Item "index.html" "www\index.html" -Force
if (Test-Path "ml_data.js") { Copy-Item "ml_data.js" "www\ml_data.js" -Force }
npx cap sync android

cd C:\Users\gopid\aquatwin-ai\mobile-app\android
.\gradlew.bat assembleDebug

cd C:\Users\gopid\aquatwin-ai
New-Item -ItemType Directory -Path "release" -Force | Out-Null
Copy-Item "mobile-app\android\app\build\outputs\apk\debug\app-debug.apk" "release\AquaTwin-AI.apk" -Force

git config core.autocrlf false
git config core.safecrlf false
$ErrorActionPreference = "Continue"
git add version.json mobile-app/index.html mobile-app/www/index.html mobile-app/www/ml_data.js mobile-app/android/app/build.gradle
git commit -m "Release AquaTwin AI $newTag (code $newCode)" --allow-empty
git tag -f $newTag
git push origin main
git push origin "refs/tags/$newTag" --force
if ($LASTEXITCODE -ne 0) { throw "Git push failed with exit code $LASTEXITCODE" }

$apkFile = (Resolve-Path "release\AquaTwin-AI.apk").Path
if (Get-Command gh -ErrorAction SilentlyContinue) {
    gh release create $newTag $apkFile --title "AquaTwin AI $newTag" --notes $Notes --latest 2>$null
    if ($LASTEXITCODE -ne 0) { gh release upload $newTag $apkFile --clobber }
    Write-Host "[OK] Auto-published $newTag with AquaTwin-AI.apk on GitHub!" -ForegroundColor Green
} else {
    Start-Process explorer.exe (Resolve-Path "release").Path
    Start-Process "chrome.exe" "https://github.com/gopidharavath43-55/aquatwin-ai/releases/new?tag=$newTag&title=AquaTwin+AI+$newTag"
}
Write-Host "`n[DONE] $newTag is live!" -ForegroundColor Green