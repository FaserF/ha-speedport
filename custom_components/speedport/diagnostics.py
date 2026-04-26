"""Diagnostics support for Telekom Speedport."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN

TO_REDACT = {
    CONF_PASSWORD,
    "public_ip_v4",
    "public_ip_v6",
    "wlan_ssid",
    "wlan_5ghz_ssid",
    "wlan_guest_ssid",
    "wlan_office_ssid",
    "serial_number",
    "mac",
    "mdevice_mac",
    "mdevice_ipv4",
    "mdevice_ipv6",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    diagnostics_data = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(coordinator.data.raw if coordinator.data else {}, TO_REDACT),
        "devices": [
            async_redact_data(device.__dict__, TO_REDACT)
            for device in (coordinator.data.devices if coordinator.data else [])
        ],
    }

    return diagnostics_data
