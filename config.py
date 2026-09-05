# config.py — constantes et configuration du projet WakeUpClock

# === ÉCRAN RGB LED MATRIX (HUB75, 64x32) ===
RGB_MATRIX_ROWS             = 32
RGB_MATRIX_COLS             = 64
RGB_MATRIX_CHAIN            = 1
RGB_MATRIX_PARALLEL         = 1
RGB_MATRIX_HARDWARE_MAPPING = "regular"  # mapping GPIO patché A/D dans le fork RGB-Matrix-Px-xx
RGB_MATRIX_GPIO_SLOWDOWN    = 2
RGB_MATRIX_RGB_SEQUENCE     = "RBG"      # canaux G/B inversés sur ce modèle de panneau
RGB_MATRIX_BRIGHTNESS       = 60         # 0-100

# === GPIO (numérotation BCM) ===
# Boutons/encodeur relogés hors des broches utilisées par le panneau RGB
# (mapping "regular" : 4,7,8,9,10,11,15,17,18,22,23,24,25,27) et hors I2S
# (18,19,20,21, réservées si un DAC audio est ajouté plus tard).
PIN_BTN_STOP     = 5    # bouton arrêt radio / snooze
PIN_BTN_RADIO    = 6    # bouton radio 1h
PIN_BTN_SNOOZE   = 13   # bouton snooze alarme
PIN_ENC_CLK      = 16   # encodeur rotatif — CLK
PIN_ENC_DT       = 26   # encodeur rotatif — DT
PIN_ENC_SW       = 12   # encodeur rotatif — bouton poussoir

# === RADIO / MPD ===
MPD_HOST         = "localhost"
MPD_PORT         = 6600
RADIO_DURATION   = 3600     # durée mode radio 1h (secondes)
SNOOZE_DURATION  = 600      # durée snooze (secondes)
DEFAULT_VOLUME   = 65       # volume au démarrage (0-100)

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
