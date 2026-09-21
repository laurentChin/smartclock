# config.py — constantes et configuration du projet WakeUpClock

# === ÉCRAN RGB LED MATRIX (HUB75, 64x32) ===
RGB_MATRIX_ROWS             = 32
RGB_MATRIX_COLS             = 64
RGB_MATRIX_CHAIN            = 1
RGB_MATRIX_PARALLEL         = 1
RGB_MATRIX_HARDWARE_MAPPING = "adafruit-hat"  # panneau branché via la Bonnet Adafruit
RGB_MATRIX_GPIO_SLOWDOWN    = 2
RGB_MATRIX_RGB_SEQUENCE     = "RBG"      # canaux G/B inversés sur ce modèle de panneau
RGB_MATRIX_BRIGHTNESS       = 50         # 0-100 : luminosité du contenu actif (réglage global du panneau)
RGB_MATRIX_BRIGHTNESS_SECONDARY = 25     # 0-100 : luminosité du contenu secondaire (obtenue en logiciel)

# Boutons et encodeur : branchés sur l'ESP32, broches définies dans firmware/src/main.cpp

# === RADIO / AUDIO (ESP32 en liaison série USB) ===
AUDIO_PORT       = "/dev/ttyUSB0"
AUDIO_BAUD       = 921600
RADIO_DURATION   = 3600     # durée mode radio 1h (secondes)
SNOOZE_DURATION  = 600      # durée snooze (secondes)
DEFAULT_VOLUME   = 50       # volume au démarrage (0-100)

# === BASE DE DONNÉES ===
DATABASE_PATH    = "wakeupclock.db"

# === SERVEUR WEB ===
FLASK_HOST       = "127.0.0.1"   # Flask n'écoute qu'en local : l'accès se fait en HTTPS par Caddy (deploy/Caddyfile)
FLASK_PORT       = 5000
FLASK_DEBUG      = False

# === ANIMATION DE L'HEURE ===
# Bascule des chiffres de l'heure quand ils changent : None (désactivée), "flip-mid", "flip-bottom" ou "flip-top"
# (ligne pivot de la bascule : milieu, base ou bord haut du chiffre). Retenu : "flip-mid".
TIME_ANIMATION      = "flip-mid"
TIME_ANIM_S         = 0.6     # durée de la bascule d'un chiffre (l'ancien se couche, le nouveau se relève)
TIME_ANIM_STAGGER_S = 0.06    # décalage entre deux chiffres qui changent ensemble (de droite à gauche)

# === LOGO DES STATIONS ===
# Côté (en pixels) de la grille de couleurs affichée à gauche du nom de la station.
LOGO_SIZE = 7

# Logo affiché quand une station n'en a pas : un émetteur radio (point central gris, ondes jaunes symétriques).
# Utilisé par le panneau et par la page Stations.
DEFAULT_LOGO = [
    [None, "#ffcc00", None, None, None, "#ffcc00", None],
    ["#ffcc00", None, None, None, None, None, "#ffcc00"],
    ["#ffcc00", None, None, None, None, None, "#ffcc00"],
    ["#ffcc00", None, "#ffcc00", "#8e8e93", "#ffcc00", None, "#ffcc00"],
    ["#ffcc00", None, None, None, None, None, "#ffcc00"],
    ["#ffcc00", None, None, None, None, None, "#ffcc00"],
    [None, "#ffcc00", None, None, None, "#ffcc00", None],
]

# === TEMPÉRATURE (NETATMO) ===
# Accès aux données de la pièce choisie dans l'interface web. Les identifiants sont saisis dans la page
# "Température" et enregistrés dans NETATMO_FILE (droits 600, hors dépôt) : ils ne sont jamais dans le code.
NETATMO_API_URL   = "https://api.netatmo.com"
NETATMO_FILE      = "netatmo.json"
NETATMO_POLL_S    = 300      # une lecture toutes les 5 minutes (l'API limite le nombre de requêtes)
NETATMO_STALE_S   = 1800     # au-delà de 30 minutes sans mesure, le panneau affiche "--"

# === STATIONS PAR DÉFAUT ===
# "logo" : grille LOGO_SIZE x LOGO_SIZE de couleurs "#rrggbb" (None = LED éteinte), affichée à gauche du nom.
# Réduits depuis les icônes carrées des stations (radiofrance.fr, franceinfo.fr) avec tools/pixelate_logo.py.
DEFAULT_STATIONS = [
    {
        "name":    "FIP",
        "url":     "https://icecast.radiofrance.fr/fip-midfi.mp3",
        "genre":   "Éclectique",
        "default": True,
        "logo":    [
            ["#e2007a", "#e2007a", "#e2007a", "#ffffff", "#ffffff", "#e2007a", "#e2007a"],
            ["#e2007a", "#e2007a", "#e2007a", "#ffffff", "#ffffff", "#e2007a", "#e2007a"],
            ["#e2007a", "#e2007a", "#e2007a", "#ffffff", "#ffffff", "#ffffff", "#e2007a"],
            ["#ffffff", "#ffffff", "#e2007a", "#e2007a", "#e2007a", "#ffffff", "#ffffff"],
            ["#ffffff", "#ffffff", "#e2007a", "#e2007a", "#e2007a", "#ffffff", "#ffffff"],
            ["#e2007a", "#ffffff", "#ffffff", "#ffffff", "#e2007a", "#e2007a", "#e2007a"],
            ["#e2007a", "#ffffff", "#ffffff", "#ffffff", "#e2007a", "#e2007a", "#e2007a"],
        ],
    },
    {
        "name":    "France Inter",
        "url":     "https://icecast.radiofrance.fr/franceinter-midfi.mp3",
        "genre":   "Généraliste",
        "default": False,
        "logo":    [
            ["#e20134", "#e20134", "#e20134", "#ffffff", "#ffffff", "#e20134", "#e20134"],
            ["#e20134", "#e20134", "#e20134", "#ffffff", "#ffffff", "#e20134", "#e20134"],
            ["#e20134", "#e20134", "#e20134", "#ffffff", "#ffffff", "#ffffff", "#e20134"],
            ["#ffffff", "#ffffff", "#e20134", "#e20134", "#e20134", "#ffffff", "#ffffff"],
            ["#ffffff", "#ffffff", "#e20134", "#e20134", "#e20134", "#ffffff", "#ffffff"],
            ["#e20134", "#ffffff", "#ffffff", "#ffffff", "#e20134", "#e20134", "#e20134"],
            ["#e20134", "#ffffff", "#ffffff", "#ffffff", "#e20134", "#e20134", "#e20134"],
        ],
    },
    {
        "name":    "France Info",
        "url":     "https://icecast.radiofrance.fr/franceinfo-midfi.mp3",
        "genre":   "Info",
        "default": False,
        "logo":    [
            ["#666666", "#666666", "#666666", "#666666", "#666666", "#666666", "#666666"],
            ["#666666", "#666666", "#666666", "#ffc300", "#666666", "#666666", "#666666"],
            ["#666666", "#666666", "#666666", "#ffc300", "#666666", "#666666", "#666666"],
            ["#666666", "#666666", "#666666", "#666666", "#666666", "#666666", "#666666"],
            ["#666666", "#666666", "#666666", "#ffc300", "#666666", "#666666", "#666666"],
            ["#666666", "#666666", "#666666", "#ffc300", "#666666", "#666666", "#666666"],
            ["#666666", "#666666", "#666666", "#666666", "#666666", "#666666", "#666666"],
        ],
    },
]
