"""Base entity for the Rockcore integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, CONF_MODULE_FW, DOMAIN
from .coordinator import InverterCoordinator


class RockcoreEntity(CoordinatorEntity[InverterCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: InverterCoordinator, key: str) -> None:
        super().__init__(coordinator)
        data = coordinator.config_entry.data
        self._attr_unique_id = f"{data[CONF_MAC]}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data[CONF_MAC])},
            connections={(CONNECTION_NETWORK_MAC, data[CONF_MAC])},
            manufacturer="Rockcore",
            model="Micro inverter",
            sw_version=data.get(CONF_MODULE_FW),
            configuration_url=f"http://{data[CONF_HOST]}",
        )
