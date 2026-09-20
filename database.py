# database.py — accès SQLite (alarmes et stations)

import sqlite3
import json
from config import DATABASE_PATH, DEFAULT_STATIONS, LOGO_SIZE


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables et insère les données par défaut si nécessaire."""
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            url     TEXT NOT NULL,
            genre   TEXT DEFAULT '',
            is_default INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            time      TEXT NOT NULL,          -- format HH:MM
            days      TEXT NOT NULL,          -- JSON array ["LU","MA",...]
            station_id INTEGER REFERENCES stations(id),
            enabled   INTEGER DEFAULT 1,
            label     TEXT DEFAULT ''
        )
    """)

    # Logo de la station (JSON) : colonne ajoutée après coup, donc migration des bases existantes
    columns = [row["name"] for row in c.execute("PRAGMA table_info(stations)")]
    if "logo" not in columns:
        c.execute("ALTER TABLE stations ADD COLUMN logo TEXT")

    # Logos d'une autre taille (changement de LOGO_SIZE) : on ne peut pas les convertir sans perdre le dessin.
    # Les stations par défaut retrouvent leur logo, les autres reviennent au logo par défaut.
    defaults = {s["name"]: s.get("logo") for s in DEFAULT_STATIONS}
    for row in c.execute("SELECT id, name, logo FROM stations WHERE logo IS NOT NULL").fetchall():
        try:
            stored = json.loads(row["logo"])
            valid = isinstance(stored, list) and len(stored) == LOGO_SIZE and all(len(r) == LOGO_SIZE for r in stored)
        except ValueError:
            valid = False
        if not valid:
            replacement = defaults.get(row["name"])
            c.execute("UPDATE stations SET logo = ? WHERE id = ?",
                      (json.dumps(replacement) if replacement else None, row["id"]))

    # Insérer les stations par défaut si la table est vide
    c.execute("SELECT COUNT(*) FROM stations")
    if c.fetchone()[0] == 0:
        for s in DEFAULT_STATIONS:
            c.execute(
                "INSERT INTO stations (name, url, genre, is_default, logo) VALUES (?, ?, ?, ?, ?)",
                (s["name"], s["url"], s["genre"], 1 if s["default"] else 0, json.dumps(s.get("logo")))
            )

    conn.commit()
    conn.close()


# === STATIONS ===

def _station(row):
    """Ligne SQL -> dict, avec le logo décodé (grille de "#rrggbb" ou None, ou None sans logo)."""
    station = dict(row)
    try:
        station["logo"] = json.loads(station["logo"]) if station.get("logo") else None
    except ValueError:
        station["logo"] = None
    return station


def get_stations():
    """Stations (la station par défaut en premier), avec le nombre d'alarmes qui l'utilisent."""
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, (SELECT COUNT(*) FROM alarms a WHERE a.station_id = s.id) AS alarm_count
        FROM stations s
        ORDER BY s.is_default DESC, s.name
    """).fetchall()
    conn.close()
    return [_station(r) for r in rows]


def get_station(station_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM stations WHERE id = ?", (station_id,)).fetchone()
    conn.close()
    return _station(row) if row else None


def get_default_station():
    conn = get_db()
    row = conn.execute("SELECT * FROM stations WHERE is_default = 1 LIMIT 1").fetchone()
    conn.close()
    return _station(row) if row else None


def add_station(name, url, genre="", logo=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO stations (name, url, genre, logo) VALUES (?, ?, ?, ?)",
        (name, url, genre, json.dumps(logo) if logo else None)
    )
    conn.commit()
    conn.close()


def update_station(station_id, name, url, genre="", logo=None):
    conn = get_db()
    cur = conn.execute(
        "UPDATE stations SET name = ?, url = ?, genre = ?, logo = ? WHERE id = ?",
        (name, url, genre, json.dumps(logo) if logo else None, station_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def delete_station(station_id):
    """Supprime la station ; ses alarmes passent sur la station par défaut."""
    conn = get_db()
    fallback = conn.execute(
        "SELECT id FROM stations WHERE is_default = 1 AND id != ? LIMIT 1", (station_id,)
    ).fetchone()
    if fallback:
        conn.execute("UPDATE alarms SET station_id = ? WHERE station_id = ?", (fallback["id"], station_id))
    cur = conn.execute("DELETE FROM stations WHERE id = ?", (station_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def set_default_station(station_id):
    conn = get_db()
    conn.execute("UPDATE stations SET is_default = 0")
    conn.execute("UPDATE stations SET is_default = 1 WHERE id = ?", (station_id,))
    conn.commit()
    conn.close()


# === ALARMES ===

def get_alarms():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, s.name as station_name
        FROM alarms a
        LEFT JOIN stations s ON a.station_id = s.id
        ORDER BY a.time
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["days"] = json.loads(d["days"])
        result.append(d)
    return result


def add_alarm(time, days, station_id, label=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO alarms (time, days, station_id, label) VALUES (?, ?, ?, ?)",
        (time, json.dumps(days), station_id, label)
    )
    conn.commit()
    conn.close()


def update_alarm(alarm_id, time, days, station_id, label=""):
    conn = get_db()
    conn.execute(
        "UPDATE alarms SET time = ?, days = ?, station_id = ?, label = ? WHERE id = ?",
        (time, json.dumps(days), station_id, label, alarm_id)
    )
    conn.commit()
    changed = conn.total_changes
    conn.close()
    return changed > 0


def toggle_alarm(alarm_id, enabled):
    conn = get_db()
    conn.execute("UPDATE alarms SET enabled = ? WHERE id = ?", (1 if enabled else 0, alarm_id))
    conn.commit()
    conn.close()


def delete_alarm(alarm_id):
    conn = get_db()
    conn.execute("DELETE FROM alarms WHERE id = ?", (alarm_id,))
    conn.commit()
    conn.close()


def get_active_alarms_for_now(weekday_fr, current_time):
    """
    Retourne les alarmes actives pour le jour et l'heure actuels.
    weekday_fr : 'LU', 'MA', 'ME', 'JE', 'VE', 'SA', 'DI'
    current_time : 'HH:MM'
    """
    alarms = get_alarms()
    triggered = []
    for a in alarms:
        if a["enabled"] and a["time"] == current_time and weekday_fr in a["days"]:
            triggered.append(a)
    return triggered
