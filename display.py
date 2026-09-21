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
    RGB_MATRIX_BRIGHTNESS, RGB_MATRIX_BRIGHTNESS_SECONDARY, DEFAULT_LOGO, LOGO_SIZE,
    TIME_ANIMATION, TIME_ANIM_S, TIME_ANIM_STAGGER_S,
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
TEMP_COLD   = (0, 200, 255)             # moins de 20 °
TEMP_WARM   = (255, 149, 0)             # de 20 à 28 °
TEMP_HOT    = (255, 59, 48)             # plus de 28 °
VOLUME_LIT  = (52, 199, 89)
VOLUME_OFF  = (10, 40, 18)

# --- Positions (x, y) ---
TIME_POS        = (4, 3)
WEEK_POS        = (45, 1)
DATE_POS        = (45, 3)
ALARM_COUNT_POS = (45, 11)
ALARM_TIME_POS  = (45, 13)
TEMP_POS        = (45, 24)              # zone 9x5 : deux chiffres 3x5 et un pixel de degré
LOGO_POS        = (4, 19)
VOLUME_POS      = (1, 19)               # 2 colonnes (x=1 et x=2) sur 10 lignes (19 à 28)
VOLUME_ROWS     = 10
VOLUME_COLUMNS  = 2
VOLUME_PIXELS   = VOLUME_ROWS * VOLUME_COLUMNS
VOLUME_STEP     = 5                     # un pixel par pas de 5 % (comme les boutons de volume)
VOLUME_HIDE_S   = 5.0                   # disparaît 5 s après la dernière commande de volume
RADIO_TEXT_X    = LOGO_POS[0] + LOGO_SIZE + 1     # texte : à droite du logo, avec 1 pixel d'écart
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
ANIM_FRAME_S      = 0.04                # 25 images par seconde pendant la bascule d'un chiffre



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


def _parse_logo(logo):
    """Grille LOGO_SIZE x LOGO_SIZE de "#rrggbb" / (r, g, b) / None -> grille de tuples ; None si absente ou invalide."""
    if not logo or len(logo) != LOGO_SIZE or any(len(row) != LOGO_SIZE for row in logo):
        return None
    grid = []
    for row in logo:
        cells = []
        for cell in row:
            if isinstance(cell, str) and len(cell) == 7 and cell.startswith("#"):
                try:
                    cell = tuple(int(cell[i:i + 2], 16) for i in (1, 3, 5))
                except ValueError:
                    return None
            cells.append(tuple(cell) if cell else None)
        grid.append(cells)
    return grid


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
        self._radio_logo = None     # grille de couleurs, None = logo par défaut
        self._alarm_label = ""
        self._time_style = TIME_ANIMATION       # None ou clé de glyphs.ANIM_PIVOTS
        self._anim_s = TIME_ANIM_S
        self._time_override = None              # "HHMM" imposé (essais d'animation), None = heure réelle
        self._shown_digits = None               # chiffres de l'heure dessinés à l'image précédente
        self._anims = {}                        # case -> (ancien chiffre, instant de départ)
        self._animating = False
        self._snooze_until = None   # instant (time.time()) de fin du snooze en cours, None sinon
        self._temperature = None    # None : zone vide ; nombre : température en °C ; "--" : mesure absente
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
        """Affiche l'indicateur de volume : un pixel par pas de 5 %, remplis d'abord sur l'axe horizontal (de gauche à
        droite) puis sur l'axe vertical (de bas en haut) : 5 % = en bas à gauche, 10 % = en bas à droite, 15 % = à gauche
        de la ligne du dessus, etc."""
        self._volume_level = max(0, min(VOLUME_PIXELS, int(percent) // VOLUME_STEP))
        self._volume_until = time.monotonic() + VOLUME_HIDE_S

    def set_alarms(self, next_alarm="", alarm_count=None, alarm_index=0):
        """next_alarm : "HH:MM". Sans alarm_count, un seul pixel est affiché si une alarme existe.
        Mémorisé pour tous les modes : le mode d'affichage n'est pas modifié."""
        self._next_alarm = next_alarm
        self._alarm_count = alarm_count if alarm_count is not None else (1 if next_alarm else 0)
        self._alarm_index = alarm_index

    def set_time_animation(self, style, duration=None):
        """Style de bascule des chiffres de l'heure (clé de glyphs.ANIM_PIVOTS) ou None ; durée en secondes."""
        self._time_style = style
        if duration:
            self._anim_s = duration
        self._anims.clear()

    def set_time_override(self, hhmm):
        """Impose l'heure affichée ("HHMM"), pour tester les animations sans attendre ; None rend l'heure réelle."""
        self._time_override = hhmm

    def set_snooze(self, until):
        """Snooze en cours jusqu'à `until` (time.time()) : la zone d'alarme clignote et affiche l'heure de
        reprise. None : plus de snooze (alarme arrêtée ou de nouveau en train de sonner)."""
        self._snooze_until = until

    def set_temperature(self, celsius):
        """Température de la pièce choisie (en °C). None : zone vide (Netatmo non configuré) ;
        "--" : configuré mais mesure absente ou trop ancienne."""
        self._temperature = celsius

    def set_mode_clock(self, next_alarm=None, alarm_count=None, alarm_index=0):
        """Sans next_alarm, les alarmes déjà mémorisées sont conservées."""
        self._mode = "clock"
        if next_alarm is not None:
            self.set_alarms(next_alarm, alarm_count, alarm_index)

    def set_mode_radio(self, station_name, program="", logo=None):
        self._mode = "radio"
        self._radio_station = station_name
        self._radio_program = program
        self._radio_logo = _parse_logo(logo)
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
            delay = ANIM_FRAME_S if self._animating else (SCROLL_FRAME_S if scrolling else IDLE_FRAME_S)
            if time.time() % 60 > 59.0:       # autour du changement de minute : on ne rate pas l'instant du changement
                delay = min(delay, 0.1)
            time.sleep(delay)

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
        """7 pixels contigus, lundi (0) à dimanche (6) ; le jour courant est actif, les autres secondaires."""
        for i in range(7):
            weekend = i >= 5
            if i == today:
                put(WEEK_POS[0] + i, WEEK_POS[1], WEEKEND_ACTIVE if weekend else DAY_ACTIVE)
            else:
                put2(WEEK_POS[0] + i, WEEK_POS[1], WEEKEND_DIM if weekend else DAY_DIM)

    def _draw_next_alarm(self, put, put2):
        """Un pixel par alarme définie, contigus (la plus proche est active), puis son heure (secondaire).
        Pendant un snooze : l'heure de reprise à la place, et toute la zone clignote (0,5 s allumée / 0,5 s
        éteinte) pour montrer que l'alarme est seulement reportée. Retourne True pendant un snooze."""
        snoozing = self._snooze_until is not None and time.time() < self._snooze_until
        if snoozing:
            digits = time.strftime("%H%M", time.localtime(self._snooze_until))
            count = max(self._alarm_count, 1)
            index = min(self._alarm_index, count - 1)
            if int(time.monotonic() * 2) % 2:
                return True
        else:
            digits = self._next_alarm.replace(":", "")
            count, index = self._alarm_count, self._alarm_index
        if not (count and len(digits) == 4 and digits.isdigit()):
            return snoozing
        for i in range(min(count, MAX_ALARM_DOTS)):
            draw = put if i == index else put2
            draw(ALARM_COUNT_POS[0] + i, ALARM_COUNT_POS[1],
                 ALARM_ACTIVE if i == index else ALARM_DIM)
        glyphs.draw_small(put2, ALARM_TIME_POS[0], ALARM_TIME_POS[1], digits[:2], digits[2:],
                          ALARM_ACTIVE, sep="dots")
        return snoozing

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
        logo = self._radio_logo or _parse_logo(DEFAULT_LOGO)
        for dy, row in enumerate(logo):
            for dx, color in enumerate(row):
                if color:
                    put(LOGO_POS[0] + dx, LOGO_POS[1] + dy, color)
        return moving

    def _draw_volume(self, put, put2):
        """Le pixel i (0 à 19) est dans la colonne i % 2, sur la ligne i // 2 en partant du bas ; les pixels éteints
        restent visibles (secondaires)."""
        for i in range(VOLUME_PIXELS):
            x = VOLUME_POS[0] + i % VOLUME_COLUMNS
            y = VOLUME_POS[1] + VOLUME_ROWS - 1 - i // VOLUME_COLUMNS
            if i < self._volume_level:
                put(x, y, VOLUME_LIT)
            else:
                put2(x, y, VOLUME_OFF)

    def _draw_temperature(self, put2):
        """Zone 9x5 : la température arrondie sur deux chiffres 3x5 et un pixel de degré en haut à droite.
        Cyan sous 20 °, orange de 20 à 28 °, rouge au-delà (d'après la valeur arrondie affichée)."""
        value = self._temperature
        if value is None:
            return
        x, y = TEMP_POS
        if value == "--":
            glyphs.draw_temperature(put2, x, y, "-", "-", GRAY_50, degree=False)
            return
        shown = int(value + 0.5) if value >= 0 else -int(-value + 0.5)     # arrondi au plus proche
        if not -9 <= shown <= 99:
            glyphs.draw_temperature(put2, x, y, "-", "-", GRAY_50, degree=False)
            return
        color = TEMP_COLD if shown < 20 else TEMP_WARM if shown <= 28 else TEMP_HOT
        if shown < 0:
            tens, units = "-", str(-shown)
        else:
            tens, units = ("" if shown < 10 else str(shown // 10)), str(shown % 10)
        glyphs.draw_temperature(put2, x, y, tens, units, color)

    def _time_transitions(self, digits):
        """Bascules en cours des chiffres de l'heure : {case: (ancien chiffre, avancement, ligne pivot)}.
        Une bascule démarre quand un chiffre diffère de celui dessiné à l'image précédente ; si plusieurs changent
        ensemble, elles se décalent légèrement, de droite à gauche."""
        pivot = glyphs.ANIM_PIVOTS.get(self._time_style)
        if pivot is None:
            self._anims.clear()
            self._animating = False
            self._shown_digits = digits
            return {}
        now = time.monotonic()
        if self._shown_digits and digits != self._shown_digits:
            changed = [i for i in range(4) if digits[i] != self._shown_digits[i]]
            for rank, cell in enumerate(reversed(changed)):
                self._anims[cell] = (self._shown_digits[cell], now + rank * TIME_ANIM_STAGGER_S)
        self._shown_digits = digits
        transitions = {}
        for cell, (old, start) in list(self._anims.items()):
            phase = (now - start) / self._anim_s
            if phase >= 1:
                del self._anims[cell]
            else:
                transitions[cell] = (old, max(0.0, phase), pivot)
        self._animating = bool(transitions)
        return transitions

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

        transitions = self._time_transitions(self._time_override or hh + mm)
        digits = self._time_override or hh + mm
        glyphs.draw_time(put, TIME_POS[0], TIME_POS[1], digits[:2], digits[2:], WHITE, transitions)
        self._draw_week(put, put2, now.tm_wday)
        glyphs.draw_small(put2, DATE_POS[0], DATE_POS[1], day, month, WHITE, sep="base", sep_color=GRAY_50)
        blinking = self._draw_next_alarm(put, put2)
        self._draw_temperature(put2)
        scrolling = (self._draw_radio(canvas, put, station, program) if radio_visible else False) or blinking
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
