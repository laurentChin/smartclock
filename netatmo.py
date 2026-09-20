# netatmo.py — température d'une pièce lue sur le hub Netatmo (API Energy : homesdata / homestatus)
#
# Authentification OAuth2 : l'accès se fait avec un jeton de renouvellement (refresh token) généré sur
# dev.netatmo.com pour l'application de l'utilisateur. Netatmo renvoie un nouveau jeton de renouvellement à
# chaque renouvellement du jeton d'accès (valable environ 3 h) : le dernier est donc toujours réécrit dans
# NETATMO_FILE (droits 600, hors dépôt). Identifiants, jetons et choix de la pièce ne sont jamais dans le code.

import json
import os
import tempfile
import threading
import time

import requests

import config


class NetatmoError(Exception):
    """Erreur présentable à l'utilisateur (message en français)."""


def _describe(response):
    """Message lisible à partir d'une réponse d'erreur de l'API Netatmo."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error")
    if isinstance(error, dict):                      # {"error": {"code": 26, "message": "..."}}
        code, message = error.get("code"), error.get("message", "")
        if code == 26:
            return "Limite de requêtes Netatmo atteinte, réessaie dans quelques minutes"
        return f"Netatmo : {message or code}"
    if error in ("invalid_grant", "invalid_client", "invalid_request", "invalid_token"):
        return "Identifiants ou jeton refusés par Netatmo : vérifie-les et régénère le jeton"
    return f"Netatmo a répondu {response.status_code}"


class Netatmo:
    def __init__(self):
        self.on_update = None          # on_update(valeur) : None = zone vide, "--" = mesure absente, sinon °C
        self._lock = threading.RLock()
        self._data = self._load()
        self._access = None
        self._access_expires = 0.0
        self.temperature = None
        self.updated_at = None         # instant (time.time()) de la dernière mesure reçue
        self.error = ""
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None

    # ---- fichier des réglages ----

    @staticmethod
    def _path():
        return config.NETATMO_FILE

    def _load(self):
        try:
            with open(self._path(), encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        """Écriture atomique avec les droits 600 : ce fichier contient des secrets. Le contenu puis le renommage
        sont forcés sur le disque (fsync) : Netatmo invalide l'ancien jeton à chaque rotation, une coupure de courant
        qui laisserait un fichier vide obligerait à tout reconnecter."""
        directory = os.path.dirname(os.path.abspath(self._path()))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".netatmo-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self._path())
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ---- état ----

    @property
    def configured(self):
        return bool(self._data.get("client_id") and self._data.get("client_secret") and self._data.get("refresh_token"))

    @property
    def room(self):
        if self._data.get("home_id") and self._data.get("room_id"):
            return {"home_id": self._data["home_id"], "room_id": self._data["room_id"],
                    "name": self._data.get("room_name", "")}
        return None

    def display_value(self):
        """Ce que le panneau doit afficher : None (zone vide), "--" ou une température en °C."""
        if not (self.configured and self.room):
            return None
        fresh = self.updated_at is not None and time.time() - self.updated_at < config.NETATMO_STALE_S
        return self.temperature if (fresh and self.temperature is not None) else "--"

    def status(self):
        """État pour l'interface web. Ne contient jamais les identifiants ni les jetons."""
        with self._lock:
            return {
                "configured": self.configured,
                "room": self.room,
                "temperature": self.temperature,
                "updated_at": self.updated_at,
                "fresh": self.display_value() not in (None, "--"),
                "error": self.error,
            }

    # ---- appels à l'API ----

    def _token_request(self, client_id, client_secret, refresh_token):
        try:
            response = requests.post(
                config.NETATMO_API_URL + "/oauth2/token",
                data={"grant_type": "refresh_token", "refresh_token": refresh_token,
                      "client_id": client_id, "client_secret": client_secret},
                timeout=(5, 10))
        except requests.RequestException:
            raise NetatmoError("Netatmo est injoignable : vérifie la connexion du Pi")
        if response.status_code != 200:
            raise NetatmoError(_describe(response))
        body = response.json()
        return body["access_token"], body.get("refresh_token", refresh_token), int(body.get("expires_in", 10800))

    def _access_token(self):
        with self._lock:
            if self._access and time.time() < self._access_expires - 60:
                return self._access
            token, refresh, lifetime = self._token_request(
                self._data["client_id"], self._data["client_secret"], self._data["refresh_token"])
            self._access, self._access_expires = token, time.time() + lifetime
            if refresh != self._data["refresh_token"]:       # Netatmo fait tourner ce jeton : on garde le dernier
                self._data["refresh_token"] = refresh
                self._save()
            return token

    def _get(self, path, params=None):
        for attempt in (1, 2):
            try:
                response = requests.get(config.NETATMO_API_URL + path, params=params, timeout=(5, 10),
                                        headers={"Authorization": f"Bearer {self._access_token()}"})
            except requests.RequestException:
                raise NetatmoError("Netatmo est injoignable : vérifie la connexion du Pi")
            if response.status_code in (401, 403) and attempt == 1:
                with self._lock:                              # jeton d'accès refusé : on en redemande un
                    self._access = None
                continue
            if response.status_code != 200:
                raise NetatmoError(_describe(response))
            return response.json().get("body", {})

    def rooms(self):
        """Pièces de toutes les maisons du compte : [{home_id, home_name, room_id, room_name}]."""
        homes = self._get("/api/homesdata").get("homes", [])
        return [{"home_id": home["id"], "home_name": home.get("name", "Maison"),
                 "room_id": room["id"], "room_name": room.get("name", "Pièce")}
                for home in homes for room in home.get("rooms", [])]

    def _read_temperature(self, home_id, room_id):
        status = self._get("/api/homestatus", {"home_id": home_id})
        for room in status.get("home", {}).get("rooms", []):
            if room.get("id") == room_id:
                value = room.get("therm_measured_temperature")
                return float(value) if value is not None else None
        raise NetatmoError("La pièce choisie n'existe plus chez Netatmo : choisis-en une autre")

    # ---- actions depuis l'interface web ----

    def connect(self, client_id, client_secret, refresh_token):
        """Vérifie les identifiants auprès de Netatmo puis les enregistre. Lève NetatmoError s'ils sont refusés."""
        token, refresh, lifetime = self._token_request(client_id, client_secret, refresh_token)
        with self._lock:
            self._data.update(client_id=client_id, client_secret=client_secret, refresh_token=refresh)
            self._save()
            self._access, self._access_expires = token, time.time() + lifetime
            self.error = ""
        self.refresh_soon()

    def select_room(self, home_id, room_id):
        for room in self.rooms():
            if room["home_id"] == home_id and room["room_id"] == room_id:
                with self._lock:
                    self._data.update(home_id=home_id, room_id=room_id, room_name=room["room_name"])
                    self.temperature, self.updated_at, self.error = None, None, ""
                    self._save()
                self.refresh_soon()
                return
        raise NetatmoError("Pièce inconnue chez Netatmo")

    def disconnect(self):
        with self._lock:
            self._data = {}
            self._access, self._access_expires = None, 0.0
            self.temperature, self.updated_at, self.error = None, None, ""
            try:
                os.unlink(self._path())
            except OSError:
                pass
        self._publish()

    # ---- lecture périodique ----

    def _publish(self):
        if self.on_update:
            self.on_update(self.display_value())

    def poll_once(self):
        if not (self.configured and self.room):
            self._publish()
            return
        room = self.room
        try:
            value = self._read_temperature(room["home_id"], room["room_id"])
            with self._lock:
                self.temperature, self.updated_at, self.error = value, time.time(), ""
                if value is None:
                    self.error = "Cette pièce n'a pas de mesure de température (thermostat ou vanne absents ?)"
        except NetatmoError as exc:
            with self._lock:
                self.error = str(exc)
        except (KeyError, ValueError, TypeError):
            with self._lock:
                self.error = "Réponse inattendue de Netatmo"
        self._publish()

    def refresh_soon(self):
        self._wake.set()

    def _run(self):
        while not self._stop.is_set():
            self._wake.clear()
            try:
                self.poll_once()
            except Exception as exc:                     # le fil de lecture ne doit jamais s'arrêter
                print(f"[netatmo] Erreur : {exc}")
            self._wake.wait(config.NETATMO_POLL_S)

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()


netatmo = Netatmo()
