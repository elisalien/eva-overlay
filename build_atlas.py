#!/usr/bin/env python3
"""Build the label atlas of the EVA-Responsive Wire source.

The fixed interface words (MAGI, SOUND ONLY, 警告, digits...) are drawn once here with
real fonts into a white-on-black PNG. The shader gets their rectangles as #defines,
written between the "// ATLAS BEGIN" and "// ATLAS END" lines of EVA_Responsive.isf.
The text typed in Arena does not go through this atlas: it comes from Text Render nodes.

Atlas convention: image row 0 (top) is v = 1 in the shader, like the text textures.
Each rectangle is vec4(u0, v0, u1, v1) around the ink of the word (v0 = bottom).
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
WIN_FONTS = Path("C:/Windows/Fonts")
USER_FONTS = Path.home() / "AppData/Local/Microsoft/Windows/Fonts"
SHADER = HERE / "EVA_Responsive.isf"
OUT = HERE / "eva_atlas.png"
W = 2048
SIZE = 112          # font size in px; labels are drawn much smaller on screen
PAD = 10


def ui_font(size=SIZE):
    f = ImageFont.truetype(str(WIN_FONTS / "bahnschrift.ttf"), size)
    f.set_variation_by_name("Bold Condensed")
    return f


FONTS = {
    "ui": ui_font,
    "uiw": lambda s=SIZE: _var(WIN_FONTS / "bahnschrift.ttf", "Bold", s),
    "goth": lambda s=SIZE: ImageFont.truetype(str(WIN_FONTS / "YuGothB.ttc"), s),
    "min": lambda s=SIZE: ImageFont.truetype(str(_noto()), s),
}


def _noto():
    """Installed per user, else the copy in fonts/ (see fonts/README.md)."""
    for d in (USER_FONTS, HERE / "fonts"):
        if (d / "NotoSerifCJKjp-Black.otf").exists():
            return d / "NotoSerifCJKjp-Black.otf"
    raise SystemExit("NotoSerifCJKjp-Black.otf not found: install it or put it in fonts/")


def _var(path, name, size):
    f = ImageFont.truetype(str(path), size)
    f.set_variation_by_name(name)
    return f


# (define name, text, font)
WORDS = [
    ("NERV", "NERV", "uiw"), ("MAGI", "MAGI", "uiw"), ("MAGISYS", "MAGI SYSTEM", "ui"),
    ("MEL", "MELCHIOR·1", "ui"), ("BAL", "BALTHASAR·2", "ui"), ("CAS", "CASPER·3", "ui"),
    ("SOUND", "SOUND ONLY", "uiw"), ("SEELE", "SEELE", "uiw"),
    ("KEIKOKU", "警告", "min"), ("WARNING", "WARNING", "uiw"), ("EMERG", "EMERGENCY", "uiw"),
    ("CAUTION", "CAUTION", "uiw"), ("DANGER", "DANGER", "uiw"),
    ("LIMIT", "活動限界まで", "goth"), ("ATR", "ACTIVE TIME REMAINING", "ui"),
    ("INTJ", "内部電源", "goth"), ("EXTJ", "外部電源", "goth"),
    ("INTERNAL", "INTERNAL", "ui"), ("EXTERNAL", "EXTERNAL", "ui"),
    ("STOP", "STOP", "ui"), ("SLOW", "SLOW", "ui"), ("NORMAL", "NORMAL", "ui"), ("RACING", "RACING", "ui"),
    ("PBJ", "パターン青", "goth"), ("PB", "PATTERN BLUE", "uiw"), ("SHITO", "使徒", "min"),
    ("SHONIN", "承認", "goth"), ("HIKETSU", "否決", "goth"), ("TEISO", "提訴", "goth"),
    ("KETSUGI", "決議", "goth"), ("SHINGI", "審議中", "goth"), ("KAKETSU", "可決", "goth"),
    ("SYNC", "SYNC RATIO", "ui"), ("SYNCJ", "シンクロ率", "goth"), ("CODE", "CODE", "ui"),
    ("SECRET", "TOP SECRET", "uiw"), ("BLOOD", "BLOOD TYPE : BLUE", "ui"),
    ("HARMO", "HARMONICS", "ui"), ("PLUG", "ENTRY PLUG", "ui"), ("ATF", "A.T. FIELD", "ui"),
    ("EPISODE", "EPISODE", "min"), ("TBC", "TO BE CONTINUED", "min"),
    ("TARGET", "TARGET", "ui"), ("LOCK", "LOCK ON", "ui"), ("DIST", "DISTANCE", "ui"),
    ("ALT", "ALTITUDE", "ui"), ("ANALYSIS", "ANALYSIS", "ui"), ("DATA", "DATA", "ui"),
    ("NOSIG", "NO SIGNAL", "uiw"), ("STANDBY", "STANDBY", "ui"), ("ONLINE", "ONLINE", "ui"),
    ("ERROR", "ERROR", "uiw"), ("MODE", "MODE", "ui"), ("UNIT", "UNIT", "ui"),
    ("KAISEKI", "解析中", "goth"), ("SHOGO", "照合", "goth"), ("SETSUZOKU", "接続", "goth"),
    ("KIDOU", "起動", "goth"), ("JIKAI", "次回予告", "min"), ("DAI", "第", "min"), ("WA", "話", "min"),
    ("REC", "REC", "uiw"), ("LIVE", "LIVE", "uiw"), ("TRANSMIT", "TRANSMISSION", "ui"),
    ("STATUS", "STATUS", "ui"), ("SIGNAL", "SIGNAL", "ui"), ("EVA", "EVA", "uiw"),
    ("JOSHIKI", "常識", "min"), ("HUMAN", "HUMAN INSTRUMENTALITY", "ui"),
]
DIGITS = "0123456789.:%-+/"


def ink(img):
    box = img.getbbox()
    if not box:
        raise SystemExit("empty glyph")
    return box


def render_word(text, font):
    l, t, r, b = font.getbbox(text)
    img = Image.new("L", (r - l + 2 * PAD, b - t + 2 * PAD), 0)
    ImageDraw.Draw(img).text((PAD - l, PAD - t), text, font=font, fill=255)
    return img.crop(ink(img))


def render_digits():
    font = _var(WIN_FONTS / "bahnschrift.ttf", "SemiBold SemiCondensed", SIZE)
    # One cell per character, all on the same baseline and the same width (tabular).
    top = min(font.getbbox(c)[1] for c in "0123456789")
    bot = max(font.getbbox(c)[3] for c in "0123456789")
    # Tabular cell as wide as the widest digit; wider symbols (%) get a smaller font.
    cw = max(font.getbbox(c)[2] - font.getbbox(c)[0] for c in "0123456789") + 6
    img = Image.new("L", (cw * len(DIGITS), bot - top + 4), 0)
    d = ImageDraw.Draw(img)
    for k, c in enumerate(DIGITS):
        f = font
        l, _, r, _ = f.getbbox(c)
        if r - l > cw - 4:
            f = _var(WIN_FONTS / "bahnschrift.ttf", "SemiBold SemiCondensed", int(SIZE * (cw - 4) / (r - l)))
            l, _, r, _ = f.getbbox(c)
        d.text((k * cw + (cw - (r - l)) / 2 - l, 2 - top), c, font=f, fill=255)
    return img, cw


def main():
    pieces = [(name, render_word(text, FONTS[f]())) for name, text, f in WORDS]
    dig, cw = render_digits()
    pieces.append(("DIGITS", dig))
    # Shelf packing, tallest first.
    order = sorted(pieces, key=lambda p: -p[1].height)
    x = y = shelf = 0
    places = {}
    for name, im in order:
        if x + im.width + PAD > W:
            x, y, shelf = 0, y + shelf + PAD, 0
        places[name] = (x + PAD // 2, y + PAD // 2)
        x += im.width + PAD
        shelf = max(shelf, im.height)
    H = y + shelf + PAD
    H = 1 << (H - 1).bit_length()
    atlas = Image.new("L", (W, H), 0)
    lines = [f"// generated by build_atlas.py ({W}x{H})"]
    for name, im in pieces:
        px, py = places[name]
        atlas.paste(im, (px, py))
        u0, u1 = px / W, (px + im.width) / W
        v1, v0 = 1 - py / H, 1 - (py + im.height) / H
        lines.append(f"#define A_{name} vec4({u0:.6f}, {v0:.6f}, {u1:.6f}, {v1:.6f})")
    lines.append(f"#define A_DIGIT_N {len(DIGITS)}.0")
    atlas.convert("RGB").save(OUT)

    src = SHADER.read_text(encoding="utf-8")
    block = "// ATLAS BEGIN\n" + "\n".join(lines) + "\n// ATLAS END"
    src, n = re.subn(r"// ATLAS BEGIN.*?// ATLAS END", lambda m: block, src, flags=re.S)
    if n != 1:
        raise SystemExit("ATLAS markers not found in the shader")
    SHADER.write_text(src, encoding="utf-8")
    print(f"{len(pieces)} entries, atlas {W}x{H} -> {OUT.name}")


if __name__ == "__main__":
    main()
