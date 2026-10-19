"""Rockcore micro inverter, read locally through socket B of its WiFi module.

The module keeps sending everything to the vendor cloud on socket A; socket B
sends a copy of the same bytes to this integration. Nothing is ever written
back, so the inverter and the RCMI app are unaffected.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from . import module
from .const import CONF_PREVIOUS_SOCKB, DOMAIN, LISTEN_HOST
from .coordinator import InverterCoordinator
from .server import InverterServer

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

type InverterConfigEntry = ConfigEntry[InverterCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: InverterConfigEntry) -> bool:
    coordinator = InverterCoordinator(hass, entry)
    server = InverterServer(
        LISTEN_HOST, entry.data[CONF_PORT], coordinator.handle_reading, coordinator.handle_connection
    )
    try:
        await server.start()
    except OSError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="port_in_use",
            translation_placeholders={"port": str(entry.data[CONF_PORT])},
        ) from err
    coordinator.server = server
    entry.runtime_data = coordinator
    entry.async_on_unload(server.stop)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InverterConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Leave the module as found: restore socket B if this integration changed
    it (best effort - at night the module has no power and cannot be reached)."""
    previous = entry.data.get(CONF_PREVIOUS_SOCKB)
    if previous is None:
        return
    try:
        await module.command(entry.data[CONF_HOST], f"AT+SOCKB={previous}", "AT+Z")
    except module.ModuleError:
        pass
