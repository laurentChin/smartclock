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
FLASK_HOST       = "0.0.0.0"
FLASK_PORT       = 5000
FLASK_DEBUG      = False

# === STATIONS PAR DÉFAUT ===
DEFAULT_STATIONS = [
    {
        "name":    "FIP",
        "url":     "https://icecast.radiofrance.fr/fip-midfi.mp3",
        "genre":   "Éclectique",
        "default": True,
    },
    {
        "name":    "France Inter",
        "url":     "https://icecast.radiofrance.fr/franceinter-midfi.mp3",
        "genre":   "Généraliste",
        "default": False,
    },
    {
        "name":    "France Info",
        "url":     "https://icecast.radiofrance.fr/franceinfo-midfi.mp3",
        "genre":   "Info",
        "default": False,
    },
    {
        "name":    "RTL2",
        "url":     "http://streaming.radio.rtl2.fr/rtl2-1-44-128",
        "genre":   "Rock/Pop",
        "default": False,
    },
    {
        "name":    "NRJ",
        "url":     "http://cdn.nrjaudio.fm/audio1/fr/30001/mp3_128.mp3",
        "genre":   "Pop/Dance",
        "default": False,
    },
    {
        "name":    "Jazz Radio",
        "url":     "http://jazz-wr02.ice.infomaniak.ch/jazz-wr02-128.mp3",
        "genre":   "Jazz",
        "default": False,
    },
]
