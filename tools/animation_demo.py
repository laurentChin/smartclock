#!/usr/bin/env python3
"""Montre sur le panneau les animations de bascule des chiffres de l'heure, sans attendre le changement de minute.

À lancer sur le Pi, service arrêté (il a besoin du panneau) :

    sudo systemctl stop wakeupclock
    cd ~/smartclock && sudo ~/venv/bin/python tools/animation_demo.py [--start-at HH:MM:SS] [--duration 0.6]
    sudo systemctl start wakeupclock

Pour chaque variante (flip-mid, flip-bottom, flip-top), l'heure imposée passe par des changements d'un, deux, trois
puis quatre chiffres : 12:41 -> 12:42 -> 12:59 -> 13:00 -> 09:59 -> 10:00. Chaque état reste affiché HOLD_S secondes.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import glyphs  # noqa: E402
from display import display  # noqa: E402

STATES = ["1241", "1242", "1259", "1300", "0959", "1000"]
FIRST_HOLD_S = 2.0
HOLD_S = 2.5
GAP_S = 1.5


def log(message):
    print(time.strftime("%H:%M:%S"), message, flush=True)


def wait_until(target):
    while time.time() < target:
        time.sleep(0.02)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-at", help="heure de départ (HH:MM:SS, aujourd'hui)")
    parser.add_argument("--duration", type=float, default=0.6, help="durée de la bascule d'un chiffre, en secondes")
    args = parser.parse_args()

    display.start()
    display.set_mode_clock()
    display.set_time_override(STATES[0])
    if args.start_at:
        log(f"prêt, départ à {args.start_at}")
        wait_until(time.mktime(time.strptime(time.strftime("%Y-%m-%d ") + args.start_at, "%Y-%m-%d %H:%M:%S")))

    try:
        for style in glyphs.ANIM_PIVOTS:
            display.set_time_animation(None)
            display.set_time_override(STATES[0])
            time.sleep(0.3)
            display.set_time_animation(style, args.duration)
            log(f"VARIANTE {style} : {STATES[0][:2]}:{STATES[0][2:]}")
            time.sleep(FIRST_HOLD_S)
            for previous, state in zip(STATES, STATES[1:]):
                changed = sum(a != b for a, b in zip(previous, state))
                display.set_time_override(state)
                log(f"  {state[:2]}:{state[2:]}  ({changed} chiffre{'s' if changed > 1 else ''} qui change{'nt' if changed > 1 else ''})")
                time.sleep(HOLD_S)
            time.sleep(GAP_S)
    finally:
        display.set_time_override(None)
        display.set_time_animation(None)
        display.stop()
        log("terminé")


if __name__ == "__main__":
    main()
