"""Diagnostics support for Telekom Speedport."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN

# Fields that must always be redacted from diagnostic output.
# This covers: credentials, IP addresses, MAC addresses, Wi-Fi SSIDs,
# phone numbers, serial numbers, CSRF/session tokens, and device hostnames.
TO_REDACT: set[str] = {
    # Config entry secrets
    CONF_PASSWORD,
    CONF_HOST,
    "host",
    "password",
    # Public IP addresses
    "public_ip_v4",
    "public_ip_v6",
    "dns_v4",
    "dns_v6",
    "gateway_ip_v4",
    "gateway_ip_v6",
    "transmitted_ip_v6_pool_for_lan",
    "used_ip_v6_lan",
    # Raw router IP fields
    "onlineipv4",
    "onlineipv6",
    "inet_ip",
    "extip",
    "ipaddr",
    "ip",
    # Wi-Fi SSIDs and passwords
    "wlan_ssid",
    "wlan_5ghz_ssid",
    "wlan_guest_ssid",
    "wlan_office_ssid",
    "wlan_key",
    "wlan_enc_key",
    "wlan_guest_key",
    "wpa_key",
    "wpa2_key",
    # MAC addresses
    "mac",
    "mdevice_mac",
    "device_mac",
    "wlan_mac",
    "lan_mac",
    # Serial / hardware identifiers
    "serial_number",
    "device_serial",
    "serialnumber",
    # Phone / SIP credentials
    "t_number",
    "t_password",
    "t_callident",
    "addphonenumber",
    "phone_auto_number",
    "dect_pin",
    # Device private IP addresses (connected clients)
    "mdevice_ipv4",
    "mdevice_ipv6",
    "mdevice_gua_ipv6",
    "mdevice_ula_ipv6",
    "device_ipv4",
    "device_ipv6",
    "gua_ipv6",
    "ula_ipv6",
    # Device hostnames (privacy)
    "mdevice_name",
    "mdevice_hostname",
    "device_name_client",
    "hostname",
    # Session / CSRF tokens
    "httoken",
    "_httoken",
    "_tn",
    "challenge",
    # VPN credentials
    "vpn_act_users",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    diagnostics_data = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(
            coordinator.data.raw if coordinator.data else {}, TO_REDACT
        ),
        "devices": [
            async_redact_data(device.__dict__, TO_REDACT)
            for device in (coordinator.data.devices if coordinator.data else [])
        ],
    }

    return diagnostics_data
