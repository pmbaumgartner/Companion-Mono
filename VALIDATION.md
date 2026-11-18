# Validation

Results for the fonts built by `build/build.sh` from the current recipe.

## Automated checks (`build/verify-fonts.py`)

All 20 styles pass:

- Family, weight, and italic metadata; fixed pitch; 1000 units per em; 11° italics.
- Every printable ASCII character advances one cell: 500 units, 547 in Semi-Extended, or 467 in Unison. The combining acute accent has zero advance.
- Cap height 735, x-height 520, and ascender 735 (Unison: 656, 486, and 686), in OS/2 and in the measured H, x, and b outlines.
- Line metrics are Source Sans 3's (1000, −326, 0) in hhea and OS/2, with USE_TYPO_METRICS set; the full block █ spans that line box, so box drawing joins from line to line; Windows clipping bounds cover the font's full vertical extent.
- HarfBuzz shapes sample Latin, Greek, Cyrillic, arrows, mathematical symbols, and box drawing without missing glyphs. Operators are unchanged by default; `dlig` substitutes ligatures without changing advance width.
- Keyboard symbols stand on the baseline and reach the x-height: ⌘ and ⎋ exactly, ⇧ with its point's overshoot.
- TrueType hinting is present.
- The Unison WOFF2 files cover printable ASCII and match their TTFs in advances, sample outlines, line metrics, and shaping.

Each TTF encodes 7,758 codepoints in about 11,950 glyphs; each WOFF2 encodes 2,483 codepoints.

## Weights

Output of `build/check-weights.py`, which also checks every weight against its target in the README: stems within 2 units, and Unison's Light and Regular color within half a percentage point of Source Sans 3's. Width of `l` at y = 350, Light/Regular/Semibold/Bold (Light in Unison only); Regular's color, the share of the lowercase's advances times the x-height that its outlines cover (Unison's Light: 24.8% / 23.5%, Source Sans 3 Light's 25.0% / 23.6%); and the share of the advance that the Bold `n`'s stems fill at y = 260 (Source Sans's `n` is proportional; Companion Mono's advance is the cell):

| | Upright | Italic | Regular color, upright / italic | Bold `n` density, upright / italic |
|---|---|---|---|---|
| Source Sans 3 | 44 / 82 / 115 / 147 | 41 / 76 / 107 / 136 | 41.3% / 39.3% | 51% / 49% |
| Companion Mono | - / 81 / 103 / 129 | - / 77 / 97 / 120 | 40.2% / 37.6% | 52% / 48% |
| Companion Mono Semi-Extended | - / 81 / 100 / 120 | - / 77 / 94 / 111 | 37.2% / 35.2% | 44% / 41% |
| Companion Mono Unison | 44 / 77 / 95 / 121 | 42 / 73 / 91 / 112 | 41.3% / 39.3% | 51% / 48% |

## Companion Mono Line

Inkscape 1.3.2's Hershey Text extension sets text in both SVG fonts without errors, including accented letters, curly quotes, dashes, and the euro sign. Each font has 228 glyphs. `build/verify-fonts.py` does not check the SVG fonts.

## Limits

Not every glyph or renderer is inspected. Line-box sharing with Source Sans follows from the line metrics above and is not re-measured in a browser.

## Build

Iosevka 34.9.0 (commit `2487637bb71f41b2a66134afd9faa6c316e5a438`, with `build/iosevka.patch`), Node.js 24.13.1, npm 11.8.0, ttfautohint 1.8.4.16-eb64 (ttfautohint-py 0.6.1), fontTools 4.67.0. Reference: Adobe Source Sans 3.052 (`3.052R`). Unison is scaled with fontTools and hinted with the same ttfautohint, using Iosevka's glyph-to-script controls. Fonts are stamped with the last commit's time; other tool versions can change binary hashes.
