# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.67.0", "brotli==1.2.0", "uharfbuzz==0.56.3"]
# ///
"""Check the delivered font contracts.

Run from any directory: uv run build/verify-fonts.py
This validates actual font metadata, coverage, outlines, advances, and shaping.
"""

import io
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
STYLES = {  # style: (CSS weight, italic)
    "Light": (300, False),
    "LightItalic": (300, True),
    "Regular": (400, False),
    "Italic": (400, True),
    "SemiBold": (600, False),
    "SemiBoldItalic": (600, True),
    "Bold": (700, False),
    "BoldItalic": (700, True),
}
IOSEVKA = (520, 735, 735)  # x-height, cap height, ascender: Iosevka's own proportions
UNISON = (486, 656, 686)  # Source Sans 3's x-height and cap height after scaling
EIGHT = list(STYLES)
SIX = EIGHT[2:]  # without Light, which only Unison has
FAMILIES = [  # (file family, width prefix, family name, cell, heights, styles, web fonts)
    ("CompanionMono", "", "Companion Mono", 500, IOSEVKA, SIX, False),
    ("CompanionMono", "SemiExtended", "Companion Mono", 547, IOSEVKA, SIX, False),
    ("CompanionMonoUnison", "", "Companion Mono Unison", 467, UNISON, EIGHT, True),
]
FONTS = [  # (file stem, family name, advance, heights, has web font, (CSS weight, italic))
    (
        f"{file}-{(prefix + style.removeprefix('Regular')) or 'Regular'}",
        family,
        advance,
        heights,
        web,
        STYLES[style],
    )
    for file, prefix, family, advance, heights, styles, web in FAMILIES
    for style in styles
]
LINE_METRICS = (1000, -326, 0)  # Source Sans 3: inline code must share its line box
SCRIPT_SAMPLES = [
    "┌─┬─┐│└─┴─┘",
    "ΑβΩ Ελληνικά",
    "АБВ Кириллица",
    "ÀÁÂÃÄÅÇéñöüßœæ",
    "→ ← ⇒ ∑ ≠ ≤ ±",
]
OPERATORS = "a != b -> c === d <= e"


def bounds(font, char):
    glyphs = font.getGlyphSet()
    pen = BoundsPen(glyphs)
    glyphs[font.getBestCmap()[ord(char)]].draw(pen)
    return pen.bounds


def line_metrics(font):
    hhea, os2 = font["hhea"], font["OS/2"]
    return {
        (hhea.ascent, hhea.descent, hhea.lineGap),
        (os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap),
    }


def shape(data, text, features=None):
    face = hb.Face(data)
    font = hb.Font(face)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(font, buffer, features or {})
    return (
        [g.codepoint for g in buffer.glyph_infos],
        sum(p.x_advance for p in buffer.glyph_positions),
    )


def check_shaping(style, data, advance):
    for block in SCRIPT_SAMPLES:
        assert all(shape(data, block)[0]), (style, "Missing shaped glyph", block)
    # Operators stay ordinary characters by default; dlig opts into ligatures.
    default = shape(data, OPERATORS)
    plain = shape(data, OPERATORS, {"calt": False, "dlig": False})
    discretionary = shape(data, OPERATORS, {"dlig": True})
    assert default == plain, (style, "Unexpected default programming ligatures")
    assert discretionary[0] != plain[0], (style, "dlig does not change operators")
    assert default[1] == discretionary[1] == len(OPERATORS) * advance, style


def check_ttf(style, family, advance, heights, weight, italic):
    """Check an installed TTF and return it."""
    data = (ROOT / "fonts" / "ttf" / f"{style}.ttf").read_bytes()
    font = TTFont(io.BytesIO(data), checkChecksums=2)
    cmap = font.getBestCmap()
    os2 = font["OS/2"]
    x_height, cap, ascender = heights
    assert font["name"].getDebugName(16) == family, style
    assert font["head"].unitsPerEm == 1000, style
    assert os2.usWeightClass == weight, style
    assert bool(os2.fsSelection & 1) == italic, style
    assert bool(font["head"].macStyle & 2) == italic, style
    assert abs(font["post"].italicAngle - (-11 if italic else 0)) < 0.01, style
    assert font["post"].isFixedPitch, style
    assert os2.sxHeight == x_height and os2.sCapHeight == cap, style
    assert os2.fsSelection & (1 << 7), (style, "Typographic metrics not preferred")
    assert line_metrics(font) == {LINE_METRICS}, (style, line_metrics(font))
    # Box drawing and blocks fill the line box, so they join from line to line.
    block = bounds(font, "█")
    assert (block[3], block[1]) == LINE_METRICS[:2], (style, "Full block", block)
    # Keyboard symbols stand on the baseline and reach the x-height, like the lowercase;
    # ⇧'s point overshoots it as a pointed letter's does.
    for char, overshoot in [("⌘", 1), ("⎋", 1), ("⇧", 20)]:
        box = bounds(font, char)
        assert abs(box[1]) <= 1, (style, char, box)
        assert x_height - 1 <= box[3] <= x_height + overshoot, (style, char, box)
    assert all(tag in font for tag in ("fpgm", "prep", "cvt ")), (style, "Hinting")
    for char, expected in [("x", x_height), ("H", cap), ("b", ascender)]:
        box = bounds(font, char)
        assert box is not None and abs(box[3] - expected) <= 1, (style, char, box)
    for cp in range(32, 127):
        assert font["hmtx"][cmap[cp]][0] == advance, (style, f"U+{cp:04X}")
    assert font["hmtx"][cmap[0x301]][0] == 0, style
    # Windows clips glyphs to these bounds, so they must cover the font's whole extent.
    assert os2.usWinAscent >= font["head"].yMax, (style, "Top clipping bound")
    assert os2.usWinDescent >= -font["head"].yMin, (style, "Bottom clipping bound")
    check_shaping(style, data, advance)
    return font


def check_web_font(style, advance, font):
    """Check that the subset web font keeps the TTF's outlines, advances, metrics, and
    shaping; return its codepoint count."""
    cmap = font.getBestCmap()
    web = TTFont(ROOT / "fonts" / "woff2" / f"{style}.woff2")
    web_cmap = web.getBestCmap()
    assert set(range(32, 127)) <= web_cmap.keys() <= cmap.keys(), (style, "WOFF2 cmap")
    assert all(
        web["hmtx"][name][0] == font["hmtx"][cmap[cp]][0]
        for cp, name in web_cmap.items()
    ), (style, "WOFF2 advances")
    for char in "Hxag0O1Il":
        assert bounds(web, char) == bounds(font, char), (style, "WOFF2 outline", char)
    assert line_metrics(web) == {LINE_METRICS}, (style, "WOFF2 line metrics")
    web.flavor = None
    web_data = io.BytesIO()
    web.save(web_data)
    check_shaping(f"{style} WOFF2", web_data.getvalue(), advance)
    return len(web_cmap)


for style, family, advance, heights, web, (weight, italic) in FONTS:
    font = check_ttf(style, family, advance, heights, weight, italic)
    summary = f"{len(font.getBestCmap())} codepoints"
    if web:
        summary += f"; WOFF2 {check_web_font(style, advance, font)}"
    print(f"PASS {style}: {summary}", flush=True)

print(f"All {len(FONTS)} styles passed.")
