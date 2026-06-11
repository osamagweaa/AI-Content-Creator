#!/usr/bin/env python3

import multiprocessing
import os
import sys

IS_FROZEN = bool(getattr(sys, "frozen", False))

if IS_FROZEN:
    # Frozen desktop build (PyInstaller): expose the bundle directory and
    # the bundled ffmpeg location on PATH for child processes.
    project_root = getattr(
        sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable))
    )
    _ffmpeg_bin = os.path.join(project_root, "ffmpeg-bin")
    for _p in (_ffmpeg_bin, project_root):
        if os.path.isdir(_p):
            os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

    # In windowed (no-console) builds, sys.stdout/sys.stderr are None.
    # Python's print() tolerates that, but libraries like tqdm crash on it
    # ("'NoneType' object has no attribute 'write'"). Route both streams to
    # a log file in the user data dir, which also aids field debugging.
    if sys.stdout is None or sys.stderr is None:
        try:
            from modules.paths import USER_DATA_DIR

            os.makedirs(USER_DATA_DIR, exist_ok=True)
            _log_file = open(
                os.path.join(USER_DATA_DIR, "app.log"),
                "a",
                buffering=1,
                encoding="utf-8",
                errors="replace",
            )
            if sys.stdout is None:
                sys.stdout = _log_file
            if sys.stderr is None:
                sys.stderr = _log_file
        except OSError:
            # Last resort: silence the streams instead of crashing later.
            _devnull = open(os.devnull, "w", encoding="utf-8")
            sys.stdout = sys.stdout or _devnull
            sys.stderr = sys.stderr or _devnull
else:
    # Add the project root to PATH so bundled ffmpeg/ffprobe are found
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.environ["PATH"] = project_root + os.pathsep + os.environ.get("PATH", "")

# On Windows, register NVIDIA CUDA DLL directories so onnxruntime-gpu can
# find cuDNN/cublas. Python 3.8+ ignores PATH for extension-module native deps —
# os.add_dll_directory() is required. Also keep PATH for child processes/ffmpeg.
# Frozen builds ship their own DLLs, so the venv scan is skipped there.
if sys.platform == "win32" and not IS_FROZEN:
    _site_packages = os.path.join(sys.prefix, "Lib", "site-packages")
    _venv_site_packages = os.path.join(project_root, "venv", "Lib", "site-packages")
    for _sp in (_site_packages, _venv_site_packages):
        _candidate_dirs = []
        _torch_lib = os.path.join(_sp, "torch", "lib")
        if os.path.isdir(_torch_lib):
            _candidate_dirs.append(_torch_lib)
        _nvidia_dir = os.path.join(_sp, "nvidia")
        if os.path.isdir(_nvidia_dir):
            for _pkg in os.listdir(_nvidia_dir):
                _bin_dir = os.path.join(_nvidia_dir, _pkg, "bin")
                if os.path.isdir(_bin_dir):
                    _candidate_dirs.append(_bin_dir)
        for _d in _candidate_dirs:
            os.environ["PATH"] = _d + os.pathsep + os.environ["PATH"]
            try:
                os.add_dll_directory(_d)
            except (OSError, AttributeError):
                pass

# On Linux, pre-load NVIDIA shared libraries (cuDNN, cuBLAS, nvrtc...) shipped
# inside the venv via pip wheels (nvidia-cudnn-cu12, etc.). LD_LIBRARY_PATH
# cannot be set after Python starts, so we use ctypes.CDLL with RTLD_GLOBAL
# instead. This makes symbols available to onnxruntime when it dlopens its
# CUDA provider.
if sys.platform.startswith("linux") and not IS_FROZEN:
    import ctypes
    import glob
    _py_lib = f"python{sys.version_info.major}.{sys.version_info.minor}"
    _site_packages_candidates = [
        os.path.join(project_root, "venv", "lib", _py_lib, "site-packages"),
        os.path.join(sys.prefix, "lib", _py_lib, "site-packages"),
    ]
    for _sp in _site_packages_candidates:
        _nvidia_dir = os.path.join(_sp, "nvidia")
        if not os.path.isdir(_nvidia_dir):
            continue
        for _pkg in os.listdir(_nvidia_dir):
            _lib_dir = os.path.join(_nvidia_dir, _pkg, "lib")
            if not os.path.isdir(_lib_dir):
                continue
            # Also expose the directory to child processes, without
            # duplicating an entry that is already present.
            _ldp = os.environ.get("LD_LIBRARY_PATH", "")
            if _lib_dir not in _ldp.split(os.pathsep):
                os.environ["LD_LIBRARY_PATH"] = (
                    _lib_dir + (os.pathsep + _ldp if _ldp else "")
                )
            for _so in sorted(glob.glob(os.path.join(_lib_dir, "lib*.so*"))):
                try:
                    ctypes.CDLL(_so, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass
        break

if __name__ == '__main__':
    # Required for frozen Windows/macOS builds: child processes spawned via
    # multiprocessing would otherwise re-run the whole app.
    multiprocessing.freeze_support()

    from modules import platform_info
    platform_info.print_banner()

    from modules import core
    core.run()
