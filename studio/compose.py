from __future__ import annotations

import html
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from studio.config import HYPERFRAMES_DIR, StudioError

WIDTH, HEIGHT, FPS = 1080, 1920, 30
WORDS_PER_CAPTION = 3

CSS = """
html,body{margin:0;background:#000}
#stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:#000}
.clip{position:absolute}
.media{left:0;top:0;width:1080px;height:1920px;object-fit:cover}
.cap{left:60px;right:60px;bottom:280px;text-align:center;font:800 68px/1.15 sans-serif;color:#fff;text-shadow:0 4px 14px #000}
.label{left:40px;top:60px;font:600 34px sans-serif;color:#fff;background:rgba(0,0,0,.45);padding:8px 18px;border-radius:10px}
"""


def media_name(index: int, path: Path) -> str:
    """Unique file name inside the build's media/ dir (cache files are all called clip.mp4 etc.)."""
    return f"{index}_{path.name}"


@dataclass
class SceneAsset:
    kind: str  # talk | scene | still
    duration: float
    clip: Path | None = None  # talk/scene video
    image: Path | None = None  # still
    voice: Path | None = None  # separate voice-over (scene/still); talk clips carry their own audio
    words: list[tuple[str, float, float]] = field(default_factory=list)


def _captions(words: list[tuple[str, float, float]], scene_start: float, scene_end: float) -> list[tuple[str, float, float]]:
    """Group words into short on-screen captions; each one holds until the next begins."""
    groups = [words[i : i + WORDS_PER_CAPTION] for i in range(0, len(words), WORDS_PER_CAPTION)]
    out = []
    for n, group in enumerate(groups):
        start = scene_start + group[0][1]
        end = scene_start + groups[n + 1][0][1] if n + 1 < len(groups) else min(scene_start + group[-1][2] + 0.4, scene_end)
        out.append((" ".join(w for w, _, _ in group), start, max(end - start, 0.2)))
    return out


def build_html(assets: list[SceneAsset], *, captions: bool, ai_label: bool) -> str:
    total = sum(a.duration for a in assets)
    body: list[str] = []
    tweens: list[str] = []
    cap_index = 0
    t = 0.0
    for i, a in enumerate(assets):
        if a.kind == "still":
            body.append(f'<img class="clip media" id="s{i}" src="media/{media_name(i, a.image)}" data-start="{t:.3f}" data-duration="{a.duration:.3f}" data-track-index="0">')
            tweens.append(f'tl.fromTo("#s{i}",{{scale:1}},{{scale:1.12,duration:{a.duration:.3f},ease:"none"}},{t:.3f});')
        else:
            muted = " muted" if a.kind == "scene" else ""
            body.append(f'<video class="clip media" id="s{i}" src="media/{media_name(i, a.clip)}" data-start="{t:.3f}" data-duration="{a.duration:.3f}" data-track-index="0"{muted} playsinline></video>')
        if a.voice:
            body.append(f'<audio class="clip" id="a{i}" src="media/{media_name(i, a.voice)}" data-start="{t:.3f}" data-duration="{a.duration:.3f}" data-track-index="2"></audio>')
        if captions:
            for text, start, dur in _captions(a.words, t, t + a.duration):
                body.append(f'<div class="clip cap" id="c{cap_index}" dir="auto" data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="1">{html.escape(text)}</div>')
                tweens.append(f'tl.from("#c{cap_index}",{{opacity:0,y:24,duration:0.18}},{start:.3f});')
                cap_index += 1
        t += a.duration
    if ai_label:
        body.append(f'<div class="clip label" id="ai" data-start="0" data-duration="{total:.3f}" data-track-index="3">AI-generated</div>')
    return (
        '<!doctype html>\n<html><head><meta charset="utf-8">'
        '<script src="gsap.min.js"></script>'
        f"<style>{CSS}</style></head>\n<body>\n"
        f'<div id="stage" data-composition-id="main" data-start="0" data-width="{WIDTH}" data-height="{HEIGHT}" data-duration="{total:.3f}">\n'
        + "\n".join(body)
        + '\n</div>\n<script>const tl=gsap.timeline({paused:true});\n'
        + "\n".join(tweens)
        + "\nwindow.__timelines=window.__timelines||{};window.__timelines.main=tl;</script>\n</body></html>\n"
    )


def write_project(build_dir: Path, assets: list[SceneAsset], *, captions: bool, ai_label: bool) -> None:
    media = build_dir / "media"
    media.mkdir(parents=True, exist_ok=True)
    for i, a in enumerate(assets):
        for path in (a.clip, a.image, a.voice):
            if path:
                shutil.copyfile(path, media / media_name(i, path))
    gsap = HYPERFRAMES_DIR / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    shutil.copyfile(gsap, build_dir / "gsap.min.js")
    (build_dir / "index.html").write_text(build_html(assets, captions=captions, ai_label=ai_label))


def ensure_renderer() -> Path:
    binary = HYPERFRAMES_DIR / "node_modules" / ".bin" / "hyperframes"
    if not binary.exists():
        try:
            subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=HYPERFRAMES_DIR, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise StudioError("node/npm not found: install Node 22+") from exc
        except subprocess.CalledProcessError as exc:
            raise StudioError(f"npm install failed: {exc.stderr[-300:]}") from exc
    return binary


def render_project(build_dir: Path, out: Path) -> None:
    binary = ensure_renderer()
    env = dict(os.environ)
    chrome = shutil.which("google-chrome")
    if chrome:
        env.setdefault("PUPPETEER_EXECUTABLE_PATH", chrome)
    try:
        subprocess.run([str(binary), "render", str(build_dir), "-o", str(out), "-f", str(FPS), "--quiet"], check=True, capture_output=True, text=True, env=env)
    except subprocess.CalledProcessError as exc:
        raise StudioError(f"hyperframes render failed: {(exc.stderr or exc.stdout)[-400:]}") from exc
