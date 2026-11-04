# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.67.0", "brotli==1.2.0"]
# ///
"""Finish the fonts that build.sh installed in fonts/.

- Line metrics become Source Sans 3's 1000/-326/0, so inline code shares the line box
  and baseline of surrounding Source Sans text. The build plans give Iosevka the same
  line, but its hhea table moves part of the descent into a line gap.
- Windows clipping bounds cover every glyph's outline.
- fonts/woff2/ receives subset web fonts of Companion Mono Unison, which matches Source
  Sans 3's x-height, and companion-mono.css declares them with the matching
  unicode-range. Companion Mono's widths are for editors and terminals.

Run by build.sh: uv run build/finalize.py
"""

from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
ASCENDER, DESCENDER = 1000, -326  # Source Sans 3 hhea and typographic metrics
# Latin (with Vietnamese), Greek, Cyrillic, punctuation, currency, letterlike symbols,
# arrows, mathematical and technical symbols, box drawing, blocks, and geometric shapes.
UNICODE_RANGE = [
    "U+0000-036F",
    "U+0370-03FF",
    "U+0400-04FF",
    "U+1E00-1EFF",
    "U+2000-206F",
    "U+20A0-20CF",
    "U+2100-214F",
    "U+2190-23FF",
    "U+2500-25FF",
    "U+FFFD",
]
# Shaping, fractions, figures, the slashed/dotted zero, and the dlig programming
# ligatures.
LAYOUT_FEATURES = [
    "ccmp", "locl", "mark", "mkmk", "calt", "dlig", "zero", "frac", "numr", "dnom", "onum", "lnum",
]  # fmt: skip


def set_line_metrics(font):
    """Set Source Sans 3's line metrics and clipping bounds that cover every glyph."""
    head, hhea, os2 = font["head"], font["hhea"], font["OS/2"]
    hhea.ascent = os2.sTypoAscender = ASCENDER
    hhea.descent = os2.sTypoDescender = DESCENDER
    hhea.lineGap = os2.sTypoLineGap = 0
    os2.usWinAscent, os2.usWinDescent = head.yMax, max(0, -head.yMin)


def write_web_font(source, target):
    options = subset.Options()
    options.layout_features = LAYOUT_FEATURES
    options.name_IDs = ["*"]
    options.notdef_outline = True
    font = TTFont(source, recalcTimestamp=False)  # keep the build's timestamp
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=subset.parse_unicodes(",".join(UNICODE_RANGE)))
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(target)


faces = []  # (CSS weight, italic, font name)
for woff2 in (ROOT / "fonts" / "woff2").glob("*.woff2"):
    woff2.unlink()  # so no web font from an older build lingers
for ttf in sorted((ROOT / "fonts" / "ttf").glob("CompanionMono*-*.ttf")):
    font = TTFont(ttf, recalcBBoxes=False, recalcTimestamp=False)
    set_line_metrics(font)
    font.save(ttf)
    if ttf.stem.startswith("CompanionMonoUnison-"):
        write_web_font(ttf, ROOT / "fonts" / "woff2" / f"{ttf.stem}.woff2")
        os2 = font["OS/2"]
        faces.append((os2.usWeightClass, bool(os2.fsSelection & 1), ttf.stem))
    print(f"Finalized {ttf.stem}", flush=True)
css = [
    f"""@font-face {{
	font-family: 'Companion Mono Unison';
	font-display: swap;
	font-weight: {weight};
	font-style: {"italic" if italic else "normal"};
	src: url('fonts/woff2/{name}.woff2') format('woff2');
	unicode-range: {", ".join(UNICODE_RANGE)};
}}
"""
    for weight, italic, name in sorted(faces)
]
(ROOT / "companion-mono.css").write_text("\n".join(css))
