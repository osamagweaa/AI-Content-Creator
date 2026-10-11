# AGENTS.md

## Cursor Cloud specific instructions

Deep-Live-Cam is a single **Python desktop application** (PySide6 GUI + a headless
CLI) for image/video/webcam face swapping. There is no web server, API, or
database. The standard setup/run commands live in `README.md`; this section only
captures the non-obvious things needed to run it in the Cursor Cloud VM.

### Environment basics
- Python 3.12 is used here (README recommends 3.11, but 3.12 works). All work runs
  inside the project venv at `./venv` — invoke tools as `./venv/bin/python`,
  `./venv/bin/pip`, `./venv/bin/ruff`. The update script (re)creates the venv and
  installs `requirements.txt`.
- `ffmpeg`/`ffprobe` are required and already present on the system.
- The VM is **CPU-only** (no GPU). `requirements.txt` pins `onnxruntime-gpu`, which
  loads fine and falls back to `CPUExecutionProvider`. Always run with
  `--execution-provider cpu`. Note: the startup banner prints
  `accelerator: CUDA (NVIDIA)` and ORT lists CUDA/Tensorrt providers, but the
  actual provider used is CPU (you'll see `Applied providers: ['CPUExecutionProvider']`).
  The `cuInit ... UNKNOWN ERROR (303)` and `Unable to register cuFFT/cuDNN/cuBLAS`
  log lines are harmless on this CPU-only host.

### Models (large, not in git)
- Core models live in `models/`: `inswapper_128_fp16.onnx` and `GFPGANv1.4.onnx`
  (download URLs in `models/instructions.txt`). On first run the app also
  auto-downloads `models/inswapper_128.onnx` (FP32, ~529 MB) and the InsightFace
  `buffalo_l` pack into `~/.insightface/models/` (~280 MB). These downloads need
  outbound internet; once present they are reused.

### Lint / test
- Lint matches CI (`.github/workflows/ruff.yml`): `ruff` is **not** in
  `requirements.txt`; the update script installs `ruff==0.15.7`. Run
  `./venv/bin/ruff check` (CI uses `ruff check --output-format=github`).
- Tests: `./venv/bin/python -m unittest discover -s tests` — fast, all heavy deps
  are mocked, no models/GPU needed.

### Running the GUI (important gotcha)
- The GUI needs a display; the VM provides `DISPLAY=:1`. Launch with:
  `DISPLAY=:1 ./venv/bin/python run.py --execution-provider cpu`
- **Qt plugin conflict:** the full `opencv-python` wheel ships its own Qt5
  platform plugins and, on import, force-sets `QT_QPA_PLATFORM_PLUGIN_PATH` to
  `cv2/qt/plugins`, shadowing PySide6's Qt6 `xcb` plugin and crashing the GUI.
  The fix (applied during setup and re-applied idempotently by the update script)
  is to neutralize cv2's bundled Qt dir, i.e. rename
  `venv/lib/python3.12/site-packages/cv2/qt` → `cv2/qt_disabled`. After that
  PySide6's own `xcb` plugin loads. This only affects the GUI; the headless CLI
  does not touch Qt.
- Required system libs for the Qt xcb plugin (libEGL/GL, xcb-*, and especially
  `libxkbcommon-x11-0`) are installed in the VM image, so they persist via the
  snapshot and are not part of the update script.

### Running the headless CLI (good for quick verification)
- `./venv/bin/python run.py -s <source_face.jpg> -t <target.jpg|mp4> -o <out> --execution-provider cpu`
- Passing `-s/-t/-o` triggers headless mode (no GUI). Output for an image target is
  written to the `-o` path.
- For a reliable face-swap demo, use clear, reasonably large, single-face frontal
  photos. Tiny crops or low-quality faces can fall below InsightFace's 0.5
  detection threshold and produce "No face found"; in that case the output is just
  a copy of the target with no swap.
