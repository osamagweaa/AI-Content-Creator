#!/usr/bin/env python3
"""Generate the Deep-Live-Cam desktop app icons.

Produces ``packaging/icons/icon.png`` (1024x1024), ``icon.ico`` (Windows)
and ``icon.icns`` (macOS) so no binary assets need to be committed.
Requires Pillow, which is already a project dependency.
"""

import os
import sys

from PIL import Image, ImageDraw

SIZE = 1024
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

BG_TOP = (24, 26, 46)
BG_BOTTOM = (58, 32, 84)
FACE_A = (64, 156, 255)
FACE_B = (255, 94, 142)
ACCENT = (240, 240, 250)


def _rounded_gradient(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        gradient.putpixel(
            (0, y),
            tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )
    gradient = gradient.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(size * 0.22)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    img.paste(gradient, (0, 0), mask)
    return img


def _draw_face(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color, width: int) -> None:
    """Stylised face: head circle + shoulders arc, stroke only."""
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=width)
    shoulder_r = int(r * 1.9)
    top = cy + int(r * 1.15)
    draw.arc(
        (cx - shoulder_r, top, cx + shoulder_r, top + 2 * shoulder_r),
        start=180,
        end=360,
        fill=color,
        width=width,
    )


def make_base_icon() -> Image.Image:
    img = _rounded_gradient(SIZE)
    draw = ImageDraw.Draw(img)
    stroke = int(SIZE * 0.045)

    # Two overlapping faces = the swap motif.
    _draw_face(draw, int(SIZE * 0.38), int(SIZE * 0.42), int(SIZE * 0.155), FACE_A, stroke)
    _draw_face(draw, int(SIZE * 0.62), int(SIZE * 0.42), int(SIZE * 0.155), FACE_B, stroke)

    # Swap arrows underneath.
    y = int(SIZE * 0.80)
    x0, x1 = int(SIZE * 0.30), int(SIZE * 0.70)
    aw = int(SIZE * 0.05)
    draw.line((x0, y - aw, x1, y - aw), fill=ACCENT, width=int(stroke * 0.6))
    draw.polygon(
        [(x1, y - 2 * aw), (x1 + aw, y - aw), (x1, y)], fill=ACCENT
    )
    draw.line((x0, y + aw, x1, y + aw), fill=ACCENT, width=int(stroke * 0.6))
    draw.polygon(
        [(x0, y), (x0 - aw, y + aw), (x0, y + 2 * aw)], fill=ACCENT
    )
    return img


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    icon = make_base_icon()

    png_path = os.path.join(OUT_DIR, "icon.png")
    icon.save(png_path)
    print(f"wrote {png_path}")

    ico_path = os.path.join(OUT_DIR, "icon.ico")
    icon.save(
        ico_path,
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"wrote {ico_path}")

    icns_path = os.path.join(OUT_DIR, "icon.icns")
    try:
        icon.save(icns_path)
        print(f"wrote {icns_path}")
    except Exception as error:  # ICNS export needs a recent Pillow
        print(f"warning: could not write {icns_path}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
