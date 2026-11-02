from __future__ import annotations

import unittest

from pydantic import ValidationError

from studio.estimate import quote
from studio.plan import Plan

PRICES = {"tts_per_1k_chars": 2.0, "talk_per_sec": 0.5, "scene_per_sec": 1.0}


def make_plan(*scenes: dict) -> Plan:
    return Plan.model_validate({"character": "sam", "scenes": list(scenes)})


class PlanTests(unittest.TestCase):
    def test_scene_clip_must_be_at_least_five_seconds(self) -> None:
        with self.assertRaises(ValidationError):
            make_plan({"type": "scene", "prompt": "pours coffee", "seconds": 3})

    def test_still_needs_an_image(self) -> None:
        with self.assertRaises(ValidationError):
            make_plan({"type": "still", "seconds": 4})


class EstimateTests(unittest.TestCase):
    def test_quote_uses_real_speech_seconds_once_known(self) -> None:
        plan = make_plan({"type": "talk", "line": "x" * 150}, {"type": "scene", "prompt": "walks", "seconds": 8})
        estimated = quote(plan, PRICES)  # 150 chars -> 10 s talk
        measured = quote(plan, PRICES, {0: 14.2})  # real TTS ran longer: bills 15 s
        self.assertEqual(estimated.total, 0.3 + 10 * 0.5 + 8 * 1.0)
        self.assertEqual(measured.total, 0.3 + 15 * 0.5 + 8 * 1.0)


if __name__ == "__main__":
    unittest.main()
