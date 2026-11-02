from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

import httpx

from studio.config import StudioError, require_key
from studio.http import json_or_raise, send

BASE = "https://api.heygen.com"
DONE = {"completed"}
FAILED = {"failed", "cancelled"}
# Plan resolution -> heygen-video-1 resolution (it has 768p, not 720p).
SCENE_RESOLUTION = {"720p": "768p", "1080p": "1080p"}


@dataclass
class Job:
    status: str
    url: str | None = None
    duration: float | None = None
    error: str | None = None

    @property
    def done(self) -> bool:
        return self.status in DONE

    @property
    def failed(self) -> bool:
        return self.status in FAILED


class HeyGen:
    """HeyGen v3 REST: assets, photo avatars, lip-synced avatar video, image-to-video scene clips."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=120)
        self._headers = {"x-api-key": require_key("HEYGEN_API_KEY")}

    def _data(self, resp: httpx.Response, what: str) -> dict:
        body = json_or_raise(resp, what)
        return body.get("data", body)

    def upload_asset(self, path: Path) -> str:
        files = {"file": (path.name, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")}
        data = self._data(send(self._client, "POST", f"{BASE}/v3/assets", headers=self._headers, files=files), "HeyGen asset upload")
        asset_id = data.get("asset_id") or data.get("id")
        if not asset_id:
            raise StudioError(f"HeyGen asset upload: no asset id in response keys {sorted(data)}")
        return asset_id

    def create_photo_avatar(self, name: str, asset_id: str) -> str:
        """Photo avatar from an uploaded selfie. Returns avatar_id (usable directly in /v3/videos)."""
        body = {"type": "photo", "name": name, "file": {"type": "asset_id", "asset_id": asset_id}}
        data = self._data(send(self._client, "POST", f"{BASE}/v3/avatars", headers=self._headers, json=body), "HeyGen avatar create")
        avatar_id = (data.get("avatar_item") or {}).get("id")
        if not avatar_id:
            raise StudioError(f"HeyGen avatar create: no avatar_item.id in response keys {sorted(data)}")
        return avatar_id

    def submit_talk(self, avatar_id: str, audio_asset_id: str, resolution: str, key: str) -> str:
        """Lip-synced talking clip: avatar + our ElevenLabs audio, vertical."""
        body = {
            "type": "avatar",
            "avatar_id": avatar_id,
            "audio_asset_id": audio_asset_id,
            "aspect_ratio": "9:16",
            "resolution": resolution,
        }
        return self._video_id(send(self._client, "POST", f"{BASE}/v3/videos", headers={**self._headers, "Idempotency-Key": key}, json=body), "HeyGen talk video")

    def submit_scene(self, frame_asset_id: str, prompt: str, seconds: int, resolution: str, key: str) -> str:
        """Image-to-video scene clip; the image is the literal first frame (9:16 in, 9:16 out)."""
        body = {
            "model": "heygen-video-1",
            "mode": "image_to_video",
            "prompt": prompt,
            "image": {"type": "asset_id", "asset_id": frame_asset_id},
            "duration": seconds,
            "resolution": SCENE_RESOLUTION[resolution],
        }
        return self._video_id(send(self._client, "POST", f"{BASE}/v3/models/videos", headers={**self._headers, "Idempotency-Key": key}, json=body), "HeyGen scene video")

    def _video_id(self, resp: httpx.Response, what: str) -> str:
        video_id = self._data(resp, what).get("video_id")
        if not video_id:
            raise StudioError(f"{what}: no video_id in response")
        return video_id

    def poll(self, kind: str, video_id: str) -> Job:
        path = "/v3/videos" if kind == "talk" else "/v3/models/videos"
        data = self._data(send(self._client, "GET", f"{BASE}{path}/{video_id}", headers=self._headers), "HeyGen poll")
        return Job(
            status=data.get("status", "unknown"),
            url=data.get("video_url"),
            duration=data.get("duration"),
            error=data.get("failure_message") or data.get("failure_code"),
        )

    def download(self, url: str, dest: Path) -> None:
        # Presigned URL on a different host: do not send the API key.
        resp = send(self._client, "GET", url, follow_redirects=True)
        if resp.status_code >= 400:
            raise StudioError(f"clip download failed: HTTP {resp.status_code}")
        dest.write_bytes(resp.content)
