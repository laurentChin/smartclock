# controls.py — boutons lus par l'ESP32 et transmis par la liaison série
#
#   BTN main      un seul bouton, selon le contexte :
#                   alarme en cours -> snooze ; radio allumée -> stop ; sinon -> radio pendant 1 h
#   BTN main_long appui long : arrêt définitif (radio, alarme et snooze en attente)
#   BTN vol_up / BTN vol_down   volume (répétés par l'ESP32 si le bouton est maintenu)

VOLUME_STEP = 5


class ControlsHandler:
    def __init__(self, radio, alarm_daemon, display, database):
        self.radio        = radio
        self.alarm_daemon = alarm_daemon
        self.display      = display
        self.database     = database

    def setup(self):
        self.radio.on_input = self._on_input
        print("[controls] Boutons reliés à l'ESP32")

    def _on_input(self, line):
        handlers = {
            "BTN main":      self._on_main,
            "BTN main_long": self._on_stop,
            "BTN vol_up":   lambda: self.radio.volume_up(VOLUME_STEP),
            "BTN vol_down": lambda: self.radio.volume_down(VOLUME_STEP),
        }
        handler = handlers.get(line.strip())
        if handler:
            handler()

    def _on_stop(self):
        print("[controls] BTN long : arrêt")
        if self.alarm_daemon:
            self.alarm_daemon.dismiss()
        else:
            self.radio.stop()
        self.display.set_mode_clock()

    def _on_main(self):
        if self.alarm_daemon and self.alarm_daemon.ringing:
            print("[controls] BTN : snooze")
            self.alarm_daemon.snooze()
        elif self.radio.is_playing:
            print("[controls] BTN : stop")
            self.radio.stop()
            self.display.set_mode_clock()
        else:
            print("[controls] BTN : radio 1 h")
            station = self.database.get_default_station()
            if station:
                self.radio.play(station["url"], station["name"], logo=station["logo"])
                self.display.set_mode_radio(station["name"], self.radio.current_title, self.radio.current_logo)
            else:
                print("[controls] Aucune station par défaut configurée")
