"""Connection of the WiFi module to Home Assistant."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import InverterConfigEntry
from .entity import RockcoreEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InverterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ConnectedSensor(entry.runtime_data)])


class ConnectedSensor(RockcoreEntity, BinarySensorEntity):
    """On while the module holds its socket B connection - off at night."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "connected")

    @property
    def is_on(self) -> bool:
        return self.coordinator.state.connected
