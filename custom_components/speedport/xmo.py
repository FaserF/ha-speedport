"""Sagemcom XMO API client and data mapper for Speedport Pro Plus."""

from __future__ import annotations

import json
import logging
import re
import secrets
from hashlib import sha512
from typing import Any
from urllib.parse import quote

import aiohttp

from .api import (
    SpeedportAuthError,
    SpeedportConnectionError,
    SpeedportData,
    WlanDevice,
)

_LOGGER = logging.getLogger(__name__)

SAGEMCOM_USERNAME = "admin"
XMO_STATUS_PATHS = {
    "model_name": "Device/DeviceInfo/ModelName",
    "firmware_version": "Device/DeviceInfo/SoftwareVersion",
    "firmware_date": "Device/DeviceInfo/BuildDate",
    "serial_number": "Device/DeviceInfo/SerialNumber",
    "mac": "Device/DeviceInfo/MACAddress",
    "date_time": "Device/Time/CurrentLocalTime",
    "uptime": "Device/DeviceInfo/UpTime",
    "device_hostname": "Device/DNS/Client/HostName",
    "dsl_link_status": "Device/DSL/Lines/Line[Alias='WAN']/Status",
    "dsl_link_detail": "Device/DSL/Lines/Line[Alias='WAN']/LinkStatus",
    "ppp_status": "Device/PPP/Interfaces/Interface[Alias='WAN']/Status",
    "internet_status": "Device/IP/Interfaces/Interface[Alias='WAN']/Status",
    "dsl_downstream": "Device/DSL/Channels/Channel[@uid='1']/DownstreamCurrRate",
    "dsl_upstream": "Device/DSL/Channels/Channel[@uid='1']/UpstreamCurrRate",
    "download_bandwidth": "Device/PPP/Interfaces/Interface[Alias='WAN']/SRD",
    "upload_bandwidth": "Device/PPP/Interfaces/Interface[Alias='WAN']/SRU",
    "dsl_pop": "Device/Managers/Network/ConnectedACName",
    "bonding_enable": "Device/Services/Bonding/Enable",
    "bonding_status": "Device/Services/Bonding/Status",
    "bonding_mode": "Device/Managers/Network/OverviewStatus",
    "wlan_ssid": "Device/WiFi/SSIDs/SSID[Alias='WLAN_2_4']/SSID",
    "wlan_5ghz_ssid": "Device/WiFi/SSIDs/SSID[Alias='WLAN_5']/SSID",
    "wifi_24_channels": 'Device/WiFi/Radios/Radio[Alias="WLAN_2_4"]/ChannelsInUse',
    "wifi_5_channels": 'Device/WiFi/Radios/Radio[Alias="WLAN_5"]/ChannelsInUse',
    "wlan_24_enabled": "Device/WiFi/SSIDs/SSID[Alias='WLAN_2_4']/Enable",
    "wlan_5_enabled": "Device/WiFi/SSIDs/SSID[Alias='WLAN_5']/Enable",
    "wifi_gaming_enable": "Device/WiFi/SSIDs/SSID[Alias='WLAN_Gaming']/Enable",
    "wifi_gaming_ssid": "Device/WiFi/SSIDs/SSID[Alias='WLAN_Gaming']/SSID",
    "wlan_guest_24_enabled": "Device/WiFi/SSIDs/SSID[Alias='GUEST_2_4']/Enable",
    "wlan_guest_5_enabled": "Device/WiFi/SSIDs/SSID[Alias='GUEST_5']/Enable",
    "wlan_guest_24_ssid": "Device/WiFi/SSIDs/SSID[Alias='GUEST_2_4']/SSID",
    "wlan_guest_5_ssid": "Device/WiFi/SSIDs/SSID[Alias='GUEST_5']/SSID",
    "wlan_guest_24_status": "Device/WiFi/SSIDs/SSID[Alias='GUEST_2_4']/Status",
    "wlan_guest_5_status": "Device/WiFi/SSIDs/SSID[Alias='GUEST_5']/Status",
    "ping_timestamp": "Device/Managers/Network/Ping/TimeStamp",
    "ping_average_latency": "Device/Managers/Network/Ping/AverageLatency",
    "lan1_status": 'Device/Ethernet/Interfaces/Interface[Alias="LAN1"]/Status',
    "lan1_speed": 'Device/Ethernet/Interfaces/Interface[Alias="LAN1"]/CurrentBitRate',
    "lan2_status": 'Device/Ethernet/Interfaces/Interface[Alias="LAN2"]/Status',
    "lan2_speed": 'Device/Ethernet/Interfaces/Interface[Alias="LAN2"]/CurrentBitRate',
    "lan3_status": 'Device/Ethernet/Interfaces/Interface[Alias="LAN3"]/Status',
    "lan3_speed": 'Device/Ethernet/Interfaces/Interface[Alias="LAN3"]/CurrentBitRate',
    "lan4_status": 'Device/Ethernet/Interfaces/Interface[Alias="LAN4"]/Status',
    "lan4_speed": 'Device/Ethernet/Interfaces/Interface[Alias="LAN4"]/CurrentBitRate',
    "smart_home_status": "Device/Services/SmartHome/Status",
    "external_modem": "Device/Managers/Network/WANPHYRole",
    "vpn_access_type": "Device/Managers/VPN/VPNType",
    "dect_base_enabled": (
        "Device/Services/VoiceServices/VoiceService[Alias='VOICESERVICE1']/"
        "ExtensionProfiles/ExtensionProfile[@uid='2']/DECTFixedPart/Enable"
    ),
    "dns_v4": "Device/DNS/Client/Servers/Server[Alias='LOCAL_DNS_RELAY_PRIMARY']/DNSServer",
    "gateway_ip_v4": 'Device/IP/Interfaces/Interface[Alias="LAN"]/IPv4Addresses/IPv4Address[Alias="LAN_ADDRESS"]/IPAddress',
    "use_lte": 'Device/Cellular/Interfaces/Interface[@uid="1"]/Enable',
    "lte_signal": "Device/Cellular/SpeedportPro/Signal",
}


class SagemcomXmoClient:
    """Client for the Sagemcom XMO API used by Speedport Pro Plus."""

    _API_ENDPOINT = "/cgi/json-req"
    _UINT_MAX = 4294967295
    _NO_ERROR = ("XMO_REQUEST_NO_ERR", "Ok")
    _UNKNOWN_PATH_ERRORS = ("XMO_INVALID_PATH_ERR", "XMO_UNKNOWN_PATH_ERR")

    def __init__(
        self,
        host: str,
        password: str,
        session: aiohttp.ClientSession,
        use_https: bool = False,
    ) -> None:
        """Initialize the XMO client."""
        self._host = host
        self._password_hash = sha512(password.encode("utf-8")).hexdigest()
        self._session = session
        self._url = f"{'https' if use_https else 'http'}://{host}{self._API_ENDPOINT}"
        self._request_id = -1
        self._session_id = 0
        self._server_nonce = ""
        self._auth_token = ""

    def _auth_key(self, request_id: int, client_nonce: int) -> str:
        """Generate the firmware's SHA512 request key or use its session token."""
        if self._auth_token:
            return self._auth_token

        credential_hash = sha512(
            f"{SAGEMCOM_USERNAME}:{self._server_nonce}:{self._password_hash}".encode()
        ).hexdigest()
        request_hash = (
            f"{credential_hash}:{request_id}:{client_nonce}:JSON:{self._API_ENDPOINT}"
        )
        return sha512(request_hash.encode("utf-8")).hexdigest()

    @staticmethod
    def _error_description(error: Any) -> str | None:
        """Extract an XMO error description from a response object."""
        if isinstance(error, dict):
            description = error.get("description")
            return str(description) if description is not None else None
        return None

    def _raise_xmo_error(self, description: str | None) -> None:
        """Translate router error descriptions into integration errors."""
        if description in self._NO_ERROR:
            return
        if description == "XMO_AUTHENTICATION_ERR":
            raise SpeedportAuthError("Sagemcom XMO authentication failed")
        if description == "XMO_INVALID_SESSION_ERR":
            raise SpeedportAuthError("The router rejected the current XMO session")
        if description == "XMO_LOGIN_RETRY_ERR":
            raise SpeedportConnectionError(
                "The router is temporarily blocking API login attempts"
            )
        if description == "XMO_ACCESS_RESTRICTION_ERR":
            raise SpeedportConnectionError(
                "The router restricted access to its XMO API"
            )
        raise SpeedportConnectionError(
            f"Speedport XMO request failed: {description or 'unknown router error'}"
        )

    def _check_response(
        self, response: dict[str, Any], ignore_unknown_paths: bool = False
    ) -> dict[str, Any]:
        """Validate request- and action-level XMO errors."""
        reply = response.get("reply")
        if not isinstance(reply, dict):
            raise SpeedportConnectionError("The router returned an invalid XMO reply")

        request_error = reply.get("error")
        description = self._error_description(request_error)
        if description in self._NO_ERROR:
            return reply
        if description != "XMO_REQUEST_ACTION_ERR":
            self._raise_xmo_error(description)

        actions = reply.get("actions")
        if not isinstance(actions, list):
            raise SpeedportConnectionError(
                "The router returned an invalid XMO action list"
            )
        for action in actions:
            if not isinstance(action, dict):
                raise SpeedportConnectionError(
                    "The router returned an invalid XMO action"
                )
            action_error = self._error_description(action.get("error"))
            if action_error in self._NO_ERROR:
                continue
            if ignore_unknown_paths and action_error in self._UNKNOWN_PATH_ERRORS:
                continue
            self._raise_xmo_error(action_error)
        return reply

    async def _request(
        self,
        actions: list[dict[str, Any]],
        *,
        priority: bool = False,
        ignore_unknown_paths: bool = False,
    ) -> dict[str, Any]:
        """Send an authenticated XMO request."""
        self._request_id += 1
        client_nonce = secrets.randbelow(self._UINT_MAX)
        payload = {
            "request": {
                "id": self._request_id,
                "session-id": self._session_id,
                "priority": priority,
                "actions": actions,
                "cnonce": client_nonce,
                "auth-key": self._auth_key(self._request_id, client_nonce),
            }
        }
        try:
            async with self._session.post(
                self._url,
                data={"req": json.dumps(payload, separators=(",", ":"))},
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                body = await response.text(errors="replace")
        except (TimeoutError, aiohttp.ClientError) as err:
            raise SpeedportConnectionError(
                f"Unable to reach Speedport XMO API at {self._host}: {err}"
            ) from err

        try:
            result = json.loads(body)
        except json.JSONDecodeError as err:
            raise SpeedportConnectionError(
                f"Speedport XMO API returned HTTP {response.status} with invalid JSON"
            ) from err
        if not isinstance(result, dict):
            raise SpeedportConnectionError(
                "The router returned an invalid XMO response"
            )

        reply = self._check_response(result, ignore_unknown_paths)
        if response.status != 200:
            raise SpeedportConnectionError(
                f"Speedport XMO API returned HTTP {response.status}"
            )
        return reply

    async def login(self) -> None:
        """Open an XMO session using the router's native SHA512 flow."""
        self._request_id = -1
        self._session_id = 0
        self._server_nonce = ""
        self._auth_token = ""
        action = {
            "id": 0,
            "method": "logIn",
            "parameters": {
                "user": SAGEMCOM_USERNAME,
                "persistent": True,
                "session-options": {
                    "nss": [
                        {
                            "name": "gtw",
                            "uri": "http://sagemcom.com/gateway-data",
                        }
                    ],
                    "language": "ident",
                    "context-flags": {
                        "get-content-name": True,
                        "local-time": True,
                    },
                    "capability-depth": 2,
                    "capability-flags": {
                        "name": True,
                        "default-value": False,
                        "restriction": True,
                        "description": False,
                    },
                    "time-format": "ISO_8601",
                    "write-only-string": "_XMO_WRITE_ONLY_",
                    "undefined-write-only-string": "_XMO_UNDEFINED_WRITE_ONLY_",
                },
            },
        }
        reply = await self._request([action], priority=True)
        actions = reply.get("actions")
        if not isinstance(actions, list) or not actions:
            raise SpeedportAuthError("The router did not return an XMO session")
        try:
            parameters = actions[0]["callbacks"][0]["parameters"]
            session_id = int(parameters["id"])
            server_nonce = parameters["nonce"]
        except (IndexError, KeyError, TypeError, ValueError) as err:
            raise SpeedportAuthError(
                "The router did not return an XMO session"
            ) from err

        self._session_id = session_id
        self._server_nonce = str(server_nonce)
        token = parameters.get("token")
        self._auth_token = token if isinstance(token, str) else ""

    async def logout(self) -> None:
        """Close the current XMO session."""
        if not self._session_id:
            return
        try:
            await self._request([{"id": 0, "method": "logOut"}])
        finally:
            self._session_id = 0
            self._server_nonce = ""
            self._auth_token = ""
            self._request_id = -1

    async def get_values_by_xpaths(
        self,
        xpaths: dict[str, str],
        *,
        options: dict[str, Any] | None = None,
        ignore_unknown_paths: bool = False,
    ) -> dict[str, Any]:
        """Read multiple values from the router's XMO data model."""
        actions = [
            {
                "id": index,
                "method": "getValue",
                "xpath": quote(xpath, safe="/=[]'@\""),
                "options": options or {},
            }
            for index, xpath in enumerate(xpaths.values())
        ]
        reply = await self._request(
            actions,
            ignore_unknown_paths=ignore_unknown_paths,
        )
        response_actions = reply.get("actions", [])
        values: dict[str, Any] = {}
        for index, key in enumerate(xpaths):
            try:
                parameters = response_actions[index]["callbacks"][0]["parameters"]
                values[key] = parameters.get("value")
            except IndexError, KeyError, TypeError:
                values[key] = None
        return values

    async def reboot(self) -> bool:
        """Request a router reboot through the XMO API."""
        await self._request(
            [
                {
                    "id": 0,
                    "method": "reboot",
                    "xpath": "Device",
                    "parameters": {"source": "GUI"},
                }
            ]
        )
        return True


def _host_value(host: dict[str, Any], key: str, *aliases: str) -> Any:
    """Return the first non-None value from candidate host keys."""
    for candidate in (key, *aliases):
        if candidate in host and host[candidate] is not None:
            return host[candidate]
    return None


def build_sagemcom_data(
    values: dict[str, Any], host_data: dict[str, Any]
) -> SpeedportData:
    """Map XMO status values and host list into SpeedportData."""

    def _text(key: str) -> str:
        value = values.get(key)
        return str(value).strip() if isinstance(value, (str, int, float)) else ""

    def _integer(key: str) -> int | None:
        try:
            return int(values[key])
        except KeyError, TypeError, ValueError:
            return None

    def _boolean(key: str) -> bool | None:
        value = values.get(key)
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in ("1", "true", "yes", "on", "up", "enabled"):
            return True
        if normalized in ("0", "false", "no", "off", "down", "disabled"):
            return False
        return None

    model_name = _text("model_name")
    if not model_name:
        raise SpeedportConnectionError(
            "XMO login succeeded, but the router returned no model information"
        )

    firmware_version = _text("firmware_version")
    serial_number = _text("serial_number")
    mac_address = _text("mac")
    dsl_downstream_bps = _integer("dsl_downstream")
    dsl_upstream_bps = _integer("dsl_upstream")
    internet_status = _text("internet_status")
    dsl_status = _text("dsl_link_status") or _text("dsl_link_detail")
    wifi_24_enabled = _boolean("wlan_24_enabled")
    wifi_5_enabled = _boolean("wlan_5_enabled")
    guest_24_enabled = _boolean("wlan_guest_24_enabled")
    guest_5_enabled = _boolean("wlan_guest_5_enabled")

    hosts = host_data.get("hosts")
    if isinstance(hosts, dict):
        hosts = [hosts]
    if not isinstance(hosts, list):
        _LOGGER.warning("Speedport XMO API did not return a host list")
        hosts = []

    devices: list[WlanDevice] = []
    wifi_device_counts = {
        "wifi_24_device_count": 0,
        "wifi_5_device_count": 0,
        "wifi_gaming_device_count": 0,
        "wifi_guest_device_count": 0,
    }
    wifi_counts_available = False
    for host in hosts:
        if not isinstance(host, dict):
            continue
        mac = _host_value(
            host,
            "phys_address",
            "physAddress",
            "PhysAddress",
            "macAddress",
            "MACAddress",
            "mac",
            "physicalAddress",
        )
        if not mac:
            continue
        active = _host_value(host, "active", "Active")
        connected = (
            str(active).strip().lower() not in ("0", "false", "off", "down")
            if active is not None
            else True
        )
        interface_type = str(
            _host_value(
                host,
                "interface_type",
                "interfaceType",
                "InterfaceType",
                "detected_device_type",
                "detectedDeviceType",
            )
            or ""
        )
        associated_device = str(
            _host_value(host, "associated_device", "AssociatedDevice") or ""
        )
        layer3_interface = str(
            _host_value(host, "layer3_interface", "Layer3Interface") or ""
        )
        alias_match = re.search(r"Alias=['\"]([^'\"]+)['\"]", associated_device)
        associated_alias = alias_match.group(1).upper() if alias_match else ""
        if connected and interface_type.lower().startswith("wifi"):
            if "GUEST" in layer3_interface.upper() or associated_alias.startswith(
                "GUEST"
            ):
                wifi_counts_available = True
                wifi_device_counts["wifi_guest_device_count"] += 1
            elif associated_alias == "WLAN_2_4":
                wifi_counts_available = True
                wifi_device_counts["wifi_24_device_count"] += 1
            elif associated_alias == "WLAN_5":
                wifi_counts_available = True
                wifi_device_counts["wifi_5_device_count"] += 1
            elif associated_alias == "WLAN_GAMING":
                wifi_counts_available = True
                wifi_device_counts["wifi_gaming_device_count"] += 1
            elif interface_type.lower().startswith("wifi2.4"):
                wifi_counts_available = True
                wifi_device_counts["wifi_24_device_count"] += 1
        devices.append(
            WlanDevice(
                mac=str(mac),
                hostname=str(
                    _host_value(
                        host,
                        "user_host_name",
                        "userHostName",
                        "UserHostName",
                        "host_name",
                        "hostName",
                        "HostName",
                        "DeviceName",
                        "name",
                    )
                    or ""
                ),
                ip=str(_host_value(host, "ip_address", "ipAddress", "IPAddress") or ""),
                type=interface_type,
                connected=connected,
                id=str(_host_value(host, "uid", "id") or mac),
            )
        )

    raw: dict[str, Any] = {
        key: value for key, value in values.items() if value is not None
    }
    raw.update(
        {
            "model_name": model_name,
            "device_type": model_name,
            "device_name": model_name,
            "firmware_version": firmware_version,
            "serial_number": serial_number,
            "mac": mac_address,
            "online_status": internet_status,
            "onlinestatus": internet_status,
            "router_state": internet_status or dsl_status,
            "dsl_link_status": dsl_status,
            "dsl_downstream": dsl_downstream_bps,
            "dsl_upstream": dsl_upstream_bps,
            "wlan_ssid": _text("wlan_ssid"),
            "wlan_5ghz_ssid": _text("wlan_5ghz_ssid"),
            "wlan_guest_ssid": _text("wlan_guest_24_ssid"),
            "dns_v4": _text("dns_v4"),
            "gateway_ip_v4": _text("gateway_ip_v4"),
            "dsl_pop": _text("dsl_pop"),
            "status_datetime": _text("date_time"),
            "router_hostname": _text("device_hostname"),
            "connected_devices_count": sum(device.connected for device in devices),
        }
    )
    if wifi_counts_available:
        raw.update(wifi_device_counts)

    return SpeedportData(
        device_name=model_name,
        firmware_version=firmware_version,
        serial_number=serial_number,
        mac=mac_address,
        online_status=internet_status,
        router_state=internet_status or dsl_status,
        dsl_link_status=dsl_status,
        dsl_downstream=dsl_downstream_bps,
        dsl_upstream=dsl_upstream_bps,
        use_wlan=(
            wifi_24_enabled or wifi_5_enabled
            if wifi_24_enabled is not None or wifi_5_enabled is not None
            else None
        ),
        wlan_ssid=_text("wlan_ssid"),
        wlan_5ghz_ssid=_text("wlan_5ghz_ssid"),
        wlan_guest_active=(
            guest_24_enabled or guest_5_enabled
            if guest_24_enabled is not None or guest_5_enabled is not None
            else None
        ),
        wlan_guest_ssid=_text("wlan_guest_24_ssid"),
        dns_v4=_text("dns_v4"),
        gateway_ip_v4=_text("gateway_ip_v4"),
        use_lte=_boolean("use_lte"),
        devices=devices,
        raw=raw,
    )
