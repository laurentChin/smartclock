# glyphs.py — chiffres pixel dessinés pour le panneau 64x32 (maquette Figma "Pixel Digits")
#
# Chaque glyphe est une liste de lignes ("#" = LED allumée). Les fonctions dessinent
# via put(x, y, (r, g, b)) pour rester indépendantes de la bibliothèque du panneau.

BIG = {  # heure : 9 lignes, largeur 5 (le 7 fait 4, le 1 fait 1)
    "0": ["#####"] + ["#...#"] * 7 + ["#####"],
    "1": ["#"] * 9,
    "2": ["#####", "....#", "....#", "....#", "#####", "#....", "#....", "#....", "#####"],
    "3": ["#####", "....#", "....#", "....#", "#####", "....#", "....#", "....#", "#####"],
    "4": ["#...#"] * 4 + ["#####"] + ["....#"] * 4,
    "5": ["#####", "#....", "#....", "#....", "#####", "....#", "....#", "....#", "#####"],
    "6": ["#####", "#....", "#....", "#....", "#####", "#...#", "#...#", "#...#", "#####"],
    "7": ["####"] + ["...#"] * 8,
    "8": ["#####"] + ["#...#"] * 3 + ["#####"] + ["#...#"] * 3 + ["#####"],
    "9": ["#####"] + ["#...#"] * 3 + ["#####"] + ["....#"] * 3 + ["#####"],
}

SMALL = {  # date et alarme : 5 lignes, largeur 3 (le 1 fait 1)
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": ["#"] * 5,
    "2": ["###", "..#", ".#.", "#..", "###"],
    "3": ["###", "..#", "###", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", "..#", "..#", "..#"],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "###"],
}

DASH = ["...", "...", "###", "...", "..."]   # signe moins et tiret d'une mesure absente (3x5)

# Cases de l'heure, relatives à x0 : H1, H2, M1, M2 (5px de large, 1px d'écart) ; deux points en x0+13.
TIME_CELLS = (0, 6, 16, 22)
TIME_COLON_X = 13
TIME_CELL_WIDTH = 5


def blit(put, x, y, rows, color):
    for dy, row in enumerate(rows):
        for dx, c in enumerate(row):
            if c == "#":
                put(x + dx, y + dy, color)


def draw_time(put, x0, y0, hh, mm, color):
    """Heure dans des cases fixes : rien ne bouge d'une minute à l'autre.
    Les glyphes étroits (1, 7) s'alignent sur le bord droit de leur case."""
    for digit, cell in zip(hh + mm, TIME_CELLS):
        rows = BIG[digit]
        blit(put, x0 + cell + TIME_CELL_WIDTH - len(rows[0]), y0, rows, color)
    put(x0 + TIME_COLON_X, y0 + 4, color)
    put(x0 + TIME_COLON_X, y0 + 7, color)


def draw_small(put, x, y, left, right, color, sep="bar", sep_color=None):
    """Deux chiffres 3x5, séparateur de 1px ("bar" : barre 1x5, "dots" : deux points),
    deux chiffres 3x5."""
    for d in left:
        blit(put, x, y, SMALL[d], color)
        x += len(SMALL[d][0]) + 1
    sep_color = sep_color or color
    if sep == "bar":
        blit(put, x, y, ["#"] * 5, sep_color)
    else:
        put(x, y + 1, sep_color)
        put(x, y + 3, sep_color)
    x += 2
    for d in right:
        blit(put, x, y, SMALL[d], color)
        x += len(SMALL[d][0]) + 1


# Température : zone de 9x5 ; les chiffres 3x5 (1 pixel d'écart, comme la date) sont alignés à droite sur
# les colonnes 1 à 7 et le pixel de degré est suspendu sur la 9e colonne, en haut.
TEMP_DIGITS_END = 7          # les chiffres se terminent avant cette colonne (relative à x0)
TEMP_DEGREE = (8, 0)


def draw_temperature(put, x0, y0, tens, units, color, degree=True):
    """tens : "" (rien), "-" ou un chiffre ; units : un chiffre ou "-"."""
    glyphs = [DASH if char == "-" else SMALL[char] for char in (tens, units) if char]
    width = sum(len(rows[0]) for rows in glyphs) + len(glyphs) - 1
    x = x0 + TEMP_DIGITS_END - width
    for rows in glyphs:
        blit(put, x, y0, rows, color)
        x += len(rows[0]) + 1
    if degree:
        put(x0 + TEMP_DEGREE[0], y0 + TEMP_DEGREE[1], color)
