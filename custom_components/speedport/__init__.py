"""The Telekom Speedport integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import config_validation as cv

from .api import SpeedportAuthError, SpeedportClient, SpeedportConnectionError
from .const import (
    CONF_PASSWORD,
    CONF_USE_HTTPS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PLATFORMS,
    SERVICE_REBOOT,
    SERVICE_RECONNECT,
    SERVICE_WPS_ON,
)
from .coordinator import SpeedportDataCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Speedport integration (config flow only)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Speedport from a config entry."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]
    use_https = entry.data.get(CONF_USE_HTTPS, False)

    session = aiohttp_client.async_create_clientsession(hass)
    client = SpeedportClient(
        host=host, password=password, session=session, use_https=use_https
    )

    try:
        await client.login()
    except SpeedportAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except (SpeedportConnectionError, Exception) as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to Speedport at {host}: {err}"
        ) from err

    coordinator = SpeedportDataCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_CLIENT: client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once per integration)
    if not hass.services.has_service(DOMAIN, SERVICE_REBOOT):
        _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register Speedport services."""

    async def _handle_reboot(call: ServiceCall) -> None:
        for data in hass.data[DOMAIN].values():
            if not isinstance(data, dict):
                continue
            client: SpeedportClient = data[DATA_CLIENT]
            await client.reboot()

    async def _handle_reconnect(call: ServiceCall) -> None:
        for data in hass.data[DOMAIN].values():
            if not isinstance(data, dict):
                continue
            client: SpeedportClient = data[DATA_CLIENT]
            await client.reconnect()

    async def _handle_wps_on(call: ServiceCall) -> None:
        for data in hass.data[DOMAIN].values():
            if not isinstance(data, dict):
                continue
            client: SpeedportClient = data[DATA_CLIENT]
            await client.wps_on()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REBOOT,
        _handle_reboot,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECONNECT,
        _handle_reconnect,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WPS_ON,
        _handle_wps_on,
        schema=vol.Schema({}),
    )
