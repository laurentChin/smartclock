# app.py — serveur Flask + point d'entrée principal

from flask import Flask, render_template, request, jsonify
import threading

from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
import database as db
from radio import radio
from display import display
from alarm import AlarmDaemon, DAYS_FR
from controls import ControlsHandler

app = Flask(__name__)

# === Initialisation ===
db.init_db()
display.start()
radio.on_title = lambda station, title: display.mode == "radio" and display.set_mode_radio(station, title)
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
    radio.play(station["url"], station["name"])
    display.set_mode_radio(station["name"], radio.current_title)
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

@app.route("/api/stations", methods=["GET"])
def api_get_stations():
    return jsonify(db.get_stations())


@app.route("/api/stations", methods=["POST"])
def api_add_station():
    data = request.json
    db.add_station(data["name"], data["url"], data.get("genre", ""))
    return jsonify({"status": "ok"}), 201


@app.route("/api/stations/<int:station_id>", methods=["DELETE"])
def api_delete_station(station_id):
    db.delete_station(station_id)
    return jsonify({"status": "ok"})


@app.route("/api/stations/<int:station_id>/default", methods=["POST"])
def api_set_default_station(station_id):
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


# ------------------------------------------------------------------ #

if __name__ == "__main__":
    try:
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, use_reloader=False)
    finally:
        display.stop()
