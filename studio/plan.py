from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from studio.config import StudioError


class Scene(BaseModel):
    """talk = lip-synced presenter; scene = AI image-to-video clip; still = photo with Ken Burns."""

    type: Literal["talk", "scene", "still"]
    line: str = ""  # spoken text (voice-over for scene/still)
    prompt: str = ""  # scene: motion/action prompt for the clip
    seconds: int | None = Field(default=None, ge=1, le=30)  # scene/still length; scene >= 5
    image: str | None = None  # still: path to the photo

    @model_validator(mode="after")
    def _check(self) -> Scene:
        if self.type == "talk" and not self.line.strip():
            raise ValueError("talk scene needs a line")
        if self.type == "scene":
            if not self.prompt.strip():
                raise ValueError("scene needs a prompt")
            if self.seconds is not None and self.seconds < 5:
                raise ValueError("scene clips are 5-30 seconds")
        if self.type == "still" and not self.image:
            raise ValueError("still needs an image path")
        if self.type == "still" and not (self.seconds or self.line.strip()):
            raise ValueError("still needs seconds or a line")
        return self


class Plan(BaseModel):
    character: str
    language: str = "en"
    resolution: Literal["720p", "1080p"] = "720p"
    captions: bool = True
    ai_label: bool = True
    scenes: list[Scene] = Field(min_length=1, max_length=20)


def load_plan(path: Path) -> Plan:
    try:
        return Plan.model_validate(json.loads(path.read_text()))
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise StudioError(f"{path}: {exc}") from exc
        raise StudioError(f"cannot read plan {path}: {exc}") from exc
