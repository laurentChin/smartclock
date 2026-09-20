# livemeta.py — titre en cours des radios Radio France (les flux Icecast n'envoient pas de métadonnées ICY)
#
# Interroge l'API publique "livemeta" (sans clef) : chaque station renvoie sa grille d'émissions
# et, pour FIP, les morceaux ; on retient l'étape la plus fine dont l'horaire couvre l'instant présent.

import threading
import time

import requests

API_URL = "https://api.radiofrance.fr/livemeta/pull/{station_id}"
REFRESH_S = 20
ERROR_RETRY_S = 10

STATION_IDS = {"franceinter": 1, "franceinfo": 2, "fip": 7}


def current_title(data, now=None):
    """Texte à afficher pour l'instant `now` : "Artiste - Titre" pour un morceau, sinon le nom de l'émission."""
    now = now if now is not None else time.time()
    steps = [s for s in data.get("steps", {}).values() if s["start"] <= now < s["end"]]
    if not steps:
        return None
    step = max(steps, key=lambda s: s.get("depth", 0))
    if step.get("embedType") == "song":
        artist = step.get("authors") or (step.get("highlightedArtists") or [""])[0]
        return f"{artist} - {step['title']}" if artist else step["title"]
    return step.get("titleConcept") or step["title"]


class LiveMeta:
    """Interroge l'API en tâche de fond et appelle on_title(titre) à chaque changement."""

    def __init__(self, station, on_title):
        self._station_id = STATION_IDS[station]
        self._on_title = on_title
        self._stop = threading.Event()
        self._last = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            delay = REFRESH_S
            try:
                resp = requests.get(API_URL.format(station_id=self._station_id), timeout=8)
                resp.raise_for_status()
                title = current_title(resp.json())
                if title and title != self._last:
                    self._last = title
                    self._on_title(title)
            except Exception:
                delay = ERROR_RETRY_S
            self._stop.wait(delay)
