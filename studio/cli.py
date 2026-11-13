from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from studio import characters
from studio.config import CACHE_DIR, DATA_DIR, StudioError, load_prices
from studio.estimate import quote
from studio.plan import load_plan
from studio.providers.elevenlabs import ElevenLabs
from studio.providers.heygen import HeyGen
from studio.providers.stub import StubVideo, StubVoice
from studio.render import run

DRY_PRICES = {"tts_per_1k_chars": 0.0, "talk_per_sec": 0.0, "scene_per_sec": 0.0}
STUB_CHARACTER = {"id": "stub", "avatar_id": "stub", "voice_id": "stub", "frame_asset_id": "stub"}


def doctor(_: argparse.Namespace) -> None:
    checks = {
        "ELEVENLABS_API_KEY set": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "HEYGEN_API_KEY set": bool(os.environ.get("HEYGEN_API_KEY")),
        "ffmpeg on PATH": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        "node on PATH": bool(shutil.which("node")),
        "chrome on PATH": bool(shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")),
    }
    for name, ok in checks.items():
        print(f"{'ok  ' if ok else 'MISSING'} {name}")
    if not all(checks.values()):
        raise StudioError("environment incomplete")


def character_new(args: argparse.Namespace) -> None:
    record = characters.create(
        args.name,
        Path(args.selfie),
        voice_samples=[Path(p) for p in args.voice_sample],
        voice_id=args.voice_id,
        consent_confirmed=args.consent_confirmed,
        voice=ElevenLabs(),
        video=HeyGen(),
    )
    print(json.dumps({k: record[k] for k in ("id", "avatar_id", "voice_id")}, indent=2))


def character_list(_: argparse.Namespace) -> None:
    for record in characters.list_all():
        print(record["id"], record["name"])


def estimate(args: argparse.Namespace) -> None:
    plan = load_plan(Path(args.plan))
    q = quote(plan, load_prices())
    for label, units, price, cost in q.lines:
        print(f"{label:30} {units:8.2f} x {price} = {cost}")
    print(f"TOTAL (estimate, before real TTS timings): {q.total}")


def render(args: argparse.Namespace) -> None:
    plan = load_plan(Path(args.plan))
    if args.dry_run:
        character, voice, video = characters.load_or(plan.character, STUB_CHARACTER), StubVoice(), StubVideo()
        prices, cache_dir, poll = DRY_PRICES, DATA_DIR / "dryrun-cache", 0
    else:
        character, voice, video = characters.load(plan.character), ElevenLabs(), HeyGen()
        prices, cache_dir, poll = load_prices(), CACHE_DIR, 10
    out = Path(args.output) if args.output else DATA_DIR / "out" / f"{plan.character}.mp4"
    print(run(plan, character, out=out, max_cost=args.max_cost, prices=prices, voice=voice, video=video, cache_dir=cache_dir, poll_interval=poll))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studio", description="Presenter videos: ElevenLabs voice + HeyGen video + HyperFrames assembly")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check keys and tools").set_defaults(fn=doctor)

    p = sub.add_parser("character-new", help="create a character (photo avatar + voice)")
    p.add_argument("--name", required=True)
    p.add_argument("--selfie", required=True)
    p.add_argument("--voice-sample", action="append", default=[], help="audio sample to clone (repeatable)")
    p.add_argument("--voice-id", help="existing ElevenLabs voice instead of cloning")
    p.add_argument("--consent-confirmed", action="store_true", help="the person shown and heard agreed")
    p.set_defaults(fn=character_new)
    sub.add_parser("character-list").set_defaults(fn=character_list)

    p = sub.add_parser("estimate", help="price a plan before spending")
    p.add_argument("plan")
    p.set_defaults(fn=estimate)

    p = sub.add_parser("render", help="generate and assemble the video")
    p.add_argument("plan")
    p.add_argument("--max-cost", type=float, required=True, help="the quote the user approved; render refuses above it")
    p.add_argument("-o", "--output")
    p.add_argument("--dry-run", action="store_true", help="offline stubs, no keys, no cost")
    p.set_defaults(fn=render)

    args = parser.parse_args(argv)
    try:
        args.fn(args)
    except StudioError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
