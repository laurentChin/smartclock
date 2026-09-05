# WakeUpClock

Radio-réveil connecté basé sur Raspberry Pi Zero 2W, avec afficheur RGB LED matrix
et audio déporté sur ESP32-S3 (USB Audio Class).

## Matériel

| Composant | Référence | Interface |
|---|---|---|
| SBC | Raspberry Pi Zero 2W | — |
| Écran | RGB LED Matrix HUB75 64×32, pas 2,5mm (Waveshare) | GPIO direct (13 lignes) |
| Alimentation écran | Mean Well LRS-50-5 ou LRS-75-5 (5V) | Secteur → bornier |
| Audio | ESP32-S3 (USB Audio Class) + DAC I2S PCM5102A | USB (Pi ↔ ESP32), I2S (ESP32 ↔ DAC) |
| Volume | Encodeur rotatif KY-040 | GPIO 16/26/12 |
| Bouton STOP | Poussoir | GPIO 5 |
| Bouton RADIO | Poussoir | GPIO 6 |
| Bouton SNOOZE | Poussoir | GPIO 13 |

## Architecture audio

L'audio ne passe plus par le Pi : le panneau RGB occupe déjà la majorité des GPIO
disponibles (dont une partie de l'interface I2S), donc le DAC audio est piloté par
un ESP32-S3 séparé plutôt que par le Pi lui-même.

```
Pi (USB) → ESP32-S3 (USB Audio Class + I2S) → DAC PCM5102A → haut-parleur
```

Le Pi voit l'ESP32-S3 comme une carte son USB générique (ALSA) — aucune intégration
logicielle spécifique n'est nécessaire côté `radio.py`/MPD au-delà du choix du
périphérique de sortie.

## Câblage écran (HUB75 → Raspberry Pi)

Câblage direct broche à broche (pas d'adaptateur/HAT), mapping GPIO `regular` de
[rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix), **patché**
dans [le fork du projet](https://github.com/laurentChin/RGB-Matrix-Px-xx) pour
échanger les lignes A et D (contact plus fiable sur ce montage — voir
`example/Rasberry-Pi/lib/hardware-mapping.c`).

| Signal | GPIO Pi (BCM) | Broche physique Pi | Broche panneau |
|---|---|---|---|
| R1 | 11 | 23 | 16 |
| G1 | 27 | 13 | 15 |
| B1 | 7  | 26 | 14 |
| R2 | 8  | 24 | 12 |
| G2 | 9  | 21 | 11 |
| B2 | 10 | 19 | 10 |
| A  | 25 *(patché)* | 22 | 8 |
| B  | 23 | 16 | 7 |
| C  | 24 | 18 | 6 |
| D  | 22 *(patché)* | 15 | 5 |
| CLK | 17 | 11 | 4 |
| LAT | 4  | 7  | 3 |
| OE  | 18 | 12 | 2 |
| GND | —  | —  | 13, 1 |

**Alimentation** : bloc secteur 5V (Mean Well LRS-50-5 pour un seul panneau,
LRS-75-5 si extension prévue), avec **masse commune obligatoire** entre la sortie
GND de l'alimentation et une broche GND du Pi — sans ce lien, l'affichage ne
fonctionne pas de façon fiable.

## Stack logicielle

- **MPD + mpc** — lecture des flux radio, sortie vers l'ESP32-S3 (carte son USB)
- **Flask** — interface web de configuration
- **SQLite** — stockage alarmes et stations
- **rpi-rgb-led-matrix** ([fork patché](https://github.com/laurentChin/RGB-Matrix-Px-xx)) — pilotage du panneau RGB, bindings Python compilés localement
- **RPi.GPIO** — gestion GPIO (encodeur, boutons)
- **systemd** — démon au démarrage

## Structure

```
wakeupclock/
├── app.py            ← serveur Flask (interface web)
├── alarm.py          ← démon de surveillance des alarmes
├── radio.py          ← contrôle MPD
├── display.py        ← pilotage panneau RGB LED matrix (rgbmatrix)
├── gpio_handler.py   ← boutons + encodeur rotatif
├── config.py         ← constantes et configuration GPIO/panneau
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
sudo apt install mpd mpc python3-pip python3-venv python3-dev cmake cython3

# Environnement Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Bindings Python du panneau RGB (depuis le fork patché, pas via pip)
git clone git@github.com:laurentChin/RGB-Matrix-Px-xx.git
pip install ./RGB-Matrix-Px-xx/example/Rasberry-Pi

# Lancer en développement (accès GPIO/DMA : root requis)
sudo venv/bin/python app.py

# Installer le service systemd
sudo cp wakeupclock.service /etc/systemd/system/
sudo systemctl enable wakeupclock
sudo systemctl start wakeupclock
```

> Sur Raspberry Pi OS avec peu de RAM (Zero 2W), la compilation des bindings
> peut échouer silencieusement par manque de mémoire. Si `pip install` s'arrête
> sans erreur explicite, ajouter de la swap temporairement avant de relancer.

## Diagnostic écran

```bash
# Test rapide du panneau (bibliothèque C++, hors venv Python)
cd RGB-Matrix-Px-xx/example/Rasberry-Pi/examples-api-use
make -j4
sudo ./demo -D0 --led-rows=32 --led-cols=64 --led-chain=1 \
  --led-slowdown-gpio=2 --led-no-hardware-pulse --led-rgb-sequence=RBG
```
