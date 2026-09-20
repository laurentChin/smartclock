# WakeUpClock

Radio-réveil connecté basé sur Raspberry Pi, avec afficheur RGB LED matrix
(branché via une Bonnet Adafruit) et audio déporté sur un ESP32 (flux MP3 relayé par le port série USB).

## Matériel

| Composant | Référence | Interface |
|---|---|---|
| SBC | Raspberry Pi 3B+ (validé) | — |
| Écran | RGB LED Matrix HUB75 64×32, pas 2,5mm (Waveshare) | Nappe HUB75 → Bonnet |
| Adaptateur écran | Adafruit RGB Matrix Bonnet (réf. 3211) | Header 40 broches du Pi |
| Alimentation écran | Mean Well LRS-50-5 ou LRS-75-5 (5V) | Secteur → bornier de la Bonnet |
| Audio | ESP32-WROOM-32 (Elegoo DevKit V1) + ampli I2S MAX98357A + haut-parleur | USB série (Pi ↔ ESP32), I2S (ESP32 ↔ ampli) |
| Volume | Encodeur rotatif KY-040 | GPIO 16/26/12 *(à réattribuer, voir Points ouverts)* |
| Bouton STOP | Poussoir | GPIO 5 *(à réattribuer)* |
| Bouton RADIO | Poussoir | GPIO 6 *(à réattribuer)* |
| Bouton SNOOZE | Poussoir | GPIO 13 *(à réattribuer)* |

> Un Raspberry Pi Zero 2W a aussi été utilisé pendant la mise au point, mais
> l'exemplaire testé présentait un défaut d'adressage (lignes du panneau
> manquantes, quel que soit le câblage). Le même panneau et la même Bonnet
> fonctionnent parfaitement sur le Pi 3B+.

## Architecture audio

Le panneau RGB monopolise une grande partie des GPIO du Pi (dont l'I2S, broches 18-21) :
l'audio est donc joué par un ESP32 branché en USB sur le Pi. Ce n'est pas une carte son USB
(l'ESP32 classique n'a pas d'USB natif) : le Pi lui envoie le flux **MP3 compressé** par le
port série, et l'ESP32 le décode. Il n'utilise pas le Wi-Fi.

```
Internet ─(HTTP/HTTPS)→ Pi (audio_link.py) ─(USB série 921600 bauds)→ ESP32 (décodage MP3)
                                                        ─(I2S)→ MAX98357A → haut-parleur
```

- **Pi** (`audio_link.py`, classe `AudioLink`) : télécharge le flux, retire les métadonnées
  ICY (titre exposé par le callback `on_metadata`), envoie les octets en trames avec somme de
  contrôle, et respecte le contrôle de débit annoncé par l'ESP32.
- **ESP32** (`firmware/`, PlatformIO + [ESP8266Audio](https://github.com/earlephilhower/ESP8266Audio)) :
  tampon de 24 Ko, démarrage après 12 Ko préremplis, décodage MP3 mono vers l'I2S.
- Limite : seuls les flux **MP3** sont pris en charge (pas d'AAC).

Protocole (détail dans `firmware/src/main.cpp`) : trame Pi → ESP32
`0xA5 | type | longueur (2 octets) | charge utile | somme de contrôle`, types AUDIO, START,
STOP, VOLUME (0-100), PING ; l'ESP32 répond par des lignes texte (`BUF`, `STATE`, `PONG`…).

### Câblage ESP32 → MAX98357A

| MAX98357A | ESP32 (DevKit V1) |
|---|---|
| BCLK | GPIO 26 |
| LRC | GPIO 25 |
| DIN | GPIO 22 |
| VIN | VIN (5 V USB) |
| GND | GND |
| SD, GAIN | non connectés (mono G+D, gain 9 dB par défaut) |

Haut-parleur sur les bornes `+` / `-` de l'ampli. L'ESP32 est relié au Pi par son câble
USB (`/dev/ttyUSB0`).

### Firmware

```bash
cd firmware
pio run                                   # compilation
pio run -t upload                         # flash (voir la note ci-dessous)
```

> Avec pioarduino, l'envoi via `pio run -t upload` peut échouer (bug de barre de progression
> d'esptool). Contournement : appeler esptool directement avec `--no-progress` et flasher
> `.pio/build/esp32dev/firmware.factory.bin` à l'adresse `0x0`.

Test rapide depuis le Pi :

```python
from audio_link import AudioLink
link = AudioLink(on_metadata=print, on_event=print)
link.open()
link.set_volume(50)
link.play("https://icecast.radiofrance.fr/fip-midfi.mp3")
```

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

- **pyserial + requests** — relais du flux MP3 vers l'ESP32 (`audio_link.py`) ; titres Radio France via l'API `livemeta` (`livemeta.py`, non officielle, interrogée en fin de morceau/émission)
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
├── radio.py          ← lecture radio (AudioLink) et titres en cours
├── livemeta.py       ← titre en cours des radios Radio France
├── audio_link.py     ← relais du flux MP3 vers l'ESP32 (port série)
├── firmware/         ← firmware ESP32 (PlatformIO)
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
sudo apt install python3-pip python3-venv python3-dev cmake cython3
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
- **Audio** : `radio.py` utilise `AudioLink` (validé sur banc avec FIP et France Info) ; léger
  grésillement intermittent restant (pistes : APLL de l'ESP32, gain de l'ampli). Non testés :
  alarmes, RTL2/NRJ (format à vérifier, l'AAC n'est pas géré), titres ICY de Jazz Radio.
- **Boutons/encodeur** : prévus sur l'ESP32, avec remontée des événements au Pi par le même
  port série.
