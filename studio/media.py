from __future__ import annotations

import subprocess
from pathlib import Path

from studio.config import StudioError


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    except FileNotFoundError as exc:
        raise StudioError(f"{cmd[0]} not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise StudioError(f"{cmd[0]} failed: {exc.stderr[-300:]}") from exc


def probe_duration(path: Path) -> float:
    out = _run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    return float(out.strip())


def crop_9x16(src: Path, dst: Path) -> None:
    """Center-crop any image to a 1080x1920 PNG (HeyGen image_to_video follows the first frame's shape)."""
    _run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-frames:v", "1", str(dst),
        ]
    )


def tag_ai_generated(src: Path, dst: Path) -> None:
    """Remux with an AI-generated metadata tag (no re-encode)."""
    _run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-c", "copy",
            "-metadata", "comment=AI-generated video", str(dst),
        ]
    )
