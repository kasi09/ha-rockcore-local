"""Config flow: find the WiFi module and point its socket B to Home Assistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.network import async_get_source_ip
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import format_mac

from . import module
from .const import CONF_MAC, CONF_MODULE_FW, CONF_PREVIOUS_SOCKB, DEFAULT_PORT, DOMAIN

CONF_CONFIGURE = "configure_socket_b"


class RockcoreConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a Rockcore micro inverter."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._title = ""
        self._ha_ip = ""
        self._current = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST], user_input[CONF_PORT]
            try:
                info, answers = await module.command(host, "AT+VER", "AT+SOCKB")
            except module.ModuleError:
                errors["base"] = "cannot_connect"
            else:
                mac = format_mac(info.mac)
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                self._ha_ip = await async_get_source_ip(self.hass, target_ip=host)
                self._current = module.answer_value(answers["AT+SOCKB"]) or ""
                self._title = f"Rockcore {info.model}"
                self._data = {
                    CONF_HOST: host, CONF_PORT: port, CONF_MAC: mac,
                    CONF_MODULE_FW: module.answer_value(answers["AT+VER"]),
                }
                if module.socket_b_target(self._current) == (self._ha_ip, port):
                    return self.async_create_entry(title=self._title, data=self._data)
                return await self.async_step_socket_b()

        suggested = user_input or {}
        if not suggested:
            found = await module.discover()
            if found:
                suggested = {CONF_HOST: found[0].ip}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1024, max=65535)
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

    async def async_step_socket_b(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain the change and do it only after confirmation."""
        errors: dict[str, str] = {}
        target = f"TCP,{self._data[CONF_PORT]},{self._ha_ip}"
        if user_input is not None:
            if not user_input[CONF_CONFIGURE]:
                return self.async_create_entry(title=self._title, data=self._data)
            try:
                _info, answers = await module.command(
                    self._data[CONF_HOST], f"AT+SOCKB={target}", "AT+SOCKB"
                )
                if module.socket_b_target(module.answer_value(answers["AT+SOCKB"])) != (
                    self._ha_ip, self._data[CONF_PORT]
                ):
                    raise module.ModuleError("socket B not accepted")
                await module.command(self._data[CONF_HOST], "AT+Z")    # restart module
            except module.ModuleError:
                errors["base"] = "configure_failed"
            else:
                return self.async_create_entry(
                    title=self._title,
                    data={**self._data, CONF_PREVIOUS_SOCKB: self._current or "NONE"},
                )
        return self.async_show_form(
            step_id="socket_b",
            data_schema=vol.Schema({vol.Required(CONF_CONFIGURE, default=True): bool}),
            description_placeholders={
                "current": self._current or "NONE",
                "target": f"{self._ha_ip}:{self._data[CONF_PORT]}",
                "command": f"AT+SOCKB={target}",
            },
            errors=errors,
        )
