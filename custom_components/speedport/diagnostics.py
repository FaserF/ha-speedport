"""Diagnostics support for Telekom Speedport."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN

# Fields that must always be redacted from diagnostic output.
# This covers: credentials, IP addresses, MAC addresses, Wi-Fi SSIDs/keys,
# phone numbers, serial numbers, CSRF/session tokens, and device hostnames.
TO_REDACT: set[str] = {
    # Config entry secrets & parameters
    CONF_PASSWORD,
    CONF_HOST,
    "host",
    "password",
    "pass",
    "auth_code",
    "secret",
    "access_token",
    "user_password",
    "presharedkey",
    "passphrase",
    "pin",
    "dect_pin",
    "wps_pin",
    "wlan_pin",
    # Public & Gateway IP addresses
    "public_ip_v4",
    "public_ip_v6",
    "dns_v4",
    "dns_v4_1",
    "dns_v4_2",
    "dns_v6",
    "dns_v6_1",
    "dns_v6_2",
    "dns_server1",
    "dns_server2",
    "other_dns",
    "gateway_ip_v4",
    "gateway_ip_v6",
    "ip_gateway",
    "transmitted_ip_v6_pool_for_lan",
    "used_ip_v6_lan",
    # Raw router IP fields
    "onlineipv4",
    "onlineipv6",
    "inet_ip",
    "extip",
    "ipaddr",
    "ip_extern",
    "srv_ipv4_wan",
    "srv_ipv6_wan",
    "wan_ip4_addr",
    "wan_ip6_addr",
    "wan_ip_address",
    "wan_ipv4",
    "wan_ipv6",
    "other_ip",
    "other_ip6",
    "ip_v4",
    "ip_v6",
    "ip",
    "ip_address",
    # Wi-Fi SSIDs and passwords
    "wlan_ssid",
    "wlan_5ghz_ssid",
    "wlan_guest_ssid",
    "wlan_office_ssid",
    "ssid",
    "ssid_24g",
    "ssid_5g",
    "ssid2",
    "guest_ssid",
    "ssid_guest",
    "wlan_ssid_24g",
    "wlan_ssid_5g",
    "wlan_key",
    "wlan_enc_key",
    "wlan_guest_key",
    "wlan_psk",
    "wpa_key",
    "wpa2_key",
    # MAC addresses & BSSIDs
    "mac",
    "lan_mac",
    "wlan_mac",
    "mdevice_mac",
    "device_mac",
    "bssid",
    "bssid_24g",
    "bssid_5g",
    # Serial / hardware identifiers
    "serial_number",
    "device_serial",
    "serialnumber",
    "serial",
    "imei",
    "imsi",
    # Phone / SIP credentials & call logs
    "t_number",
    "t_password",
    "t_callident",
    "addphonenumber",
    "phone_auto_number",
    "caller_number",
    "called_number",
    "dialed_number",
    "phonenumber",
    "number",
    "phone_number",
    "remote_number",
    # Device private IP addresses & hostnames (connected clients)
    "mdevice_ipv4",
    "mdevice_ipv6",
    "mdevice_gua_ipv6",
    "mdevice_ula_ipv6",
    "device_ipv4",
    "device_ipv6",
    "gua_ipv6",
    "ula_ipv6",
    "reservedip",
    "mdevice_name",
    "mdevice_hostname",
    "device_name_client",
    "hostname",
    # Session / CSRF tokens
    "httoken",
    "_httoken",
    "_tn",
    "challenge",
    "sessionid",
    "session_id",
    "sid",
    "token",
    # VPN credentials
    "vpn_act_users",
    "vpn_users",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    data = coordinator.data

    router_info: dict[str, Any] = {}
    if data:
        router_info = {
            "device_name": data.device_name,
            "firmware_version": data.firmware_version,
            "online_status": data.online_status,
            "router_state": data.router_state,
            "dsl_link_status": data.dsl_link_status,
            "dsl_downstream": data.dsl_downstream,
            "dsl_upstream": data.dsl_upstream,
            "dsl_pop": data.dsl_pop,
            "dualstack": data.dualstack,
            "use_lte": data.use_lte,
            "dsl_tunnel": data.dsl_tunnel,
            "lte_tunnel": data.lte_tunnel,
            "hybrid_tunnel": data.hybrid_tunnel,
            "ex5g_signal_5g": data.ex5g_signal_5g,
            "ex5g_freq_5g": data.ex5g_freq_5g,
            "ex5g_signal_lte": data.ex5g_signal_lte,
            "ex5g_freq_lte": data.ex5g_freq_lte,
            "update_available": data.update_available,
            "latest_version": data.latest_version,
            "connected_devices_count": len(data.devices),
            "calls_count": len(data.calls),
        }

    raw_data = data.raw if data else {}
    devices = [device.__dict__ for device in data.devices] if data else []
    calls = data.calls if data else []
    update_info = data.update_info if data else {}

    diagnostics_data: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "router_info": router_info,
        "data": async_redact_data(raw_data, TO_REDACT),
        "update_info": async_redact_data(update_info, TO_REDACT),
        "devices": [async_redact_data(dev, TO_REDACT) for dev in devices],
        "calls": [async_redact_data(call, TO_REDACT) for call in calls],
    }

    return diagnostics_data
