"""The Telekom Speedport integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
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
    SERVICE_GENERATE_REPORT,
    SERVICE_GET_RAW_DATA,
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
        entry_id = call.data.get("entry_id")
        for eid, data in hass.data[DOMAIN].items():
            if entry_id and eid != entry_id:
                continue
            client: SpeedportClient = data[DATA_CLIENT]
            await client.reboot()

    async def _handle_reconnect(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        for eid, data in hass.data[DOMAIN].items():
            if entry_id and eid != entry_id:
                continue
            client: SpeedportClient = data[DATA_CLIENT]
            await client.reconnect()

    async def _handle_wps_on(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        for eid, data in hass.data[DOMAIN].items():
            if entry_id and eid != entry_id:
                continue
            client: SpeedportClient = data[DATA_CLIENT]
            await client.wps_on()

    async def _handle_get_raw_data(call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        entry_id = call.data.get("entry_id")
        if not entry_id:
            if len(hass.data[DOMAIN]) == 1:
                entry_id = list(hass.data[DOMAIN].keys())[0]
            else:
                raise vol.Invalid(
                    "Multiple Speedports configured, entry_id is required"
                )

        if entry_id not in hass.data[DOMAIN]:
            raise vol.Invalid(f"Config entry {entry_id} not found")

        coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry_id][
            DATA_COORDINATOR
        ]
        return coordinator.data.raw if coordinator.data else {}

    async def _handle_generate_report(call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        entry_id = call.data.get("entry_id")
        if not entry_id:
            if len(hass.data[DOMAIN]) == 1:
                entry_id = list(hass.data[DOMAIN].keys())[0]
            else:
                raise vol.Invalid(
                    "Multiple Speedports configured, entry_id is required"
                )

        if entry_id not in hass.data[DOMAIN]:
            raise vol.Invalid(f"Config entry {entry_id} not found")

        coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry_id][
            DATA_COORDINATOR
        ]
        data = coordinator.data
        if not data:
            return {"report": "No data available"}

        report = f"# Speedport System Report - {data.device_name}\n\n"
        report += f"**Model:** {data.device_name}\n"
        report += f"**Firmware:** {data.firmware_version}\n"
        report += f"**Serial Number:** {data.serial_number}\n"
        report += f"**Online Status:** {data.online_status}\n"
        report += f"**DSL Link:** {data.dsl_link_status}\n\n"

        report += "## Connection Details\n"
        report += f"- IPv4: {data.public_ip_v4}\n"
        report += f"- IPv6: {data.public_ip_v6}\n"
        report += f"- Uptime: {data.inet_uptime}\n\n"

        report += "## Network\n"
        report += f"- Connected Devices: {len(data.devices)}\n"
        report += f"- WiFi Active: {data.use_wlan}\n"
        report += f"- Guest WiFi: {data.wlan_guest_active}\n\n"

        report += "## Device List\n"
        for device in data.devices[:20]:  # Limit to 20 devices
            report += f"- {device.hostname or 'Unknown'} ({device.mac}) - {device.ip} [{device.type}]\n"

        return {"report": report}

    hass.services.async_register(
        DOMAIN,
        SERVICE_REBOOT,
        _handle_reboot,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECONNECT,
        _handle_reconnect,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WPS_ON,
        _handle_wps_on,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RAW_DATA,
        _handle_get_raw_data,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_REPORT,
        _handle_generate_report,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
