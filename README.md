# WakeUpClock

Radio-réveil connecté basé sur Raspberry Pi, avec afficheur RGB LED matrix
(branché via une Bonnet Adafruit) et audio déporté sur ESP32-S3 (USB Audio Class).

## Matériel

| Composant | Référence | Interface |
|---|---|---|
| SBC | Raspberry Pi 3B+ (validé) | — |
| Écran | RGB LED Matrix HUB75 64×32, pas 2,5mm (Waveshare) | Nappe HUB75 → Bonnet |
| Adaptateur écran | Adafruit RGB Matrix Bonnet (réf. 3211) | Header 40 broches du Pi |
| Alimentation écran | Mean Well LRS-50-5 ou LRS-75-5 (5V) | Secteur → bornier de la Bonnet |
| Audio | ESP32-S3 (USB Audio Class) + DAC I2S PCM5102A | USB (Pi ↔ ESP32), I2S (ESP32 ↔ DAC) |
| Volume | Encodeur rotatif KY-040 | GPIO 16/26/12 *(à réattribuer, voir Points ouverts)* |
| Bouton STOP | Poussoir | GPIO 5 *(à réattribuer)* |
| Bouton RADIO | Poussoir | GPIO 6 *(à réattribuer)* |
| Bouton SNOOZE | Poussoir | GPIO 13 *(à réattribuer)* |

> Un Raspberry Pi Zero 2W a aussi été utilisé pendant la mise au point, mais
> l'exemplaire testé présentait un défaut d'adressage (lignes du panneau
> manquantes, quel que soit le câblage). Le même panneau et la même Bonnet
> fonctionnent parfaitement sur le Pi 3B+.

## Architecture audio

L'audio ne passe plus par le Pi : le panneau RGB monopolise une grande partie des GPIO
(dont l'interface I2S, broches 18-21), donc le DAC audio est piloté par un ESP32-S3
séparé plutôt que par le Pi lui-même.

```
Pi (USB) → ESP32-S3 (USB Audio Class + I2S) → DAC PCM5102A → haut-parleur
```

Le Pi voit l'ESP32-S3 comme une carte son USB générique (ALSA) — aucune intégration
logicielle spécifique n'est nécessaire côté `radio.py`/MPD au-delà du choix du
périphérique de sortie.

## Connexion de l'écran (Bonnet Adafruit)

Aucun fil volant : la Bonnet s'emboîte sur le header 40 broches du Pi et intègre un
level shifter 3,3V → 5V (74AHCT245) ainsi que le connecteur HUB75.

1. Emboîter la Bonnet sur le header du Pi.
2. Brancher la nappe HUB75 de la Bonnet sur le port **IN** du panneau.
3. Raccorder l'alimentation 5V du panneau sur le bornier de la Bonnet (bloc secteur
   dédié, pas le 5V du Pi). Dans ce montage, aucune masse à relier séparément entre
   l'alimentation et le Pi (contrairement au câblage direct sans Bonnet).

Le pilotage utilise le mapping GPIO `adafruit-hat` de
[rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) :

| Signal | GPIO (BCM) |
|---|---|
| R1 / G1 / B1 | 5 / 13 / 6 |
| R2 / G2 / B2 | 12 / 16 / 23 |
| A / B / C / D / E | 22 / 26 / 27 / 20 / 24 |
| CLK / LAT / OE | 17 / 21 / 4 |

Réglages propres à ce panneau (dans `config.py`) :
- `RGB_MATRIX_RGB_SEQUENCE = "RBG"` : les canaux vert et bleu sont inversés sur ce modèle
- `RGB_MATRIX_GPIO_SLOWDOWN = 2` et `--led-no-hardware-pulse` (recommandation Waveshare)

## Stack logicielle

- **MPD + mpc** — lecture des flux radio, sortie vers l'ESP32-S3 (carte son USB)
- **Flask** — interface web de configuration
- **SQLite** — stockage alarmes et stations
- **rpi-rgb-led-matrix** ([fork](https://github.com/laurentChin/RGB-Matrix-Px-xx)) — pilotage du panneau, bindings Python compilés localement, polices bitmap BDF dans `fonts/`
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
├── fonts/            ← polices bitmap BDF pour le panneau
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
```

**Désactiver le son embarqué** (il utilise le même sous-système matériel que le panneau
et empêche la bibliothèque de fonctionner), puis redémarrer :

```bash
sudo sed -i 's/^dtparam=audio=on/dtparam=audio=off/' /boot/firmware/config.txt
echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
sudo reboot
```

```bash
# Environnement Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Bindings Python du panneau RGB (depuis le fork, pas via pip)
git clone https://github.com/laurentChin/RGB-Matrix-Px-xx.git
pip install ./RGB-Matrix-Px-xx/example/Rasberry-Pi

# Lancer en développement (accès GPIO/DMA : root requis)
sudo venv/bin/python app.py

# Installer le service systemd
sudo cp wakeupclock.service /etc/systemd/system/
sudo systemctl enable wakeupclock
sudo systemctl start wakeupclock
```

> Sur un Pi avec peu de RAM (Zero 2W : ~415 Mo utilisables), la compilation des
> bindings peut s'arrêter silencieusement par manque de mémoire. Ajouter un
> fichier de swap avant de relancer `pip install`.

## Diagnostic écran

```bash
# Test rapide du panneau (bibliothèque C++, hors venv Python)
cd RGB-Matrix-Px-xx/example/Rasberry-Pi/examples-api-use
make -j3
sudo ./demo -D3 --led-rows=32 --led-cols=64 --led-chain=1 \
  --led-slowdown-gpio=2 --led-no-hardware-pulse \
  --led-rgb-sequence=RBG --led-gpio-mapping=adafruit-hat
```

`-D3` dessine un cadre (haut rouge, bas jaune, gauche bleu, droite vert) et deux
diagonales (blanche et magenta) : les 32 lignes doivent toutes s'allumer.

## Points ouverts

- **Broches boutons/encodeur** : les valeurs de `config.py` (5, 6, 13, 16, 26, 12)
  sont utilisées par le mapping `adafruit-hat` (R1, B1, G1, G2, B, R2) et entrent en
  conflit avec la Bonnet. À réattribuer sur des GPIO libres accessibles.
- **Audio** : firmware USB Audio Class de l'ESP32-S3 et sélection de la sortie ALSA
  dans MPD à mettre en place.
