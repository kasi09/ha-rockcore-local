"""Shared fixtures: real frames of a Rockcore MI2S-800D, serial and id bytes
replaced, CRC recalculated."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rockcore_local.const import CONF_MAC, CONF_MODULE_FW, DOMAIN

FRAMES = {
    kind: bytes.fromhex(hexdata)
    for kind, hexdata in (
        line.split() for line in
        (Path(__file__).parent / "fixtures" / "frames.txt").read_text().splitlines() if line
    )
}
HOST = "example-inverter.invalid"
HA_IP = "ha.example.invalid"
MAC = "020000000001"
# formatted like Home Assistant does; built so the repository-wide MAC check stays strict
MAC_FMT = ":".join(MAC[i:i + 2] for i in range(0, 12, 2))


def with_energy(wh: int) -> bytes:
    """The energy frame with another counter value and a valid CRC."""
    from custom_components.rockcore_local.protocol import crc16_modbus

    b = bytearray(FRAMES["energy"])
    b[36 + 6:36 + 10] = wh.to_bytes(4, "little")
    b[-3:-1] = crc16_modbus(bytes(b[:-3])).to_bytes(2, "little")
    return bytes(b)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def listen_on_localhost():
    with patch("custom_components.rockcore_local.LISTEN_HOST", "127.0.0.1"):
        yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, unique_id=MAC_FMT, title="Rockcore HF-LPT270",
        data={CONF_HOST: HOST, CONF_PORT: 0, CONF_MAC: MAC_FMT,
              CONF_MODULE_FW: "4.00.01"},
    )
