from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from studio.config import CHARACTERS_DIR, StudioError
from studio.media import crop_9x16


def _dir(character_id: str) -> Path:
    return CHARACTERS_DIR / character_id


def load(character_id: str) -> dict:
    path = _dir(character_id) / "character.json"
    if not path.exists():
        raise StudioError(f"character '{character_id}' not found; run `studio character new` first")
    return json.loads(path.read_text())


def list_all() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(CHARACTERS_DIR.glob("*/character.json"))]


def create(
    name: str,
    selfie: Path,
    *,
    voice_samples: list[Path],
    voice_id: str | None,
    consent_confirmed: bool,
    voice,
    video,
) -> dict:
    """Photo avatar (HeyGen) + voice (ElevenLabs clone or an existing voice_id)."""
    if not consent_confirmed:
        raise StudioError(
            "Refusing to create a likeness/voice clone without --consent-confirmed "
            "(the person shown and heard must have agreed)."
        )
    if bool(voice_id) == bool(voice_samples):
        raise StudioError("give either --voice-id (existing voice) or --voice-sample files to clone, not both/neither")
    if not selfie.is_file():
        raise StudioError(f"selfie not found: {selfie}")

    character_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not character_id:
        raise StudioError("name must contain letters or digits")
    folder = _dir(character_id)
    folder.mkdir(parents=True, exist_ok=True)

    stored = folder / f"selfie{selfie.suffix.lower()}"
    shutil.copyfile(selfie, stored)
    frame = folder / "frame.png"
    crop_9x16(stored, frame)

    avatar_id = video.create_photo_avatar(name, video.upload_asset(stored))
    frame_asset_id = video.upload_asset(frame)
    if voice_samples:
        voice_id = voice.clone_voice(name, voice_samples)

    record = {
        "id": character_id,
        "name": name,
        "avatar_id": avatar_id,
        "voice_id": voice_id,
        "frame_asset_id": frame_asset_id,
        "consent": {"confirmed": True, "at": datetime.now(timezone.utc).isoformat()},
    }
    (folder / "character.json").write_text(json.dumps(record, indent=2))
    return record


def load_or(character_id: str, fallback: dict) -> dict:
    """Dry runs may use a stand-in character; real runs call load()."""
    try:
        return load(character_id)
    except StudioError:
        return fallback
