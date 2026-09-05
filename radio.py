# radio.py — contrôle MPD pour la lecture des flux radio

import subprocess
import threading
import time
from config import MPD_HOST, MPD_PORT, RADIO_DURATION

try:
    from mpd import MPDClient
    MPD_AVAILABLE = True
except ImportError:
    MPD_AVAILABLE = False
    print("[radio] python-mpd2 non disponible — mode simulation")


def _mpc(cmd):
    """Exécute une commande mpc (fallback si python-mpd2 absent)."""
    try:
        result = subprocess.run(
            ["mpc"] + cmd.split(),
            capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[radio] mpc error: {e}")
        return ""


class Radio:
    def __init__(self):
        self._client = None
        self._playing = False
        self._timer = None
        self._current_station = None
        self._volume = 65

    def _connect(self):
        if not MPD_AVAILABLE:
            return False
        try:
            self._client = MPDClient()
            self._client.connect(MPD_HOST, MPD_PORT)
            return True
        except Exception as e:
            print(f"[radio] MPD connexion échouée : {e}")
            self._client = None
            return False

    def _disconnect(self):
        if self._client:
            try:
                self._client.close()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

    # ------------------------------------------------------------------ #

    def play(self, station_url, station_name="", duration=RADIO_DURATION):
        """Joue un flux radio pendant `duration` secondes."""
        self.stop()
        self._current_station = station_name
        print(f"[radio] Lecture : {station_name} ({station_url})")

        if MPD_AVAILABLE and self._connect():
            try:
                self._client.clear()
                self._client.add(station_url)
                self._client.play()
                self._client.setvol(self._volume)
                self._disconnect()
            except Exception as e:
                print(f"[radio] MPD play error : {e}")
                self._disconnect()
        else:
            # Fallback mpc
            _mpc(f"clear")
            subprocess.run(["mpc", "add", station_url])
            _mpc("play")
            _mpc(f"volume {self._volume}")

        self._playing = True

        # Arrêt automatique après `duration` secondes
        if duration > 0:
            self._timer = threading.Timer(duration, self.stop)
            self._timer.daemon = True
            self._timer.start()

    def stop(self):
        """Arrête la radio."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

        if MPD_AVAILABLE and self._connect():
            try:
                self._client.stop()
                self._client.clear()
                self._disconnect()
            except Exception:
                self._disconnect()
        else:
            _mpc("stop")
            _mpc("clear")

        self._playing = False
        self._current_station = None
        print("[radio] Arrêt")

    def set_volume(self, vol):
        """Règle le volume (0-100)."""
        vol = max(0, min(100, int(vol)))
        self._volume = vol
        if MPD_AVAILABLE and self._connect():
            try:
                self._client.setvol(vol)
                self._disconnect()
            except Exception:
                self._disconnect()
        else:
            _mpc(f"volume {vol}")
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
    def volume(self):
        return self._volume


# Singleton global
radio = Radio()
