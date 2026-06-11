#!/usr/bin/env bash
# Build the Deep-Live-Cam standalone desktop app (Linux / macOS).
#
# Usage:  packaging/build.sh
#
# Environment overrides:
#   PYTHON       python interpreter to use (default: python3)
#   VENV_DIR     build virtualenv location (default: <repo>/.venv-build)
#   SKIP_FFMPEG  set to 1 to skip bundling static ffmpeg/ffprobe
#   DLC_CONSOLE  set to 1 to keep a console attached (debug builds)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv-build}"

echo "==> Using interpreter: $PYTHON"
if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Installing dependencies"
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller static-ffmpeg

echo "==> Generating app icons"
python packaging/make_icon.py || echo "warning: icon generation failed, building without icon"

if [ "${SKIP_FFMPEG:-0}" != "1" ]; then
    echo "==> Fetching static ffmpeg/ffprobe"
    export FFMPEG_BIN_DIR="$ROOT/packaging/ffmpeg-bin"
    mkdir -p "$FFMPEG_BIN_DIR"
    python - <<'PY'
import os
import shutil

from static_ffmpeg import run

ffmpeg, ffprobe = run.get_or_fetch_platform_executables_else_none()
dest = os.environ["FFMPEG_BIN_DIR"]
for src in (ffmpeg, ffprobe):
    if src and os.path.isfile(src):
        target = os.path.join(dest, os.path.basename(src))
        shutil.copy2(src, target)
        os.chmod(target, 0o755)
        print(f"bundled {target}")
PY
else
    echo "==> Skipping ffmpeg bundling (SKIP_FFMPEG=1)"
fi

echo "==> Running PyInstaller"
pyinstaller packaging/deep-live-cam.spec --noconfirm

echo "==> Creating archive"
OS_NAME="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
mkdir -p dist
if [ "$OS_NAME" = "darwin" ]; then
    ARCHIVE="dist/Deep-Live-Cam-macos-$ARCH.zip"
    rm -f "$ARCHIVE"
    ditto -c -k --keepParent "dist/Deep-Live-Cam.app" "$ARCHIVE"
else
    ARCHIVE="dist/Deep-Live-Cam-$OS_NAME-$ARCH.tar.gz"
    rm -f "$ARCHIVE"
    tar -C dist -czf "$ARCHIVE" Deep-Live-Cam
fi

echo "==> Done: $ARCHIVE"
