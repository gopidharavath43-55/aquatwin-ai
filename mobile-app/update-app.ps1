$ErrorActionPreference = "Stop"
cd C:\Users\gopid\aquatwin-ai\mobile-app

$jdk21 = (Get-ChildItem "C:\Program Files\Microsoft","C:\Program Files\Eclipse Adoptium" -Directory -Filter "jdk-21*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1).FullName
if (-not $jdk21) { throw "Java 21 not found. Install Microsoft OpenJDK 21 first." }

$env:JAVA_HOME = $jdk21
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:PATH = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:PATH"

$adb = "$env:ANDROID_HOME\platform-tools\adb.exe"
$adbOut = (& $adb devices | Out-String)
if ($adbOut -match "\tunauthorized") {
    throw "Tap 'Allow' on the USB Debugging popup on your Vivo phone, then run this again."
}
if ($adbOut -notmatch "\tdevice") {
    throw "Vivo phone not detected over USB. Plug in USB cable and enable USB Debugging."
}

# Increment versionCode & versionName cleanly
$gp = (Resolve-Path "android\app\build.gradle").Path
$g = Get-Content $gp -Raw
$g = [regex]::Replace($g, 'applicationId\s+"[^"]+"', 'applicationId "com.aquatwin.ai"')
$m = [regex]::Match($g, 'versionCode\s+(\d+)')
$nextVer = if ($m.Success) { [int]$m.Groups[1].Value + 1 } else { 2 }
$g = [regex]::Replace($g, 'versionCode\s+\d+', "versionCode $nextVer")
$g = [regex]::Replace($g, 'versionName\s+"[^"]+"', "versionName `"1.$nextVer`"")
[System.IO.File]::WriteAllText($gp, $g, [System.Text.UTF8Encoding]::new($false))

# Stamp new version into index.html so the app runs the on-open update banner
$hp = (Resolve-Path "index.html").Path
$h = [System.IO.File]::ReadAllText($hp)
$h = [regex]::Replace($h, 'window\.AQUATWIN_VERSION\s*=\s*"[^"]*"', "window.AQUATWIN_VERSION = `"1.$nextVer`"")
[System.IO.File]::WriteAllText($hp, $h, [System.Text.UTF8Encoding]::new($false))
Copy-Item index.html www\index.html -Force

Write-Host "Updating AquaTwin AI to v1.$nextVer..." -ForegroundColor Cyan
npx cap sync android | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Sync failed." }

cd android
.\gradlew.bat assembleDebug
if ($LASTEXITCODE -ne 0) { throw "Build failed." }

$buildFile = (Resolve-Path "app\build\outputs\apk\debug\app-debug.apk").Path
& $adb install -r -d $buildFile
if ($LASTEXITCODE -ne 0) { throw "Could not push update to Vivo phone. Enable 'Install via USB' in Vivo Developer Options." }

# Clean up any leftover renamed files and restart AquaTwin AI directly on your phone
Get-ChildItem "app\build\outputs\apk\debug" -Filter "AquaTwin*.apk" -ErrorAction SilentlyContinue | Remove-Item -Force
& $adb shell am force-stop com.aquatwin.ai | Out-Null
& $adb shell monkey -p com.aquatwin.ai -c android.intent.category.LAUNCHER 1 | Out-Null
Write-Host "AquaTwin AI v1.$nextVer updated and opened on your phone!" -ForegroundColor Green
