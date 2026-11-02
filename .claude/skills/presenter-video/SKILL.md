---
name: presenter-video
description: Make a vertical 9:16 AI presenter video (talk-to-camera and short scenes) from a selfie, a voice sample and a one-line brief, using only ElevenLabs (voice), HeyGen (avatar, lip-sync, scene clips) and HyperFrames (assembly, captions). Use when the user wants a UGC / talking-head / "video of me saying ..." / character video, mentions studio, HeyGen or ElevenLabs keys, or asks to quote, render or fix a presenter video.
---

# Presenter video pipeline

Vendors are fixed: **ElevenLabs** (voice clone + speech), **HeyGen** (photo avatar, lip-sync, image-to-video scene clips), **HyperFrames** (local HTML to MP4: stitching, captions, Ken Burns, labels). Never add another vendor.

All commands run from the repo root: `python -m studio <command>`.

## Hard rules

1. **Keys:** read `ELEVENLABS_API_KEY` and `HEYGEN_API_KEY` from the environment only. If one is missing, tell the user to run `export NAME=...` in their shell. Never ask for a key in chat, print it, or write it to a file.
2. **Consent:** a selfie avatar or voice clone needs the person's agreement. Do not run `character-new --consent-confirmed` unless the user states the person shown and heard has agreed. Refuse to impersonate someone else or make a real person appear to say things they did not agree to. Leave the on-screen "AI-generated" label on for real-person likeness.
3. **Quote before spend:** never run `render` without `estimate` first, the user's explicit yes on the number, and `--max-cost` set to that number. `render` re-checks the live cost after speech is synthesized and refuses above it, before any HeyGen call.
4. **Prices are the user's:** `studio/prices.toml` (copy of `studio/prices.example.toml`) holds unit prices the user took from their own ElevenLabs and HeyGen pages. Do not invent numbers. If it is missing or zeros, ask the user to fill it in.
5. **Never re-run a render "to see"** while a job is in flight. Re-running is safe (finished scenes are cached by content, so only changed scenes are paid for again), but each changed scene is a new paid job.
6. Relay every error message as printed. Do not retry paid steps in a loop.

## Setup (once)

```bash
pip install -r requirements-studio.txt
python -m studio doctor        # keys, ffmpeg, node 22+, chrome
cp studio/prices.example.toml studio/prices.toml   # then the user fills in their numbers
```

`render` installs HyperFrames from `studio/hyperframes/package.json` on first use (needs Node 22+).

## Character (once per person)

```bash
python -m studio character-new --name "Sam" --selfie sam.jpg \
  --voice-sample sam-voice.mp3 --consent-confirmed
# or reuse an ElevenLabs voice: --voice-id <id> instead of --voice-sample
python -m studio character-list
```

Use a clear, front-facing, single-person selfie. A voice sample of about 1-2 minutes of clean speech clones best. Show the user what was created and get their OK before writing scripts.

## Making a video

1. Get the brief in one pass: goal, product/offer, audience, platform, length, language, tone, the one action viewers should take.
2. Offer three genuinely different hooks (direct benefit, curiosity gap, relatable problem), each sayable in 2-3 seconds. Let the user pick.
3. Write spoken language: about 35 words per 15 seconds. Hook, one idea, one call to action. Do not claim facts you did not check.
4. Write the plan as JSON (schema below), show it, get approval.
5. `python -m studio estimate plan.json`. Show the total and the line items. Say it is an estimate: real speech length can change it.
6. On the user's yes: `python -m studio render plan.json --max-cost <approved number> -o out/video.mp4`.
7. Deliver the path. Offer fixes.

### plan.json

```json
{
  "character": "sam",
  "language": "en",
  "resolution": "720p",
  "captions": true,
  "ai_label": true,
  "scenes": [
    {"type": "talk",  "line": "Hi, I'm Sam. Three quick updates from the shop."},
    {"type": "scene", "line": "We roast every batch by hand.", "prompt": "Sam pours green coffee beans into a roaster, warm morning light", "seconds": 5},
    {"type": "still", "image": "assets/bag.png", "line": "Our new 250 gram bag is here.", "seconds": 4}
  ]
}
```

- `talk`: lip-synced presenter speaking `line` (ElevenLabs voice into HeyGen). Best for identity and the main message.
- `scene`: AI clip starting from the character's photo, driven by `prompt` (HeyGen image-to-video, 5-30 s). `line` is an optional voice-over. Describe the presenter doing things; keep one person in frame. Identity can drift in generated scenes, so keep them short and mostly use `talk`.
- `still`: your own photo with a slow zoom (no generation cost). Needs `image` and `seconds` or a `line`.
- `resolution`: `720p` or `1080p`. Output is always 1080x1920.

## Fixing one scene

Edit that scene in `plan.json` (change `line`, `prompt`, or `seconds`), then `estimate` and `render` again with the new approved number. Unchanged scenes come from the cache at no cost, so the quote for the edit is only for the changed scene. Resume after a restart works the same way.

## Dry run (no keys, no cost)

`python -m studio render plan.json --max-cost 1 --dry-run -o out/test.mp4` swaps in offline stubs (placeholder clips and tones) to check the plan, captions and assembly. Use it to preview layout, never as a deliverable.

## Known unknowns (verify on the first real run, then tell the user)

- HeyGen photo avatars may take a moment to become ready; if the first `talk` render fails with an avatar-not-ready error, wait and re-run.
- Arabic and other non-Latin speech on ElevenLabs is not confirmed in the docs read; check a short test line first.
- Identity consistency of `scene` clips from a single selfie.
- Real prices: fill `studio/prices.toml` from the vendors' pricing pages.
