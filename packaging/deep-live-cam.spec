# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Deep-Live-Cam standalone desktop app.

Build from the repository root with:

    pyinstaller packaging/deep-live-cam.spec --noconfirm

Optional environment variables:

    FFMPEG_BIN_DIR  directory containing static ffmpeg/ffprobe binaries to
                    bundle (the app falls back to system PATH when absent)
    DLC_CONSOLE=1   keep a console window attached (useful for debugging)
"""

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

APP_NAME = "Deep-Live-Cam"
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))  # noqa: F821 (SPECPATH is injected by PyInstaller)

datas = [
    (os.path.join(ROOT, "locales"), "locales"),
]
binaries = []
hiddenimports = [
    "cv2_enumerate_cameras",
]

# insightface loads model wrappers dynamically through its model zoo and
# ships small data files (e.g. mesh/objects for landmarks).
datas += collect_data_files("insightface")
hiddenimports += collect_submodules("insightface")

# The NSFW checker (optional at runtime, enabled via a UI toggle).
try:
    import opennsfw2  # noqa: F401
    datas += collect_data_files("opennsfw2")
    hiddenimports += ["opennsfw2"]
except ImportError:
    pass

if sys.platform == "win32":
    hiddenimports += ["pygrabber", "pygrabber.dshow_graph"]

# Bundle static ffmpeg/ffprobe when the build script provides them.
ffmpeg_bin_dir = os.environ.get("FFMPEG_BIN_DIR")
if ffmpeg_bin_dir and os.path.isdir(ffmpeg_bin_dir):
    for entry in sorted(os.listdir(ffmpeg_bin_dir)):
        full = os.path.join(ffmpeg_bin_dir, entry)
        if os.path.isfile(full):
            binaries.append((full, "ffmpeg-bin"))

# Trim libraries that are pulled in transitively but never used at runtime.
excludes = [
    "tkinter",
    "matplotlib",
    "IPython",
    "jupyter",
    "pytest",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtPdf",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
]

icons_dir = os.path.join(SPECPATH, "icons")  # noqa: F821
if sys.platform == "win32":
    icon_file = os.path.join(icons_dir, "icon.ico")
elif sys.platform == "darwin":
    icon_file = os.path.join(icons_dir, "icon.icns")
else:
    icon_file = os.path.join(icons_dir, "icon.png")
if not os.path.exists(icon_file):
    icon_file = None

console = os.environ.get("DLC_CONSOLE") == "1"

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=console,
    disable_windowed_traceback=False,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_file,
        bundle_identifier="net.deeplivecam.desktop",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "NSCameraUsageDescription": (
                "Deep-Live-Cam uses the camera for the real-time face swap "
                "preview (Live mode)."
            ),
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
