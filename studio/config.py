from __future__ import annotations

import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("STUDIO_DATA_DIR", ROOT / "data"))
CHARACTERS_DIR = DATA_DIR / "characters"
CACHE_DIR = DATA_DIR / "cache"
PRICES_FILE = Path(os.environ.get("STUDIO_PRICES_FILE", ROOT / "prices.toml"))
HYPERFRAMES_DIR = ROOT / "hyperframes"
BUILDS_DIR = HYPERFRAMES_DIR / "builds"

ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")


class StudioError(RuntimeError):
    """User-facing failure: message is safe to show and never contains keys."""


def require_key(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise StudioError(
            f"{name} is not set. Run `export {name}=...` in your shell (do not paste keys into chat)."
        )
    return value


def load_prices() -> dict[str, float]:
    """Per-unit prices the user copied from their own plan pages. Never guessed."""
    if not PRICES_FILE.exists():
        raise StudioError(
            f"{PRICES_FILE} not found. Copy studio/prices.example.toml to studio/prices.toml "
            "and fill in your own ElevenLabs/HeyGen unit prices."
        )
    prices = tomllib.loads(PRICES_FILE.read_text()).get("prices", {})
    missing = [k for k in ("tts_per_1k_chars", "talk_per_sec", "scene_per_sec") if k not in prices]
    if missing:
        raise StudioError(f"{PRICES_FILE} is missing: {', '.join(missing)}")
    return {k: float(v) for k, v in prices.items()}
