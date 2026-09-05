# display.py — pilotage écran RGB LED Matrix 64x32 (HUB75) via rpi-rgb-led-matrix

import time
import threading
from config import (
    RGB_MATRIX_ROWS, RGB_MATRIX_COLS, RGB_MATRIX_CHAIN, RGB_MATRIX_PARALLEL,
    RGB_MATRIX_HARDWARE_MAPPING, RGB_MATRIX_GPIO_SLOWDOWN, RGB_MATRIX_RGB_SEQUENCE,
    RGB_MATRIX_BRIGHTNESS,
)

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    from PIL import ImageFont, Image, ImageDraw
    MATRIX_AVAILABLE = True
except ImportError:
    MATRIX_AVAILABLE = False
    print("[display] rgbmatrix non disponible — mode simulation")


def _load_fonts():
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    font_big = font_med = font_small = None
    for p in paths:
        try:
            font_big   = ImageFont.truetype(p, 14)
            font_med   = ImageFont.truetype(p, 10)
            font_small = ImageFont.truetype(p, 8)
            break
        except Exception:
            continue
    if font_big is None:
        font_big = font_med = font_small = ImageFont.load_default()
    return font_big, font_med, font_small


class RGBMatrixDisplay:
    def __init__(self):
        self.matrix = None
        self.canvas = None
        self.width  = RGB_MATRIX_COLS
        self.height = RGB_MATRIX_ROWS
        self.font_big, self.font_med, self.font_small = _load_fonts()
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._mode = "clock"        # "clock" | "radio" | "alarm" | "off"
        self._radio_station = ""
        self._alarm_label = ""
        self._next_alarm = ""
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

    def _render(self, draw_fn):
        """Dessine une image PIL via draw_fn puis l'envoie au panneau (double buffer)."""
        image = Image.new("RGB", (self.width, self.height), "black")
        draw_fn(ImageDraw.Draw(image))
        with self._lock:
            self.canvas.SetImage(image)
            self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def _draw_clock(self):
        now   = time.localtime()
        heure = time.strftime("%H:%M", now)
        date  = time.strftime("%a %d", now)

        if self.matrix:
            def draw_fn(draw):
                draw.text((2, 0),  heure, font=self.font_big,   fill=(255, 255, 255))
                draw.text((2, 20), date,  font=self.font_small, fill=(0, 200, 255))
                if self._next_alarm:
                    draw.text((self.width - 26, 20), self._next_alarm,
                              font=self.font_small, fill=(255, 150, 0))
            self._render(draw_fn)
        else:
            print(f"[display] CLOCK  {heure}  {date}  {self._next_alarm}")

    def _draw_radio(self):
        now     = time.localtime()
        heure   = time.strftime("%H:%M", now)
        station = self._radio_station[:12]

        if self.matrix:
            def draw_fn(draw):
                draw.text((0, 0),  f"▶ {heure}", font=self.font_med, fill=(0, 255, 0))
                draw.text((0, 16), station,           font=self.font_med, fill=(255, 255, 255))
            self._render(draw_fn)
        else:
            print(f"[display] RADIO  {heure}  {station}")

    def _draw_alarm(self):
        """Affichage clignotant pendant l'alarme."""
        tick = int(time.time() * 2) % 2  # clignote à 1Hz

        if self.matrix:
            def draw_fn(draw):
                if tick:
                    draw.rectangle([(0, 0), (self.width - 1, self.height - 1)], outline=(255, 0, 0))
                draw.text((4, 4),  "REVEIL",              font=self.font_med,   fill=(255, 0, 0))
                draw.text((4, 20), self._alarm_label[:12], font=self.font_small, fill=(255, 255, 255))
            self._render(draw_fn)
        else:
            print(f"[display] *** ALARME *** {self._alarm_label}")

    def _clear(self):
        if self.matrix:
            with self._lock:
                self.matrix.Clear()


# Singleton global
display = RGBMatrixDisplay()
