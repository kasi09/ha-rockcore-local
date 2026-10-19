"""Diagnostics for the Rockcore integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import InverterConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InverterConfigEntry
) -> dict[str, Any]:
    c = entry.runtime_data
    s = c.state
    return {
        "entry": dict(entry.data),
        "listening_port": c.server.port,
        "connected": s.connected,
        "serial": s.serial,
        "last_frame": s.last_frame.isoformat() if s.last_frame else None,
        "values": s.values,
        "energy_kwh": s.energy_kwh,
        "fresh": {k: c.fresh(k) for k in ("channels", "power", "energy")},
        "energy_guard_rejections": c.energy_guard.rejected,
    }
