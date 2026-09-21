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
| Alimentation du Pi | Bloc 5,1 V / 3 A, câble court et épais | micro-USB ; alimente aussi l'ESP32, l'ampli et le haut-parleur |
| Audio | ESP32-WROOM-32 (Elegoo DevKit V1) + ampli I2S MAX98357A + haut-parleur | USB série (Pi ↔ ESP32), I2S (ESP32 ↔ ampli) |
| Boutons | 3 poussoirs (principal, volume +, volume −) | GPIO 32 / 33 / 27 de l'ESP32, vers GND |

> **Alimentation du Pi** : le Pi alimente aussi l'ESP32, l'ampli et le haut-parleur (par USB).
> Un bloc trop faible fait chuter le 5 V quand le panneau et le son tournent, ce qui provoque un
> grésillement dans le haut-parleur (mesuré : environ 5 sous-tensions par 90 s avec l'ancien bloc,
> aucune avec un 5 V / 3 A). Vérification : `vcgencmd get_throttled` doit renvoyer `0x0` et
> `sudo dmesg | grep -i undervoltage` ne rien afficher.

> Un Raspberry Pi Zero 2W a aussi été utilisé pendant la mise au point, mais
> l'exemplaire testé présentait un défaut d'adressage (lignes du panneau
> manquantes, quel que soit le câblage). Le même panneau et la même Bonnet
> fonctionnent parfaitement sur le Pi 3B+.

## Alimentation du boîtier

**Mesures** (courant lu sur l'alimentation du panneau, 5 V) avec `tools/power_scenarios.py`, luminosité
configurée à 50 % :

| Scénario | Courant |
|---|---|
| Horloge seule | 0,092 A |
| Écran le plus chargé (radio, alarme, température, volume) | 0,104 A |
| Tout blanc à 50 % | 0,290 A |
| Tout blanc à 100 % (pire cas, 10 s) | 1,236 A |

La branche du Pi (Pi + ESP32 + ampli + haut-parleur) n'a pas été mesurée : les valeurs retenues sont les
valeurs publiées (Pi 3B+ : environ 1 A courant, 2,5 A en pointe ; ESP32 : 0,1 A ; MAX98357A : jusqu'à 3,2 W,
soit 0,8 A à fond).

**Budget** : environ 1,5 A en fonctionnement normal ; environ 3,7 A en cumulant tous les pires cas avec la
luminosité configurée ; environ 4,6 A si la luminosité montait à 100 %.

**Solution retenue pour le boîtier** : un adaptateur externe certifié **5 V / 5 A** (6 A si la luminosité
dépasse 50 %), sortie 5,0 à 5,2 V pour compenser la chute dans les fils, sur une prise DC 5,5 × 2,1 mm. Aucun
230 V à l'intérieur du boîtier. À l'intérieur, une distribution en étoile :
- fusible de 5 A (lame ATO, 32 V continu) et condensateur de 2200 µF au départ de la distribution ;
- trois branches courtes en fil épais (18 AWG environ) : le panneau (bornes de la Bonnet), le Pi (câble
  micro-USB coupé, pour garder son fusible et sa détection de sous-tension) et l'ESP32 avec l'ampli ;
- le câble USB entre le Pi et l'ESP32 ne transporte que les données (fil rouge coupé) pour éviter deux
  sources sur la même carte ;
- ne pas alimenter le Pi par la Bonnet : sa diode limite à 1 A
  ([forum Adafruit](https://forums.adafruit.com/viewtopic.php?t=180682)).

**Nomenclature** (références dont les caractéristiques ont été vérifiées sur les fiches des revendeurs ; les
fiches techniques elles-mêmes sont à relire avant commande) :

| Élément | Qté | Référence | Caractéristiques |
|---|---|---|---|
| Adaptateur secteur | 1 | Mean Well GST60A05-P1J | 5 V / 6 A (30 W), fiche DC 2,1 × 5,5 mm, centre positif, embase secteur C14 ([Farnell](https://cpc.farnell.com/mean-well/gst60a05-p1j/adaptor-ac-dc-5v-6a/dp/PW04637)) |
| Cordon secteur | 1 | cordon C13, fiche européenne, 3 × 0,75 mm², 1,5 m | générique |
| Embase DC | 1 | Switchcraft RAPC722X, ou toute embase à visser à **pivot de 2,1 mm et 5 A minimum** | RAPC722X : 2,1 mm, 5,5 mm extérieur, 5 A, à souder sur circuit imprimé ([Newark](https://www.newark.com/switchcraft-conxall/rapc722x/connector-dc-power-socket-5a/dp/65K7786)). Ne pas prendre les Switchcraft 712A ni RAPC712 : leur pivot est de 2,5 mm ([Newark](https://www.newark.com/switchcraft-conxall/712a/connector-dc-power-jack-5a/dp/37F2993)) |
| Fusible | 1 | Littelfuse 0287005.PXCN | lame ATO 5 A, 32 V ([Farnell](https://cpc.farnell.com/littelfuse/0287005-pxcn/fuse-atof-blade-5a/dp/FF02736)) |
| Porte-fusible | 1 | porte-fusible ATO en ligne, fil 16 AWG | générique |
| Condensateur | 1 | Panasonic EEU-FR1C222 | 2200 µF, 16 V, faible ESR, Ø 12,5 × 20 mm, 105 °C ([Farnell](https://uk.farnell.com/panasonic/eeufr1c222/cap-2200-f-16v-20/dp/1800641)) ; repère « − » côté masse |
| Bornes de distribution | 2 | WAGO 221-415 | 5 conducteurs, 24 à 12 AWG, 32 A ([Farnell](https://cpc.farnell.com/wago/221-415/compact-lever-connector-5-way/dp/CN20137)) ; un pour le +5 V, un pour la masse (arrivée, 3 branches, condensateur) |
| Fil | — | silicone 18 AWG rouge et noir (arrivée, panneau) ; 22 AWG (ESP32) | générique |
| Embouts de câblage | — | 0,75 mm² | bornes de la Bonnet et WAGO |
| Câble du Pi | 1 | micro-USB coupé, moins de 30 cm, fils d'alimentation de 20 AWG environ | garde le fusible et la détection de sous-tension du Pi |
| Câble de l'ESP32 | 1 | micro-USB données seules (ou fil rouge coupé) | l'alimentation vient de la distribution |
| Dissipateur | 1 | dissipateur pour Pi 3B+ (en option : ventilateur 5 V de 40 mm) | générique |

Avant de brancher : contrôler au multimètre l'absence de court-circuit entre +5 V et masse, monter le fusible en
dernier, puis relever la tension au niveau du Pi en charge (au moins 4,9 V).

**Thermique** : le processeur atteint environ 56 °C une minute après le démarrage, hors boîtier (limite
douce à 60 °C). Prévoir des aérations et un petit dissipateur.

**Vérification** : `vcgencmd get_throttled` doit renvoyer `0x0` (le bit `0x80000` seul signale la limite de
température) et `sudo dmesg | grep -i undervoltage` ne rien afficher.

**Coupures de courant** : déjà en place, le système en `noatime`, le swap en mémoire (zram), aucun journal
système persistant, SQLite en mode sûr (`synchronous=FULL`) et le fichier de jeton Netatmo écrit puis
synchronisé sur disque (`fsync`). Pour la version finale, un système en lecture seule (overlay) demandera une
partition de données séparée, à prévoir en fabriquant l'image de la carte.

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

Alarme en snooze : tant qu'une alarme est seulement reportée (et non arrêtée), la zone d'alarme du panneau
(les points et l'heure sous la date) clignote à 1 Hz et affiche l'heure de reprise à la place de la prochaine
alarme. Le clignotement cesse quand l'alarme reprend, ou quand on l'arrête (appui long ou
`POST /api/alarm/dismiss`).

Indicateur de volume (`display.py`, maquette Figma) : deux colonnes de 10 pixels à gauche du logo (x=1 et
x=2, lignes 19-28), soit 20 pixels à raison d'un pixel par pas de 5 % (comme les boutons de volume). Ils se
remplissent d'abord sur l'axe horizontal puis sur l'axe vertical : 5 % = en bas à gauche, 10 % = en bas à
droite, 15 % = à gauche de la ligne du dessus, et ainsi de suite jusqu'à 100 % (20 pixels). L'indicateur
s'affiche à chaque changement de volume (boutons ou interface web), quel que soit le mode d'affichage, et
disparaît 5 s après la dernière commande.

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

**Logo des stations** : chaque station a un logo de 7 × 7 pixels affiché à gauche de son nom sur le
panneau (à la radio, pendant une alarme et via le bouton), et un logo par défaut si elle n'en a pas.
Dans le formulaire d'une station, un petit éditeur permet de :
- colorier la grille (touche ou glisse ; couleur au choix, pastilles des couleurs déjà utilisées,
  gomme, « Tout effacer », « Annuler ») ;
- **réduire une image** (PNG, JPEG, SVG) : le navigateur la ramène en 7 × 7 en gardant des couleurs
  franches (couleur de fond, sauf si un motif couvre assez la case). Réglages : cadrage (image entière
  ou recadrée), zoom sur le centre (utile pour les icônes entourées de marge), détail du motif et
  éclaircissement des couleurs sombres. Le résultat reste retouchable pixel par pixel.

Les logos par défaut de FIP, France Inter et France Info viennent des icônes carrées des stations
(`radiofrance.fr/external/favicons/<station>/favicon.png`, `franceinfo.fr/icon.svg`). Le même travail se
fait en ligne de commande avec `tools/pixelate_logo.py` (options `--size`, `--fit`, `--margin`, `--threshold`,
`--lighten`, `--preview`). Le logo est stocké avec la station (colonne `logo`, JSON de 7 lignes de 7
couleurs `#rrggbb`, `null` = LED éteinte) et se règle aussi par l'API.

Le côté de la grille est `LOGO_SIZE` dans `config.py` (7) ; le panneau, l'API, la page et l'outil s'y
adaptent, et le texte de la station se place juste à droite du logo. Si `LOGO_SIZE` change, les logos
enregistrés à l'ancienne taille sont remplacés au démarrage : les stations par défaut retrouvent leur
logo, les autres reviennent au logo par défaut (`DEFAULT_LOGO`, un émetteur radio).

**Température** (`/temperature`) : affiche sur le panneau la température d'une pièce lue sur le hub Netatmo
(thermostat ou vannes connectées, API Energy `homesdata` / `homestatus`). La page permet de connecter le
compte, de choisir la pièce et montre la mesure en cours, la pièce et l'heure de la dernière lecture.
- **Connexion** : créer une application sur dev.netatmo.com (Mes applications), générer un jeton avec la
  portée `read_thermostat` (« Token generator »), puis saisir dans la page l'identifiant et le secret de
  l'application et le jeton de renouvellement. Le module `netatmo.py` les vérifie auprès de Netatmo avant de
  les enregistrer dans `netatmo.json` (droits 600, ignoré par git) ; ils ne sont jamais renvoyés par l'API ni
  écrits dans le code. Netatmo renvoie un nouveau jeton de renouvellement à chaque renouvellement du jeton
  d'accès (environ 3 h) : le dernier est toujours réécrit dans le fichier.
- **Lecture** : une mesure toutes les 5 minutes (`NETATMO_POLL_S`) ; au-delà de 30 minutes sans mesure
  (`NETATMO_STALE_S`) le panneau affiche « -- ».
- **Panneau** : zone de 9 × 5 pixels en (45, 24), avec les chiffres 3 × 5 de la date et de l'alarme (luminosité
  secondaire), alignés à droite, et un pixel de degré suspendu sur la 9e colonne, en haut. Couleur d'après la
  valeur arrondie : cyan sous 20 °, orange de 20 à 28 °, rouge au-delà. Zone vide tant que Netatmo n'est
  pas configuré ; « -- » en gris si la mesure est absente ou trop ancienne.

**Système** (`/system`) : redémarrer ou éteindre le Pi, après confirmation. La radio s'arrête
et l'écran s'éteint avant l'action ; après un redémarrage, la page attend le retour du serveur.
Un Pi éteint doit être débranché puis rebranché pour repartir.

> **Pas de mot de passe** : la protection repose sur le réseau (voir « Accès réservé au réseau
> local ») ; tout appareil connecté au même réseau peut modifier les alarmes et éteindre le Pi.

API (JSON) :

| Route | Rôle |
|---|---|
| `GET/POST /api/alarms` | lister / créer une alarme |
| `PUT/DELETE /api/alarms/<id>` | modifier / supprimer |
| `POST /api/alarms/<id>/toggle` | activer ou désactiver (`{"enabled": true}`) |
| `POST /api/alarm/snooze`, `/api/alarm/dismiss` | snooze / arrêt de l'alarme en cours |
| `POST /api/radio/play`, `/stop`, `/volume` | radio (`{"station_id": 1}`, `{"volume": 40}`) |
| `GET/POST /api/stations` | lister / créer une station (`name`, `url`, `genre`, `logo` facultatif) |
| `PUT/DELETE /api/stations/<id>` | modifier (sans clé `logo`, il est conservé ; `"logo": null` l'efface) / supprimer (409 pour la station par défaut) |
| `POST /api/stations/<id>/default` | définir la station par défaut |
| `GET /api/netatmo`, `DELETE /api/netatmo` | état (jamais de secret) / déconnecter et supprimer les identifiants |
| `PUT /api/netatmo/credentials` | connecter le compte (`client_id`, `client_secret`, `refresh_token`), vérifié avant enregistrement |
| `GET /api/netatmo/rooms`, `PUT /api/netatmo/room` | pièces du compte / choisir la pièce affichée (`home_id`, `room_id`) |
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

### Accès réservé au réseau local

Plutôt qu'un code, l'interface n'accepte que les appareils **du même réseau que le Pi** (`access.py`) :
le sous-réseau de l'une de ses interfaces (IPv4 comme IPv6, adresses publiques comprises : le préfixe
est relu chaque minute car un fournisseur peut le renuméroter), le lien local et le Pi lui-même.
Internet, un autre sous-réseau et le réseau invité de la box reçoivent une erreur 403. Flask utilise
l'adresse réelle du client transmise par Caddy (`X-Forwarded-For`, que Caddy écrase) ; ne pas exposer
le port 5000 autrement qu'en local. Le certificat racine (`/root.crt`, public) reste téléchargeable
en HTTP simple sur le port 80.

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
├── access.py         ← accès limité au réseau local
├── netatmo.py        ← température d'une pièce lue sur le hub Netatmo
├── config.py         ← constantes et configuration GPIO/panneau
├── database.py       ← accès SQLite (alarmes, stations)
├── netatmo.json      ← identifiants et pièce Netatmo (créé par la page Température, hors dépôt)
├── fonts/            ← polices bitmap BDF pour le panneau
├── tools/            ← outils (réduction d'un logo en grille de pixels, police du panneau)
├── wakeupclock.db    ← base SQLite (générée au premier lancement)
├── requirements.txt  ← dépendances Python
├── wakeupclock.service ← unit systemd
├── deploy/           ← Caddyfile (HTTPS) et réglages systemd (attente de l'heure)
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

**Alléger le Pi** (HDMI, Bluetooth et bureau sont inutiles : on l'utilise par SSH et par l'interface
web ; cela libère environ 100 Mo de mémoire et réduit la consommation), puis redémarrer :

```bash
sudo sed -i 's/^dtoverlay=vc4-kms-v3d$/dtoverlay=vc4-kms-v3d,nohdmi/' /boot/firmware/config.txt
echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt
sudo systemctl disable bluetooth
sudo systemctl set-default multi-user.target     # démarrage en mode texte, sans bureau
sudo systemctl disable lightdm
sudo reboot
```

Sur Raspberry Pi OS avec bureau, désinstaller ensuite les paquets du bureau libère environ 3 Go (Chromium,
Firefox, VLC, VNC, imageur, thème `rpd-*`, `labwc`, `lightdm`…). Toujours simuler avant
(`apt-get -s purge …`, puis `apt-get -s autoremove --purge`) et vérifier que Python, Caddy, avahi, SSH,
NetworkManager, le Wi-Fi, git, les compilateurs et cmake ne figurent pas dans la liste. Les environnements
Python du projet (`include-system-site-packages = false`) n'utilisent pas les paquets Python du système.

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

**Heure au démarrage** : le Pi n'a pas d'horloge interne, il démarre sur l'heure de sa dernière sauvegarde puis
saute à l'heure réelle une fois le réseau synchronisé. Sans précaution, une alarme peut alors être manquée ou
décalée après une coupure de courant, et Caddy peut servir un certificat daté d'une heure fausse (le HTTPS échoue
jusqu'à son renouvellement). Le réveil et Caddy attendent donc `time-sync.target` (déjà dans
`wakeupclock.service`), ce qui demande d'activer le service d'attente et de lui donner un délai maximum :

```bash
sudo mkdir -p /etc/systemd/system/systemd-time-wait-sync.service.d /etc/systemd/system/caddy.service.d
sudo cp deploy/time-wait-sync-timeout.conf /etc/systemd/system/systemd-time-wait-sync.service.d/timeout.conf
sudo cp deploy/caddy-wait-time.conf /etc/systemd/system/caddy.service.d/wait-time.conf
sudo systemctl enable systemd-time-wait-sync.service
sudo systemctl daemon-reload
```

Le réveil démarre alors environ 35 s après le Pi (temps de la synchronisation). Sans réseau, le délai maximum est de
120 s : il démarre ensuite quand même, sur l'heure non synchronisée. Vérification après un redémarrage :
`systemd-analyze critical-chain wakeupclock.service` doit montrer `systemd-time-wait-sync.service` avant lui, et
`journalctl -u wakeupclock -b` doit porter la date du jour. Un module horloge à pile (RTC DS3231, I2C) gardant l'heure
sans réseau reste possible pour la version finale.

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

- **Audio** : `radio.py` utilise `AudioLink` (validé sur banc avec FIP, France Inter et France Info). Le
  léger grésillement observé venait de l'alimentation du Pi (voir « Matériel »). Alarme (déclenchement,
  snooze, arrêt) validée sur banc. Flux MP3 uniquement (l'AAC n'est pas géré) ; les flux Radio France
  n'envoient pas de titre ICY, il vient de `livemeta`.
- **Boutons** : firmware, logique et lancement complet de `app.py` validés sur banc.
- **Température** : affichage sur le panneau et lecture Netatmo validés sur banc avec un vrai compte (API Energy :
  `homesdata` / `homestatus`, jeton de renouvellement avec la portée `read_thermostat`).
- **Interface web** : alarmes, stations, température et système faits. Le serveur est le serveur de
  développement de Flask, suffisant sur un réseau domestique.
- **Alimentation** : plan défini (voir « Alimentation du boîtier ») ; à réaliser dans le boîtier. La branche du
  Pi reste à mesurer avec un wattmètre USB si l'on veut affiner la marge.
- **Figma** : la maquette a la zone température et les deux colonnes de volume, mais le clignotement du snooze et
  une frame de référence des logos 7 × 7 restent à y ajouter, et le remplissage du volume y est à confronter au code.
