# livemeta.py — titre en cours des radios Radio France (les flux Icecast n'envoient pas de métadonnées ICY)
#
# Interroge l'API publique "livemeta" (sans clef) : chaque station renvoie sa grille d'émissions
# et, pour FIP, les morceaux ; on retient l'étape la plus fine dont l'horaire couvre l'instant présent.

import threading
import time
from urllib.parse import urlparse

import requests

API_URL = "https://api.radiofrance.fr/livemeta/pull/{station_id}"
MIN_DELAY_S = 10        # jamais plus d'une requête toutes les 10 s
MAX_DELAY_S = 300       # revérifie au moins toutes les 5 min (grille modifiée en direct)
ERROR_RETRY_S = 30

STATION_IDS = {"franceinter": 1, "franceinfo": 2, "fip": 7}


def station_for_url(url):
    """"https://icecast.radiofrance.fr/fip-midfi.mp3" -> "fip" ; None si ce n'est pas un flux Radio France connu."""
    parsed = urlparse(url)
    if parsed.hostname != "icecast.radiofrance.fr":
        return None
    name = parsed.path.lstrip("/").split("-")[0]
    return name if name in STATION_IDS else None


def current_step(data, now=None):
    """(titre, fin) de l'étape la plus fine couvrant l'instant `now` : "Artiste - Titre" pour un
    morceau, sinon le nom de l'émission. (None, None) si aucune étape ne couvre cet instant."""
    now = now if now is not None else time.time()
    steps = [s for s in data.get("steps", {}).values() if s["start"] <= now < s["end"]]
    if not steps:
        return None, None
    step = max(steps, key=lambda s: s.get("depth", 0))
    if step.get("embedType") == "song":
        # "authors" liste tous les auteurs ("A & B & C") : on ne garde que l'artiste principal
        artist = (step.get("highlightedArtists") or [""])[0] or step.get("authors") or ""
        title = f"{artist} - {step['title']}" if artist else step["title"]
    else:
        title = step.get("titleConcept") or step["title"]
    return title.strip(), step["end"]


def current_title(data, now=None):
    return current_step(data, now)[0]


class LiveMeta:
    """Interroge l'API en tâche de fond et appelle on_title(titre) à chaque changement.

    L'API n'est pas officielle : on ne la sollicite qu'à la fin de l'étape en cours (changement
    de morceau ou d'émission), et en cas d'erreur on garde silencieusement le dernier titre."""

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
            delay = ERROR_RETRY_S
            try:
                resp = requests.get(API_URL.format(station_id=self._station_id), timeout=8)
                resp.raise_for_status()
                title, end = current_step(resp.json())
                if title and title != self._last:
                    self._last = title
                    if not self._stop.is_set():
                        self._on_title(title)
                delay = MAX_DELAY_S if end is None else min(MAX_DELAY_S, max(MIN_DELAY_S, end - time.time() + 2))
            except Exception:
                pass
            self._stop.wait(delay)
