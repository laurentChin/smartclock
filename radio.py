# radio.py — lecture des flux radio via l'ESP32 (audio_link) et titres en cours (livemeta / ICY)

import threading

from audio_link import AudioLink
from config import AUDIO_PORT, AUDIO_BAUD, DEFAULT_VOLUME, RADIO_DURATION
from livemeta import LiveMeta, station_for_url


class Radio:
    def __init__(self):
        self._link = None
        self._lock = threading.RLock()
        self._playing = False
        self._timer = None
        self._meta = None
        self._current_station = None
        self._current_title = ""
        self._volume = DEFAULT_VOLUME
        # on_title(nom_station, titre) : appelé à chaque changement de titre (à brancher sur l'affichage)
        self.on_title = None

    # ------------------------------------------------------------------ #

    def start(self):
        """Ouvre la liaison avec l'ESP32 (à appeler au démarrage : l'ouverture le redémarre)."""
        with self._lock:
            return self._ensure_link()

    def _ensure_link(self):
        if self._link:
            return True
        try:
            link = AudioLink(AUDIO_PORT, AUDIO_BAUD,
                             on_metadata=self._set_title,
                             on_event=lambda line: print(f"[audio] {line}") if line.startswith("EVT") else None)
            link.open()
            link.set_volume(self._volume)
            self._link = link
            print("[radio] ESP32 audio connecté")
            return True
        except Exception as e:
            print(f"[radio] ESP32 audio indisponible ({e}) — mode simulation")
            return False

    def _set_title(self, title):
        if not self._playing:
            return
        self._current_title = title
        print(f"[radio] Titre : {title}")
        if self.on_title:
            self.on_title(self._current_station, title)

    # ------------------------------------------------------------------ #

    def play(self, station_url, station_name="", duration=RADIO_DURATION):
        """Joue un flux radio pendant `duration` secondes."""
        with self._lock:
            self.stop()
            self._current_station = station_name
            print(f"[radio] Lecture : {station_name} ({station_url})")

            if self._ensure_link():
                self._link.set_volume(self._volume)
                self._link.play(station_url)

            # Les flux Radio France n'envoient pas de métadonnées ICY : titre via l'API livemeta
            key = station_for_url(station_url)
            if key:
                self._meta = LiveMeta(key, self._set_title)
                self._meta.start()

            self._playing = True

            if duration > 0:
                self._timer = threading.Timer(duration, self.stop)
                self._timer.daemon = True
                self._timer.start()

    def stop(self):
        """Arrête la radio."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            if self._meta:
                self._meta.stop()
                self._meta = None
            if self._link:
                self._link.stop()
            self._playing = False
            self._current_station = None
            self._current_title = ""
        print("[radio] Arrêt")

    def set_volume(self, vol):
        """Règle le volume (0-100)."""
        vol = max(0, min(100, int(vol)))
        with self._lock:
            self._volume = vol
            if self._link:
                self._link.set_volume(vol)
        print(f"[radio] Volume : {vol}%")

    def volume_up(self, step=5):
        self.set_volume(self._volume + step)

    def volume_down(self, step=5):
        self.set_volume(self._volume - step)

    @property
    def is_playing(self):
        return self._playing

    @property
    def current_station(self):
        return self._current_station

    @property
    def current_title(self):
        return self._current_title

    @property
    def volume(self):
        return self._volume


# Singleton global
radio = Radio()
