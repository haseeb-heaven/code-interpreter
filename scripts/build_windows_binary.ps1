# Build Windows portable binary for Open Code Interpreter (PyInstaller onedir + zip)
# Lean build: avoid --collect-all/--collect-submodules litellm (pulls torch/etc).
param(
    [string]$Version = "",
    [string]$Python = "D:\henv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "interpreter.py"))) {
    $Root = (Get-Location).Path
}
Set-Location $Root

if (-not $Version) {
    $Version = (Get-Content VERSION -Raw).Trim().TrimStart("v")
}

$Name = "open-code-interpreter"
$DistDir = Join-Path $Root "dist\$Name"
$ZipName = "open-code-interpreter-windows-x64-v$Version.zip"
$ZipPath = Join-Path $Root "dist\$ZipName"

Write-Host "==> Building Windows binary v$Version (lean)"

& $Python -m pip install -q pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

Remove-Item -Recurse -Force (Join-Path $Root "build\$Name") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $DistDir -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $Root "$Name.spec") -ErrorAction SilentlyContinue

# Windows --add-data uses ';' separator
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --console `
    --name $Name `
    --paths $Root `
    --add-data "configs;configs" `
    --add-data "system;system" `
    --add-data ".env.example;." `
    --hidden-import dotenv `
    --hidden-import rich `
    --hidden-import litellm `
    --hidden-import pygments `
    --exclude-module torch `
    --exclude-module torchvision `
    --exclude-module torchaudio `
    --exclude-module tensorflow `
    --exclude-module tensorboard `
    --exclude-module IPython `
    --exclude-module jupyter `
    --exclude-module notebook `
    interpreter.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

if (-not (Test-Path (Join-Path $DistDir "$Name.exe"))) {
    throw "Missing exe at $DistDir\$Name.exe"
}

foreach ($folder in @("configs", "system")) {
    $src = Join-Path $Root $folder
    $dst = Join-Path $DistDir $folder
    if (-not (Test-Path $dst)) {
        Copy-Item -Recurse -Force $src $dst
    }
}
Copy-Item -Force (Join-Path $Root ".env.example") (Join-Path $DistDir ".env.example") -ErrorAction SilentlyContinue

$exe = Join-Path $DistDir "$Name.exe"
Write-Host "==> Smoke: --version"
& $exe --version
if ($LASTEXITCODE -ne 0) { throw "--version failed" }
Write-Host "==> Smoke: --help"
& $exe --help | Select-Object -First 20
if ($LASTEXITCODE -ne 0) { throw "--help failed" }

Remove-Item -Force $ZipPath -ErrorAction SilentlyContinue
Compress-Archive -Path $DistDir -DestinationPath $ZipPath -Force
$sizeMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
Write-Host "==> Zip: $ZipPath ($sizeMB MB)"
Write-Host "DONE"
