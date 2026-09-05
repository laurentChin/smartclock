# WakeUpClock

Radio-réveil connecté basé sur Raspberry Pi Zero 2W.

## Matériel

| Composant | Référence | Interface |
|---|---|---|
| SBC | Raspberry Pi Zero 2W | — |
| Écran | OLED 128×32 SSD1306 (A1-XSMK-EK) | I2C 0x3C |
| Audio | DAC I2S PCM5102A | I2S |
| Volume | Encodeur rotatif KY-040 | GPIO 23/24 |
| Bouton STOP | Poussoir | GPIO 17 |
| Bouton RADIO | Poussoir | GPIO 27 |
| Bouton SNOOZE | Poussoir | GPIO 22 |

## Pinout I2C (OLED)

```
OLED GND → Pi Pin 6  (GND)
OLED VCC → Pi Pin 1  (3.3V)
OLED SCL → Pi Pin 5  (GPIO 3)
OLED SDA → Pi Pin 3  (GPIO 2)
```

## Stack logicielle

- **MPD + mpc** — lecture des flux radio
- **Flask** — interface web de configuration
- **SQLite** — stockage alarmes et stations
- **luma.oled** — pilotage écran SSD1306
- **pigpio** — gestion GPIO (encodeur, boutons)
- **systemd** — démon au démarrage

## Structure

```
wakeupclock/
├── app.py            ← serveur Flask (interface web)
├── alarm.py          ← démon de surveillance des alarmes
├── radio.py          ← contrôle MPD
├── display.py        ← pilotage écran OLED
├── gpio_handler.py   ← boutons + encodeur rotatif
├── config.py         ← constantes et configuration GPIO
├── database.py       ← accès SQLite (alarmes, stations)
├── wakeupclock.db    ← base SQLite (générée au premier lancement)
├── requirements.txt  ← dépendances Python
├── wakeupclock.service ← unit systemd
├── templates/
│   └── index.html    ← interface web
└── static/
    ├── css/style.css
    └── js/app.js
```

## Installation

```bash
# Dépendances système
sudo apt install mpd mpc i2c-tools python3-pip python3-venv

# Activer I2C
sudo raspi-config  # Interface Options → I2C → Yes

# Environnement Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Lancer en développement
python app.py

# Installer le service systemd
sudo cp wakeupclock.service /etc/systemd/system/
sudo systemctl enable wakeupclock
sudo systemctl start wakeupclock
```

## Diagnostic écran

```bash
# Vérifier que l'écran est détecté
i2cdetect -y 1   # doit afficher 3c
```
