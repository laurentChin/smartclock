#!/usr/bin/env python3
"""Enchaîne des scénarios d'affichage et d'audio pour relever la consommation réelle (dimensionnement du 5 V).

À lancer sur le Pi, service arrêté (il a besoin du panneau et du port série de l'ESP32) :

    sudo systemctl stop wakeupclock
    cd ~/smartclock && sudo ~/venv/bin/python tools/power_scenarios.py [--seconds 25] [--start-at HH:MM:SS] [--only LETTRES] [--max]
    sudo systemctl start wakeupclock

Avec --start-at, le script s'initialise puis attend cette heure pour démarrer : les scénarios ont ainsi des heures
prévisibles. Chaque scénario dure --seconds ; le script affiche l'heure de début et de fin. Relever le courant :
  - branche du panneau : sur l'alimentation du panneau (scénarios A à D, et E avec --max) ;
  - branche du Pi (Pi + ESP32 + ampli + haut-parleur) : avec un wattmètre USB entre le bloc et le Pi
    (scénarios F à I).
--only E,G… ne joue que les scénarios cités (--only E lance seulement le pire cas).
--max ajoute le pire cas du panneau : tout blanc à pleine luminosité pendant 10 s seulement (à ne lancer que si
l'alimentation du panneau supporte plusieurs ampères).
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from audio_link import AudioLink  # noqa: E402
from config import RGB_MATRIX_BRIGHTNESS  # noqa: E402
from display import display  # noqa: E402

RADIO_URL = "https://icecast.radiofrance.fr/franceinter-midfi.mp3"


def log(message):
    print(time.strftime("%H:%M:%S"), message, flush=True)


def white(brightness):
    """Tout le panneau en blanc, à la luminosité indiquée."""
    display.set_mode_off()
    display.matrix.brightness = brightness
    display.matrix.Fill(255, 255, 255)


def busy_screen():
    """Écran le plus chargé de l'interface : radio avec logo, alarme, température et indicateur de volume."""
    display.matrix.brightness = RGB_MATRIX_BRIGHTNESS
    display.set_alarms("07:30", 3, 1)
    display.set_temperature(23.4)
    display.set_mode_radio("France Inter", "Le grand face-a-face")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds", type=int, default=25, help="durée de chaque scénario")
    parser.add_argument("--start-at", help="heure de départ du premier scénario (HH:MM:SS, aujourd'hui)")
    parser.add_argument("--only", help="ne joue que ces scénarios (lettres, par exemple E ou A,B)")
    parser.add_argument("--max", action="store_true", help="ajoute le pire cas : tout blanc à pleine luminosité (10 s)")
    args = parser.parse_args()
    only = {letter.strip().upper() for letter in args.only.replace(",", " ").split()} if args.only else None

    display.start()
    link = AudioLink()
    link.open()

    if args.start_at:
        target = time.mktime(time.strptime(time.strftime("%Y-%m-%d ") + args.start_at, "%Y-%m-%d %H:%M:%S"))
        log(f"prêt, départ à {args.start_at}")
        while time.time() < target:
            time.sleep(0.2)

    def scenario(name, setup, seconds=args.seconds):
        if only and name[0] not in only:
            return
        log(f"DÉBUT {name}")
        setup()
        end = time.time() + seconds
        while time.time() < end:
            if display.mode == "radio":
                display.show_volume(100)         # garde l'indicateur de volume affiché
            time.sleep(1)
        log(f"FIN   {name}")

    def silent():
        link.stop()

    try:
        log("--- Branche du panneau (relever le courant sur l'alimentation du panneau) ---")
        scenario("A. panneau noir (balayage sans aucune LED allumée)", lambda: (silent(), display.set_mode_off(), display.matrix.Clear()))
        scenario("B. horloge seule (luminosité configurée)", lambda: (display.matrix.__setattr__("brightness", RGB_MATRIX_BRIGHTNESS), display.set_mode_clock()))
        scenario("C. écran le plus chargé (radio, alarme, température, volume)", busy_screen)
        scenario(f"D. tout blanc à la luminosité configurée ({RGB_MATRIX_BRIGHTNESS} %)", lambda: white(RGB_MATRIX_BRIGHTNESS))
        if args.max or (only and "E" in only):
            scenario("E. PIRE CAS : tout blanc à 100 %", lambda: white(100), seconds=10)

        log("--- Branche du Pi (relever le courant avec le wattmètre USB) ---")
        display.set_mode_off()
        display.matrix.brightness = RGB_MATRIX_BRIGHTNESS
        scenario("F. Pi au repos, panneau noir, sans audio", lambda: (silent(), display.matrix.Clear()))
        link.set_volume(50)
        scenario("G. radio à volume 50, panneau noir", lambda: (link.play(RADIO_URL), display.matrix.Clear()))
        scenario("H. radio à volume 50 + écran le plus chargé", lambda: busy_screen())
        link.set_volume(100)
        scenario("I. radio à volume 100 + écran le plus chargé (pire cas de la branche Pi)", lambda: None)
    finally:
        link.close()
        display.matrix.brightness = RGB_MATRIX_BRIGHTNESS
        display.stop()
        log("terminé")


if __name__ == "__main__":
    main()
