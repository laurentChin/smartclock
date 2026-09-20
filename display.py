# display.py — pilotage écran RGB LED Matrix 64x32 (HUB75) via rpi-rgb-led-matrix
#
# Mise en page issue de la maquette Figma "Smartclock | Pixel Digits" : 1 pixel Figma = 1 LED.

import functools
import os
import time
import threading

import glyphs
from config import (
    RGB_MATRIX_ROWS, RGB_MATRIX_COLS, RGB_MATRIX_CHAIN, RGB_MATRIX_PARALLEL,
    RGB_MATRIX_HARDWARE_MAPPING, RGB_MATRIX_GPIO_SLOWDOWN, RGB_MATRIX_RGB_SEQUENCE,
    RGB_MATRIX_BRIGHTNESS, RGB_MATRIX_BRIGHTNESS_SECONDARY,
)

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
    MATRIX_AVAILABLE = True
except ImportError:
    MATRIX_AVAILABLE = False
    print("[display] rgbmatrix non disponible — mode simulation")

# --- Couleurs (RGB) ---
WHITE       = (255, 255, 255)
GRAY_50     = (128, 128, 128)           # séparateur de la date
DAY_DIM     = (43, 43, 43)
DAY_ACTIVE  = (217, 217, 217)
WEEKEND_DIM = (51, 41, 0)
WEEKEND_ACTIVE = (255, 204, 0)          # non dessiné dans la maquette : jaune plein
ALARM_DIM   = (0, 27, 51)
ALARM_ACTIVE = (0, 95, 178)
LOGO_GRAY   = (142, 142, 147)
LOGO_YELLOW = (255, 204, 0)
VOLUME_LIT  = (52, 199, 89)
VOLUME_OFF  = (10, 40, 18)

# --- Positions (x, y) ---
TIME_POS        = (4, 3)
WEEK_POS        = (45, 1)
DATE_POS        = (45, 3)
ALARM_COUNT_POS = (45, 11)
ALARM_TIME_POS  = (45, 13)
LOGO_POS        = (4, 19)
VOLUME_POS      = (2, 19)               # colonne de 10 pixels, le bas de la colonne = volume minimal
VOLUME_PIXELS   = 10
VOLUME_HIDE_S   = 5.0                   # disparaît 5 s après la dernière commande de volume
RADIO_TEXT_X    = 10
RADIO_TEXT_WIDTH = 24                   # fenêtre du texte : 6 caractères, assez pour "France", "Europe", "Culture"
RADIO_BASELINES = (24, 30)              # lettres de 5px sur les lignes 19-23 (comme le logo) et 25-29
MAX_ALARM_DOTS  = 8
LOGO_BAND_TOP   = 18                    # bande basse à gauche : logo + zone masquée pendant le défilement
BLACK           = (0, 0, 0)

# Défilement des textes radio trop longs (déclenché périodiquement, jamais en continu)
SCROLL_PERIOD_S   = 10.0                # un défilement toutes les 10 s
SCROLL_LEAD_S     = 2.0                 # le début du texte reste lisible avant de démarrer
SCROLL_STEP_S     = 0.12                # 1 pixel tous les 0,12 s
SCROLL_HOLD_S     = 1.5                 # pause sur la fin du texte
SCROLL_MIN_IDLE_S = 3.0                 # immobilité minimale entre deux défilements
SCROLL_FRAME_S    = 0.1                 # rafraîchissement pendant le défilement
IDLE_FRAME_S      = 0.5

# Logo par défaut : maquette (carré gris 5x5, deux points jaunes) ; à remplacer par un logo de station.
DEFAULT_LOGO = [
    [LOGO_GRAY] * 5,
    [LOGO_GRAY, LOGO_GRAY, LOGO_YELLOW, LOGO_GRAY, LOGO_GRAY],
    [LOGO_GRAY] * 5,
    [LOGO_GRAY, LOGO_GRAY, LOGO_YELLOW, LOGO_GRAY, LOGO_GRAY],
    [LOGO_GRAY] * 5,
]


def _to_luminance(value):
    """Valeur 0-255 -> luminance relative, avec la courbe CIE1931 appliquée par la bibliothèque."""
    lightness = value * 100 / 255
    return lightness / 902.3 if lightness <= 8 else ((lightness + 16) / 116) ** 3


def _from_luminance(y):
    lightness = y * 902.3 if y <= 8 / 902.3 else 116 * y ** (1 / 3) - 16
    return max(0, min(255, round(lightness * 255 / 100)))


SECONDARY_FACTOR = min(1.0, RGB_MATRIX_BRIGHTNESS_SECONDARY / RGB_MATRIX_BRIGHTNESS)


@functools.lru_cache(maxsize=None)
def secondary(color):
    """Couleur assombrie pour le contenu secondaire : luminance réelle multipliée par SECONDARY_FACTOR
    (le panneau reste réglé sur la luminosité du contenu actif)."""
    return tuple(_from_luminance(_to_luminance(v) * SECONDARY_FACTOR) for v in color)


def _load_font(name):
    font = graphics.Font()
    font.LoadFont(os.path.join(FONTS_DIR, name))
    return font


class RGBMatrixDisplay:
    def __init__(self):
        self.matrix = None
        self.canvas = None
        self.width  = RGB_MATRIX_COLS
        self.height = RGB_MATRIX_ROWS
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._mode = "clock"        # "clock" | "radio" | "alarm" | "off"
        self._next_alarm = ""       # "HH:MM" de l'alarme la plus proche
        self._alarm_count = 0       # nombre d'alarmes définies (un pixel chacune)
        self._alarm_index = 0       # rang de l'alarme la plus proche
        self._radio_station = ""
        self._radio_program = ""
        self._radio_logo = None     # 5x5 de couleurs, None = logo par défaut
        self._alarm_label = ""
        self._volume_level = 0      # pixels allumés de l'indicateur de volume
        self._volume_until = 0.0    # instant (monotonic) où l'indicateur disparaît
        self._scroll_t0 = time.monotonic()

        if MATRIX_AVAILABLE:
            self.font_text = _load_font("tiny5.bdf")    # texte radio : Tiny5, lettres 3x5
            self.color_white = graphics.Color(*WHITE)

        self._connect()

    def _connect(self):
        if not MATRIX_AVAILABLE:
            return
        try:
            options = RGBMatrixOptions()
            options.rows                     = RGB_MATRIX_ROWS
            options.cols                     = RGB_MATRIX_COLS
            options.chain_length             = RGB_MATRIX_CHAIN
            options.parallel                 = RGB_MATRIX_PARALLEL
            options.hardware_mapping         = RGB_MATRIX_HARDWARE_MAPPING
            options.gpio_slowdown            = RGB_MATRIX_GPIO_SLOWDOWN
            options.led_rgb_sequence         = RGB_MATRIX_RGB_SEQUENCE
            options.brightness               = RGB_MATRIX_BRIGHTNESS
            options.disable_hardware_pulsing = True
            options.drop_privileges          = False

            self.matrix = RGBMatrix(options=options)
            self.canvas = self.matrix.CreateFrameCanvas()
            print(f"[display] Panneau RGB {self.width}x{self.height} connecté "
                  f"(mapping={RGB_MATRIX_HARDWARE_MAPPING}, rgb_sequence={RGB_MATRIX_RGB_SEQUENCE})")
        except Exception as e:
            print(f"[display] Impossible de connecter le panneau RGB : {e}")
            self.matrix = None

    # ------------------------------------------------------------------ #
    #  API publique                                                        #
    # ------------------------------------------------------------------ #

    def start(self):
        """Lance le thread de rafraîchissement."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self.matrix:
            self.matrix.Clear()

    @property
    def mode(self):
        return self._mode

    def show_volume(self, percent):
        """Affiche l'indicateur de volume ; un pixel de plus tous les 10 % (donc tous les deux pas de 5 %)."""
        self._volume_level = max(0, min(VOLUME_PIXELS, int(percent) // 10))
        self._volume_until = time.monotonic() + VOLUME_HIDE_S

    def set_mode_clock(self, next_alarm="", alarm_count=None, alarm_index=0):
        """next_alarm : "HH:MM". Sans alarm_count, un seul pixel est affiché si une alarme existe."""
        self._mode = "clock"
        self._next_alarm = next_alarm
        self._alarm_count = alarm_count if alarm_count is not None else (1 if next_alarm else 0)
        self._alarm_index = alarm_index

    def set_mode_radio(self, station_name, program="", logo=None):
        self._mode = "radio"
        self._radio_station = station_name
        self._radio_program = program
        self._radio_logo = logo
        self._scroll_t0 = time.monotonic()

    def set_mode_alarm(self, label=""):
        self._mode = "alarm"
        self._alarm_label = label
        self._scroll_t0 = time.monotonic()

    def set_mode_off(self):
        self._mode = "off"
        self._clear()

    # ------------------------------------------------------------------ #
    #  Boucle interne                                                     #
    # ------------------------------------------------------------------ #

    def _loop(self):
        while self._running:
            scrolling = False
            try:
                if self._mode in ("clock", "radio", "alarm"):
                    scrolling = self._draw_screen()
            except Exception as e:
                print(f"[display] Erreur rendu : {e}")
            time.sleep(SCROLL_FRAME_S if scrolling else IDLE_FRAME_S)

    def _text_width(self, text):
        """Largeur d'encre en pixels (l'avance du dernier caractère contient 1px d'espacement)."""
        return max(0, sum(self.font_text.CharacterWidth(ord(c)) for c in text) - 1)

    def _fit(self, text, max_width):
        while text and self._text_width(text) > max_width:
            text = text[:-1]
        return text

    def _scroll_offsets(self, texts, room):
        """Décalage en pixels de chaque ligne, et True pendant que le texte se déplace.

        Cycle : le début reste lisible (LEAD), le texte défile jusqu'à sa fin, pause (HOLD),
        puis retour au début et immobilité jusqu'au cycle suivant (toutes les PERIOD s,
        avec au moins MIN_IDLE s d'arrêt pour les textes très longs)."""
        overflow = [max(0, self._text_width(t) - room) for t in texts]
        longest = max(overflow)
        if not longest:
            return [0] * len(texts), False
        moving_time = longest * SCROLL_STEP_S
        active = SCROLL_LEAD_S + moving_time + SCROLL_HOLD_S
        cycle = max(SCROLL_PERIOD_S, active + SCROLL_MIN_IDLE_S)
        t = (time.monotonic() - self._scroll_t0) % cycle
        if t >= active:
            return [0] * len(texts), False
        steps = int(max(0.0, t - SCROLL_LEAD_S) / SCROLL_STEP_S)
        moving = SCROLL_LEAD_S <= t < SCROLL_LEAD_S + moving_time
        return [min(o, steps) for o in overflow], moving

    # -- éléments de la maquette --

    def _draw_week(self, put, put2, today):
        """7 pixels, lundi (0) à dimanche (6) ; le jour courant est actif, les autres secondaires."""
        for i in range(7):
            weekend = i >= 5
            if i == today:
                put(WEEK_POS[0] + 2 * i, WEEK_POS[1], WEEKEND_ACTIVE if weekend else DAY_ACTIVE)
            else:
                put2(WEEK_POS[0] + 2 * i, WEEK_POS[1], WEEKEND_DIM if weekend else DAY_DIM)

    def _draw_next_alarm(self, put, put2):
        """Un pixel par alarme définie (la plus proche est active), puis son heure (secondaire)."""
        digits = self._next_alarm.replace(":", "")
        if not (self._alarm_count and len(digits) == 4 and digits.isdigit()):
            return
        for i in range(min(self._alarm_count, MAX_ALARM_DOTS)):
            draw = put if i == self._alarm_index else put2
            draw(ALARM_COUNT_POS[0] + 2 * i, ALARM_COUNT_POS[1],
                 ALARM_ACTIVE if i == self._alarm_index else ALARM_DIM)
        glyphs.draw_small(put2, ALARM_TIME_POS[0], ALARM_TIME_POS[1], digits[:2], digits[2:],
                          ALARM_ACTIVE, sep="dots")

    def _draw_radio(self, canvas, put, station, program):
        """Logo à gauche, deux lignes de texte à droite. Retourne True pendant un défilement."""
        room = RADIO_TEXT_WIDTH
        texts = (station, program)
        offsets, moving = self._scroll_offsets(texts, room)
        for baseline, text, offset in zip(RADIO_BASELINES, texts, offsets):
            # À l'arrêt, seuls les caractères entiers qui tiennent sont affichés.
            shown = text if offset else self._fit(text, room)
            graphics.DrawText(canvas, self.font_text, RADIO_TEXT_X - offset, baseline,
                              self.color_white, shown)
        if any(offsets):
            # Le texte qui défile déborde de sa fenêtre : on masque à gauche (sous le logo) et à droite.
            for y in range(LOGO_BAND_TOP, self.height):
                for x in list(range(RADIO_TEXT_X)) + list(range(RADIO_TEXT_X + RADIO_TEXT_WIDTH, self.width)):
                    put(x, y, BLACK)
        logo = self._radio_logo or DEFAULT_LOGO
        for dy, row in enumerate(logo):
            for dx, color in enumerate(row):
                if color:
                    put(LOGO_POS[0] + dx, LOGO_POS[1] + dy, color)
        return moving

    def _draw_volume(self, put, put2):
        """Colonne de 10 pixels remplie depuis le bas ; les pixels éteints restent visibles (secondaires)."""
        for i in range(VOLUME_PIXELS):
            y = VOLUME_POS[1] + VOLUME_PIXELS - 1 - i
            if i < self._volume_level:
                put(VOLUME_POS[0], y, VOLUME_LIT)
            else:
                put2(VOLUME_POS[0], y, VOLUME_OFF)

    def _draw_screen(self):
        now = time.localtime()
        hh, mm = time.strftime("%H", now), time.strftime("%M", now)
        day, month = time.strftime("%d", now), time.strftime("%m", now)
        radio_visible = self._mode in ("radio", "alarm")
        station = self._radio_station or self._alarm_label
        program = self._radio_program

        if not self.matrix:
            print(f"[display] {self._mode.upper()}  {hh}:{mm}  {day}|{month}  alarme {self._next_alarm}"
                  f"{'  ' + station + ' / ' + program if radio_visible else ''}")
            return False

        canvas = self.canvas
        canvas.Clear()
        put = lambda x, y, c: canvas.SetPixel(x, y, c[0], c[1], c[2])

        put2 = lambda x, y, c: put(x, y, secondary(c))    # contenu secondaire

        glyphs.draw_time(put, TIME_POS[0], TIME_POS[1], hh, mm, WHITE)
        self._draw_week(put, put2, now.tm_wday)
        glyphs.draw_small(put2, DATE_POS[0], DATE_POS[1], day, month, WHITE, sep="bar", sep_color=GRAY_50)
        self._draw_next_alarm(put, put2)
        scrolling = self._draw_radio(canvas, put, station, program) if radio_visible else False
        if time.monotonic() < self._volume_until:
            self._draw_volume(put, put2)
            scrolling = True    # rafraîchissement rapide tant que l'indicateur est visible

        with self._lock:
            self.canvas = self.matrix.SwapOnVSync(canvas)
        return scrolling

    def _clear(self):
        if self.matrix:
            with self._lock:
                self.matrix.Clear()


# Singleton global
display = RGBMatrixDisplay()
