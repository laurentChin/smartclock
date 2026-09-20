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
| Boutons | 3 poussoirs (principal, volume +, volume −) | GPIO 32 / 33 / 27 de l'ESP32, vers GND |

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

### Câblage des boutons (ESP32)

| Bouton | Broche ESP32 |
|---|---|
| Principal (radio / stop / snooze) | GPIO 32 → GND |
| Volume + | GPIO 33 → GND |
| Volume − | GPIO 27 → GND |

Résistances de rappel internes, pas de composant externe. Sur un poussoir à 4 broches, brancher
deux broches **en diagonale** (les broches voisines sont reliées entre elles). Les trois GND
peuvent partager un rail de breadboard relié à une broche GND de l'ESP32.

Comportement (décidé côté Pi dans `controls.py`) :
- **Bouton principal, appui court** : alarme en cours → snooze ; radio allumée → stop ;
  sinon → radio par défaut pendant 1 h.
- **Bouton principal, appui long (1 s)** : arrêt définitif (radio, alarme, snooze en attente).
- **Volume ± ** : pas de 5 %, répété toutes les 150 ms si le bouton est maintenu.

Indicateur de volume (`display.py`, maquette Figma) : colonne de 10 pixels à gauche du logo
(x=2, lignes 19-28), remplie depuis le bas, un pixel par tranche de 10 % (donc mise à jour
tous les deux pas de 5 %). Elle s'affiche à chaque changement de volume (boutons ou interface
web), quel que soit le mode d'affichage, et disparaît 5 s après la dernière commande.

Les appuis sont envoyés par le même port série (`BTN main`, `BTN main_long`, `BTN vol_up`,
`BTN vol_down`).

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

## Interface web

Le serveur Flask (`app.py`) démarre avec le Pi (service systemd, voir Installation) et sert
les pages sur **`https://smartclock.local`** (voir « Accès HTTPS »). Une navigation en haut relie les trois pages
(`templates/base.html`), pensées pour le téléphone, en thèmes clair et sombre automatiques.

**Alarmes** (`/`, `templates/index.html`) : liste avec heure, jours, station et nom ;
interrupteur activer/désactiver ; ajout et modification dans un formulaire (heure, jours avec
raccourcis Semaine / Week-end / Tous les jours, station, nom facultatif) ; suppression depuis
la modification.

**Stations** (`/stations`) : liste avec genre, serveur, nombre d'alarmes qui l'utilisent et badge
« Par défaut » ; ajout, modification (nom, adresse, genre, station par défaut) et suppression.
À l'ajout ou au changement d'adresse, le serveur vérifie que le flux répond en MP3 (seul format
lu par l'ESP32) et refuse une page web ou un flux injoignable. La station par défaut ne peut pas
être supprimée (en choisir une autre d'abord) ; à la suppression d'une station, ses alarmes
passent sur la station par défaut.

**Système** (`/system`) : redémarrer ou éteindre le Pi, après confirmation. La radio s'arrête
et l'écran s'éteint avant l'action ; après un redémarrage, la page attend le retour du serveur.
Un Pi éteint doit être débranché puis rebranché pour repartir.

> **Pas d'authentification** : toute personne qui accède au réseau local peut modifier les
> alarmes et les stations, et redémarrer ou éteindre le Pi. À réserver à un réseau de confiance.

Le panneau LED suit les alarmes : un point par alarme active, la prochaine en couleur vive, et son
heure (mis à jour à chaque changement et toutes les 15 s).

API (JSON) :

| Route | Rôle |
|---|---|
| `GET/POST /api/alarms` | lister / créer une alarme |
| `PUT/DELETE /api/alarms/<id>` | modifier / supprimer |
| `POST /api/alarms/<id>/toggle` | activer ou désactiver (`{"enabled": true}`) |
| `POST /api/alarm/snooze`, `/api/alarm/dismiss` | snooze / arrêt de l'alarme en cours |
| `POST /api/radio/play`, `/stop`, `/volume` | radio (`{"station_id": 1}`, `{"volume": 40}`) |
| `GET/POST /api/stations` | lister / créer une station (`name`, `url`, `genre`) |
| `PUT/DELETE /api/stations/<id>` | modifier / supprimer (409 pour la station par défaut) |
| `POST /api/stations/<id>/default` | définir la station par défaut |
| `POST /api/system/reboot`, `/api/system/shutdown` | redémarrer / éteindre le Pi (corps JSON `{}`) |

Une alarme demande une heure `HH:MM`, au moins un jour (`LU`…`DI`) et une station existante ;
sinon l'API répond 400 avec un message. Une station demande un nom, une adresse `http(s)://`
et un flux MP3 joignable.

## Accès HTTPS (`smartclock.local`)

Le Pi s'appelle `smartclock` et annonce `smartclock.local` sur le réseau local (mDNS/avahi,
installé par défaut) : l'adresse reste valable si son IP change. Flask n'écoute qu'en local
(`FLASK_HOST = "127.0.0.1"`) ; [Caddy](https://caddyserver.com) reçoit les connexions et les
transmet à Flask (`deploy/Caddyfile`). `http://smartclock.local` redirige vers HTTPS.

Un nom en `.local` ne peut pas avoir de certificat public : Caddy crée sa propre autorité de
certification (nommée « SmartClock ») et signe le certificat du site, renouvelé automatiquement.
Le certificat racine doit être installé **une fois sur chaque appareil**, sinon le navigateur
affiche un avertissement :

- **Récupérer le certificat** : `http://smartclock.local/root.crt` (servi en HTTP simple).
- **Mac** : ouvrir le fichier (Trousseau d'accès), double-clic sur « SmartClock », Approbation →
  « Toujours approuver ». Firefox utilise son propre magasin de certificats.
- **iPhone** : ouvrir `http://smartclock.local/root.crt` dans Safari, autoriser, installer le profil
  (Réglages), puis Réglages → Général → Informations → Réglages des certificats de confiance →
  activer « SmartClock ».

Si le dossier de données de Caddy (`/var/lib/caddy`) est supprimé, l'autorité est recréée avec une
nouvelle clé : le certificat racine est alors à réinstaller sur les appareils.

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
├── controls.py       ← actions des boutons (reçus de l'ESP32)
├── config.py         ← constantes et configuration GPIO/panneau
├── database.py       ← accès SQLite (alarmes, stations)
├── fonts/            ← polices bitmap BDF pour le panneau
├── wakeupclock.db    ← base SQLite (générée au premier lancement)
├── requirements.txt  ← dépendances Python
├── wakeupclock.service ← unit systemd
├── deploy/Caddyfile  ← HTTPS local (Caddy)
├── templates/        ← pages : base, alarmes (index), stations, système
└── static/
    ├── css/style.css
    └── js/           ← common.js (partagé), app.js (alarmes), stations.js, system.js
```

## Installation

```bash
# Dépendances système
sudo apt install python3-pip python3-venv python3-dev cmake cython3 caddy
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

# Nom et HTTPS : hostname smartclock (=> smartclock.local) et Caddy (voir « Accès HTTPS »)
sudo hostnamectl set-hostname smartclock
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy

# Installer le service systemd (adapter User/WorkingDirectory/ExecStart de wakeupclock.service
# à l'emplacement du projet et du venv ; le service tourne en root pour piloter le panneau)
sudo cp wakeupclock.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wakeupclock
journalctl -u wakeupclock -f      # messages en direct
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

- **Audio** : `radio.py` utilise `AudioLink` (validé sur banc avec FIP et France Info) ; léger
  grésillement intermittent restant (pistes : APLL de l'ESP32, gain de l'ampli). Alarme (déclenchement,
  snooze, arrêt) validée sur banc. Flux MP3 uniquement (l'AAC n'est pas géré) ; les flux Radio France
  n'envoient pas de titre ICY, il vient de `livemeta`.
- **Boutons** : firmware, logique et lancement complet de `app.py` validés sur banc.
- **Interface web** : alarmes, stations et système faits. Restent la radio (lecture, volume, station
  en cours) et l'alarme en cours (snooze / arrêt) dans la page, dont les routes API existent déjà.
  Le serveur est le serveur de développement de Flask, suffisant sur un réseau domestique.
