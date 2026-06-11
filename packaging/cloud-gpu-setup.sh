#!/usr/bin/env bash
# Deep-Live-Cam — cloud GPU server setup (the "upgrade path").
#
# Provisions a fresh Ubuntu 22.04/24.04 VM with an NVIDIA GPU (AWS g4dn/g5,
# GCP T4/L4, Paperspace, Lambda, etc.) to run Deep-Live-Cam with CUDA
# acceleration. Intended for fast VIDEO FILE processing via CLI mode;
# for live webcam use, prefer a local machine with a dedicated GPU.
#
# Usage (run on the VM as a regular user with sudo):
#   git clone <your-fork-url> deep-live-cam && cd deep-live-cam
#   bash packaging/cloud-gpu-setup.sh
#
# Then process a video:
#   source venv/bin/activate
#   python run.py -s face.jpg -t input.mp4 -o output.mp4 \
#       --execution-provider cuda --keep-fps
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Checking for NVIDIA GPU"
if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "ERROR: nvidia-smi not found. Pick a VM image with NVIDIA drivers"
    echo "preinstalled (e.g. AWS Deep Learning AMI, GCP Deep Learning VM,"
    echo "Lambda/Paperspace ML images), or install the driver first:"
    echo "  sudo apt-get update && sudo apt-get install -y ubuntu-drivers-common"
    echo "  sudo ubuntu-drivers autoinstall && sudo reboot"
    exit 1
fi
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo "==> Installing system dependencies"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-venv python3-dev build-essential ffmpeg \
    libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0

echo "==> Creating virtual environment"
if [ ! -d venv ]; then
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip

echo "==> Installing Python dependencies (includes onnxruntime-gpu)"
pip install -r requirements.txt

echo "==> Installing CUDA runtime libraries via pip wheels"
# onnxruntime-gpu 1.23 needs CUDA 12 + cuDNN 9. Shipping them as pip wheels
# keeps the setup self-contained; run.py preloads them from the venv at start.
pip install \
    "nvidia-cuda-runtime-cu12" \
    "nvidia-cublas-cu12" \
    "nvidia-cudnn-cu12>=9,<10" \
    "nvidia-cufft-cu12" \
    "nvidia-cuda-nvrtc-cu12"

echo "==> Verifying CUDA execution provider"
python - <<'PY'
import sys

# Mirror run.py's loader so onnxruntime can find the pip-provided CUDA libs.
import os, ctypes, glob
py_lib = f"python{sys.version_info.major}.{sys.version_info.minor}"
nvidia_dir = os.path.join("venv", "lib", py_lib, "site-packages", "nvidia")
if os.path.isdir(nvidia_dir):
    for pkg in os.listdir(nvidia_dir):
        lib_dir = os.path.join(nvidia_dir, pkg, "lib")
        if os.path.isdir(lib_dir):
            for so in sorted(glob.glob(os.path.join(lib_dir, "lib*.so*"))):
                try:
                    ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass

import onnxruntime
providers = onnxruntime.get_available_providers()
print(f"onnxruntime {onnxruntime.__version__} providers: {providers}")
if "CUDAExecutionProvider" not in providers:
    print("ERROR: CUDAExecutionProvider not available — check driver/CUDA setup")
    sys.exit(1)
print("CUDA OK")
PY

echo
echo "==> Setup complete. Process a video with:"
echo "    source venv/bin/activate"
echo "    python run.py -s face.jpg -t input.mp4 -o output.mp4 \\"
echo "        --execution-provider cuda --keep-fps"
echo
echo "    (models are downloaded automatically on first run, ~600MB)"
echo
echo "Tip: shut the VM down when not in use — GPU instances bill hourly."
