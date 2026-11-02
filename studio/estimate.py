from __future__ import annotations

import math
from dataclasses import dataclass

from studio.plan import Plan, Scene

CHARS_PER_SEC = 15  # ~2.5 words/s; only used before real TTS timings exist


@dataclass
class Quote:
    lines: list[tuple[str, float, float, float]]  # (label, units, unit_price, cost)

    @property
    def total(self) -> float:
        return round(sum(cost for *_, cost in self.lines), 4)


def scene_seconds(scene: Scene, speech_seconds: float | None) -> int:
    """Clip length HeyGen will bill: explicit seconds, or the voice-over rounded up (scene clips are 5-30 s)."""
    if scene.type == "talk":
        return math.ceil(speech_seconds or len(scene.line) / CHARS_PER_SEC)
    spoken = math.ceil(speech_seconds or len(scene.line) / CHARS_PER_SEC)
    seconds = max(scene.seconds or 0, spoken)
    return min(max(seconds, 5), 30) if scene.type == "scene" else seconds


def quote(plan: Plan, prices: dict[str, float], speech: dict[int, float] | None = None) -> Quote:
    """Cost of a plan. `speech` maps scene index -> real TTS seconds once synthesized."""
    speech = speech or {}
    chars = sum(len(s.line) for s in plan.scenes)
    talk = sum(scene_seconds(s, speech.get(i)) for i, s in enumerate(plan.scenes) if s.type == "talk")
    clips = sum(scene_seconds(s, speech.get(i)) for i, s in enumerate(plan.scenes) if s.type == "scene")
    rows = [
        ("ElevenLabs TTS (1k chars)", chars / 1000, prices["tts_per_1k_chars"]),
        ("HeyGen talking clips (sec)", talk, prices["talk_per_sec"]),
        ("HeyGen scene clips (sec)", clips, prices["scene_per_sec"]),
    ]
    return Quote([(label, units, price, round(units * price, 4)) for label, units, price in rows])
