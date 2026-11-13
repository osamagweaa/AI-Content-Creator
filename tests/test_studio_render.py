from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from studio import characters
from studio.config import StudioError
from studio.plan import Plan
from studio.providers.stub import StubVideo, StubVoice
from studio.render import run

CHARACTER = {"id": "sam", "avatar_id": "av", "voice_id": "vo", "frame_asset_id": "fr"}
PRICES = {"tts_per_1k_chars": 0.0, "talk_per_sec": 1.0, "scene_per_sec": 1.0}
PLAN = Plan.model_validate(
    {
        "character": "sam",
        "scenes": [
            {"type": "talk", "line": "Hello there, welcome to the shop."},
            {"type": "scene", "line": "We roast by hand.", "prompt": "pours beans", "seconds": 5},
        ],
    }
)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required for stub media")
class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # Assembly (Node + Chrome) is covered by the manual dry run, not unit tests.
        for name in ("render_project", "write_project", "tag_ai_generated"):
            patcher = mock.patch(f"studio.render.{name}", side_effect=lambda *a, **k: None)
            patcher.start()
            self.addCleanup(patcher.stop)

    def render(self, video: StubVideo, max_cost: float, voice: StubVoice | None = None) -> Path:
        return run(
            PLAN, CHARACTER, out=self.tmp / "out.mp4", max_cost=max_cost, prices=PRICES,
            voice=voice or StubVoice(), video=video, cache_dir=self.tmp / "cache", poll_interval=0, log=lambda _: None,
        )

    def test_refuses_before_any_paid_heygen_call_when_live_cost_exceeds_approval(self) -> None:
        video = StubVideo()
        with self.assertRaises(StudioError):
            self.render(video, max_cost=1.0)
        self.assertEqual(video.submitted, [])

    def test_rerun_resumes_from_cache_without_paying_again(self) -> None:
        first = StubVideo()
        self.render(first, max_cost=100.0)
        self.assertEqual(len(first.submitted), 2)

        voice, second = mock.Mock(), StubVideo()
        self.render(second, max_cost=100.0, voice=voice)
        self.assertEqual(second.submitted, [])
        voice.tts.assert_not_called()


class ConsentTests(unittest.TestCase):
    def test_no_likeness_or_voice_clone_without_consent(self) -> None:
        video, voice = mock.Mock(), mock.Mock()
        with self.assertRaises(StudioError):
            characters.create("Sam", Path("selfie.jpg"), voice_samples=[], voice_id="v", consent_confirmed=False, voice=voice, video=video)
        video.create_photo_avatar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
