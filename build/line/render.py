# /// script
# requires-python = ">=3.12"
# dependencies = ["shapely==2.1.2", "pillow==12.3.0"]
# ///
"""Render Companion Mono Line as a pen plotter draws it.

uv run build/line/render.py     fonts/svg -> preview-line.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from strokes import svg_font_glyphs

ROOT = Path(__file__).resolve().parents[2]
SCALE = 2
W, LEFT = 1120, 48
PAPER, INK, MUTED, BLUE = "#fbfaf6", "#1b1b18", "#706e66", "#185a96"
upright = svg_font_glyphs(ROOT / "fonts" / "svg" / "CompanionMonoLine.svg")
italic = svg_font_glyphs(ROOT / "fonts" / "svg" / "CompanionMonoLineItalic.svg")
image = Image.new("RGB", (W * SCALE, 1400 * SCALE), PAPER)
draw = ImageDraw.Draw(image)


def sans(size, style="Regular"):
    path = ROOT / "build" / "reference" / f"SourceSans3-{style}.ttf"
    return ImageFont.truetype(str(path), size * SCALE)


def caption(baseline, value):
    draw.text(
        (LEFT * SCALE, baseline * SCALE),
        value,
        font=sans(12, "Semibold"),
        fill=MUTED,
        anchor="ls",
    )


def strokes(x, baseline, value, glyphs, size, pen, color=INK):
    """Draw value with its baseline at y = baseline, size in px per em and pen in em, as a
    plotter would: round pen, round ends. Returns the x where it ends."""
    k = size / 1000 * SCALE
    width = max(1, round(pen * size * SCALE))
    x0 = x * SCALE
    for char in value:
        advance, polylines = glyphs.get(char, glyphs["?"])
        for polyline in polylines:
            points = [(x0 + px * k, baseline * SCALE - py * k) for px, py in polyline]
            draw.line(
                points * (2 if len(points) == 1 else 1),
                fill=color,
                width=width,
                joint="curve",
            )
            for px, py in (points[0], points[-1]):
                r = width / 2
                draw.ellipse((px - r, py - r, px + r, py + r), fill=color)
        x0 += advance * k
    return x0 / SCALE


y = 46
draw.text(
    (LEFT * SCALE, y * SCALE),
    "SINGLE STROKES FOR PEN PLOTTERS",
    font=sans(13, "Semibold"),
    fill=BLUE,
    anchor="ls",
)
strokes(LEFT, y + 56, "Companion Mono Line", upright, 52, 0.06)
draw.text(
    (LEFT * SCALE, (y + 92) * SCALE),
    "Companion Mono's letters as single strokes, at Unison's size, for Hershey Text.",
    font=sans(20),
    fill=MUTED,
    anchor="ls",
)
y += 130
for label, glyphs in (("UPRIGHT", upright), ("ITALIC", italic)):
    caption(y + 30, label)
    y += 30
    for row in (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz",
        "0123456789 !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
        "ÀÉÎÕÜ Çß æøå ñ ŠŽ €£¥ «»“” – — ¶§©°±×÷",  # noqa: RUF001
    ):
        y += 48
        strokes(LEFT, y, row, glyphs, 34, 0.03)
    y += 26
caption(y + 30, "CODE AT TEXT SIZE, WITH A PEN 6% OF THE EM (0.3 MM AT 5 MM)")
y += 34
for row, glyphs in (
    ("def plot(path, pen=0.3, speed=25):", upright),
    ("    # Lift the pen between strokes.", italic),
    ("    return [line for line in path if line.length > 0]", upright),
    ("Il1| 0O ij {}[]() == != <= -> => &&", upright),
):
    y += 36
    strokes(LEFT, y, row, glyphs, 26, 0.06)
y += 30
draw.text(
    (LEFT * SCALE, y * SCALE),
    "Each stroke is drawn once, with round ends, as a pen draws it.",
    font=sans(14),
    fill=MUTED,
    anchor="ls",
)
y += 20
out = ROOT / "preview-line.png"
image.crop((0, 0, W * SCALE, int(y * SCALE))).save(out, optimize=True)
print(out)
