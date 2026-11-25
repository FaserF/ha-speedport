"""Data models and exceptions for the Telekom Speedport integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _format_mac(mac: str) -> str:
    """Format the mac address string to lowercase with colons."""
    to_test = mac.lower().replace("-", "").replace(":", "")
    if len(to_test) == 12:
        return ":".join(to_test[i : i + 2] for i in range(0, 12, 2))
    return mac.lower()


@dataclass
class WlanDevice:
    """Represents a device connected to the Speedport router."""

    mac: str = ""
    hostname: str = ""
    ip: str = ""
    speed: str = ""
    downspeed: str = ""
    upspeed: str = ""
    type: str = ""
    connected: bool = True
    rssi: str = ""
    fix_dhcp: str = ""
    ipv6: str = ""
    gua_ipv6: str = ""
    ula_ipv6: str = ""
    hasui: str = ""
    reservedip: str = ""
    slave: str = ""
    use_dhcp: str = ""
    wifi: str = ""
    id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WlanDevice:
        """Create a WlanDevice from raw device API data."""
        raw_mac = data.get(
            "mdevice_mac",
            data.get("device_mac", data.get("mac_addr", data.get("mac", ""))),
        )
        return cls(
            mac=_format_mac(raw_mac) if raw_mac else "",
            hostname=data.get(
                "mdevice_name",
                data.get(
                    "mdevice_hostname",
                    data.get("device_name", data.get("hostname", data.get("name", ""))),
                ),
            ),
            ip=data.get(
                "mdevice_ipv4",
                data.get("device_ipv4", data.get("ip_addr", data.get("ip", ""))),
            ),
            speed=data.get("mdevice_speed", data.get("device_speed", "")),
            downspeed=data.get("mdevice_downspeed", data.get("device_downspeed", "")),
            upspeed=data.get("mdevice_upspeed", data.get("device_upspeed", "")),
            type=data.get("mdevice_type", data.get("device_type", "")),
            connected=str(
                data.get("mdevice_connected", data.get("device_connected", "1"))
            )
            in ("1", "true", "on"),
            rssi=data.get("mdevice_rssi", data.get("device_rssi", "")),
            fix_dhcp=data.get("mdevice_fix_dhcp", data.get("device_fix_dhcp", "")),
            ipv6=data.get("mdevice_ipv6", data.get("device_ipv6", "")),
            gua_ipv6=data.get("mdevice_gua_ipv6", data.get("gua_ipv6", "")),
            ula_ipv6=data.get("mdevice_ula_ipv6", data.get("ula_ipv6", "")),
            hasui=data.get("mdevice_hasui", data.get("hasui", "")),
            reservedip=data.get("mdevice_reservedip", data.get("reservedip", "")),
            slave=data.get("mdevice_slave", data.get("slave", "")),
            use_dhcp=data.get("mdevice_use_dhcp", data.get("use_dhcp", "")),
            wifi=data.get("mdevice_wifi", data.get("wifi", "")),
            id=data.get("mdevice_id", data.get("id", "")),
        )


@dataclass
class SpeedportData:
    """All data fetched from a Speedport router."""

    # Device info
    device_name: str = "Speedport"
    firmware_version: str = ""
    serial_number: str = ""
    mac: str = ""

    # Connection status
    online_status: str = ""
    router_state: str = ""
    dsl_link_status: str = ""
    dsl_downstream: int | None = None
    dsl_upstream: int | None = None
    inet_download: int | None = None
    inet_upload: int | None = None
    inet_uptime: str = ""
    dsl_pop: str = ""

    # WiFi
    use_wlan: bool | None = None
    wlan_ssid: str = ""
    wlan_5ghz_ssid: str = ""
    wlan_guest_active: bool | None = None
    wlan_guest_ssid: str = ""
    wlan_office_active: bool | None = None
    wlan_office_ssid: str = ""

    # IP data
    public_ip_v4: str = ""
    public_ip_v6: str = ""
    dns_v4: str = ""
    dns_v6: str = ""
    gateway_ip_v4: str = ""

    # Features
    dualstack: bool | None = None
    use_lte: bool | None = None
    dsl_tunnel: bool | None = None
    lte_tunnel: bool | None = None
    hybrid_tunnel: bool | None = None

    # Signal (5G/LTE)
    ex5g_signal_5g: str = ""
    ex5g_freq_5g: str = ""
    ex5g_signal_lte: str = ""
    ex5g_freq_lte: str = ""

    # Connected devices
    devices: list[WlanDevice] = field(default_factory=list)

    # Telephony calls
    calls: list[dict[str, Any]] = field(default_factory=list)

    # Update information
    update_available: bool = False
    latest_version: str | None = None
    update_info: dict[str, Any] = field(default_factory=dict)

    # Traffic & Bandwidth (ToTR64 / CWMP)
    bytes_received: int | None = None
    bytes_sent: int | None = None
    bandwidth_download: float | None = None
    bandwidth_upload: float | None = None

    # Raw data
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from raw data."""
        return self.raw.get(key, default)

    def get_device(self, mac: str) -> WlanDevice | None:
        """Get a device by its MAC address."""
        mac_lower = mac.lower()
        for device in self.devices:
            if device.mac.lower() == mac_lower:
                return device
        return None


class SpeedportAuthError(Exception):
    """Authentication failed."""


class SpeedportConnectionError(Exception):
    """Cannot connect to router."""
