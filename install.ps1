# Install OpenAgent on Windows.
# Usage: irm https://raw.githubusercontent.com/haseeb-heaven/open-agent/main/install.ps1 | iex

Write-Host "Installing OpenAgent..." -ForegroundColor Cyan

if (Get-Command npm -ErrorAction SilentlyContinue) {
    npm install -g open-agent
    Write-Host "Installed! Run: openagent" -ForegroundColor Green
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install HaseebHeaven.OpenAgent
    Write-Host "Installed via winget! Run: openagent" -ForegroundColor Green
} elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
    scoop bucket add openagent https://github.com/haseeb-heaven/scoop-openagent
    scoop install openagent
    Write-Host "Installed via scoop! Run: openagent" -ForegroundColor Green
} else {
    Write-Host "Please install Node.js 22+ from https://nodejs.org" -ForegroundColor Red
    exit 1
}
