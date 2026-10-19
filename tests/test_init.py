"""Receiving frames over a real TCP connection, night behaviour, energy."""

import asyncio
import time

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.rockcore_local.const import DOMAIN

from .conftest import FRAMES, MAC_FMT, with_energy

# real TCP connections to 127.0.0.1
pytestmark = pytest.mark.usefixtures("socket_enabled")


async def setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


def st(hass, key, domain="sensor"):
    eid = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{MAC_FMT}_{key}")
    assert eid, key
    return hass.states.get(eid)


async def send(hass, coordinator, *frames, chunk: int = 11):
    _reader, writer = await asyncio.open_connection("127.0.0.1", coordinator.server.port)
    data = b"".join(frames)
    for i in range(0, len(data), chunk):
        writer.write(data[i:i + chunk])
        await writer.drain()
    for _ in range(50):
        await asyncio.sleep(0.01)
        await hass.async_block_till_done()
    return writer


async def test_frames_become_sensors(hass: HomeAssistant, config_entry) -> None:
    c = await setup(hass, config_entry)
    writer = await send(hass, c, FRAMES["channels"], FRAMES["power"], FRAMES["energy"])
    assert float(st(hass, "power").state) == 683.0
    assert float(st(hass, "pv1_power").state) == 21
    assert float(st(hass, "pv1_voltage").state) == 33.0
    assert float(st(hass, "pv1_current").state) == round(21 / 33.0, 2)
    assert float(st(hass, "grid_frequency").state) == 50.04
    s = st(hass, "energy_total")
    assert float(s.state) == 636.156
    assert s.attributes["state_class"] == "total_increasing"
    assert float(st(hass, "energy_today").state) == 0.0
    assert st(hass, "connected", "binary_sensor").state == "on"
    writer.close()
    await writer.wait_closed()
    for _ in range(20):
        await asyncio.sleep(0.01)
        await hass.async_block_till_done()
    assert st(hass, "connected", "binary_sensor").state == "off"


async def test_night_power_zero_counter_kept(hass, config_entry) -> None:
    c = await setup(hass, config_entry)
    await send(hass, c, FRAMES["channels"], FRAMES["power"], FRAMES["energy"])
    for kind in c.state.received:                     # last frames an hour ago
        c.state.received[kind] = time.monotonic() - 3600
    c.async_update_listeners()
    await hass.async_block_till_done()
    assert float(st(hass, "power").state) == 0
    assert float(st(hass, "pv1_current").state) == 0
    assert st(hass, "grid_voltage").state == "unknown"
    assert float(st(hass, "energy_total").state) == 636.156


async def test_energy_guard_and_today(hass, config_entry) -> None:
    c = await setup(hass, config_entry)
    await send(hass, c, FRAMES["energy"])
    c.energy_guard.last_time -= 300                      # counter frames come every 5 min
    await send(hass, c, with_energy(636256))             # +100 Wh
    assert float(st(hass, "energy_today").state) == 0.1
    await send(hass, c, with_energy(0))                  # glitch / reset to 0
    assert float(st(hass, "energy_total").state) == 636.256
    c.energy_guard.last_time -= 300
    await send(hass, c, with_energy(99_000_000))         # impossible jump
    assert float(st(hass, "energy_total").state) == 636.256


async def test_unload_closes_port(hass, config_entry) -> None:
    c = await setup(hass, config_entry)
    port = c.server.port
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    try:
        _r, w = await asyncio.open_connection("127.0.0.1", port)
        w.close()
        raise AssertionError("port still open")
    except OSError:
        pass
