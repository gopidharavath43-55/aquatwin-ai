Add-Type -AssemblyName System.Drawing

$resDir = Join-Path (Get-Location) "android\app\src\main\res"

function New-DropletPath([float]$size, [float]$scale, [float]$yShift) {
  $cx = [float]($size * 0.50)
  $cy = [float]($size * (0.56 + $yShift))
  $r  = [float]($size * 0.255 * $scale)
  $p  = New-Object System.Drawing.Drawing2D.GraphicsPath
  $p.AddBezier($cx, [float]($cy - $r * 1.80), [float]($cx - $r * 0.14), [float]($cy - $r * 1.25), [float]($cx - $r), [float]($cy - $r * 0.55), [float]($cx - $r), [float]($cy + $r * 0.05))
  $p.AddBezier([float]($cx - $r), [float]($cy + $r * 0.05), [float]($cx - $r), [float]($cy + $r * 0.62), [float]($cx - $r * 0.55), [float]($cy + $r), $cx, [float]($cy + $r))
  $p.AddBezier($cx, [float]($cy + $r), [float]($cx + $r * 0.55), [float]($cy + $r), [float]($cx + $r), [float]($cy + $r * 0.62), [float]($cx + $r), [float]($cy + $r * 0.05))
  $p.AddBezier([float]($cx + $r), [float]($cy + $r * 0.05), [float]($cx + $r), [float]($cy - $r * 0.55), [float]($cx + $r * 0.14), [float]($cy - $r * 1.25), $cx, [float]($cy - $r * 1.80))
  $p.CloseFigure()
  return $p
}

function New-RoundedRectPath([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
  $d = [float]($r * 2.0)
  $p = New-Object System.Drawing.Drawing2D.GraphicsPath
  $p.AddArc($x, $y, $d, $d, [float]180, [float]90)
  $p.AddArc([float]($x + $w - $d), $y, $d, $d, [float]270, [float]90)
  $p.AddArc([float]($x + $w - $d), [float]($y + $h - $d), $d, $d, [float]0, [float]90)
  $p.AddArc($x, [float]($y + $h - $d), $d, $d, [float]90, [float]90)
  $p.CloseFigure()
  return $p
}

function Draw-ObsidianBg([System.Drawing.Graphics]$g, [int]$size) {
  $g.Clear([System.Drawing.Color]::FromArgb(255, 13, 16, 22))
  $gp = New-Object System.Drawing.Drawing2D.GraphicsPath
  $gp.AddEllipse([float](-$size * 0.25), [float](-$size * 0.35), [float]($size * 1.50), [float]($size * 1.50))
  $pgb = New-Object System.Drawing.Drawing2D.PathGradientBrush($gp)
  $pgb.CenterPoint = [System.Drawing.PointF]::new([float]($size * 0.50), [float]($size * 0.26))
  $pgb.CenterColor = [System.Drawing.Color]::FromArgb(255, 40, 48, 62)
  $pgb.SurroundColors = [System.Drawing.Color[]]@([System.Drawing.Color]::FromArgb(255, 13, 16, 22))
  $g.FillRectangle($pgb, 0, 0, $size, $size)
  $pgb.Dispose(); $gp.Dispose()

  $sheen = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(20, 255, 255, 255))
  $g.FillEllipse($sheen, [float](-$size * 0.15), [float](-$size * 0.34), [float]($size * 1.30), [float]($size * 0.72))
  $sheen.Dispose()
}

function Draw-LiquidDroplet([System.Drawing.Graphics]$g, [int]$size, [float]$scale) {
  $path = New-DropletPath ([float]$size) $scale ([float]0.0)

  # Soft cyan liquid-glass ambient aura
  foreach ($step in @(@(0.11, 12), @(0.075, 18), @(0.045, 26), @(0.022, 34))) {
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb([int]$step[1], 56, 189, 248), [float]($size * $step[0]))
    $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $g.DrawPath($pen, $path)
    $pen.Dispose()
  }

  # Iridescent Apple Liquid Glass fill
  $grad = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    [System.Drawing.PointF]::new([float]($size * 0.22), [float]($size * 0.14)),
    [System.Drawing.PointF]::new([float]($size * 0.78), [float]($size * 0.86)),
    [System.Drawing.Color]::FromArgb(245, 175, 250, 255),
    [System.Drawing.Color]::FromArgb(245, 214, 146, 255)
  )
  $cb = New-Object System.Drawing.Drawing2D.ColorBlend
  $cb.Colors = [System.Drawing.Color[]]@(
    [System.Drawing.Color]::FromArgb(245, 175, 250, 255),
    [System.Drawing.Color]::FromArgb(245, 56, 198, 252),
    [System.Drawing.Color]::FromArgb(245, 96, 138, 255),
    [System.Drawing.Color]::FromArgb(245, 214, 146, 255)
  )
  $cb.Positions = [float[]]@(0.0, 0.36, 0.72, 1.0)
  $grad.InterpolationColors = $cb
  $g.FillPath($grad, $path)
  $grad.Dispose()

  # Clipped glass refraction, specular highlight, and caustics
  $state = $g.Save()
  $g.SetClip($path)

  # Inner refraction depth
  $dp = New-Object System.Drawing.Drawing2D.GraphicsPath
  $dr = [float]($size * 0.22 * $scale)
  $dp.AddEllipse([float]($size * 0.50 - $dr), [float]($size * 0.58 - $dr * 0.85), [float]($dr * 2.0), [float]($dr * 1.9))
  $dpgb = New-Object System.Drawing.Drawing2D.PathGradientBrush($dp)
  $dpgb.CenterColor = [System.Drawing.Color]::FromArgb(85, 8, 28, 92)
  $dpgb.SurroundColors = [System.Drawing.Color[]]@([System.Drawing.Color]::FromArgb(0, 8, 28, 92))
  $g.FillPath($dpgb, $dp)
  $dpgb.Dispose(); $dp.Dispose()

  # Upper-left specular highlight
  $st2 = $g.Save()
  $g.TranslateTransform([float]($size * 0.405), [float]($size * 0.525))
  $g.RotateTransform([float]-16)
  $sb1 = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(145, 255, 255, 255))
  $g.FillEllipse($sb1, [float](-$size * 0.055 * $scale), [float](-$size * 0.11 * $scale), [float]($size * 0.11 * $scale), [float]($size * 0.22 * $scale))
  $sb1.Dispose()
  $sb2 = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(230, 255, 255, 255))
  $g.FillEllipse($sb2, [float](-$size * 0.028 * $scale), [float](-$size * 0.075 * $scale), [float]($size * 0.052 * $scale), [float]($size * 0.105 * $scale))
  $sb2.Dispose()
  $g.Restore($st2)

  # Bottom-right caustic bounce light
  $cbBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(105, 196, 248, 255))
  $g.FillEllipse($cbBrush, [float]($size * 0.46), [float]($size * 0.65), [float]($size * 0.22 * $scale), [float]($size * 0.11 * $scale))
  $cbBrush.Dispose()

  $g.Restore($state)

  # Crisp specular glass rim
  $rimGrad = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    [System.Drawing.PointF]::new([float]($size * 0.2), [float]($size * 0.1)),
    [System.Drawing.PointF]::new([float]($size * 0.8), [float]($size * 0.9)),
    [System.Drawing.Color]::FromArgb(235, 255, 255, 255),
    [System.Drawing.Color]::FromArgb(135, 165, 225, 255)
  )
  $rimPen = New-Object System.Drawing.Pen($rimGrad, [float]([Math]::Max(2.0, $size * 0.013)))
  $rimPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  $g.DrawPath($rimPen, $path)
  $rimPen.Dispose(); $rimGrad.Dispose(); $path.Dispose()
}

function New-MasterBitmap([int]$size, [string]$mode) {
  $bmp = New-Object System.Drawing.Bitmap($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

  if ($mode -eq "fg") {
    $g.Clear([System.Drawing.Color]::Transparent)
    Draw-LiquidDroplet $g $size ([float]0.78)
  } elseif ($mode -eq "round") {
    $g.Clear([System.Drawing.Color]::Transparent)
    $cp = New-Object System.Drawing.Drawing2D.GraphicsPath
    $cp.AddEllipse([float]0, [float]0, [float]($size - 1), [float]($size - 1))
    $g.SetClip($cp)
    Draw-ObsidianBg $g $size
    Draw-LiquidDroplet $g $size ([float]1.06)
    $g.ResetClip()
    $cp.Dispose()
  } else {
    Draw-ObsidianBg $g $size
    Draw-LiquidDroplet $g $size ([float]1.06)
  }
  $g.Dispose()
  return $bmp
}

function Resize-Bitmap([System.Drawing.Bitmap]$src, [int]$w, [int]$h) {
  $dst = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($dst)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $g.DrawImage($src, 0, 0, $w, $h)
  $g.Dispose()
  return $dst
}

function New-SplashBitmap([int]$w, [int]$h, [System.Drawing.Bitmap]$iconMaster) {
  $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.Clear([System.Drawing.Color]::FromArgb(255, 6, 17, 36))

  $s = [Math]::Min($w, $h)
  $gr = [float]($s * 0.42)
  $gp = New-Object System.Drawing.Drawing2D.GraphicsPath
  $gp.AddEllipse([float]($w * 0.5 - $gr), [float]($h * 0.5 - $gr), [float]($gr * 2.0), [float]($gr * 2.0))
  $pgb = New-Object System.Drawing.Drawing2D.PathGradientBrush($gp)
  $pgb.CenterColor = [System.Drawing.Color]::FromArgb(72, 24, 118, 198)
  $pgb.SurroundColors = [System.Drawing.Color[]]@([System.Drawing.Color]::FromArgb(0, 6, 17, 36))
  $g.FillPath($pgb, $gp)
  $pgb.Dispose(); $gp.Dispose()

  $bs = [int]($s * 0.27)
  $bx = [float](($w - $bs) * 0.5)
  $by = [float](($h - $bs) * 0.5)
  $br = [float]($bs * 0.25)
  $sq = New-RoundedRectPath $bx $by ([float]$bs) ([float]$bs) $br
  $st = $g.Save()
  $g.SetClip($sq)
  $g.DrawImage($iconMaster, $bx, $by, [float]$bs, [float]$bs)
  $g.Restore($st)
  $bpen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(145, 196, 234, 255), [float]([Math]::Max(2.0, $bs / 72.0)))
  $g.DrawPath($bpen, $sq)
  $bpen.Dispose(); $sq.Dispose(); $g.Dispose()
  return $bmp
}

$mFull  = New-MasterBitmap 512 "full"
$mRound = New-MasterBitmap 512 "round"
$mFg    = New-MasterBitmap 512 "fg"

$updated = 0
if (Test-Path $resDir) {
  Get-ChildItem $resDir -Recurse -Filter "*.png" | ForEach-Object {
    $folder = $_.Directory.Name
    $name = $_.Name.ToLower()
    if ($folder -like "mipmap-*" -and ($name -like "*ic_launcher*")) {
      $im = [System.Drawing.Image]::FromFile($_.FullName)
      $w = $im.Width; $h = $im.Height; $im.Dispose()
      $src = if ($name -like "*foreground*") { $mFg } elseif ($name -like "*round*") { $mRound } else { $mFull }
      $out = Resize-Bitmap $src $w $h
      $out.Save($_.FullName, [System.Drawing.Imaging.ImageFormat]::Png)
      $out.Dispose()
      $updated++
    } elseif ($folder -like "drawable*" -and $name -eq "splash.png") {
      $im = [System.Drawing.Image]::FromFile($_.FullName)
      $w = $im.Width; $h = $im.Height; $im.Dispose()
      $sp = New-SplashBitmap $w $h $mFull
      $sp.Save($_.FullName, [System.Drawing.Imaging.ImageFormat]::Png)
      $sp.Dispose()
      $updated++
    }
  }

  $bgXml = Join-Path $resDir "values\ic_launcher_background.xml"
  if (Test-Path $bgXml) {
    $t = [System.IO.File]::ReadAllText($bgXml)
    $t = [regex]::Replace($t, '(<color\s+name="ic_launcher_background"\s*>)[^<]+(</color>)', '${1}#14171D${2}')
    [System.IO.File]::WriteAllText($bgXml, $t, [System.Text.UTF8Encoding]::new($false))
  }

  foreach ($sub in @("drawable", "drawable-v24")) {
    $bgDraw = Join-Path $resDir "$sub\ic_launcher_background.xml"
    if (Test-Path $bgDraw) {
      $gradXml = '<?xml version="1.0" encoding="utf-8"?>' + "`n" +
        '<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">' + "`n" +
        '  <gradient android:type="radial" android:gradientRadius="85%p" android:centerX="50%" android:centerY="28%" android:startColor="#242B37" android:endColor="#0D1016"/>' + "`n" +
        '</shape>'
      [System.IO.File]::WriteAllText($bgDraw, $gradXml, [System.Text.UTF8Encoding]::new($false))
    }
  }

  $stylesXml = Join-Path $resDir "values\styles.xml"
  if (Test-Path $stylesXml) {
    $st = [System.IO.File]::ReadAllText($stylesXml)
    $st = [regex]::Replace($st, '(<item\s+name="android:windowSplashScreenBackground"\s*>)[^<]+(</item>)', '${1}#061124${2}')
    [System.IO.File]::WriteAllText($stylesXml, $st, [System.Text.UTF8Encoding]::new($false))
  }
}

$mFull.Dispose(); $mRound.Dispose(); $mFg.Dispose()
Write-Host "Generated $updated Apple Liquid Glass icon & splash PNGs natively!" -ForegroundColor Green
