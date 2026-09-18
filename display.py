# display.py — pilotage écran RGB LED Matrix 64x32 (HUB75) via rpi-rgb-led-matrix

import os
import time
import threading
from config import (
    RGB_MATRIX_ROWS, RGB_MATRIX_COLS, RGB_MATRIX_CHAIN, RGB_MATRIX_PARALLEL,
    RGB_MATRIX_HARDWARE_MAPPING, RGB_MATRIX_GPIO_SLOWDOWN, RGB_MATRIX_RGB_SEQUENCE,
    RGB_MATRIX_BRIGHTNESS,
)

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
    MATRIX_AVAILABLE = True
except ImportError:
    MATRIX_AVAILABLE = False
    print("[display] rgbmatrix non disponible — mode simulation")


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
        self._radio_station = ""
        self._alarm_label = ""
        self._next_alarm = ""

        if MATRIX_AVAILABLE:
            # Polices bitmap (BDF) — pas d'anti-crénelage, lisibles sur les LEDs
            # espacées de ce panneau (contrairement aux polices TrueType lissées).
            self.font_time  = _load_font("9x15B.bdf")   # heure — grand, gras
            self.font_small = _load_font("clR6x12.bdf") # date / alarme / radio — police "Clean", peu arrondie

            self.color_white  = graphics.Color(255, 255, 255)
            self.color_cyan   = graphics.Color(0, 200, 255)
            self.color_orange = graphics.Color(255, 150, 0)
            self.color_green  = graphics.Color(0, 255, 0)
            self.color_red    = graphics.Color(255, 0, 0)

            # Carrés jour de la semaine : gris/blanc en semaine, orange le week-end,
            # version vive pour le jour courant, version tamisée pour les autres.
            self.DAY_DIM_WEEK    = (45, 45, 45)
            self.DAY_BRIGHT_WEEK = (255, 255, 255)
            self.DAY_DIM_WEEKEND    = (75, 32, 0)
            self.DAY_BRIGHT_WEEKEND = (255, 140, 0)

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

    def set_mode_clock(self, next_alarm=""):
        self._mode = "clock"
        self._next_alarm = next_alarm

    def set_mode_radio(self, station_name):
        self._mode = "radio"
        self._radio_station = station_name

    def set_mode_alarm(self, label=""):
        self._mode = "alarm"
        self._alarm_label = label

    def set_mode_off(self):
        self._mode = "off"
        self._clear()

    # ------------------------------------------------------------------ #
    #  Boucle interne                                                     #
    # ------------------------------------------------------------------ #

    def _loop(self):
        while self._running:
            try:
                if self._mode == "clock":
                    self._draw_clock()
                elif self._mode == "radio":
                    self._draw_radio()
                elif self._mode == "alarm":
                    self._draw_alarm()
                elif self._mode == "off":
                    pass
            except Exception as e:
                print(f"[display] Erreur rendu : {e}")
            time.sleep(0.5)

    def _text_width(self, font, text):
        return sum(font.CharacterWidth(ord(c)) for c in text)

    def _draw_day_squares(self, canvas, x0, y0, today_idx):
        """7 carrés 2x2 espacés de 1px — lundi (0) à dimanche (6)."""
        for i in range(7):
            is_weekend = i >= 5
            is_today = (i == today_idx)
            if is_weekend:
                color = self.DAY_BRIGHT_WEEKEND if is_today else self.DAY_DIM_WEEKEND
            else:
                color = self.DAY_BRIGHT_WEEK if is_today else self.DAY_DIM_WEEK
            x = x0 + i * 3
            for dx in range(2):
                for dy in range(2):
                    canvas.SetPixel(x + dx, y0 + dy, *color)

    def _draw_time(self, canvas, hh, mm, x, baseline, color):
        """HH puis MM, séparés par deux carrés 2x2 superposés (pas de glyphe ':')."""
        w = self.font_time.CharacterWidth(ord("0"))
        graphics.DrawText(canvas, self.font_time, x, baseline, color, hh)
        colon_x = x + 2 * w + 1
        for top in (baseline - 9, baseline - 3):
            for dx in range(2):
                for dy in range(2):
                    canvas.SetPixel(colon_x + dx, top + dy, color.red, color.green, color.blue)
        graphics.DrawText(canvas, self.font_time, colon_x + 4, baseline, color, mm)

    def _draw_date(self, canvas, day, month, x, baseline, color):
        """JJ | MM avec une barre verticale de 1px (le glyphe '/' gaspille des pixels)."""
        w = self.font_small.CharacterWidth(ord("0"))
        graphics.DrawText(canvas, self.font_small, x, baseline, color, day)
        bar_x = x + 2 * w
        graphics.DrawLine(canvas, bar_x, baseline - 8, bar_x, baseline - 1, color)
        graphics.DrawText(canvas, self.font_small, bar_x + 2, baseline, color, month)

    def _draw_clock(self):
        now   = time.localtime()
        hh, mm = time.strftime("%H", now), time.strftime("%M", now)
        day, month = time.strftime("%d", now), time.strftime("%m", now)
        date = f"{day}/{month}"
        heure = f"{hh}:{mm}"

        if self.matrix:
            self.canvas.Clear()
            self._draw_time(self.canvas, hh, mm, 2, 14, self.color_white)
            self._draw_day_squares(self.canvas, 22, 17, now.tm_wday)
            self._draw_date(self.canvas, day, month, 1, 31, self.color_cyan)
            if self._next_alarm:
                w = self._text_width(self.font_small, self._next_alarm)
                x = max(0, self.width - w - 1)
                graphics.DrawText(self.canvas, self.font_small, x, 31, self.color_orange, self._next_alarm)
            with self._lock:
                self.canvas = self.matrix.SwapOnVSync(self.canvas)
        else:
            print(f"[display] CLOCK  {heure}  {date}  {self._next_alarm}")

    def _draw_radio(self):
        now     = time.localtime()
        hh, mm  = time.strftime("%H", now), time.strftime("%M", now)
        heure   = f"{hh}:{mm}"
        station = self._radio_station[:10]

        if self.matrix:
            self.canvas.Clear()
            self._draw_time(self.canvas, hh, mm, 2, 15, self.color_green)
            graphics.DrawText(self.canvas, self.font_small, 2, 31, self.color_white, station)
            with self._lock:
                self.canvas = self.matrix.SwapOnVSync(self.canvas)
        else:
            print(f"[display] RADIO  {heure}  {station}")

    def _draw_alarm(self):
        """Affichage clignotant pendant l'alarme."""
        tick = int(time.time() * 2) % 2  # clignote à 1Hz

        if self.matrix:
            self.canvas.Clear()
            if tick:
                w, h = self.width - 1, self.height - 1
                graphics.DrawLine(self.canvas, 0, 0, w, 0, self.color_red)
                graphics.DrawLine(self.canvas, 0, h, w, h, self.color_red)
                graphics.DrawLine(self.canvas, 0, 0, 0, h, self.color_red)
                graphics.DrawLine(self.canvas, w, 0, w, h, self.color_red)
            graphics.DrawText(self.canvas, self.font_small, 4, 14, self.color_red, "REVEIL")
            graphics.DrawText(self.canvas, self.font_small, 4, 31, self.color_white, self._alarm_label[:10])
            with self._lock:
                self.canvas = self.matrix.SwapOnVSync(self.canvas)
        else:
            print(f"[display] *** ALARME *** {self._alarm_label}")

    def _clear(self):
        if self.matrix:
            with self._lock:
                self.matrix.Clear()


# Singleton global
display = RGBMatrixDisplay()
