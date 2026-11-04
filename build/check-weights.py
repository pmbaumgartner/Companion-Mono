# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.67.0"]
# ///
"""Measure Companion Mono's stems beside Source Sans 3 and check the weight targets.

uv run build/check-weights.py         fonts/ttf
uv run build/check-weights.py DIR     another build, e.g. .cache/draft

Prints the stem table in VALIDATION.md. Each weight must be within TOLERANCE units of the
target that the README's "Weight" choice sets for the stem of `l`:
- Light and Light Italic, which only Unison has, match Source Sans 3 Light's.
- Regular and Italic match Source Sans 3's.
- Bold has the stem in FAMILIES: the stems of `n` fill about 51% of the standard and
  Unison cells, as in Source Sans 3 Bold, and 44% of the Semi-Extended cell.
- Bold Italic is lighter than Bold by the same ratio as in Source Sans 3.
- Semibold is the geometric mean of Regular and Bold in each slope.
"""

import math
import sys
from pathlib import Path

from fontTools.misc.bezierTools import splitLine, splitQuadratic
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "build" / "reference"
if len(sys.argv) > 2:
    sys.exit(__doc__)
font_dir = Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "fonts" / "ttf"

# Styles per slope (upright, italic), from Light to Bold.
SOURCE_SANS = [
    ["Light", "Regular", "Semibold", "Bold"],
    ["LightIt", "It", "SemiboldIt", "BoldIt"],
]
COMPANION = [
    ["Light", "Regular", "SemiBold", "Bold"],
    ["LightItalic", "Italic", "SemiBoldItalic", "BoldItalic"],
]
FAMILIES = {  # (file family, width prefix): (table name, upright Bold stem, has Light)
    # Bold as dense as Source Sans 3 Bold
    ("CompanionMono", ""): ("Companion Mono", 128, False),
    # Bold like SF Mono
    ("CompanionMono", "SemiExtended"): ("Companion Mono Semi-Extended", 120, False),
    # Bold as dense as the standard width's: its 128, scaled to the 467 cell
    ("CompanionMonoUnison", ""): ("Companion Mono Unison", 120, True),
}
TOLERANCE = 2


class ScanlinePen(BasePen):
    """Collect the x positions where a glyph's outline crosses the horizontal line at y."""

    def __init__(self, glyph_set, y):
        super().__init__(glyph_set)
        self.y, self.xs = y, []

    def _moveTo(self, pt):
        self.start = pt

    def _lineTo(self, pt):
        self.cross(splitLine(self._getCurrentPoint(), pt, self.y, isHorizontal=True))

    def _qCurveToOne(self, pt1, pt2):
        start = self._getCurrentPoint()
        self.cross(splitQuadratic(start, pt1, pt2, self.y, isHorizontal=True))

    def _closePath(self):
        self._lineTo(self.start)

    def cross(self, pieces):
        # Segments split where 0 <= t < 1, so a crossing at a shared point counts once.
        self.xs += [piece[-1][0] for piece in pieces[:-1]]


def stem_widths(font, char, y, count):
    """Widths of the glyph's count stems along the horizontal line at y, left to right."""
    glyphs = font.getGlyphSet()
    pen = ScanlinePen(glyphs, y)
    glyphs[font.getBestCmap()[ord(char)]].draw(pen)
    xs = sorted(pen.xs)
    assert len(xs) == 2 * count, (char, y, xs)
    return [right - left for left, right in zip(xs[::2], xs[1::2], strict=True)]


def measure(paths):
    """Per slope: the stems of `l` at y = 350 in each font, Bold last, and the share of its
    advance that the Bold `n`'s stems fill at y = 260."""
    stems, shares = [], []
    for slope in paths:
        fonts = [TTFont(path) for path in slope]
        stems.append([stem_widths(font, "l", 350, 1)[0] for font in fonts])
        bold = fonts[-1]
        advance = bold["hmtx"][bold.getBestCmap()[ord("n")]][0]
        shares.append(sum(stem_widths(bold, "n", 260, 2)) / advance)
    return stems, shares


def companion_mono(family, prefix, style):
    """The file build.sh installs; Iosevka drops "Regular" from all but the plain name."""
    name = (prefix + style.removeprefix("Regular")) or "Regular"
    return font_dir / f"{family}-{name}.ttf"


def row(name, stems, shares):
    upright, italic = (
        " / ".join("-" if stem is None else f"{stem:.0f}" for stem in slope)
        for slope in stems
    )
    return f"| {name} | {upright} | {italic} | {shares[0]:.0%} / {shares[1]:.0%} |"


ss_stems, ss_shares = measure(
    [
        [REFERENCE / f"SourceSans3-{style}.ttf" for style in slope]
        for slope in SOURCE_SANS
    ]
)
table = [
    "| | Upright | Italic | Bold `n` density, upright / italic |",
    "|---|---|---|---|",
    row("Source Sans 3", ss_stems, ss_shares),
]
misses = []
for (family, prefix), (name, bold_stem, has_light) in FAMILIES.items():
    stems, shares = measure(
        [
            [companion_mono(family, prefix, style) for style in styles]
            for styles in (slope if has_light else slope[1:] for slope in COMPANION)
        ]
    )
    if not has_light:
        stems = [[None, *slope] for slope in stems]
    table.append(row(name, stems, shares))
    (light, regular, semibold, bold), (light_it, italic, semibold_it, bold_it) = stems
    targets = {  # style: (measured stem, target)
        "Light": (light, ss_stems[0][0]),
        "Light Italic": (light_it, ss_stems[1][0]),
        "Regular": (regular, ss_stems[0][1]),
        "Italic": (italic, ss_stems[1][1]),
        "Bold": (bold, bold_stem),
        "Bold Italic": (bold_it, bold * ss_stems[1][3] / ss_stems[0][3]),
        "Semibold": (semibold, math.sqrt(regular * bold)),
        "Semibold Italic": (semibold_it, math.sqrt(italic * bold_it)),
    }
    misses += [
        f"{name} {style}: stem {stem:.1f}, target {target:.1f}"
        for style, (stem, target) in targets.items()
        if stem is not None and abs(stem - target) > TOLERANCE
    ]

print("\n".join(table))
if misses:
    sys.exit(f"Weights more than {TOLERANCE} units off target:\n" + "\n".join(misses))
