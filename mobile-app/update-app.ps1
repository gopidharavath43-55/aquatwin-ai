$ErrorActionPreference = "Stop"
cd C:\Users\gopid\aquatwin-ai\mobile-app

# Locate Java 21 (Microsoft OpenJDK or Android Studio JBR)
$jdk21 = (Get-ChildItem "C:\Program Files\Microsoft" -Directory -Filter "jdk-21*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1).FullName
if (-not $jdk21 -and (Test-Path "C:\Program Files\Android\Android Studio\jbr")) {
  $jdk21 = "C:\Program Files\Android\Android Studio\jbr"
}
if (-not $jdk21) { throw "Java 21 not found. Install Microsoft OpenJDK 21 or Android Studio." }

$sdkDir = "$env:LOCALAPPDATA\Android\Sdk"
if (-not (Test-Path $sdkDir)) { throw "Android SDK not found at $sdkDir." }

$env:JAVA_HOME = $jdk21
$env:ANDROID_HOME = $sdkDir
$env:ANDROID_SDK_ROOT = $sdkDir
$env:PATH = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:PATH"

# Keep local.properties pointing to Android SDK
[System.IO.File]::WriteAllText(
  (Join-Path (Resolve-Path "android").Path "local.properties"),
  "sdk.dir=$($sdkDir -replace '\\','/')`r`n",
  [System.Text.UTF8Encoding]::new($false)
)

# Lock package ID & auto-increment versionCode / versionName
$gp = (Resolve-Path "android\app\build.gradle").Path
$g  = [System.IO.File]::ReadAllText($gp)
$g  = [regex]::Replace($g, 'applicationId\s+"[^"]+"', 'applicationId "com.aquatwin.ai"')

$m       = [regex]::Match($g, 'versionCode\s+(\d+)')
$nextVer = if ($m.Success) { [int]$m.Groups[1].Value + 1 } else { 2 }
$verStr  = "1.$nextVer"

$g = [regex]::Replace($g, 'versionCode\s+\d+', "versionCode $nextVer")
$g = [regex]::Replace($g, 'versionName\s+"[^"]+"', "versionName `"$verStr`"")
[System.IO.File]::WriteAllText($gp, $g, [System.Text.UTF8Encoding]::new($false))

# Stamp matching version into index.html & sync www\index.html
$htmlPath = (Resolve-Path "index.html").Path
$html     = [System.IO.File]::ReadAllText($htmlPath)
$html     = [regex]::Replace($html, 'window\.AQUATWIN_VERSION\s*=\s*"[^"]+"', "window.AQUATWIN_VERSION = `"$verStr`"")
[System.IO.File]::WriteAllText($htmlPath, $html, [System.Text.UTF8Encoding]::new($false))

if (-not (Test-Path "www")) { New-Item -ItemType Directory -Path "www" | Out-Null }
Copy-Item $htmlPath "www\index.html" -Force

npx cap sync android
if ($LASTEXITCODE -ne 0) { throw "Capacitor sync failed." }

# Build signed release APK
Push-Location "android"
try {
  if (-not (Test-Path "keystore.properties")) {
    throw "keystore.properties not found in mobile-app\android. Run keystore setup first."
  }
  Write-Host "Building signed Release APK v$verStr (code $nextVer)..." -ForegroundColor Cyan
  .\gradlew.bat assembleRelease "-Dorg.gradle.java.home=$jdk21"
  if ($LASTEXITCODE -ne 0) { throw "Gradle assembleRelease failed." }
  $apk = (Resolve-Path "app\build\outputs\apk\release\app-release.apk").Path
} finally {
  Pop-Location
}

# Auto-install on USB-connected phone (handles one-time debug->release signature switch)
$adb = "$env:ANDROID_HOME\platform-tools\adb.exe"
if (Test-Path $adb) {
  $connected = (& $adb devices | Select-String "\tdevice$")
  if ($connected) {
    Write-Host "Installing signed AquaTwin AI v$verStr on connected phone..." -ForegroundColor Cyan
    & $adb install -r $apk
    if ($LASTEXITCODE -ne 0) {
      Write-Host "Switching from old debug signature to release signature (one-time clean install)..." -ForegroundColor Yellow
      & $adb uninstall com.aquatwin.ai | Out-Null
      & $adb install $apk
    }
    & $adb shell monkey -p com.aquatwin.ai -c android.intent.category.LAUNCHER 1 | Out-Null
    Write-Host "UPDATED & OPENED signed AquaTwin AI v$verStr on phone!" -ForegroundColor Green
  }
}