# alarm.py — démon de surveillance et déclenchement des alarmes

import time
import threading
from config import SNOOZE_DURATION, RADIO_DURATION
from database import get_active_alarms_for_now, get_default_station, get_stations

DAYS_FR = ["LU", "MA", "ME", "JE", "VE", "SA", "DI"]


class AlarmDaemon:
    def __init__(self, radio, display):
        self.radio   = radio
        self.display = display
        self._running      = False
        self._thread       = None
        self._last_checked = ""     # HH:MM déjà déclenché
        self._snoozed_until = None  # timestamp fin snooze
        self._ringing      = False  # une alarme vient de démarrer la radio
        self._snoozed_alarm = None  # alarme à rejouer à la fin du snooze
        self._current_alarm = None  # dernière alarme déclenchée (rejouée après un snooze)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[alarm] Démon démarré")

    def stop(self):
        self._running = False

    @property
    def ringing(self):
        """Vrai tant que la radio lancée par une alarme joue."""
        return self._ringing and self.radio.is_playing

    def snooze(self):
        """Reporte l'alarme en cours de SNOOZE_DURATION secondes."""
        self._ringing = False
        self.radio.stop()
        self.display.set_mode_clock()
        self._snoozed_alarm = self._current_alarm
        self._snoozed_until = time.time() + SNOOZE_DURATION
        print(f"[alarm] Snooze {SNOOZE_DURATION}s")

    def dismiss(self):
        """Arrête l'alarme définitivement (annule aussi un snooze en attente)."""
        self._ringing = False
        self._snoozed_alarm = None
        self.radio.stop()
        self.display.set_mode_clock()
        self._snoozed_until = None
        print("[alarm] Alarme arrêtée")

    # ------------------------------------------------------------------ #

    def _loop(self):
        while self._running:
            now        = time.localtime()
            current_hm = time.strftime("%H:%M", now)
            weekday    = DAYS_FR[now.tm_wday]   # 0=LU … 6=DI

            # Snooze en cours ?
            if self._snoozed_until:
                remaining = self._snoozed_until - time.time()
                if remaining > 0:
                    time.sleep(min(10, remaining))   # réveil précis à la fin du snooze
                    continue
                alarm, self._snoozed_alarm, self._snoozed_until = self._snoozed_alarm, None, None
                if alarm:
                    print("[alarm] Fin du snooze")
                    self._trigger(alarm)

            # Vérifier seulement une fois par minute
            if current_hm != self._last_checked:
                self._last_checked = current_hm
                triggered = get_active_alarms_for_now(weekday, current_hm)
                for alarm in triggered:
                    self._trigger(alarm)

            time.sleep(15)

    def _trigger(self, alarm):
        self._current_alarm = alarm
        print(f"[alarm] Déclenchement : {alarm['time']} — {alarm.get('station_name','?')}")

        # Récupérer l'URL de la station
        stations = {s["id"]: s for s in get_stations()}
        station  = stations.get(alarm["station_id"])
        if not station:
            print(f"[alarm] Station introuvable pour l'alarme {alarm['id']} — station par défaut")
            station = get_default_station()

        if station:
            self._ringing = True
            self.display.set_mode_alarm(station["name"])
            self.radio.play(
                station["url"],
                station_name=station["name"],
                duration=RADIO_DURATION
            )
            # Repasser en mode radio sur l'écran après 5s d'affichage alarme
            def switch_to_radio():
                time.sleep(5)
                if self.radio.is_playing:
                    self.display.set_mode_radio(station["name"], self.radio.current_title)
            threading.Thread(target=switch_to_radio, daemon=True).start()
        else:
            print("[alarm] Aucune station disponible")
