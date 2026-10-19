"""Holds the latest readings pushed by the inverter."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_MAC, DOMAIN, STALE, TICK
from .guard import MeterGuard
from .protocol import Reading

_LOGGER = logging.getLogger(__name__)


@dataclass
class InverterState:
    values: dict[str, Any] = field(default_factory=dict)
    received: dict[str, float] = field(default_factory=dict)   # kind -> monotonic
    last_frame: datetime | None = None
    connected: bool = False
    serial: str | None = None
    energy_kwh: float | None = None


class InverterCoordinator(DataUpdateCoordinator[InverterState]):
    """Push based; the periodic refresh only re-evaluates staleness."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name="inverter", update_interval=TICK)
        self.state = InverterState()
        self.energy_guard = MeterGuard()
        self.server: Any = None          # InverterServer, set in async_setup_entry
        self.data = self.state

    async def _async_update_data(self) -> InverterState:
        return self.state

    def fresh(self, kind: str) -> bool:
        seen = self.state.received.get(kind)
        return seen is not None and time.monotonic() - seen < STALE.total_seconds()

    def seed_energy(self, kwh: float) -> None:
        """Start the guard from the restored total, so that a bogus first
        frame after a restart cannot pull the meter down."""
        if self.energy_guard.last is None:
            self.energy_guard.check(kwh, "kWh", time.monotonic())
            self.state.energy_kwh = kwh

    @callback
    def handle_reading(self, reading: Reading) -> None:
        now = time.monotonic()
        state = self.state
        state.received[reading.kind] = now
        state.last_frame = dt_util.utcnow()
        values = dict(reading.values)
        if reading.kind == "energy":
            kwh = values.pop("energy_wh") / 1000
            state.energy_kwh = self.energy_guard.check(kwh, "kWh", now)
            state.received["power"] = now
        if reading.kind == "channels" and values.get("serial") != state.serial:
            state.serial = values["serial"]
            self._update_device()
        values.pop("serial", None)
        state.values.update(values)
        self.async_set_updated_data(state)

    @callback
    def handle_connection(self, connected: bool) -> None:
        self.state.connected = connected
        self.async_set_updated_data(self.state)

    def _update_device(self) -> None:
        reg = dr.async_get(self.hass)
        device = reg.async_get_device_by_identifier(
            (DOMAIN, self.config_entry.data[CONF_MAC]), self.config_entry.entry_id
        )
        if device:
            reg.async_update_device(device.id, serial_number=self.state.serial)
