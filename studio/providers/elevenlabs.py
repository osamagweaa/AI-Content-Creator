from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path

import httpx

from studio.config import ELEVENLABS_MODEL, StudioError, require_key
from studio.http import json_or_raise, send

BASE = "https://api.elevenlabs.io"


@dataclass
class Speech:
    mp3: bytes
    words: list[tuple[str, float, float]]  # (word, start_s, end_s)

    @property
    def duration(self) -> float:
        return self.words[-1][2] if self.words else 0.0


def words_from_alignment(chars: list[str], starts: list[float], ends: list[float]) -> list[tuple[str, float, float]]:
    """Group ElevenLabs character timings into whitespace-delimited words."""
    words: list[tuple[str, float, float]] = []
    text, start, end = "", 0.0, 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if text:
                words.append((text, start, end))
            text = ""
            continue
        if not text:
            start = s
        text += ch
        end = e
    if text:
        words.append((text, start, end))
    return words


class ElevenLabs:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=120)
        self._headers = {"xi-api-key": require_key("ELEVENLABS_API_KEY")}

    def clone_voice(self, name: str, sample_paths: list[Path]) -> str:
        """Instant voice clone from audio samples. Returns voice_id."""
        files = [
            ("files", (p.name, p.read_bytes(), mimetypes.guess_type(p.name)[0] or "audio/mpeg"))
            for p in sample_paths
        ]
        resp = send(self._client, "POST", f"{BASE}/v1/voices/add", headers=self._headers, data={"name": name}, files=files)
        voice_id = json_or_raise(resp, "ElevenLabs voice clone").get("voice_id")
        if not voice_id:
            raise StudioError("ElevenLabs voice clone: no voice_id in response")
        return voice_id

    def tts(self, voice_id: str, text: str) -> Speech:
        """Speech plus per-character timing (used for captions and scene length)."""
        resp = send(
            self._client,
            "POST",
            f"{BASE}/v1/text-to-speech/{voice_id}/with-timestamps",
            params={"output_format": "mp3_44100_128"},
            headers=self._headers,
            json={"text": text, "model_id": ELEVENLABS_MODEL},
        )
        body = json_or_raise(resp, "ElevenLabs text-to-speech")
        align = body.get("alignment") or {}
        return Speech(
            mp3=base64.b64decode(body["audio_base64"]),
            words=words_from_alignment(
                align.get("characters", []),
                align.get("character_start_times_seconds", []),
                align.get("character_end_times_seconds", []),
            ),
        )
