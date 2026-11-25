$target = "C:\Users\gopid\aquatwin-ai\mobile-app\index.html"
$lastWrite = (Get-Item $target).LastWriteTime
Write-Host "Watching $target for edits... (Press Ctrl+C to stop)" -ForegroundColor Cyan
while ($true) {
    Start-Sleep -Seconds 5
    $curr = (Get-Item $target).LastWriteTime
    if ($curr -gt $lastWrite) {
        $lastWrite = $curr
        Write-Host "`n[CHANGE DETECTED] Building & publishing update to GitHub..." -ForegroundColor Yellow
        powershell -ExecutionPolicy Bypass -File "C:\Users\gopid\aquatwin-ai\mobile-app\publish-update.ps1" -Notes "Auto-published update"
    }
}