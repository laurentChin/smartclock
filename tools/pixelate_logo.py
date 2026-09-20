#!/usr/bin/env python3
"""Réduit un logo en grille de pixels pour le panneau LED (logo d'une station, 7x7 par défaut).

Usage : python tools/pixelate_logo.py logo.png [--fit contain|cover|left|right] [--colors 4]
                                      [--size 7] [--threshold 0.3] [--margin 0.0] [--lighten] [--preview apercu.png]

Le logo est cadré en carré et ses couleurs sont réduites à quelques teintes franches. Chaque case de la
grille prend la couleur de fond, sauf si une autre couleur en couvre au moins --threshold (un tiers par
défaut) : sinon les lettres fines disparaîtraient dans le fond, et une moyenne donnerait des couleurs
délavées.
--size        : côté de la grille (doit correspondre à LOGO_SIZE dans config.py)
Sortie : la grille en JSON, au format stocké avec la station (lignes de "#rrggbb", null = éteint).

--fit contain : tout le logo, avec des bandes éteintes si l'image n'est pas carrée
      cover   : recadre au centre pour remplir le carré
      left / right : garde le carré le plus à gauche / à droite d'une image large
--margin      : rogne cette fraction (0 à 0,4) sur chaque bord avant réduction, pour agrandir un motif centré
--lighten     : éclaircit les couleurs trop sombres (elles seraient à peine visibles sur une LED)
"""

import argparse
import collections
import json
import sys

from PIL import Image

CELLS = 7           # côté de la grille (modifiable avec --size)
CELL_PX = 60        # taille de travail : pixels par case


def to_square(image, fit):
    width, height = image.size
    if fit in ("cover", "left", "right") and width != height:
        side = min(width, height)
        left = {"left": 0, "right": width - side}.get(fit, (width - side) // 2)
        top = (height - side) // 2
        return image.crop((left, top, left + side, top + side))
    side = max(width, height)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(image, ((side - width) // 2, (side - height) // 2))
    return square


def lighten(color, floor=110):
    """Remonte la luminosité d'une couleur sombre en gardant sa teinte."""
    peak = max(color)
    if peak >= floor or peak == 0:
        return color
    factor = floor / peak
    return tuple(min(255, round(v * factor)) for v in color)


def pixelate(path, fit="contain", colors=4, light=False, threshold=0.3, margin=0.0, size=CELLS):
    work = size * CELL_PX
    image = Image.open(path).convert("RGBA")
    if margin:
        w, h = image.size
        image = image.crop((round(w * margin), round(h * margin), round(w * (1 - margin)), round(h * (1 - margin))))
    square = to_square(image, fit).resize((work, work), Image.LANCZOS)
    flat = Image.new("RGB", square.size, (0, 0, 0))     # transparent = LED éteinte
    flat.paste(square, mask=square.split()[3])
    palette_image = flat.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    indexes = palette_image.load()
    pixels = flat.load()
    # Couleur réelle la plus fréquente de chaque teinte (la palette de la quantification est une moyenne)
    real = {}
    for index in set(indexes[x, y] for y in range(work) for x in range(work)):
        real[index] = collections.Counter(
            pixels[x, y] for y in range(work) for x in range(work) if indexes[x, y] == index).most_common(1)[0][0]
    step = CELL_PX
    background = collections.Counter(indexes[x, y] for y in range(work) for x in range(work)).most_common(1)[0][0]
    grid = []
    for row in range(size):
        line = []
        for col in range(size):
            counts = collections.Counter(
                indexes[x, y]
                for y in range(row * step, (row + 1) * step)
                for x in range(col * step, (col + 1) * step))
            total = step * step
            foreground = [(n, i) for i, n in counts.items() if i != background]
            index = background
            if foreground:
                count, candidate = max(foreground)
                if count >= threshold * total:
                    index = candidate
            color = real[index]
            if light:
                color = lighten(color)
            line.append(None if max(color) < 24 else "#%02x%02x%02x" % color)
        grid.append(line)
    return grid


def preview(grid, path, scale=40):
    """Aperçu façon panneau : fond noir, un carré par LED."""
    n = len(grid)
    image = Image.new("RGB", (n * scale, n * scale), (0, 0, 0))
    for row, line in enumerate(grid):
        for col, cell in enumerate(line):
            if cell:
                color = tuple(int(cell[i:i + 2], 16) for i in (1, 3, 5))
                for y in range(row * scale + 2, (row + 1) * scale - 2):
                    for x in range(col * scale + 2, (col + 1) * scale - 2):
                        image.putpixel((x, y), color)
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image")
    parser.add_argument("--fit", choices=("contain", "cover", "left", "right"), default="contain")
    parser.add_argument("--colors", type=int, default=4)
    parser.add_argument("--threshold", type=float, default=0.3)
    parser.add_argument("--margin", type=float, default=0.0)
    parser.add_argument("--size", type=int, default=CELLS)
    parser.add_argument("--lighten", action="store_true")
    parser.add_argument("--preview")
    args = parser.parse_args()
    grid = pixelate(args.image, args.fit, args.colors, args.lighten, args.threshold, args.margin, args.size)
    if args.preview:
        preview(grid, args.preview)
    json.dump(grid, sys.stdout)
    print()


if __name__ == "__main__":
    main()
