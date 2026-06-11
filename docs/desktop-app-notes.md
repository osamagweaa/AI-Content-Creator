# Desktop App — Status Log and Notes

Working log for the standalone desktop app effort (branch `cursor/desktop-app-2964`,
PR #1). Written so work can resume after a hardware upgrade without re-discovering
anything.

## Current status (2026-06-11)

**Working.** The app builds as a self-contained desktop bundle for Windows,
macOS (Apple Silicon), and Linux, and was field-verified on Windows 11.

| Release tag | What it proved |
|---|---|
| `v2.1.7-desktop-rc1` | First green CI build on all 3 OSes |
| `v2.1.7-desktop-rc2` | Same, on current GA runners (`windows-2025`, `macos-15`, `ubuntu-24.04`) |
| `v2.1.7-desktop-rc3` | Windowed-crash fix + DirectML + lazy TensorFlow (current best) |

Artifacts are attached to draft GitHub releases per tag. **Use rc3 or later.**

## Field test results (Windows 11, Intel Iris Xe, 8 GB RAM)

- App launches, full UI renders, webcam detected. Functionally correct.
- **Performance is poor on this hardware.** Two compounding causes:
  1. No dedicated GPU — inswapper inference is heavy; Iris Xe via DirectML
     (rc3) helps but does not reach comfortable real-time.
  2. 8 GB RAM at ~90% utilisation — the system swaps to disk under load.
     rc3's lazy TensorFlow reduces footprint substantially, but 8 GB remains
     tight for live mode.
- Conclusion: real-time use needs a dedicated GPU (or the cloud path below).

## Bugs found and fixed along the way

| Bug | Root cause | Fix |
|---|---|---|
| Crash on first run: `'NoneType' object has no attribute 'write'` | Windowed PyInstaller builds set `sys.stdout`/`stderr` to `None`; tqdm writes to stderr during model download | `run.py` redirects both streams to `app.log` in the user data dir; tqdm disabled when stderr is absent |
| Linux frozen app aborts under X11 | opencv-python sets `QT_QPA_PLATFORM_PLUGIN_PATH` to its bundled **Qt5** plugins, breaking PySide6 (**Qt6**) | Env var sanitised before `QApplication`; `cv2/qt` stripped from the bundle |
| `ModuleNotFoundError: matplotlib` in frozen app | insightface imports matplotlib at package-import time (`face3d/mesh/vis.py`) | matplotlib must stay in the bundle (removed from the spec's excludes) |

## Architecture decisions

- **Models/settings/logs** live in a per-user data dir when frozen
  (`%LOCALAPPDATA%\Deep-Live-Cam`, `~/Library/Application Support/Deep-Live-Cam`,
  `~/.local/share/deep-live-cam`); source checkouts keep `<repo>/models`.
  See `modules/paths.py`.
- **ffmpeg/ffprobe** are bundled (`ffmpeg-bin/` inside the app) with system
  `PATH` fallback. See `find_binary()` in `modules/utilities.py`.
- **Windows bundle uses onnxruntime-directml** (any DX12 GPU, CPU fallback)
  instead of onnxruntime-gpu — smaller (655 MB vs 877 MB zip) and works on
  iGPUs. CUDA stays a run-from-source workflow.
- **TensorFlow is lazy** — only loaded when the NSFW filter is used
  (`modules/predicter.py`). Saves hundreds of MB of startup RAM.

## How to cut a release

```bash
git tag v<version>
git push origin v<version>
```

CI (`.github/workflows/desktop-build.yml`) builds all three OSes (~10 min)
and attaches archives to a draft release. Review and publish it. Manual
builds: *Actions → Desktop App Build → Run workflow* (after merge to main).

Local builds: `packaging/build.sh` (Linux/macOS) or `packaging\build.ps1`
(Windows).

## The upgrade paths (in order of bang-for-buck)

1. **Local hardware upgrade** — a machine with a dedicated NVIDIA/AMD GPU and
   16 GB+ RAM. The rc3 Windows build will use any DX12 GPU automatically via
   DirectML; nothing to reconfigure. NVIDIA users wanting maximum speed can
   run from source with `--execution-provider cuda`.
2. **Cloud GPU server for video files** — `packaging/cloud-gpu-setup.sh`
   provisions an Ubuntu NVIDIA VM (AWS g4dn/g5, GCP T4/L4, Paperspace,
   Lambda) end to end: system deps, venv, CUDA wheels, provider verification.
   Process videos headless:

   ```bash
   source venv/bin/activate
   python run.py -s face.jpg -t input.mp4 -o output.mp4 \
       --execution-provider cuda --keep-fps
   ```

   Cost ballpark: ~$0.30–1.00/hr; remember to stop the instance.
   Live webcam over a remote VM is not recommended (camera forwarding
   latency makes it impractical).
3. **Hosted web service** (browser → WebRTC → GPU server → stream back) —
   significant new development (streaming backend, web frontend, scaling).
   Not started; revisit only if 1 or 2 prove insufficient.

## Known limitations / future work

- **Unsigned binaries** — SmartScreen/Gatekeeper warn on first launch.
  Fix: code-signing cert (or Azure Trusted Signing) wired into CI as secrets.
- **No Windows ARM64 build** — x64 runs under emulation on Snapdragon
  devices; native build blocked on upstream wheel availability.
- **Bundle size** — Linux ~1.3 GB compressed (TensorFlow + ONNX Runtime
  dominate). Could shrink by making the NSFW filter's TensorFlow an optional
  download, at the cost of shipping the safety feature separately.
- **First-launch model download (~600 MB)** has no GUI progress indicator —
  progress goes to `app.log`. A download dialog would improve UX.
