# /// script
# requires-python = ">=3.12"
# dependencies = ["shapely==2.1.2"]
# ///
"""Write an SVG font of single strokes in EMS Readability's format, for Hershey Text.

uv run build/line/write_svg.py CENTERLINES.json FAMILY OUT.svg
CENTERLINES.json comes from extract.mjs; the font is scaled to Unison's size.
"""

import sys

from shapely import LineString

from strokes import iosevka_glyphs

SCALE = 486 / 520  # Unison: Iosevka's x-height to Source Sans's, and EMS Readability's

src, family, out = sys.argv[1:]
metrics, glyphs = iosevka_glyphs(src)
fid = family.replace(" ", "")


def num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


rows = []
for ch, (adv, polys) in sorted(glyphs.items()):
    d = []
    for poly in polys:
        line = LineString(poly)
        pts = line.simplify(0.4).coords if len(poly) > 2 else poly
        d.append(
            "M " + " L ".join(f"{num(x * SCALE)} {num(y * SCALE)}" for x, y in pts)
        )
    path = f' d="{" ".join(d)}"' if d else ""
    uni = f"&#x{ord(ch):X};" if ch in "'\"&<>" or ord(ch) > 0x7E else ch
    rows.append(
        f'<glyph unicode="{uni}" glyph-name="u{ord(ch):04X}" '
        f'horiz-adv-x="{num(adv * SCALE)}"{path} />'
    )
adv = num(500 * SCALE)
svg = f'''<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" >
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1">
<metadata>
Font name:               {family}
License:                 SIL Open Font License http://scripts.sil.org/OFL
A derivative of:         Iosevka (Renzhi Li), as Companion Mono (Peter Baumgartner)
Construction:            stroke centerlines of Companion Mono's letterforms, traced from
                         the Iosevka build and scaled to Companion Mono Unison's size
</metadata>
<defs>
<font id="{fid}" horiz-adv-x="{adv}" >
<font-face
font-family="{family}"
units-per-em="1000"
ascent="800"
descent="-200"
cap-height="{num(metrics["cap"] * SCALE)}"
x-height="{num(metrics["xheight"] * SCALE)}"
/>
<missing-glyph horiz-adv-x="{adv}" />
{chr(10).join(rows)}
</font>
</defs>
</svg>
'''
with open(out, "w") as f:
    f.write(svg)
print(f"Wrote {out}: {len(rows)} glyphs, {len(svg) // 1024} KB")
