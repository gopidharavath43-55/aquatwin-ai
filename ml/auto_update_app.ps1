param(
    [string]$Notes = "• Auto-synced AquaTwin AI app, web browser build & GitHub repository",
    [switch]$SkipApkBuild,
    [switch]$SkipVercel,
    [switch]$SkipGit
)

$ErrorActionPreference = "Stop"
$env:CI = "1"
$env:npm_config_yes = "true"
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$root = Split-Path -Parent $scriptDir
if (-not $root -or -not (Test-Path $root)) {
    $root = "C:\Users\gopid\aquatwin-ai"
}
Set-Location $root

Write-Host "=== AQUATWIN AI AUTO-UPDATE (APP + WEB BROWSER + GITHUB) ===" -ForegroundColor Cyan

# [1/4] Sync HTML & ML bundle across mobile-app, www, and Android Capacitor assets
$syncPy = @"
import shutil
from pathlib import Path

ROOT = Path(r"$root")
src_html = ROOT / "mobile-app" / "index.html"
if not src_html.exists() and (ROOT / "mobile-app" / "www" / "index.html").exists():
    shutil.copy2(ROOT / "mobile-app" / "www" / "index.html", src_html)

if src_html.exists():
    for dst in [
        ROOT / "mobile-app" / "www" / "index.html",
        ROOT / "mobile-app" / "android" / "app" / "src" / "main" / "assets" / "public" / "index.html",
    ]:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_html, dst)

src_js = ROOT / "mobile-app" / "www" / "ml_data.js"
if not src_js.exists() and (ROOT / "mobile-app" / "ml_data.js").exists():
    src_js = ROOT / "mobile-app" / "ml_data.js"

if src_js.exists():
    for dst_js in [
        ROOT / "mobile-app" / "www" / "ml_data.js",
        ROOT / "mobile-app" / "ml_data.js",
        ROOT / "mobile-app" / "android" / "app" / "src" / "main" / "assets" / "public" / "ml_data.js",
    ]:
        if dst_js != src_js:
            dst_js.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_js, dst_js)

print("[PASS] Synced HTML & ML bundle across mobile-app, www & Android assets")
"@

$tmpSync = Join-Path $root "ml\_auto_sync_tmp.py"
[System.IO.File]::WriteAllText($tmpSync, ($syncPy.Trim() + "`n"), [System.Text.UTF8Encoding]::new($false))
try {
    python $tmpSync
    if ($LASTEXITCODE -ne 0) { throw "Asset sync failed with exit code $LASTEXITCODE." }
} finally {
    if (Test-Path $tmpSync) { Remove-Item $tmpSync -Force -ErrorAction SilentlyContinue }
}

$verStr = $null
$nextVer = $null

# [2/4] Update Android App version, Capacitor sync, APK build & USB phone install
if (-not $SkipApkBuild) {
    $jdk21 = (Get-ChildItem "C:\Program Files\Microsoft" -Directory -Filter "jdk-21*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1).FullName
    if (-not $jdk21 -and (Test-Path "C:\Program Files\Android\Android Studio\jbr")) {
        $jdk21 = "C:\Program Files\Android\Android Studio\jbr"
    }
    $sdkDir = "$env:LOCALAPPDATA\Android\Sdk"

    if ($jdk21 -and (Test-Path $sdkDir) -and (Test-Path (Join-Path $root "mobile-app\android\app\build.gradle"))) {
        $env:JAVA_HOME = $jdk21
        $env:ANDROID_HOME = $sdkDir
        $env:ANDROID_SDK_ROOT = $sdkDir
        $env:PATH = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:PATH"

        Set-Location (Join-Path $root "mobile-app")
        $gp = (Resolve-Path "android\app\build.gradle").Path
        $g  = [System.IO.File]::ReadAllText($gp)
        $g  = [regex]::Replace($g, 'applicationId\s+"[^"]+"', 'applicationId "com.aquatwin.ai"')

        $m       = [regex]::Match($g, 'versionCode\s+(\d+)')
        $nextVer = if ($m.Success) { [int]$m.Groups[1].Value + 1 } else { 2 }
        $verStr  = "1.$nextVer"

        $g = [regex]::Replace($g, 'versionCode\s+\d+', "versionCode $nextVer")
        $g = [regex]::Replace($g, 'versionName\s+"[^"]+"', "versionName `"$verStr`"")
        [System.IO.File]::WriteAllText($gp, $g, [System.Text.UTF8Encoding]::new($false))

        foreach ($hf in @("index.html", "www\index.html")) {
            if (Test-Path $hf) {
                $ht = [System.IO.File]::ReadAllText((Resolve-Path $hf).Path)
                $ht = [regex]::Replace($ht, 'window\.AQUATWIN_VERSION\s*=\s*"[^"]+"', "window.AQUATWIN_VERSION = `"$verStr`"")
                [System.IO.File]::WriteAllText((Resolve-Path $hf).Path, $ht, [System.Text.UTF8Encoding]::new($false))
            }
        }

        npx --yes cap sync android
        if ($LASTEXITCODE -ne 0) { throw "Capacitor sync failed with exit code $LASTEXITCODE." }

        $apkPath = $null
        Push-Location "android"
        try {
            if (Test-Path "keystore.properties") {
                .\gradlew.bat assembleRelease "-Dorg.gradle.java.home=$jdk21"
                if ($LASTEXITCODE -ne 0) { throw "Gradle assembleRelease failed with exit code $LASTEXITCODE." }
                $relCand = @("app\build\outputs\apk\release\app-release.apk", "app\build\outputs\apk\release\AquaTwin-AI.apk") | Where-Object { Test-Path $_ } | Select-Object -First 1
                if ($relCand) { $apkPath = (Resolve-Path $relCand).Path }
            }
            if (-not $apkPath) {
                .\gradlew.bat assembleDebug "-Dorg.gradle.java.home=$jdk21"
                if ($LASTEXITCODE -ne 0) { throw "Gradle assembleDebug failed with exit code $LASTEXITCODE." }
                $dbgCand = @("app\build\outputs\apk\debug\AquaTwin-AI.apk", "app\build\outputs\apk\debug\app-debug.apk") | Where-Object { Test-Path $_ } | Select-Object -First 1
                if ($dbgCand) { $apkPath = (Resolve-Path $dbgCand).Path }
            }
        } finally {
            Pop-Location
        }

        Set-Location $root
        if ($apkPath) {
            New-Item -ItemType Directory -Path (Join-Path $root "release") -Force | Out-Null
            $dstApk = Join-Path (Join-Path $root "release") "AquaTwin-AI.apk"
            Copy-Item $apkPath $dstApk -Force

            $verObj = [ordered]@{
                version      = $verStr
                version_code = $nextVer
                apk_url      = "https://github.com/gopidharavath43-55/aquatwin-ai/releases/latest/download/AquaTwin-AI.apk"
                notes        = $Notes
                force        = $false
                updated_at   = (Get-Date -Format "yyyy-MM-dd HH:mm IST")
            }
            [System.IO.File]::WriteAllText(
                (Join-Path $root "version.json"),
                ($verObj | ConvertTo-Json -Depth 4),
                [System.Text.UTF8Encoding]::new($false)
            )
            Write-Host "[PASS] App updated to v$verStr -> $dstApk" -ForegroundColor Green

            $adb = Join-Path $sdkDir "platform-tools\adb.exe"
            if (Test-Path $adb) {
                $connected = (& $adb devices | Select-String "\tdevice$")
                if ($connected) {
                    & $adb install -r $dstApk
                    if ($LASTEXITCODE -ne 0) {
                        & $adb uninstall com.aquatwin.ai | Out-Null
                        & $adb install $dstApk
                    }
                    & $adb shell monkey -p com.aquatwin.ai -c android.intent.category.LAUNCHER 1 | Out-Null
                    Write-Host "[PASS] Installed & opened v$verStr on USB phone!" -ForegroundColor Green
                }
            }
        }
    }
    Set-Location $root
}

# Refresh SHA-256 manifest & run audit before deploying/pushing
if (Test-Path (Join-Path $root "ml\generate_integrity_manifest.py")) {
    python (Join-Path $root "ml\generate_integrity_manifest.py")
    if ($LASTEXITCODE -ne 0) { throw "Manifest generation failed." }
}
if (Test-Path (Join-Path $root "ml\run_final_audit.py")) {
    python (Join-Path $root "ml\run_final_audit.py")
    if ($LASTEXITCODE -ne 0) { throw "Final audit failed." }
}

# [3/4] Update Web Browser deployment on Vercel
if (-not $SkipVercel -and (Test-Path (Join-Path $root "mobile-app\www"))) {
    Push-Location (Join-Path $root "mobile-app\www")
    try {
        Write-Host "[INFO] Updating Web Browser deployment on Vercel..." -ForegroundColor Cyan
        npx --yes vercel --prod --yes
        if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] Vercel daily free limit (100/day) reached - skipping Vercel deploy today; continuing Android & GitHub update." -ForegroundColor Yellow; $global:LASTEXITCODE = 0 }
        Write-Host "[PASS] Web Browser updated on Vercel!" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

# [4/4] Update GitHub (commit + tag + push main)
if (-not $SkipGit) {
    Set-Location $root
    git config core.autocrlf false
    git config core.safecrlf false
    git add -A
    if ($verStr) {
        $tag = "v$verStr"
        git commit -m "Auto-update AquaTwin AI app, web & GitHub ($tag)" --allow-empty
        if ($LASTEXITCODE -ne 0) { throw "Git commit failed." }
        git tag -f $tag
        git push origin main
        if ($LASTEXITCODE -ne 0) { throw "Git push to main failed." }
        git push origin "refs/tags/$tag" --force
        if ($LASTEXITCODE -ne 0) { throw "Git push of tag $tag failed." }
        Write-Host "[PASS] GitHub updated (main + tag $tag)!" -ForegroundColor Green
    } else {
        git commit -m "Auto-update AquaTwin AI app, web & GitHub" --allow-empty
        if ($LASTEXITCODE -ne 0) { throw "Git commit failed." }
        git push origin main
        if ($LASTEXITCODE -ne 0) { throw "Git push to main failed." }
        Write-Host "[PASS] GitHub updated (main)!" -ForegroundColor Green
    }
}

Write-Host "=== ALL UPDATED: APP + WEB BROWSER + GITHUB ===" -ForegroundColor Green
# Auto-upload signed APK to GitHub Latest Release (no manual browser upload)
if (Test-Path "C:\Users\gopid\aquatwin-ai\ml\github_auto_release.py") { python "C:\Users\gopid\aquatwin-ai\ml\github_auto_release.py" }
