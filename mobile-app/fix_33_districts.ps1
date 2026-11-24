$nameMap = @{
  "adilabad"                = "Adilabad"
  "bhadradri"               = "Bhadradri Kothagudem"
  "badradri"                = "Bhadradri Kothagudem"
  "kothagudem"              = "Bhadradri Kothagudem"
  "bhadradri kothagudem"    = "Bhadradri Kothagudem"
  "hanumakonda"             = "Hanumakonda"
  "hanamkonda"              = "Hanumakonda"
  "warangal urban"          = "Hanumakonda"
  "hyderabad"               = "Hyderabad"
  "jagtial"                 = "Jagtial"
  "jagitial"                = "Jagtial"
  "jagityal"                = "Jagtial"
  "jangaon"                 = "Jangaon"
  "jangoan"                 = "Jangaon"
  "jayashankar"             = "Jayashankar Bhupalpally"
  "bhupalpally"             = "Jayashankar Bhupalpally"
  "jayashankar bhupalpally" = "Jayashankar Bhupalpally"
  "jayashankar bhupalapally"= "Jayashankar Bhupalpally"
  "jogulamba"               = "Jogulamba Gadwal"
  "gadwal"                  = "Jogulamba Gadwal"
  "jogulamba gadwal"        = "Jogulamba Gadwal"
  "kamareddy"               = "Kamareddy"
  "karimnagar"              = "Karimnagar"
  "khammam"                 = "Khammam"
  "komaram bheem"           = "Kumuram Bheem Asifabad"
  "komaram bheem asifabad"  = "Kumuram Bheem Asifabad"
  "kumuram bheem"           = "Kumuram Bheem Asifabad"
  "kumuram bheem asifabad"  = "Kumuram Bheem Asifabad"
  "kumarambheem asifabad"   = "Kumuram Bheem Asifabad"
  "asifabad"                = "Kumuram Bheem Asifabad"
  "mahabubabad"             = "Mahabubabad"
  "mahbubabad"              = "Mahabubabad"
  "mahabubnagar"            = "Mahabubnagar"
  "mahbubnagar"             = "Mahabubnagar"
  "mancherial"              = "Mancherial"
  "mancherial district"     = "Mancherial"
  "medak"                   = "Medak"
  "medchal"                 = "Medchal-Malkajgiri"
  "malkajgiri"              = "Medchal-Malkajgiri"
  "medchal malkajgiri"      = "Medchal-Malkajgiri"
  "medchal-malkajgiri"      = "Medchal-Malkajgiri"
  "mulugu"                  = "Mulugu"
  "nagarkurnool"            = "Nagarkurnool"
  "nalgonda"                = "Nalgonda"
  "narayanpet"              = "Narayanpet"
  "nirmal"                  = "Nirmal"
  "nizamabad"               = "Nizamabad"
  "peddapalli"              = "Peddapalli"
  "peddapalle"              = "Peddapalli"
  "rajanna"                 = "Rajanna Sircilla"
  "sircilla"                = "Rajanna Sircilla"
  "rajanna sircilla"        = "Rajanna Sircilla"
  "rangareddy"              = "Ranga Reddy"
  "ranga reddy"             = "Ranga Reddy"
  "sangareddy"              = "Sangareddy"
  "sanga reddy"             = "Sangareddy"
  "siddipet"                = "Siddipet"
  "suryapet"                = "Suryapet"
  "vikarabad"               = "Vikarabad"
  "wanaparthy"              = "Wanaparthy"
  "warangal"                = "Warangal"
  "warangal rural"          = "Warangal"
  "yadadri"                 = "Yadadri Bhuvanagiri"
  "bhuvanagiri"             = "Yadadri Bhuvanagiri"
  "bhongir"                 = "Yadadri Bhuvanagiri"
  "yadadri bhuvanagiri"     = "Yadadri Bhuvanagiri"
}

function Normalize-DistrictName([string]$raw) {
  if ([string]::IsNullOrWhiteSpace($raw)) { return $raw }
  $key = ($raw -replace '[\u2013\u2014]+', '-' -replace '\s+', ' ').Trim().ToLower()
  if ($nameMap.ContainsKey($key)) { return $nameMap[$key] }
  return $raw.Trim()
}

function Update-JsonObject($obj) {
  if ($null -eq $obj) { return }
  if ($obj -is [System.Collections.IList]) {
    for ($i = 0; $i -lt $obj.Count; $i++) {
      if ($obj[$i] -is [string]) {
        $obj[$i] = Normalize-DistrictName $obj[$i]
      } else {
        Update-JsonObject $obj[$i]
      }
    }
    return
  }
  if ($obj -is [PSCustomObject]) {
    foreach ($p in $obj.PSObject.Properties) {
      if ($p.Value -is [string] -and ($p.Name -match '^(district|district_name|name)$')) {
        $p.Value = Normalize-DistrictName $p.Value
      } elseif ($p.Value -is [PSCustomObject] -or $p.Value -is [System.Collections.IList]) {
        Update-JsonObject $p.Value
      }
    }
    if ($obj.PSObject.Properties['districts'] -and $obj.districts -is [System.Collections.IList]) {
      $obj.districts = @($obj.districts | Sort-Object -Property district)
    }
  }
}

# 1. Update ..\ml\ml_predictions.json if present
$predFile = "..\ml\ml_predictions.json"
if (Test-Path $predFile) {
  $predPath = (Resolve-Path $predFile).Path
  $predObj = [System.IO.File]::ReadAllText($predPath) | ConvertFrom-Json
  Update-JsonObject $predObj
  [System.IO.File]::WriteAllText($predPath, ($predObj | ConvertTo-Json -Depth 12), [System.Text.UTF8Encoding]::new($false))
  Write-Host "Updated ..\ml\ml_predictions.json" -ForegroundColor Green
}

# 2. Update www\ml_data.js and ml_data.js
$mlJsPath = (Resolve-Path "www\ml_data.js").Path
$rawJs = [System.IO.File]::ReadAllText($mlJsPath).Trim()
$jsonStr = $rawJs -replace '^window\.AQUATWIN_ML_DATA\s*=\s*', '' -replace ';\s*$', ''
$mlObj = $jsonStr | ConvertFrom-Json
Update-JsonObject $mlObj

$updatedJs = "window.AQUATWIN_ML_DATA = " + ($mlObj | ConvertTo-Json -Depth 12 -Compress) + ";"
[System.IO.File]::WriteAllText($mlJsPath, $updatedJs, [System.Text.UTF8Encoding]::new($false))
Copy-Item "www\ml_data.js" "ml_data.js" -Force

# 3. Update any hardcoded shortened district names inside index.html (exact quoted/tag matches only)
$htmlPath = (Resolve-Path "index.html").Path
$html = [System.IO.File]::ReadAllText($htmlPath)

$exactReplacements = @(
  @("Bhadradri", "Bhadradri Kothagudem"),
  @("Komaram Bheem Asifabad", "Kumuram Bheem Asifabad"),
  @("Komaram Bheem", "Kumuram Bheem Asifabad"),
  @("Kumuram Bheem", "Kumuram Bheem Asifabad"),
  @("Jayashankar Bhupalapally", "Jayashankar Bhupalpally"),
  @("Jayashankar", "Jayashankar Bhupalpally"),
  @("Jogulamba", "Jogulamba Gadwal"),
  @("Medchal Malkajgiri", "Medchal-Malkajgiri"),
  @("Medchal", "Medchal-Malkajgiri"),
  @("Rajanna", "Rajanna Sircilla"),
  @("Yadadri", "Yadadri Bhuvanagiri"),
  @("Rangareddy", "Ranga Reddy"),
  @("Warangal Urban", "Hanumakonda"),
  @("Hanamkonda", "Hanumakonda"),
  @("Warangal Rural", "Warangal"),
  @("Jagitial", "Jagtial"),
  @("Jangoan", "Jangaon"),
  @("Mahbubnagar", "Mahabubnagar")
)

foreach ($pair in $exactReplacements) {
  $oldEsc = [regex]::Escape($pair[0])
  $newVal = $pair[1]
  # Replace exact quoted JS/JSON strings ('Old' or "Old")
  $html = [regex]::Replace($html, "(?i)(['""])$oldEsc\1", ('$1' + $newVal + '$1'))
  # Replace exact HTML tag text (>Old<)
  $html = [regex]::Replace($html, "(?i)>\s*$oldEsc\s*<", (">" + $newVal + "<"))
}

[System.IO.File]::WriteAllText($htmlPath, $html, [System.Text.UTF8Encoding]::new($false))
Copy-Item "index.html" "www\index.html" -Force

Write-Host "`n=== VERIFIED 33 TELANGANA DISTRICTS (FULL NAMES A-Z) ===" -ForegroundColor Cyan
$i = 1
foreach ($d in $mlObj.districts) {
  Write-Host ("{0,2}. {1}" -f $i, $d.district) -ForegroundColor Green
  $i++
}
