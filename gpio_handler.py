# gpio_handler.py — gestion des boutons et de l'encodeur rotatif

from config import (
    PIN_BTN_STOP, PIN_BTN_RADIO, PIN_BTN_SNOOZE,
    PIN_ENC_CLK, PIN_ENC_DT, PIN_ENC_SW
)

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[gpio] RPi.GPIO non disponible — mode simulation")


class GPIOHandler:
    def __init__(self, radio, alarm_daemon, display, database):
        self.radio        = radio
        self.alarm_daemon = alarm_daemon
        self.display      = display
        self.database     = database
        self._enc_last    = None

    def setup(self):
        if not GPIO_AVAILABLE:
            print("[gpio] GPIO non initialisé (pas sur Pi)")
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Boutons avec pull-up interne
        for pin in [PIN_BTN_STOP, PIN_BTN_RADIO, PIN_BTN_SNOOZE, PIN_ENC_SW]:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Encodeur rotatif
        GPIO.setup(PIN_ENC_CLK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_ENC_DT,  GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self._enc_last = GPIO.input(PIN_ENC_CLK)

        # Interruptions
        GPIO.add_event_detect(PIN_BTN_STOP,  GPIO.FALLING,
                              callback=self._on_stop,  bouncetime=300)
        GPIO.add_event_detect(PIN_BTN_RADIO, GPIO.FALLING,
                              callback=self._on_radio, bouncetime=300)
        GPIO.add_event_detect(PIN_BTN_SNOOZE,GPIO.FALLING,
                              callback=self._on_snooze,bouncetime=300)
        GPIO.add_event_detect(PIN_ENC_CLK,   GPIO.BOTH,
                              callback=self._on_encoder)
        GPIO.add_event_detect(PIN_ENC_SW,    GPIO.FALLING,
                              callback=self._on_enc_button, bouncetime=300)

        print("[gpio] GPIO initialisé")

    def cleanup(self):
        if GPIO_AVAILABLE:
            GPIO.cleanup()

    # ------------------------------------------------------------------ #

    def _on_stop(self, channel):
        print("[gpio] BTN STOP")
        if self.alarm_daemon:
            self.alarm_daemon.dismiss()
        else:
            self.radio.stop()
        self.display.set_mode_clock()

    def _on_radio(self, channel):
        print("[gpio] BTN RADIO 1H")
        station = self.database.get_default_station()
        if station:
            self.radio.play(station["url"], station["name"])
            self.display.set_mode_radio(station["name"], self.radio.current_title)
        else:
            print("[gpio] Aucune station par défaut configurée")

    def _on_snooze(self, channel):
        print("[gpio] BTN SNOOZE")
        if self.alarm_daemon:
            self.alarm_daemon.snooze()

    def _on_encoder(self, channel):
        if not GPIO_AVAILABLE:
            return
        clk = GPIO.input(PIN_ENC_CLK)
        if clk != self._enc_last:
            dt = GPIO.input(PIN_ENC_DT)
            if dt != clk:
                self.radio.volume_up()
            else:
                self.radio.volume_down()
            self._enc_last = clk

    def _on_enc_button(self, channel):
        """Appui sur l'encodeur : pause/reprise."""
        print("[gpio] ENC bouton")
        if self.radio.is_playing:
            self.radio.stop()
            self.display.set_mode_clock()
        else:
            station = self.database.get_default_station()
            if station:
                self.radio.play(station["url"], station["name"])
                self.display.set_mode_radio(station["name"], self.radio.current_title)
