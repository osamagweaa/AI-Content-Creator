"""Shared path constants for the Deep-Live-Cam project.

Handles both source checkouts (``python run.py``) and frozen desktop
builds produced by PyInstaller. When frozen:

* read-only resources (locales, media, ...) live inside the bundle and
  are resolved relative to ``sys._MEIPASS``;
* writable data (downloaded models, settings) is redirected to a
  per-user application-data directory, because the install location of
  a desktop app must be treated as read-only.
"""

import os
import sys

APP_NAME = "Deep-Live-Cam"

#: True when running inside a PyInstaller (or similar) frozen bundle.
IS_FROZEN = bool(getattr(sys, "frozen", False))

# Directory containing bundled read-only resources. For source checkouts
# this is the repository root; for frozen builds it is the PyInstaller
# extraction/_internal directory.
if IS_FROZEN:
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
else:
    BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Kept for backwards compatibility with code that expects the project root.
ROOT_DIR = BUNDLE_DIR


def _user_data_dir() -> str:
    """Return the per-user writable data directory for this app."""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return os.path.join(base, APP_NAME)
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", APP_NAME)
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return os.path.join(base, APP_NAME.lower())


USER_DATA_DIR = _user_data_dir()

# Models are downloaded at runtime (~600MB), so they must live somewhere
# writable. Source checkouts keep the historical ``<repo>/models`` layout.
if IS_FROZEN:
    MODELS_DIR = os.path.join(USER_DATA_DIR, "models")
    SETTINGS_DIR = USER_DATA_DIR
else:
    MODELS_DIR = os.path.join(ROOT_DIR, "models")
    SETTINGS_DIR = ROOT_DIR


def resource_path(*relative: str) -> str:
    """Resolve a read-only resource shipped with the application."""
    return os.path.join(BUNDLE_DIR, *relative)


def ensure_writable_dir(path: str) -> str:
    """Create ``path`` (and parents) if missing and return it."""
    os.makedirs(path, exist_ok=True)
    return path
