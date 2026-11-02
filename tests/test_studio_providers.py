from __future__ import annotations

import base64
import json
import os
import unittest
from unittest import mock

import httpx

from studio.config import StudioError
from studio.providers.elevenlabs import ElevenLabs, words_from_alignment
from studio.providers.heygen import HeyGen


def mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class HeyGenTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ, {"HEYGEN_API_KEY": "k"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_talk_request_is_vertical_lipsync_from_our_audio(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"], seen["body"], seen["headers"] = str(request.url), json.loads(request.content), request.headers
            return httpx.Response(202, json={"data": {"status": "pending", "video_id": "v1"}})

        video_id = HeyGen(mock_client(handler)).submit_talk("av1", "asset9", "720p", "key-1")
        self.assertEqual(video_id, "v1")
        self.assertTrue(seen["url"].endswith("/v3/videos"))
        self.assertEqual(
            seen["body"],
            {"type": "avatar", "avatar_id": "av1", "audio_asset_id": "asset9", "aspect_ratio": "9:16", "resolution": "720p"},
        )
        self.assertEqual(seen["headers"]["x-api-key"], "k")
        self.assertEqual(seen["headers"]["idempotency-key"], "key-1")

    def test_scene_request_maps_720p_to_768p_and_polls_the_models_route(self) -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "POST":
                self.assertEqual(json.loads(request.content)["resolution"], "768p")
                return httpx.Response(202, json={"data": {"video_id": "v2"}})
            return httpx.Response(200, json={"data": {"status": "completed", "video_url": "https://x/v.mp4", "duration": 5}})

        heygen = HeyGen(mock_client(handler))
        video_id = heygen.submit_scene("frame1", "she waves", 5, "720p", "key-2")
        job = heygen.poll("scene", video_id)
        self.assertTrue(job.done)
        self.assertEqual(calls, [("POST", "/v3/models/videos"), ("GET", "/v3/models/videos/v2")])

    def test_api_error_surfaces_status_and_reason(self) -> None:
        heygen = HeyGen(mock_client(lambda r: httpx.Response(402, text="insufficient credits")))
        with self.assertRaisesRegex(StudioError, "402.*insufficient credits"):
            heygen.create_photo_avatar("Sam", "asset1")


class ElevenLabsTests(unittest.TestCase):
    def test_words_are_rebuilt_from_character_timings(self) -> None:
        words = words_from_alignment(list("hi you"), [0, 0.1, 0.2, 0.3, 0.4, 0.5], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        self.assertEqual(words, [("hi", 0, 0.2), ("you", 0.3, 0.6)])

    def test_tts_returns_audio_and_timings(self) -> None:
        body = {
            "audio_base64": base64.b64encode(b"mp3").decode(),
            "alignment": {"characters": list("ok"), "character_start_times_seconds": [0, 0.1], "character_end_times_seconds": [0.1, 0.2]},
        }
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k"}):
            speech = ElevenLabs(mock_client(lambda r: httpx.Response(200, json=body))).tts("voice1", "ok")
        self.assertEqual(speech.mp3, b"mp3")
        self.assertEqual(speech.words, [("ok", 0, 0.2)])


if __name__ == "__main__":
    unittest.main()
