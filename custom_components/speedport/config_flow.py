"""Config flow for the Telekom Speedport integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client
from yarl import URL

from .api import SpeedportAuthError, SpeedportClient, SpeedportConnectionError
from .const import (
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USE_HTTPS,
    DEFAULT_HOST,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
        ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
    }
)


class SpeedportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Speedport."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if host.startswith(("http://", "https://")):
                url = URL(host)
                use_https = url.scheme == "https"
                host = url.host or host
                if url.port and (
                    (use_https and url.port != 443) or (not use_https and url.port != 80)
                ):
                    host = f"{host}:{url.port}"
            else:
                host = host.rstrip("/")
                use_https = False

            password = user_input[CONF_PASSWORD]

            session = aiohttp_client.async_create_clientsession(self.hass)
            client = SpeedportClient(
                host=host, password=password, session=session, use_https=use_https
            )

            try:
                await client.login()
                data = await client.get_all_data()
            except SpeedportAuthError:
                errors["base"] = "invalid_auth"
            except (SpeedportConnectionError, Exception) as err:
                _LOGGER.exception("Unexpected error connecting to Speedport: %s", err)
                errors["base"] = "cannot_connect"
            else:
                device_name = data.device_name or "Speedport"
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_HOST: host,
                        CONF_PASSWORD: password,
                        CONF_USE_HTTPS: use_https,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow."""
        return SpeedportOptionsFlow(config_entry)


class SpeedportOptionsFlow(config_entries.OptionsFlow):
    """Handle Speedport options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL, default=current_interval
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                }
            ),
        )
