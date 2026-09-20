# app.py — serveur Flask + point d'entrée principal

from flask import Flask, render_template, request, jsonify
import threading

from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
import database as db
from radio import radio
from display import display
from alarm import AlarmDaemon
from controls import ControlsHandler

app = Flask(__name__)

# === Initialisation ===
db.init_db()
display.start()
radio.on_title = lambda station, title: display.mode == "radio" and display.set_mode_radio(station, title)
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


@app.route("/api/alarms", methods=["POST"])
def api_add_alarm():
    data = request.json
    db.add_alarm(
        time=data["time"],
        days=data["days"],
        station_id=data["station_id"],
        label=data.get("label", "")
    )
    return jsonify({"status": "ok"}), 201


@app.route("/api/alarms/<int:alarm_id>", methods=["DELETE"])
def api_delete_alarm(alarm_id):
    db.delete_alarm(alarm_id)
    return jsonify({"status": "ok"})


@app.route("/api/alarms/<int:alarm_id>/toggle", methods=["POST"])
def api_toggle_alarm(alarm_id):
    enabled = request.json.get("enabled", True)
    db.toggle_alarm(alarm_id, enabled)
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
