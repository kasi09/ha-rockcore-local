"""Sensors for the Rockcore micro inverter.

At night the inverter has no power and sends nothing. That is normal, not a
fault: power sensors then show 0 W (physically true, and the energy and
power-flow cards need a number), grid values become unknown, the energy
meter keeps its last value.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.util import dt as dt_util

from . import InverterConfigEntry
from .coordinator import InverterCoordinator, InverterState
from .entity import RockcoreEntity

M = SensorStateClass.MEASUREMENT


@dataclass(frozen=True, kw_only=True)
class RockcoreSensorDescription(SensorEntityDescription):
    kind: str                                  # frame kind the value comes from
    value_fn: Callable[[InverterState], float | None]
    zero_when_asleep: bool = False             # power: 0 W at night


def val(key: str) -> Callable[[InverterState], float | None]:
    return lambda s: s.values.get(key)


def current(n: int) -> Callable[[InverterState], float | None]:
    def calc(s: InverterState) -> float | None:
        p, u = s.values.get(f"pv{n}_power"), s.values.get(f"pv{n}_voltage")
        return round(p / u, 2) if p is not None and u else None
    return calc


def power(key: str, kind: str, **kw: Any) -> RockcoreSensorDescription:
    return RockcoreSensorDescription(
        key=key, kind=kind, device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT, state_class=M,
        suggested_display_precision=0, zero_when_asleep=True, value_fn=val(key), **kw,
    )


DESCRIPTIONS: tuple[RockcoreSensorDescription, ...] = (
    power("power", "power"),
    power("pv1_power", "channels"),
    power("pv2_power", "channels"),
    power("pv3_power", "channels", entity_registry_enabled_default=False),
    power("pv4_power", "channels", entity_registry_enabled_default=False),
    *(
        RockcoreSensorDescription(
            key=f"pv{n}_voltage", kind="channels", device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT, state_class=M,
            suggested_display_precision=1, value_fn=val(f"pv{n}_voltage"),
        )
        for n in (1, 2)
    ),
    *(
        # not transmitted - calculated like the RCMI app does: P / U
        RockcoreSensorDescription(
            key=f"pv{n}_current", kind="channels", device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, state_class=M,
            suggested_display_precision=2, zero_when_asleep=True, value_fn=current(n),
        )
        for n in (1, 2)
    ),
    RockcoreSensorDescription(
        key="grid_voltage", kind="channels", device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT, state_class=M,
        suggested_display_precision=0, value_fn=val("grid_voltage"),
    ),
    RockcoreSensorDescription(
        key="grid_frequency", kind="channels", device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ, state_class=M,
        suggested_display_precision=2, value_fn=val("grid_frequency"),
    ),
    RockcoreSensorDescription(
        key="temperature", kind="channels", device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=M,
        suggested_display_precision=0, value_fn=val("temperature"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InverterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(RockcoreSensor(coordinator, d) for d in DESCRIPTIONS),
            EnergyTotalSensor(coordinator),
            EnergyTodaySensor(coordinator),
            LastFrameSensor(coordinator),
        ]
    )


class RockcoreSensor(RockcoreEntity, SensorEntity):
    entity_description: RockcoreSensorDescription

    def __init__(self, coordinator: InverterCoordinator, description: RockcoreSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        d = self.entity_description
        if not self.coordinator.fresh(d.kind):
            return 0 if d.zero_when_asleep else None
        return d.value_fn(self.coordinator.state)


class EnergyTotalSensor(RockcoreEntity, RestoreSensor):
    """Lifetime energy from the inverter's own counter (every 5 minutes)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: InverterCoordinator) -> None:
        super().__init__(coordinator, "energy_total")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) and last.native_value is not None:
            self.coordinator.seed_energy(float(last.native_value))

    @property
    def native_value(self) -> float | None:
        return self.coordinator.state.energy_kwh


class TodayData(ExtraStoredData):
    """Day, baseline and last counter value, kept across restarts."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def as_dict(self) -> dict[str, Any]:
        return self._data


class EnergyTodaySensor(RockcoreEntity, RestoreSensor):
    """Today's yield, formed from the counter - the inverter knows no days."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: InverterCoordinator) -> None:
        super().__init__(coordinator, "energy_today")
        self._day: date | None = None
        self._baseline: float | None = None
        self._last_total: float | None = None
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_extra_data()) is not None:
            data = last.as_dict()
            self._day = date.fromisoformat(data["day"]) if data.get("day") else None
            self._baseline = data.get("baseline")
            self._last_total = data.get("last_total")
        self._recalculate()

    @property
    def extra_restore_state_data(self) -> TodayData:
        return TodayData({"day": self._day.isoformat() if self._day else None,
                          "baseline": self._baseline, "last_total": self._last_total})

    @property
    def last_reset(self) -> datetime:
        return dt_util.start_of_local_day()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._recalculate()
        super()._handle_coordinator_update()

    def _recalculate(self) -> None:
        total = self.coordinator.state.energy_kwh
        today = dt_util.now().date()
        if self._day != today:
            # the inverter sleeps over night: yesterday's last reading is
            # this morning's starting point
            self._baseline = self._last_total if self._last_total is not None else total
            self._day = today
        if total is not None:
            if self._baseline is None:
                self._baseline = total
            self._last_total = total
            self._attr_native_value = round(max(total - self._baseline, 0.0), 3)
        else:
            self._attr_native_value = 0.0


class LastFrameSensor(RockcoreEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: InverterCoordinator) -> None:
        super().__init__(coordinator, "last_frame")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.state.last_frame
