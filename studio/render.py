from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Callable

from studio.compose import SceneAsset, render_project, write_project
from studio.config import BUILDS_DIR, StudioError
from studio.estimate import quote, scene_seconds
from studio.media import probe_duration, tag_ai_generated
from studio.plan import Plan, Scene


def _digest(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def scene_key(plan: Plan, character: dict, scene: Scene) -> str:
    """Cache key: changing one scene (or the character/voice) regenerates only what it affects."""
    image = hashlib.sha256(Path(scene.image).read_bytes()).hexdigest() if scene.image else None
    return _digest(
        character["avatar_id"], character["voice_id"], character["frame_asset_id"],
        plan.language, plan.resolution, scene.model_dump(), image,
    )[:24]


def _speech(voice, character: dict, scene: Scene, folder: Path) -> tuple[Path, list[tuple[str, float, float]]] | None:
    if not scene.line.strip():
        return None
    mp3, words_file = folder / "speech.mp3", folder / "words.json"
    if not mp3.exists():
        speech = voice.tts(character["voice_id"], scene.line)
        mp3.write_bytes(speech.mp3)
        words_file.write_text(json.dumps(speech.words))
    return mp3, [tuple(w) for w in json.loads(words_file.read_text())]


def _submit(video, plan: Plan, character: dict, scene: Scene, folder: Path, key: str, speech: Path | None, speech_seconds: float | None) -> dict:
    """Start the provider job once; job.json records the id so a restart resumes instead of re-paying."""
    job_file = folder / "job.json"
    if job_file.exists():
        return json.loads(job_file.read_text())
    if scene.type == "talk":
        audio_id = video.upload_asset(speech)
        video_id = video.submit_talk(character["avatar_id"], audio_id, plan.resolution, key)
    else:
        seconds = scene_seconds(scene, speech_seconds)
        video_id = video.submit_scene(character["frame_asset_id"], scene.prompt, seconds, plan.resolution, key)
    job = {"kind": scene.type, "video_id": video_id}
    job_file.write_text(json.dumps(job))
    return job


def run(
    plan: Plan,
    character: dict,
    *,
    out: Path,
    max_cost: float,
    prices: dict[str, float],
    voice,
    video,
    cache_dir: Path,
    poll_interval: float = 10,
    timeout: float = 45 * 60,
    log: Callable[[str], None] = print,
) -> Path:
    folders = []
    for scene in plan.scenes:
        folder = cache_dir / scene_key(plan, character, scene)
        folder.mkdir(parents=True, exist_ok=True)
        folders.append(folder)

    # 1. Voice first: cheap, and gives real durations for the final price check.
    speech = [_speech(voice, character, s, f) for s, f in zip(plan.scenes, folders)]
    seconds = {i: probe_duration(sp[0]) for i, sp in enumerate(speech) if sp}

    # 2. Refuse before any HeyGen spend if the live price exceeds what the user approved.
    live = quote(plan, prices, seconds)
    if live.total > max_cost:
        raise StudioError(f"live cost {live.total} exceeds --max-cost {max_cost}; re-run `estimate` and get approval for the new number")
    log(f"approved: live cost {live.total} <= max {max_cost}")

    # 3. Submit every missing clip, then poll them together.
    pending: dict[int, dict] = {}
    for i, (scene, folder) in enumerate(zip(plan.scenes, folders)):
        if scene.type == "still" or (folder / "clip.mp4").exists():
            continue
        key = folder.name
        sp = speech[i][0] if speech[i] else None
        pending[i] = _submit(video, plan, character, scene, folder, key, sp, seconds.get(i))
        log(f"scene {i}: {scene.type} job {pending[i]['video_id']}")

    deadline = time.monotonic() + timeout
    while pending:
        for i, job in list(pending.items()):
            state = video.poll(job["kind"], job["video_id"])
            if state.failed:
                raise StudioError(f"scene {i} failed at HeyGen: {state.error or state.status}. Fix the scene and re-run; finished scenes are cached.")
            if state.done:
                video.download(state.url, folders[i] / "clip.mp4")
                log(f"scene {i}: done")
                del pending[i]
        if pending:
            if time.monotonic() > deadline:
                raise StudioError(f"timed out waiting for scenes {sorted(pending)}; re-run to resume")
            time.sleep(poll_interval)

    # 4. Assemble with HyperFrames.
    assets = []
    for i, (scene, folder) in enumerate(zip(plan.scenes, folders)):
        voice_file, words = speech[i] if speech[i] else (None, [])
        if scene.type == "still":
            image = folder / f"image{Path(scene.image).suffix}"
            shutil.copyfile(scene.image, image)
            duration = float(scene.seconds or seconds[i])
            assets.append(SceneAsset("still", duration, image=image, voice=voice_file, words=words))
        else:
            clip = folder / "clip.mp4"
            assets.append(
                SceneAsset(scene.type, probe_duration(clip), clip=clip, voice=voice_file if scene.type == "scene" else None, words=words)
            )

    build_dir = BUILDS_DIR / _digest([a.__dict__ for a in assets], plan.captions, plan.ai_label)[:12]
    write_project(build_dir, assets, captions=plan.captions, ai_label=plan.ai_label)
    raw = build_dir / "render.mp4"
    render_project(build_dir, raw)
    out.parent.mkdir(parents=True, exist_ok=True)
    tag_ai_generated(raw, out)
    return out
