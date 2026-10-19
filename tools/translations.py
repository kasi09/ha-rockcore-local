#!/usr/bin/env python3
"""Generate strings.json and translations/{en,de}.json from one table.

    python3 tools/translations.py
"""
import json
import os

DEST = os.path.join(os.path.dirname(__file__), "..", "custom_components", "rockcore_local")

SENSOR = {
    "power": ("Power", "Leistung"),
    "pv1_power": ("PV1 power", "Leistung PV1"),
    "pv2_power": ("PV2 power", "Leistung PV2"),
    "pv3_power": ("PV3 power", "Leistung PV3"),
    "pv4_power": ("PV4 power", "Leistung PV4"),
    "pv1_voltage": ("PV1 voltage", "Spannung PV1"),
    "pv2_voltage": ("PV2 voltage", "Spannung PV2"),
    "pv1_current": ("PV1 current", "Strom PV1"),
    "pv2_current": ("PV2 current", "Strom PV2"),
    "grid_voltage": ("Grid voltage", "Netzspannung"),
    "grid_frequency": ("Grid frequency", "Netzfrequenz"),
    "temperature": ("Temperature", "Temperatur"),
    "energy_total": ("Total energy", "Energie gesamt"),
    "energy_today": ("Energy today", "Energie heute"),
    "last_frame": ("Last data", "Letzte Daten"),
}
BINARY = {"connected": ("Connection", "Verbindung")}


def build(i):
    t = lambda pair: pair[i]  # noqa: E731
    return {
        "config": {
            "step": {
                "user": {
                    "title": t(("Rockcore micro inverter", "Rockcore-Mikrowechselrichter")),
                    "description": t((
                        "Address of the inverter's WiFi module (found automatically if possible) and the port Home Assistant listens on. The inverter must be running - at night it has no power.",
                        "Adresse des WLAN-Moduls am Wechselrichter (wenn möglich automatisch gefunden) und der Port, auf dem Home Assistant lauscht. Der Wechselrichter muss laufen - nachts hat er keinen Strom.")),
                    "data": {"host": t(("Host", "Adresse")), "port": t(("Port", "Port"))},
                    "data_description": {
                        "host": t(("IP address of the WiFi module.", "IP-Adresse des WLAN-Moduls.")),
                        "port": t(("TCP port Home Assistant listens on for the module.", "TCP-Port, auf dem Home Assistant für das Modul lauscht.")),
                    },
                },
                "socket_b": {
                    "title": t(("Send data to Home Assistant", "Daten an Home Assistant senden")),
                    "description": t((
                        "The WiFi module can send a copy of the inverter data to Home Assistant on its second socket (socket B). The cloud connection and the RCMI app stay unchanged; the module restarts once.\n\nSocket B now: `{current}`\nNew target: `{target}`\nCommand: `{command}`\n\nWhen this integration is removed, the previous setting is restored.",
                        "Das WLAN-Modul kann über seinen zweiten Kanal (Socket B) eine Kopie der Wechselrichterdaten an Home Assistant schicken. Die Cloud-Verbindung und die RCMI-App bleiben unverändert; das Modul startet einmal neu.\n\nSocket B jetzt: `{current}`\nNeues Ziel: `{target}`\nBefehl: `{command}`\n\nWird diese Integration entfernt, wird die vorherige Einstellung wiederhergestellt.")),
                    "data": {"configure_socket_b": t(("Set socket B now", "Socket B jetzt einstellen"))},
                },
            },
            "error": {
                "cannot_connect": t(("The WiFi module does not answer. At night the inverter has no power - try again in daylight.",
                                     "Das WLAN-Modul antwortet nicht. Nachts hat der Wechselrichter keinen Strom - bitte bei Tageslicht erneut versuchen.")),
                "configure_failed": t(("The module did not accept the setting.", "Das Modul hat die Einstellung nicht übernommen.")),
            },
            "abort": {"already_configured": t(("This inverter is already configured.", "Dieser Wechselrichter ist bereits eingerichtet."))},
        },
        "entity": {
            "sensor": {k: {"name": t(v)} for k, v in SENSOR.items()},
            "binary_sensor": {k: {"name": t(v)} for k, v in BINARY.items()},
        },
        "exceptions": {
            "port_in_use": {"message": t(("Port {port} is already in use.", "Port {port} ist bereits belegt."))},
        },
    }


def write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    write(os.path.join(DEST, "strings.json"), build(0))
    write(os.path.join(DEST, "translations", "en.json"), build(0))
    write(os.path.join(DEST, "translations", "de.json"), build(1))
    print("written:", len(SENSOR) + len(BINARY), "entity names")
