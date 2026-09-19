"""Génère fonts/tiny5.bdf (Tiny5 à sa taille native de 8px, lettres 3x5) depuis Tiny5-Regular.ttf.

Usage : python tools/make_tiny5_bdf.py Tiny5-Regular.ttf fonts/tiny5.bdf   (nécessite Pillow)
Tiny5 : https://github.com/Gissio/font_tiny5 — licence SIL OFL 1.1 (voir fonts/Tiny5-OFL.txt).
"""
import sys
from PIL import Image, ImageDraw, ImageFont

ASCENT, DESCENT, WIDTH = 8, 2, 8
ttf, out = sys.argv[1], sys.argv[2]
font = ImageFont.truetype(ttf, 8)
height = ASCENT + DESCENT

lines = ["STARTFONT 2.1", "FONT -tiny5-regular-r-normal--8-80-75-75-p-40-iso10646-1",
         "SIZE 8 75 75", f"FONTBOUNDINGBOX {WIDTH} {height} 0 -{DESCENT}",
         "STARTPROPERTIES 2", f"FONT_ASCENT {ASCENT}", f"FONT_DESCENT {DESCENT}", "ENDPROPERTIES",
         "CHARS 95"]
for code in range(32, 127):
    ch = chr(code)
    img = Image.new("1", (WIDTH, height), 0)
    draw = ImageDraw.Draw(img)
    draw.fontmode = "1"
    draw.text((0, ASCENT), ch, font=font, fill=1, anchor="ls")
    advance = max(1, round(font.getlength(ch)))
    lines += [f"STARTCHAR U+{code:04X}", f"ENCODING {code}", "SWIDTH 500 0", f"DWIDTH {advance} 0",
              f"BBX {WIDTH} {height} 0 -{DESCENT}", "BITMAP"]
    for y in range(height):
        bits = "".join("1" if img.getpixel((x, y)) else "0" for x in range(WIDTH))
        lines.append(f"{int(bits, 2):02X}")
    lines.append("ENDCHAR")
lines.append("ENDFONT")
open(out, "w").write("\n".join(lines) + "\n")
print(f"{out} écrit ({len(lines)} lignes)")
