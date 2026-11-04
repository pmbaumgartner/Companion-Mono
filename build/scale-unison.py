# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.67.0"]
# ///
"""Scale Companion Mono Unison to Source Sans 3's x-height.

Run by build.sh: uv run build/scale-unison.py OUT_DIR UNHINTED.ttf...

Iosevka builds Unison as the standard width with heavier weights. This scales every
outline, advance, anchor, and metric to 93.4%, so the x-height falls from 520 to Source
Sans 3's 486, the cell from 500 to 467 units, and the stems to their targets. Box drawing,
blocks, and Powerline glyphs keep the full line box (1000/-326) and narrow with the cell,
so they still join from line to line. build.sh hints the scaled fonts afterwards.
"""

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem

NEW_UPEM = 934  # 1000 * 486 / 520: the scale, as the em it shrinks 1000 units to
LINE_BOX_RANGES = [
    (0x2500, 0x259F),  # box drawing, block elements
    (0xE0A0, 0xE0D7),  # Powerline
    (0x1FB00, 0x1FBFF),  # symbols for legacy computing
]


def line_box_outlines(font):
    """Simple glyphs drawn to the full line box: box drawing, blocks, and Powerline.

    Composites in those ranges (all at zero offsets) follow their parts: their own
    line-box parts, and unmapped parts that only line-box glyphs use. Shared parts such
    as the arrows keep the scale of the characters they also draw.
    """
    glyf, cmap = font["glyf"], font.getBestCmap()
    line_box = {
        name
        for code, name in cmap.items()
        if any(low <= code <= high for low, high in LINE_BOX_RANGES)
    }
    users = {}  # component glyph -> the composites that use it
    for name in font.getGlyphOrder():
        for component in getattr(glyf[name], "components", []):
            users.setdefault(component.glyphName, set()).add(name)
    outlines = {name for name in line_box if not glyf[name].isComposite()}
    outlines |= {
        component.glyphName
        for name in line_box
        for component in getattr(glyf[name], "components", [])
        if component.glyphName not in cmap.values()
        and users[component.glyphName] <= line_box
    }
    return {name for name in outlines if glyf[name].numberOfContours}


out_dir, *sources = map(Path, sys.argv[1:])
if not sources:
    sys.exit(__doc__)
for source in sources:
    font = TTFont(source)
    glyf, hmtx = font["glyf"], font["hmtx"]
    # Line-box glyphs keep their heights exactly; only their widths follow the cell.
    original = {name: glyf[name].coordinates.copy() for name in line_box_outlines(font)}
    scale_upem(font, NEW_UPEM)
    font["head"].unitsPerEm = 1000
    for name, coordinates in original.items():
        coordinates.scale((NEW_UPEM / 1000, 1))
        coordinates.toInt()
        glyf[name].coordinates = coordinates
        glyf[name].recalcBounds(glyf)
        hmtx[name] = (hmtx[name][0], glyf[name].xMin)
    font.save(out_dir / source.name)
    print(f"Scaled {source.stem}", flush=True)
