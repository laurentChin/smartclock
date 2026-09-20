# app.py — serveur Flask + point d'entrée principal

from flask import Flask, render_template, request, jsonify
import re
import subprocess
import threading
import time
from urllib.parse import urlparse

import requests

from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, DEFAULT_LOGO, LOGO_SIZE
import access
import database as db
from radio import radio
from display import display
from alarm import AlarmDaemon, DAYS_FR
from audio_link import USER_AGENT
from controls import ControlsHandler

app = Flask(__name__)

@app.before_request
def only_local_network():
    """Refuse tout client hors du réseau local. Flask n'écoute qu'en local : seul Caddy s'y connecte, et il
    écrase l'en-tête X-Forwarded-For par l'adresse réelle du client."""
    client = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[-1].strip()
    if not access.is_local(client):
        print(f"[access] refusé : {client}")
        return jsonify({"error": "Accès réservé au réseau local"}), 403


# === Initialisation ===
db.init_db()
display.start()
radio.on_title = lambda station, title: display.mode == "radio" and display.set_mode_radio(station, title, radio.current_logo)
radio.on_volume = display.show_volume
radio.start()

alarm_daemon = AlarmDaemon(radio, display)
alarm_daemon.start()

controls = ControlsHandler(radio, alarm_daemon, display, db)
controls.setup()

display.set_mode_clock()


# ------------------------------------------------------------------ #
#  Routes API                                                         #
# ------------------------------------------------------------------ #

@app.route("/")
def index():
    return render_template(
        "index.html",
        page="alarms",
        stations=db.get_stations(),
        alarms=db.get_alarms(),
        volume=radio.volume,
        is_playing=radio.is_playing,
        current_station=radio.current_station or "",
    )


# --- Radio ---

@app.route("/api/radio/play", methods=["POST"])
def api_radio_play():
    data       = request.json or {}
    station_id = data.get("station_id")
    stations   = {s["id"]: s for s in db.get_stations()}
    station    = stations.get(station_id) or db.get_default_station()
    if not station:
        return jsonify({"error": "Aucune station disponible"}), 400
    radio.play(station["url"], station["name"], logo=station["logo"])
    display.set_mode_radio(station["name"], radio.current_title, radio.current_logo)
    return jsonify({"status": "playing", "station": station["name"]})


@app.route("/api/radio/stop", methods=["POST"])
def api_radio_stop():
    radio.stop()
    display.set_mode_clock()
    return jsonify({"status": "stopped"})


@app.route("/api/radio/volume", methods=["POST"])
def api_radio_volume():
    vol = request.json.get("volume", 65)
    radio.set_volume(vol)
    return jsonify({"volume": radio.volume})


# --- Alarmes ---

@app.route("/api/alarms", methods=["GET"])
def api_get_alarms():
    return jsonify(db.get_alarms())


def _alarm_from_request():
    """Lit et valide le corps JSON d'une alarme. Retourne (valeurs, None) ou (None, message d'erreur)."""
    data = request.get_json(silent=True) or {}
    time_value = str(data.get("time", ""))
    try:
        hour, minute = map(int, time_value.split(":"))
        valid_time = len(time_value) == 5 and 0 <= hour < 24 and 0 <= minute < 60
    except ValueError:
        valid_time = False
    if not valid_time:
        return None, "Heure invalide (format HH:MM)"
    days = data.get("days")
    if not isinstance(days, list) or not days or not all(d in DAYS_FR for d in days):
        return None, "Choisis au moins un jour"
    if data.get("station_id") not in {s["id"] for s in db.get_stations()}:
        return None, "Station inconnue"
    return {
        "time": time_value,
        "days": [d for d in DAYS_FR if d in days],
        "station_id": data["station_id"],
        "label": str(data.get("label", "")).strip()[:40],
    }, None


@app.route("/api/alarms", methods=["POST"])
def api_add_alarm():
    values, error = _alarm_from_request()
    if error:
        return jsonify({"error": error}), 400
    db.add_alarm(**values)
    alarm_daemon.refresh_display()
    return jsonify({"status": "ok"}), 201


@app.route("/api/alarms/<int:alarm_id>", methods=["PUT"])
def api_update_alarm(alarm_id):
    values, error = _alarm_from_request()
    if error:
        return jsonify({"error": error}), 400
    if not db.update_alarm(alarm_id, **values):
        return jsonify({"error": "Alarme introuvable"}), 404
    alarm_daemon.refresh_display()
    return jsonify({"status": "ok"})


@app.route("/api/alarms/<int:alarm_id>", methods=["DELETE"])
def api_delete_alarm(alarm_id):
    db.delete_alarm(alarm_id)
    alarm_daemon.refresh_display()
    return jsonify({"status": "ok"})


@app.route("/api/alarms/<int:alarm_id>/toggle", methods=["POST"])
def api_toggle_alarm(alarm_id):
    enabled = (request.get_json(silent=True) or {}).get("enabled", True)
    db.toggle_alarm(alarm_id, enabled)
    alarm_daemon.refresh_display()
    return jsonify({"status": "ok"})


# --- Stations ---

def _check_stream(url):
    """Vérifie que le flux répond en MP3 (seul format lu par l'ESP32). Retourne un message d'erreur ou None."""
    try:
        with requests.get(url, stream=True, timeout=(5, 8), headers={"User-Agent": USER_AGENT}) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").lower()
    except requests.RequestException:
        return "Flux injoignable : vérifie l'adresse"
    if "mpeg" not in content_type and "mp3" not in content_type:
        return "Format non pris en charge : seuls les flux MP3 sont lus"
    return None


def _logo_valid(logo):
    return (isinstance(logo, list) and len(logo) == LOGO_SIZE
            and all(isinstance(row, list) and len(row) == LOGO_SIZE
                    and all(cell is None or (isinstance(cell, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", cell))
                            for cell in row)
                    for row in logo))


def _station_from_request(current_logo=None):
    """Lit et valide le corps JSON d'une station. Retourne (valeurs, None) ou (None, message d'erreur).
    Sans clé "logo", le logo actuel est conservé ; "logo": null l'efface."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    url = str(data.get("url", "")).strip()
    parsed = urlparse(url)
    if not name:
        return None, "Donne un nom à la station"
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None, "Adresse invalide (http:// ou https://)"
    logo = data.get("logo", current_logo)
    if logo is not None and not _logo_valid(logo):
        return None, f"Logo invalide (grille {LOGO_SIZE}x{LOGO_SIZE} de couleurs #rrggbb)"
    return {"name": name[:40], "url": url, "genre": str(data.get("genre", "")).strip()[:30],
            "logo": logo}, None


@app.route("/stations")
def stations_page():
    return render_template("stations.html", page="stations", stations=db.get_stations(), default_logo=DEFAULT_LOGO,
                           logo_size=LOGO_SIZE)


@app.route("/api/stations", methods=["GET"])
def api_get_stations():
    return jsonify(db.get_stations())


@app.route("/api/stations", methods=["POST"])
def api_add_station():
    values, error = _station_from_request()
    if values:
        error = _check_stream(values["url"])
    if error:
        return jsonify({"error": error}), 400
    db.add_station(**values)
    return jsonify({"status": "ok"}), 201


@app.route("/api/stations/<int:station_id>", methods=["PUT"])
def api_update_station(station_id):
    current = db.get_station(station_id)
    if not current:
        return jsonify({"error": "Station introuvable"}), 404
    values, error = _station_from_request(current["logo"])
    if values and values["url"] != current["url"]:      # le flux n'est revérifié que si l'adresse change
        error = _check_stream(values["url"])
    if error:
        return jsonify({"error": error}), 400
    db.update_station(station_id, **values)
    return jsonify({"status": "ok"})


@app.route("/api/stations/<int:station_id>", methods=["DELETE"])
def api_delete_station(station_id):
    station = db.get_station(station_id)
    if not station:
        return jsonify({"error": "Station introuvable"}), 404
    if station["is_default"]:
        return jsonify({"error": "Choisis d'abord une autre station par défaut"}), 409
    db.delete_station(station_id)
    alarm_daemon.refresh_display()
    return jsonify({"status": "ok"})


@app.route("/api/stations/<int:station_id>/default", methods=["POST"])
def api_set_default_station(station_id):
    if not db.get_station(station_id):
        return jsonify({"error": "Station introuvable"}), 404
    db.set_default_station(station_id)
    return jsonify({"status": "ok"})


# --- Alarme physique ---

@app.route("/api/alarm/snooze", methods=["POST"])
def api_snooze():
    alarm_daemon.snooze()
    return jsonify({"status": "snoozed"})


@app.route("/api/alarm/dismiss", methods=["POST"])
def api_dismiss():
    alarm_daemon.dismiss()
    return jsonify({"status": "dismissed"})


# --- Système ---

SYSTEM_COMMANDS = {"reboot": ["systemctl", "reboot"], "shutdown": ["systemctl", "poweroff"]}


def _run_system_command(command):
    time.sleep(1.5)     # laisse partir la réponse HTTP
    try:
        subprocess.run(command, check=True, timeout=30)
    except Exception as e:
        print(f"[system] Échec de {' '.join(command)} : {e}")
        display.set_mode_clock()    # l'écran avait été éteint pour rien


@app.route("/system")
def system_page():
    return render_template("system.html", page="system")


@app.route("/api/system/<action>", methods=["POST"])
def api_system(action):
    command = SYSTEM_COMMANDS.get(action)
    if not command:
        return jsonify({"error": "Action inconnue"}), 404
    if not request.is_json:     # refuse les envois de formulaire venus d'une autre page
        return jsonify({"error": "Requête JSON attendue"}), 400
    print(f"[system] {action}")
    radio.stop()
    display.set_mode_off()
    threading.Thread(target=_run_system_command, args=(command,), daemon=True).start()
    return jsonify({"status": action})


# ------------------------------------------------------------------ #

if __name__ == "__main__":
    try:
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, use_reloader=False)
    finally:
        display.stop()
