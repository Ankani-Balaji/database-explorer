# Builds release\DatabaseExplorer.exe from scratch.
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
# A separate environment just for building, so the build never changes backend\venv
# (which may be in use by a running backend).
$buildVenv = Join-Path $root "packaging\.venv"
$py = Join-Path $buildVenv "Scripts\python.exe"

Write-Host "1/4 Preparing the build environment..."
if (-not (Test-Path $py)) {
  & (Join-Path $root "backend\venv\Scripts\python.exe") -m venv $buildVenv
  if ($LASTEXITCODE) { throw "creating the build environment failed" }
}
& $py -m pip install --disable-pip-version-check -q -r (Join-Path $root "backend\requirements.txt") -r (Join-Path $root "packaging\requirements-build.txt")
if ($LASTEXITCODE) { throw "pip install failed" }

Write-Host "2/4 Drawing icons..."
& $py (Join-Path $root "packaging\make_icons.py")
if ($LASTEXITCODE) { throw "icon generation failed" }

Write-Host "3/4 Building the web app..."
Push-Location (Join-Path $root "frontend")
try {
  # "npm install", not "npm ci": ci deletes node_modules first, which fails (and leaves it
  # half-deleted) while a dev server is running.
  npm install --no-audit --no-fund
  if ($LASTEXITCODE) { throw "npm install failed" }
  npm run build
  if ($LASTEXITCODE) { throw "npm run build failed" }
} finally { Pop-Location }

Write-Host "4/4 Packaging DatabaseExplorer.exe..."
& $py -m PyInstaller --noconfirm --clean `
  --distpath (Join-Path $root "release") `
  --workpath (Join-Path $root "packaging\build") `
  (Join-Path $root "packaging\DatabaseExplorer.spec")
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$exe = Join-Path $root "release\DatabaseExplorer.exe"
$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
Write-Host ""
Write-Host "Done: $exe ($size MB)"
Write-Host "SHA-256: $hash"
