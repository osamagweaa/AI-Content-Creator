"""Offline stand-ins for ElevenLabs/HeyGen (`render --dry-run`): real ffmpeg media, no network, no cost."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from studio.media import probe_duration
from studio.providers.elevenlabs import Speech
from studio.providers.heygen import Job

CHARS_PER_SEC = 15


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


class StubVoice:
    def tts(self, voice_id: str, text: str) -> Speech:
        seconds = max(len(text) / CHARS_PER_SEC, 1.0)
        words = text.split()
        step = seconds / max(len(words), 1)
        timed = [(w, i * step, (i + 1) * step) for i, w in enumerate(words)]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tts.mp3"
            _ffmpeg("-f", "lavfi", "-i", f"sine=f=330:d={seconds}", "-c:a", "libmp3lame", str(out))
            return Speech(mp3=out.read_bytes(), words=timed)


class StubVideo:
    """Matches the HeyGen methods render.py calls. `submitted` lets tests count paid calls."""

    def __init__(self) -> None:
        self.submitted: list[str] = []
        self._seconds: dict[str, float] = {}
        self._audio: dict[str, Path] = {}

    def upload_asset(self, path: Path) -> str:
        self._audio[path.name] = path
        return f"asset:{path}"

    def submit_talk(self, avatar_id: str, audio_asset_id: str, resolution: str, key: str) -> str:
        video_id = f"talk-{len(self.submitted)}"
        self._seconds[video_id] = probe_duration(Path(audio_asset_id.removeprefix("asset:")))
        self.submitted.append(video_id)
        return video_id

    def submit_scene(self, frame_asset_id: str, prompt: str, seconds: int, resolution: str, key: str) -> str:
        video_id = f"scene-{len(self.submitted)}"
        self._seconds[video_id] = float(seconds)
        self.submitted.append(video_id)
        return video_id

    def poll(self, kind: str, video_id: str) -> Job:
        return Job(status="completed", url=f"stub://{video_id}", duration=self._seconds[video_id])

    def download(self, url: str, dest: Path) -> None:
        seconds = self._seconds[url.removeprefix("stub://")]
        _ffmpeg(
            "-f", "lavfi", "-i", f"color=c=0x335577:s=720x1280:r=24:d={seconds}",
            "-f", "lavfi", "-i", f"sine=f=220:d={seconds}",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dest),
        )
