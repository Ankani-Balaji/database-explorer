# Builds release\DatabaseExplorer-Setup-<version>.exe (the installer friends download) from scratch.
# Needs Inno Setup 6:  winget install JRSoftware.InnoSetup --scope user
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

Write-Host "4/5 Packaging the app (release\DatabaseExplorer\)..."
$old = Join-Path $root "release\DatabaseExplorer.exe"  # single-file build of version 1.0.0
if (Test-Path $old) { Remove-Item $old }
& $py -m PyInstaller --noconfirm --clean `
  --distpath (Join-Path $root "release") `
  --workpath (Join-Path $root "packaging\build") `
  (Join-Path $root "packaging\DatabaseExplorer.spec")
if ($LASTEXITCODE) { throw "PyInstaller failed" }

Write-Host "5/5 Building the installer..."
$version = (Select-String -Path (Join-Path $root "backend\app.py") -Pattern '^VERSION = "(.+)"').Matches[0].Groups[1].Value
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found. Install it with: winget install JRSoftware.InnoSetup --scope user" }
& $iscc /Q "/DAppVersion=$version" (Join-Path $root "packaging\installer.iss")
if ($LASTEXITCODE) { throw "Inno Setup failed" }

$setup = Join-Path $root "release\DatabaseExplorer-Setup-$version.exe"
$size = [math]::Round((Get-Item $setup).Length / 1MB, 1)
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash
Write-Host ""
Write-Host "Done: $setup ($size MB)"
Write-Host "SHA-256: $hash"
