"""Config flow: discovery, socket B only after confirmation, restore on removal."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.rockcore_local import module
from custom_components.rockcore_local.const import CONF_PREVIOUS_SOCKB, DOMAIN

from .conftest import HA_IP, HOST, MAC, MAC_FMT

INFO = module.ModuleInfo(HOST, MAC, "HF-LPT270")


def answers(sockb: str):
    return {"AT+VER": "+ok=4.00.01", "AT+SOCKB": f"+ok={sockb}"}


def patches(cmd):
    return (
        patch("custom_components.rockcore_local.config_flow.module.discover",
              AsyncMock(return_value=[INFO])),
        patch("custom_components.rockcore_local.config_flow.module.command", cmd),
        patch("custom_components.rockcore_local.config_flow.async_get_source_ip",
              AsyncMock(return_value=HA_IP)),
        patch("custom_components.rockcore_local.async_setup_entry", return_value=True),
    )


async def start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_already_pointing_to_ha(hass: HomeAssistant) -> None:
    cmd = AsyncMock(return_value=(INFO, answers(f"TCP,8899,{HA_IP}")))
    p = patches(cmd)
    with p[0], p[1], p[2], p[3]:
        result = await start(hass)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: 8899}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_PREVIOUS_SOCKB not in result["data"]
    assert result["result"].unique_id == MAC_FMT


async def test_socket_b_set_after_confirmation(hass: HomeAssistant) -> None:
    calls = []

    async def cmd(host, *commands, **kw):
        calls.append(commands)
        if commands and commands[0].startswith("AT+SOCKB="):
            return INFO, {commands[0]: "+ok", "AT+SOCKB": f"+ok=TCP,8899,{HA_IP}"}
        return INFO, answers("TCP,8899,old.example.invalid")

    p = patches(cmd)
    with p[0], p[1], p[2], p[3]:
        result = await start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: 8899}
        )
        assert result["step_id"] == "socket_b"
        assert result["description_placeholders"]["current"] == "TCP,8899,old.example.invalid"
        assert len(calls) == 1                          # nothing changed yet
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"configure_socket_b": True}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (f"AT+SOCKB=TCP,8899,{HA_IP}", "AT+SOCKB") in calls
    assert ("AT+Z",) in calls
    assert result["data"][CONF_PREVIOUS_SOCKB] == "TCP,8899,old.example.invalid"


async def test_declined_changes_nothing(hass: HomeAssistant) -> None:
    cmd = AsyncMock(return_value=(INFO, answers("NONE")))
    p = patches(cmd)
    with p[0], p[1], p[2], p[3]:
        result = await start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: 8899}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"configure_socket_b": False}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert cmd.await_count == 1
    assert CONF_PREVIOUS_SOCKB not in result["data"]


async def test_module_asleep(hass: HomeAssistant) -> None:
    cmd = AsyncMock(side_effect=module.ModuleError("no answer"))
    p = patches(cmd)
    with p[0], p[1], p[2], p[3]:
        result = await start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PORT: 8899}
        )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_removal_restores_socket_b(hass: HomeAssistant, config_entry) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, unique_id="x",
                            data={**config_entry.data, CONF_PREVIOUS_SOCKB: "TCP,8899,old.example.invalid"})
    entry.add_to_hass(hass)
    cmd = AsyncMock(return_value=(INFO, {}))
    with patch("custom_components.rockcore_local.module.command", cmd):
        await hass.config_entries.async_remove(entry.entry_id)
    cmd.assert_awaited_once_with(HOST, "AT+SOCKB=TCP,8899,old.example.invalid", "AT+Z")
