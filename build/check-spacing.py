# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.67.0", "brotli==1.2.0", "pillow==12.3.0"]
# ///
"""Warn when a build opens gaps between Companion Mono Unison's letters.

uv run build/check-spacing.py              fonts/ttf against HEAD's fonts/woff2
uv run build/check-spacing.py DIR [REV]    another build, e.g. .cache/draft, against REV

A change to one letter can look right on its own and still leave gaps beside its
neighbours, as plain stems on i and l did beside each other. For every pair of printable
ASCII characters, this measures how open the white channel between them is: each glyph is
blurred, as the eye blurs text at reading size, and averaged over the x-height band into a
darkness profile across the line; a pair's channel is the lightest column between the two
cells' centres, the sum of the two glyphs' profiles there. A pair scores its channel's
darkness as a share of nn's: 1 is as closed as nn, 0 as open as a word space.

Pairs whose score falls by more than RELATIVE of the committed fonts' score, and by at least
ABSOLUTE, are listed as warnings, most opened first, and .cache/spacing.png shows them in
both builds. Spacing
in a fixed-width cell is a judgement, so the check warns and never fails.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
if len(sys.argv) > 3:
    sys.exit(__doc__)
font_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "fonts" / "ttf"
rev = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
PROOF = ROOT / ".cache" / "spacing.png"

STYLES = [
    "Light", "LightItalic", "Regular", "Italic",
    "SemiBold", "SemiBoldItalic", "Bold", "BoldItalic",
]  # fmt: skip
CHARS = [chr(code) for code in range(33, 127)]
SCALE = 0.2  # pixels per unit
BLUR = 0.2  # Gaussian radius, in x-heights
PAD = 80  # pixels beside the cell, for overhangs and the blur
RELATIVE, ABSOLUTE = 0.10, 0.03
SHOWN = 12  # pairs per style in the warning and the proof


def profiles(path):
    """Each character's blurred darkness across x, averaged over the x-height band, and
    the advance in pixels."""
    font = TTFont(path)
    x_height = font["OS/2"].sxHeight * SCALE
    advance = font["hmtx"][font.getBestCmap()[ord("n")]][0] * SCALE
    pil = ImageFont.truetype(str(path), round(font["head"].unitsPerEm * SCALE))
    width, height, baseline = (
        round(advance) + 2 * PAD,
        round(1400 * SCALE),
        round(1000 * SCALE),
    )
    top = round(baseline - x_height)
    result = {}
    for char in CHARS:
        image = Image.new("L", (width, height))
        ImageDraw.Draw(image).text(
            (PAD, baseline), char, font=pil, fill=255, anchor="ls"
        )
        pixels = image.filter(ImageFilter.GaussianBlur(BLUR * x_height)).load()
        result[char] = [
            sum(pixels[x, y] for y in range(top, baseline)) / (baseline - top)
            for x in range(width)
        ]
    return result, round(advance)


def scores(path):
    """Every pair's channel as a share of nn's."""
    profile, advance = profiles(path)

    def channel(a, b):
        left, right = profile[a], profile[b]
        return min(
            left[x] + right[x - advance]
            for x in range(PAD + advance // 2, PAD + advance + advance // 2)
        )

    reference = channel("n", "n")
    return {a + b: channel(a, b) / reference for a in CHARS for b in CHARS}


def committed(style, out):
    """REV's committed WOFF2 for a style, as a TTF in out."""
    woff2 = subprocess.run(
        [
            "git",
            "-C",
            ROOT,
            "show",
            f"{rev}:fonts/woff2/CompanionMonoUnison-{style}.woff2",
        ],
        check=True,
        capture_output=True,
    ).stdout
    source, path = Path(out) / f"{style}.woff2", Path(out) / f"{style}.ttf"
    source.write_bytes(woff2)
    font = TTFont(source)
    font.flavor = None
    font.save(path)
    return path


def proof(rows):
    """Each style's opened pairs between n's, in REV's fonts and in this build's."""
    size, line, label = 40, 56, ImageFont.truetype(str(rows[0][1]), 18)
    image = Image.new("L", (1600, sum(2 * line + 40 for _ in rows) + 10), 255)
    draw, y = ImageDraw.Draw(image), 10
    for style, old, new, pairs in rows:
        text = "  ".join(f"n{pair}n" for pair in pairs)
        draw.text(
            (10, y), f"{style}: {rev} above, this build below", font=label, fill=110
        )
        for path in (old, new):
            y += line
            draw.text(
                (10, y),
                text,
                font=ImageFont.truetype(str(path), size),
                fill=0,
                anchor="ls",
            )
        y += 40
    PROOF.parent.mkdir(exist_ok=True)
    image.save(PROOF)


warnings, rows = [], []
with tempfile.TemporaryDirectory() as tmp:
    for style in STYLES:
        new_path = font_dir / f"CompanionMonoUnison-{style}.ttf"
        old_path = committed(style, tmp)
        old, new = scores(old_path), scores(new_path)
        opened = sorted(
            (pair for pair in new if new[pair] < old[pair] * (1 - RELATIVE)
             and old[pair] - new[pair] >= ABSOLUTE),
            key=lambda pair: new[pair] - old[pair],
        )  # fmt: skip
        print(f"{style}: {len(opened)} pairs more open than in {rev}")
        if opened:
            shown = ", ".join(f"{p} {old[p]:.2f}→{new[p]:.2f}" for p in opened[:SHOWN])
            warnings.append(
                f"Unison {style}: {len(opened)} pairs opened, most: {shown}"
            )
            rows.append((style, old_path, new_path, opened[:SHOWN]))
    if rows:
        proof(rows)

annotate = (
    "::warning title=Spacing::" if os.environ.get("GITHUB_ACTIONS") else "Warning: "
)
for warning in warnings:
    print(annotate + warning)
if warnings:
    print(f"Pairs shown in {PROOF}")
