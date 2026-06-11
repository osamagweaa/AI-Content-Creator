# Build the Deep-Live-Cam standalone desktop app (Windows).
#
# Usage:  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#
# Environment overrides:
#   $env:PYTHON       python interpreter to use (default: python)
#   $env:VENV_DIR     build virtualenv location (default: <repo>\.venv-build)
#   $env:SKIP_FFMPEG  set to 1 to skip bundling static ffmpeg/ffprobe
#   $env:DLC_CONSOLE  set to 1 to keep a console attached (debug builds)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$VenvDir = if ($env:VENV_DIR) { $env:VENV_DIR } else { Join-Path $Root ".venv-build" }

Write-Host "==> Using interpreter: $Python"
if (-not (Test-Path $VenvDir)) {
    & $Python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
& (Join-Path $VenvDir "Scripts\Activate.ps1")

Write-Host "==> Installing dependencies"
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "dependency install failed" }

# Ship DirectML instead of the CUDA build of onnxruntime: it accelerates
# inference on ANY DirectX 12 GPU (NVIDIA, AMD, Intel iGPUs) without CUDA
# runtime DLLs, and falls back to CPU automatically when no GPU is present.
Write-Host "==> Swapping onnxruntime-gpu for onnxruntime-directml"
pip uninstall -y onnxruntime onnxruntime-gpu
pip install onnxruntime-directml==1.23.0
if ($LASTEXITCODE -ne 0) { throw "onnxruntime-directml install failed" }

pip install pyinstaller static-ffmpeg
if ($LASTEXITCODE -ne 0) { throw "build tool install failed" }

Write-Host "==> Generating app icons"
python packaging\make_icon.py
if ($LASTEXITCODE -ne 0) { Write-Warning "icon generation failed, building without icon" }

if ($env:SKIP_FFMPEG -ne "1") {
    Write-Host "==> Fetching static ffmpeg/ffprobe"
    $env:FFMPEG_BIN_DIR = Join-Path $Root "packaging\ffmpeg-bin"
    New-Item -ItemType Directory -Force -Path $env:FFMPEG_BIN_DIR | Out-Null
    $fetchScript = @"
import os
import shutil

from static_ffmpeg import run

ffmpeg, ffprobe = run.get_or_fetch_platform_executables_else_raise()
dest = os.environ['FFMPEG_BIN_DIR']
for src in (ffmpeg, ffprobe):
    if src and os.path.isfile(src):
        target = os.path.join(dest, os.path.basename(src))
        shutil.copy2(src, target)
        print(f'bundled {target}')
"@
    python -c $fetchScript
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg fetch failed" }
} else {
    Write-Host "==> Skipping ffmpeg bundling (SKIP_FFMPEG=1)"
}

Write-Host "==> Running PyInstaller"
pyinstaller packaging\deep-live-cam.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "==> Creating archive"
$Archive = "dist\Deep-Live-Cam-windows-x64.zip"
if (Test-Path $Archive) { Remove-Item $Archive }
Compress-Archive -Path "dist\Deep-Live-Cam" -DestinationPath $Archive

Write-Host "==> Done: $Archive"
