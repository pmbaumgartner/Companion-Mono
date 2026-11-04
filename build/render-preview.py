# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==12.3.0"]
# ///
"""Render Companion Mono in use beside Source Sans 3.

uv run build/render-preview.py                  fonts/ttf -> preview.png
uv run build/render-preview.py DIR OUT.png      another build, e.g. .cache/draft
"""

import re
import sys
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "build" / "reference"
if len(sys.argv) == 3:
    font_dir, out = map(Path, sys.argv[1:])
elif len(sys.argv) == 1:
    font_dir, out = ROOT / "fonts" / "ttf", ROOT / "preview.png"
else:
    sys.exit(__doc__)

SCALE = 2
W, LEFT, MID, RIGHT = 1120, 48, 578, 1072
LINE_BOX = 1.326  # ascender + descender in em, shared by both families
# Inline code's tint above and below the baseline, in em: centred on Unison's capitals
# (0.69), so code sits level in it, and deep enough to clear its descenders (0.21).
CODE_TINT = (0.95, 0.27)
PAPER, INK, MUTED, BLUE, RULE = "#fbfaf6", "#1b1b18", "#706e66", "#185a96", "#cbc7bc"
TINT, GREEN = "#efece3", "#4a6b2f"
SANS_FILES = {  # Companion Mono style -> Source Sans 3 file suffix
    "Light": "Light",
    "LightItalic": "LightIt",
    "Regular": "Regular",
    "Italic": "It",
    "SemiBold": "Semibold",
    "SemiBoldItalic": "SemiboldIt",
    "Bold": "Bold",
    "BoldItalic": "BoldIt",
}
image = Image.new("RGB", (W * SCALE, 3200 * SCALE), PAPER)
draw = ImageDraw.Draw(image)


@cache
def sans(size, style="Regular"):
    path = REFERENCE / f"SourceSans3-{SANS_FILES[style]}.ttf"
    return ImageFont.truetype(str(path), size * SCALE)


@cache
def mono(size, style="Regular", family="CompanionMono"):
    path = font_dir / f"{family}-{style}.ttf"
    return ImageFont.truetype(str(path), size * SCALE)


def unison(size, style="Regular"):
    return mono(size, style, "CompanionMonoUnison")


def width(value, font):
    return font.getlength(value) / SCALE


def text(x, baseline, value, font, color=INK, anchor="ls"):
    """Draw value with its baseline at y = baseline; return the x where it ends."""
    draw.text(
        (x * SCALE, baseline * SCALE), value, font=font, fill=color, anchor=anchor
    )
    return x + width(value, font)


def box(x0, y0, x1, y1, fill, radius):
    rect = (x0 * SCALE, y0 * SCALE, x1 * SCALE, y1 * SCALE)
    draw.rounded_rectangle(rect, radius * SCALE, fill=fill)


def line(y, color=RULE, w=1, start=LEFT, end=RIGHT):
    draw.line(
        (start * SCALE, y * SCALE, end * SCALE, y * SCALE),
        fill=color,
        width=w * SCALE,
    )


def caption(baseline, value, x=LEFT):
    text(x, baseline, value, sans(12, "SemiBold"), MUTED)


def paragraph(y, markup, size, style="Regular", x0=LEFT, x1=RIGHT):
    """Set markup in Source Sans, with `code` in Companion Mono Unison and **bold** runs.

    Lines are 1.5 em apart, starting at y; returns the y below the last line.
    Inline code gets a tinted box around its letters, brackets, and descenders; the line
    box it shares with the prose reaches well above them.
    """
    tokens = []  # (text, is_code, is_bold, may_break_before)
    bold = code = False
    for part in re.split(r"(\*\*|`)", markup):
        if part == "**":
            bold = not bold
        elif part == "`":
            code = not code
        else:
            for word in [part] if code else re.findall(r"\S+\s*|\s+", part):
                breakable = not tokens or tokens[-1][0].endswith(" ")
                tokens.append((word, code, bold, breakable))

    pitch, pad = 1.5 * size, 0.2 * size
    baseline = y + (1.5 - LINE_BOX) / 2 * size + size
    x = x0
    for value, is_code, is_bold, breakable in tokens:
        font = (unison if is_code else sans)(size, "Bold" if is_bold else style)
        advance = width(value.rstrip(), font) + (2 * pad if is_code else 0)
        if breakable and x > x0 and x + advance > x1:
            baseline, x = baseline + pitch, x0
        if is_code:
            top, bottom = CODE_TINT
            box(
                x, baseline - top * size, x + advance, baseline + bottom * size, TINT, 3
            )
            x = text(x + pad, baseline, value, font) + pad
        else:
            x = text(x, baseline, value, font)
    return baseline + (LINE_BOX - 1) * size + (1.5 - LINE_BOX) / 2 * size


SOURCE = '''\
def fetch_with_retry(url, attempts=3, base_delay=0.5, max_delay=8.0):
    """Fetch url, retrying transient failures with backoff."""
    for attempt in range(attempts):
        try:
            return http.get(url, timeout=10)
        except TransientError:
            if attempt == attempts - 1:
                raise
            time.sleep(min(base_delay * 2**attempt, max_delay))  # cap the wait'''
PYTHON_TOKEN = re.compile(r'"""[^"]*"""|"[^"]*"|#.*|\d+(?:\.\d+)?|\w+|\s+|.')
KEYWORDS = {"def", "for", "in", "try", "return", "except", "if", "raise"}


def highlight(token):
    """Return the Companion Mono style and color of a Python token."""
    if token.startswith('"'):
        return "Italic", GREEN
    if token.startswith("#"):
        return "Italic", MUTED
    if token in KEYWORDS:
        return "SemiBold", INK
    if token[0].isdigit():
        return "Regular", BLUE
    return "Regular", INK


STYLES = [  # (label, CSS weight, upright, italic, sentence)
    ("LIGHT", 300, "Light", "LightItalic", "Pass `--quiet` to hide the progress bar."),
    ("REGULAR", 400, "Regular", "Italic", "Returns `None` when the cache is empty."),
    (
        "SEMIBOLD",
        600,
        "SemiBold",
        "SemiBoldItalic",
        "Call `flush()` before closing the file.",
    ),
    ("BOLD", 700, "Bold", "BoldItalic", "Never commit `.env` to the repository."),
]
GRID = [
    "abcdefghijklm",
    "nopqrstuvwxyz",
    "ABCDEFGHIJKLM",
    "NOPQRSTUVWXYZ",
    "0123456789&@%",
    "{}[]()<>*#$?!",
]
CONFUSABLES = ["Il1|", "0O", "ij", "rn m"]

# The size at which Semi-Extended's 547-unit cell is a whole 19 pixels: Pillow
# rounds advances to whole pixels, which would leave seams in box drawing.
TERM_SIZE, TERM_BG = 19 / 0.547 / SCALE, "#1d1e1b"
TERM_STYLES = {  # markup key -> (color, Companion Mono style)
    "fg": ("#e4e1d8", "SemiExtended"),
    "dim": ("#8d8a80", "SemiExtended"),
    "dir": ("#7fb0de", "SemiExtendedBold"),
    "head": ("#e4e1d8", "SemiExtendedBold"),
    "num": ("#e0bd6a", "SemiExtended"),
    "ok": ("#9fc477", "SemiExtended"),
    "pass": ("#9fc477", "SemiExtendedBold"),
    "mod": ("#e0bd6a", "SemiExtendedBold"),
    "new": ("#e0907c", "SemiExtendedBold"),
}
TERM_MARKUP = re.compile(r"\{(\w+):([^}]*)\}|([^{]+)")
PROMPT = "{dir:~/api} {dim:$} "
TERM_PANES = [
    [
        PROMPT + "tree src",
        "{dir:src}",
        "{dim:├──} {dir:client}",
        "{dim:│   ├──} __init__.py",
        "{dim:│   └──} retry.py",
        "{dim:└──} {dir:tests}",
        "{dim:    └──} test_retry.py",
        "",
        PROMPT + "pytest -q",
        "{ok:........................} {dim:[100%]}",
        "{pass:24 passed} in 0.41s",
    ],
    [
        PROMPT + 'sqlite3 -box app.db "select * from slow"',
        "{dim:┌────────────┬───────┬────────┐}",
        "{dim:│} {head:endpoint}   {dim:│} {head:calls} {dim:│} {head:p95 ms} {dim:│}",
        "{dim:├────────────┼───────┼────────┤}",
        "{dim:│} /search    {dim:│} {num: 1204} {dim:│} {num:  38.2} {dim:│}",
        "{dim:│} /users/:id {dim:│} {num:  877} {dim:│} {num:  12.9} {dim:│}",
        "{dim:│} /checkout  {dim:│} {num:  215} {dim:│} {num: 141.0} {dim:│}",
        "{dim:└────────────┴───────┴────────┘}",
        "",
        PROMPT + "git status -s",
        "{mod: M} src/client/retry.py",
        "{new:??} src/tests/test_retry.py",
    ],
]


def terminal_line(x, baseline, markup):
    for match in TERM_MARKUP.finditer(markup):
        key, value = (match[1], match[2]) if match[1] else ("fg", match[3])
        color, style = TERM_STYLES[key]
        x = text(x, baseline, value, mono(TERM_SIZE, style), color)


y = 46
text(LEFT, y, "A MONOSPACED COMPANION TO SOURCE SANS 3", sans(13, "SemiBold"), BLUE)
text(LEFT, y + 56, "Companion Mono", mono(46, "Bold"))
text(
    LEFT,
    y + 92,
    "Three cuts: Unison, from Light to Bold, for code in Source Sans text, and two "
    "widths for editors and terminals.",
    sans(20),
    MUTED,
)
y += 118
line(y, INK, 2)

caption(y + 34, "UNISON IN A DOCUMENT")
text(LEFT, y + 80, "Retrying requests", sans(28, "Bold"))
y = paragraph(
    y + 96,
    "`fetch_with_retry()` wraps a request in exponential backoff. Each failed "
    "attempt waits twice as long as the one before, starting at `base_delay` "
    "and stopping at `max_delay`. Errors that a retry cannot fix, such as "
    "`404 Not Found`, are raised immediately.",
    20,
)
y = paragraph(
    y + 8,
    "**`attempts` counts the first request,** so `attempts=1` never retries. "
    "Timeouts apply to each attempt, not to the whole call.",
    20,
)
y += 18
code_lines = SOURCE.splitlines()
box(LEFT, y, RIGHT, y + 36 + 26 * len(code_lines), TINT, 6)
for i, source_line in enumerate(code_lines):
    x = LEFT + 22
    for token in PYTHON_TOKEN.findall(source_line):
        style, color = highlight(token)
        x = text(x, y + 37 + 26 * i, token, unison(17, style), color)
y += 36 + 26 * len(code_lines) + 36
line(y)

# Each style sets inline code in its matching Source Sans sentence.
caption(y + 34, "UNISON'S EIGHT STYLES, MATCHED TO SOURCE SANS")
for row, (label, weight, upright, italic, sentence) in enumerate(STYLES):
    top = y + 50 + 74 * row
    for x0, style, suffix in [(LEFT, upright, ""), (MID, italic, " ITALIC")]:
        caption(top + 14, f"{label}{suffix} · {weight}", x0)
        paragraph(top + 16, sentence, 22, style, x0=x0, x1=x0 + 494)
y += 50 + 74 * len(STYLES) + 14
line(y)

# Each cell pairs a Source Sans glyph (grey) with Unison's (black) beneath it.
caption(y + 34, "LETTERFORMS — SOURCE SANS 3 ABOVE, UNISON BELOW")
y += 44
cell = (MID - LEFT - 36) / len(GRID[0])
for x0, style in [(LEFT, "Regular"), (MID, "Italic")]:
    for r, chars in enumerate(GRID):
        row = y + 88 * r
        for font, color, baseline in (
            (sans(32, style), MUTED, row + 38),
            (unison(32, style), INK, row + 78),
        ):
            for i, char in enumerate(chars):
                text(x0 + cell * (i + 0.5), baseline, char, font, color, anchor="ms")
        if r < len(GRID) - 1:
            line(row + 90, start=x0, end=x0 + cell * len(chars))
y += 88 * len(GRID) + 14
line(y)

caption(y + 34, "TELLING CODE APART")
xs = [LEFT + 140]
for group in CONFUSABLES[:-1]:
    xs.append(xs[-1] + max(width(group, sans(36)), width(group, unison(36))) + 36)
for i, (label, font, color) in enumerate(
    [("SOURCE SANS 3", sans(36), MUTED), ("UNISON", unison(36), INK)]
):
    baseline = y + 90 + 54 * i
    caption(baseline - 4, label)
    for x, group in zip(xs, CONFUSABLES, strict=True):
        text(x, baseline, group, font, color)

# Guides at each face's cap height and x-height, measured from H and x.
caption(y + 34, "CAP HEIGHT AND X-HEIGHT AT THE SAME SIZE", MID)
baseline = y + 136
line(baseline, start=MID, end=RIGHT - 40)
for x, font, color, label in [
    (MID + 10, sans(84), MUTED, "SOURCE SANS 3"),
    (MID + 175, unison(84), INK, "UNISON"),
    (MID + 340, mono(84), INK, "COMPANION MONO"),
]:
    end = x + width("Hx", font)
    for glyph in "Hx":
        height = -font.getbbox(glyph, anchor="ls")[1] / SCALE
        line(baseline - height, start=x - 8, end=end + 8)
    text(x, baseline, "Hx", font, color)
    caption(baseline + 22, label, x)
y += 178
line(y)

# Lines are one line box apart, on whole pixels, so box drawing joins between them.
caption(y + 34, "SEMI-EXTENDED IN A TERMINAL")
top = round(y) + 50
pitch = int(TERM_SIZE * LINE_BOX * SCALE) / SCALE
rows = max(map(len, TERM_PANES))
box(LEFT, top, RIGHT, top + 40 + pitch * rows, TERM_BG, 8)
for x0, pane in zip([LEFT + 24, LEFT + 470], TERM_PANES, strict=True):
    for i, markup in enumerate(pane):
        terminal_line(x0, top + 38 + pitch * i, markup)
y = top + 40 + pitch * rows + 30

text(
    LEFT,
    y,
    "All faces are set at the same font size throughout. Reference: Source Sans 3.052.",
    sans(14),
    MUTED,
)
y += 26

image.crop((0, 0, W * SCALE, int(y * SCALE))).save(out, optimize=True)
print(out)
