# access.py — l'interface web n'est accessible que depuis le réseau local du Pi
#
# Un client est accepté s'il est sur un réseau directement relié au Pi : le sous-réseau de l'une de
# ses interfaces (IPv4 ou IPv6, adresses publiques comprises, le préfixe étant relu régulièrement
# car un fournisseur peut le renuméroter), le lien local, ou le Pi lui-même. Tout le reste
# (Internet, autre sous-réseau, réseau invité de la box) est refusé.

import ipaddress
import json
import subprocess
import time

REFRESH_S = 60
_cache = {"at": 0.0, "networks": None}


def _interface_networks():
    """Sous-réseaux des interfaces du Pi (None si `ip` est indisponible)."""
    try:
        out = subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True, timeout=3, check=True).stdout
        networks = []
        for iface in json.loads(out):
            if iface.get("ifname") == "lo":
                continue
            for info in iface.get("addr_info", []):
                networks.append(ipaddress.ip_network(f"{info['local']}/{info['prefixlen']}", strict=False))
        return networks
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return None


def local_networks():
    now = time.monotonic()
    if _cache["networks"] is None or now - _cache["at"] > REFRESH_S:
        _cache.update(at=now, networks=_interface_networks() or [])
    return _cache["networks"]


def is_local(address):
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip.is_loopback or ip.is_link_local:
        return True
    networks = local_networks()
    if not networks:                # `ip` indisponible (poste de développement) : réseaux privés seulement
        return ip.is_private
    return any(ip in network for network in networks)
