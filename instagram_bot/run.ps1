# Run Instagram bot with correct Playwright browser path (use if you have PLAYWRIGHT_BROWSERS_PATH set elsewhere)
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
Set-Location $PSScriptRoot
try {
    python main.py
} finally {
    Read-Host "`nPress Enter to close this window"
}
