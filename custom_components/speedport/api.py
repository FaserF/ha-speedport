"""Telekom Speedport API client.

Supports multiple generations of Speedport routers:
- Older models (e.g. W 724V): Plain JSON, MD5 login, httoken CSRF.
- Newer models (e.g. Smart 3/4, Pro): AES-CCM encrypted JSON, SHA256 challenge-response login.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from hashlib import md5, sha256
from typing import Any, cast

import aiohttp
from Crypto.Cipher import AES
from yarl import URL

_LOGGER = logging.getLogger(__name__)

# The default key used for initial/public encrypted communication on newer models
DEFAULT_KEY = "cdc0cac1280b516e674f0057e4929bca84447cca8425007e33a88a5cf598a190"
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def _simplify_response(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert the Speedport API's list-of-dicts format into a flat dict.

    This version is robust for legacy models (W 724V) where properties are often
    nested in lists of varid/varvalue pairs.
    """
    result: dict[str, Any] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        varid = item.get("varid", "")
        varvalue = item.get("varvalue", "")

        if isinstance(varvalue, list):
            # Check if this list is a collection of property dicts (varid/varvalue pairs)
            if varvalue and all(isinstance(v, dict) and "varid" in v for v in varvalue):
                flat_item = {}
                for v in varvalue:
                    v_id = v.get("varid", "")
                    v_val = v.get("varvalue", "")
                    if isinstance(v_val, list):
                        # Nested properties? Flatten them too
                        v_val = _simplify_response(v_val)
                    flat_item[v_id] = v_val

                # If we already have a list for this varid, append. Otherwise create list.
                if varid in result and isinstance(result[varid], list):
                    result[varid].append(flat_item)
                else:
                    result[varid] = [flat_item]
            else:
                # Fallback: process list normally
                sub_items = []
                for sub in varvalue:
                    if isinstance(sub, dict) and "varid" in sub:
                        sub_items.append(_simplify_response([sub]))
                    else:
                        sub_items.append(sub)
                result[varid] = sub_items
        else:
            result[varid] = varvalue
    return result


def _decode(data: str, key: str = DEFAULT_KEY) -> dict[str, Any] | str:
    """Decode Speedport's AES-CCM encrypted response."""
    try:
        ciphertext_tag = bytes.fromhex(data)
        cipher = AES.new(bytes.fromhex(key), AES.MODE_CCM, bytes.fromhex(key)[:8])
        decrypted = cipher.decrypt_and_verify(
            ciphertext_tag[:-16], ciphertext_tag[-16:]
        )
        text = decrypted.decode("utf-8")
        try:
            parsed = cast(dict[str, Any] | list[Any], json.loads(text))
            if isinstance(parsed, list):
                return _simplify_response(parsed)
            return parsed
        except json.JSONDecodeError:
            return text
    except Exception as exc:
        _LOGGER.debug("Failed to decode encrypted data: %s", exc)
        return data


def _encode(data: str, key: str = DEFAULT_KEY) -> str:
    """Encode data using Speedport's AES-CCM encryption."""
    cipher = AES.new(bytes.fromhex(key), AES.MODE_CCM, bytes.fromhex(key)[:8])
    ciphertext, tag = cipher.encrypt_and_digest(data.encode("utf-8"))
    return ciphertext.hex() + tag.hex()


def _parse_response(text: str, key: str | None = None) -> dict[str, Any]:
    """Parse a response from the Speedport router (handles plain and encrypted)."""
    if not text or text.strip() in ("[]", ""):
        return {}

    # Check if it's hex (encrypted) or JSON (plain)
    cleaned_text = text.strip()
    if HEX_RE.match(cleaned_text) and len(cleaned_text) > 32:
        decoded = _decode(cleaned_text, key or DEFAULT_KEY)
        if isinstance(decoded, dict):
            return decoded
        return {}

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return _simplify_response(data)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as exc:
        _LOGGER.debug("Failed to parse JSON response: %s | text: %s", exc, text[:200])
    return {}


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
        return cls(
            mac=data.get("mdevice_mac", data.get("device_mac", data.get("mac", ""))),
            hostname=data.get(
                "mdevice_name",
                data.get(
                    "mdevice_hostname", data.get("device_name", data.get("name", ""))
                ),
            ),
            ip=data.get("mdevice_ipv4", data.get("device_ipv4", data.get("ip", ""))),
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

    # Update information
    update_available: bool = False
    latest_version: str | None = None
    update_info: dict[str, Any] = field(default_factory=dict)

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


class SpeedportClient:
    """API client for Telekom Speedport routers.

    Supports legacy (plain) and modern (encrypted) models.
    """

    def __init__(
        self,
        host: str,
        password: str,
        session: aiohttp.ClientSession,
        use_https: bool = False,
    ) -> None:
        """Initialize the client."""
        host = host.strip()
        if host.startswith(("http://", "https://")):
            url = URL(host)
            self._host = url.host or host
            use_https = use_https or (url.scheme == "https")
        else:
            self._host = host.rstrip("/")

        self._password = password
        self._session = session
        self._base_url = (
            f"https://{self._host}" if use_https else f"http://{self._host}"
        )
        self._logged_in = False
        self._login_key: str | None = None  # Challenge key for modern models
        self._encrypted_mode: bool | None = None  # Detected on first request

    async def logout(self) -> None:
        """Log out from the Speedport."""
        if not self._logged_in:
            return
        try:
            # Arcadyan models like W 724V Typ B use logout: "byby"
            kwargs = self._req_kwargs()
            headers = dict(kwargs.get("headers", {}))
            headers["X-Requested-With"] = "XMLHttpRequest"

            await self._session.post(
                f"{self._base_url}/data/Login.json",
                data={"logout": "byby"},
                headers=headers,
                **{k: v for k, v in kwargs.items() if k != "headers"},
            )
        except Exception as exc:
            _LOGGER.debug("Logout failed: %s", exc)
        finally:
            self._logged_in = False

    @property
    def is_logged_in(self) -> bool:
        """Return True if authenticated."""
        return self._logged_in

    def _req_kwargs(self) -> dict[str, Any]:
        """Default request kwargs with browser-like headers."""
        return {
            "ssl": False,
            "timeout": aiohttp.ClientTimeout(total=30),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
            },
        }

    async def _get_httoken(self, page_url: str) -> str:
        """Fetch a page and extract the httoken CSRF value (Legacy)."""
        try:
            kwargs = self._req_kwargs()
            async with self._session.get(page_url, **kwargs) as resp:
                raw = await resp.read()
                text = raw.decode("latin-1", errors="replace")
                for pattern in [
                    r"var _httoken = \"?(\d+)\"?;",
                ]:
                    if match := re.search(pattern, text):
                        _LOGGER.debug("Found httoken: %s", match.group(1))
                        return match.group(1)
        except Exception as exc:
            _LOGGER.debug("Could not get httoken from %s: %s", page_url, exc)
        return ""

    async def _get_json(
        self, path: str, referer: str = "", auth: bool = False
    ) -> dict[str, Any]:
        """Perform a GET request and parse the JSON response."""
        # Add cache-busting params as expected by the router
        import random
        import time

        timestamp = int(time.time() * 1000)
        rand = random.randint(0, 1000)

        url = f"{self._base_url}/{path}"
        if "?" in url:
            url += f"&_time={timestamp}&_rand={rand}"
        else:
            url += f"?_time={timestamp}&_rand={rand}"

        # For legacy models like W 724V Typ B, we must pass _tn token in GET requests
        if hasattr(self, "_token") and self._token:
            url += f"&_tn={self._token}"

        kwargs = self._req_kwargs()
        headers = dict(kwargs.get("headers", {}))
        headers["X-Requested-With"] = "XMLHttpRequest"

        # For legacy models like W 724V, Referer MUST be the login page for data endpoints
        if path.startswith("data/") or not referer:
            referer = "html/login/index.html"

        ref_url = f"{self._base_url}/{referer}"
        headers["Referer"] = ref_url

        try:
            async with self._session.get(
                url,
                headers=headers,
                **{k: v for k, v in kwargs.items() if k != "headers"},
            ) as resp:
                text = await resp.text(errors="replace")

                # Robust parsing: if it redirects to login, we are logged out
                if (
                    "Document moved" in text
                    or "login/index.html" in text
                    or "login_index_html" in text
                ):
                    _LOGGER.debug("Session expired or redirected to login for %s", path)
                    self._logged_in = False
                    return {}

                _LOGGER.debug(
                    "Raw response from %s (first 300 chars): %s", path, text[:300]
                )

                if self._encrypted_mode is None:
                    # Detect mode on first request: if it's hex-only, it's encrypted
                    if (
                        all(c in "0123456789abcdefABCDEF" for c in text.strip())
                        and len(text) > 32
                    ):
                        self._encrypted_mode = True
                    else:
                        self._encrypted_mode = False

                key = (
                    self._login_key if (auth and self._encrypted_mode) else DEFAULT_KEY
                )
                data = _parse_response(text, key)

                _LOGGER.debug(
                    "Parsed %d keys from %s: %s",
                    len(data),
                    path,
                    list(data.keys())[:20],
                )

                # If data is empty for Overview, try fallback to Login.json
                if not data and path == "data/Overview.json":
                    _LOGGER.debug("Overview.json empty, trying Login.json fallback")
                    return dict(
                        await self._get_json("data/Login.json", referer=referer)
                    )

                return data
        except aiohttp.ClientError as exc:
            raise SpeedportConnectionError(f"GET {url} failed: {exc}") from exc

    async def _post_json(
        self, path: str, data: dict[str, Any], referer: str = "", auth: bool = False
    ) -> dict[str, Any]:
        """Perform a POST request and parse the JSON response."""
        url = f"{self._base_url}/{path}"
        kwargs = self._req_kwargs()
        headers = dict(kwargs.get("headers", {}))
        headers["X-Requested-With"] = "XMLHttpRequest"

        if referer:
            ref_url = f"{self._base_url}/{referer}"
            headers["Referer"] = ref_url
            token = await self._get_httoken(ref_url)
            if token:
                data = {**data, "httoken" if self._encrypted_mode else "_tn": token}

        body_str = "&".join(f"{k}={v}" for k, v in data.items())
        key = (
            self._login_key if (auth and self._encrypted_mode) else None
        ) or DEFAULT_KEY

        if self._encrypted_mode:
            body = _encode(body_str, key)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = body_str
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        try:
            async with self._session.post(
                url,
                data=body,
                headers=headers,
                **{k: v for k, v in kwargs.items() if k != "headers"},
            ) as resp:
                text = await resp.text(errors="replace")
                return _parse_response(text, key)
        except aiohttp.ClientError as exc:
            raise SpeedportConnectionError(f"POST {url} failed: {exc}") from exc

    async def set_wifi(self, on: bool) -> bool:
        """Turn WiFi on or off."""
        return await self._set_module_state({"use_wlan": "1" if on else "0"})

    async def set_wifi_guest(self, on: bool) -> bool:
        """Turn Guest WiFi on or off."""
        return await self._set_module_state({"wlan_guest_active": "1" if on else "0"})

    async def set_wifi_office(self, on: bool) -> bool:
        """Turn Office WiFi on or off."""
        return await self._set_module_state({"wlan_office_active": "1" if on else "0"})

    async def _set_module_state(self, data: dict[str, str]) -> bool:
        """Set a module state via Modules.json."""
        referer = "html/content/overview/index.html"
        result = await self._post_json("data/Modules.json", data, referer=referer)
        return result.get("status") == "ok"

    async def _get_challenge(self) -> str | None:
        """Get login challenge (Modern)."""
        data = {"getChallenge": "1"}
        result = await self._post_json("data/Login.json", data, referer="")
        return result.get("challenge")

    async def login(self) -> None:
        """Authenticate with the router (supports Legacy MD5 and Modern SHA256)."""
        self._logged_in = False
        self._login_key = None

        # First, try to get a challenge (Modern detection)
        try:
            challenge = await self._get_challenge()
            if challenge:
                self._encrypted_mode = True
                self._login_key = challenge
                # Compute SHA256 hash: challenge:password
                auth_str = f"{challenge}:{self._password}".encode()
                password_hash = sha256(auth_str).hexdigest()
                data = {"showpw": "0", "password": password_hash}
                result = await self._post_json(
                    "data/Login.json", data, referer="", auth=False
                )
                if result.get("login") == "success":
                    self._logged_in = True
                    _LOGGER.info(
                        "Successfully logged in (SHA256 mode) to %s", self._host
                    )
                    return
        except Exception as exc:
            _LOGGER.debug(
                "Modern login attempt failed, falling back to legacy: %s", exc
            )

        # Fallback/Legacy: W 724V style (MD5)
        self._encrypted_mode = False
        login_page = f"{self._base_url}/html/login/index.html"
        token = await self._get_httoken(login_page)
        self._token = token
        password_hash = md5(self._password.encode("utf-8")).hexdigest()

        # Build form body manually to ensure compatibility
        data = {"password": password_hash, "showpw": "0", "_tn": token}

        kwargs = self._req_kwargs()
        headers = dict(kwargs.get("headers", {}))
        headers.update(
            {"Referer": login_page, "Content-Type": "application/x-www-form-urlencoded"}
        )

        # We try multiple combinations for legacy models:
        methods = [
            {"password": password_hash, "showpw": "0", "_tn": token},
            {"password": password_hash, "showpw": "0", "httoken": token},
            {"password": self._password, "showpw": "0", "httoken": token},
        ]

        for body in methods:
            try:
                async with self._session.post(
                    f"{self._base_url}/data/Login.json",
                    data=body,
                    headers=headers,
                    **{k: v for k, v in kwargs.items() if k != "headers"},
                ) as resp:
                    text = await resp.text(errors="replace")
                    result = _parse_response(text)
                    login_status = str(
                        result.get("login", result.get("status", ""))
                    ).lower()
                    if login_status in ("success", "ok", "true", "1"):
                        # Navigate to overview to "activate" the session
                        nav_headers = dict(kwargs.get("headers", {}))
                        nav_headers["Referer"] = login_page
                        await self._session.get(
                            f"{self._base_url}/html/content/overview/index.html?lang=de",
                            headers=nav_headers,
                            **{k: v for k, v in kwargs.items() if k != "headers"},
                        )
                        self._logged_in = True
                        _LOGGER.info(
                            "Successfully logged in (Legacy mode) to %s", self._host
                        )
                        return
            except Exception as exc:
                _LOGGER.debug("Login method failed: %s", exc)

        raise SpeedportAuthError("All login methods failed")

    async def _ensure_auth(self) -> None:
        """Ensure we are logged in."""
        if not self._logged_in:
            await self.login()

    async def get_all_data(self) -> SpeedportData:
        """Fetch all available data from the router."""
        raw: dict[str, Any] = {}

        # Public Status — always available, even without auth on W 724V.
        # This gives us domain_name (e.g. "Speedport_W_724V_...") for model detection.
        try:
            status = await self._get_json("data/Status.json")
            raw.update(status)
        except Exception:
            pass

        # Detect legacy W 724V early using domain_name from Status.json
        # (device_name may not yet be populated at this stage)
        domain_name = str(raw.get("domain_name", ""))
        is_legacy_w724v = any(
            x in domain_name or x in str(raw.get("device_name", ""))
            for x in ("W_724V", "W 724V")
        )
        _LOGGER.debug(
            "Model detection: domain_name=%s, is_legacy_w724v=%s",
            domain_name,
            is_legacy_w724v,
        )

        # Auth required for the rest
        try:
            await self._ensure_auth()

            if is_legacy_w724v:
                # For W 724V: fetch Status.json again after auth (session cookie may unlock more fields)
                _LOGGER.debug(
                    "Legacy W 724V detected — fetching authenticated Status.json"
                )
                status_auth = await self._get_json(
                    "data/Status.json", referer="html/login/index.html"
                )
                raw.update(status_auth)

                # W 724V fallback endpoints for WLAN and DSL details
                for ep, ref in [
                    ("data/WLAN.json", "html/content/network/wlan_basic.html"),
                    ("data/WLANBasic.json", "html/content/network/wlan_basic.html"),
                    (
                        "data/WLANSettings.json",
                        "html/content/network/wlan_settings.html",
                    ),
                    ("data/WLANGuest.json", "html/content/network/wlan_guest.html"),
                    ("data/LAN.json", "html/content/network/lan.html"),
                    ("data/IPData.json", "html/content/internet/con_ipdata.html"),
                    ("data/Internet.json", "html/content/internet/con_ipdata.html"),
                ]:
                    try:
                        res = await self._get_json(ep, referer=ref)
                        if res:
                            raw.update(res)
                    except Exception:
                        pass

                # Overview last (may return partial data on W 724V — don't override good values)
                try:
                    overview = await self._get_json(
                        "data/Overview.json",
                        referer="html/content/overview/index.html",
                    )
                    for k, v in overview.items():
                        if k not in raw or not raw[k]:
                            raw[k] = v
                except Exception as exc:
                    _LOGGER.debug("Overview.json fetch failed (W 724V): %s", exc)

            else:
                # Modern models: Overview first, then extended endpoints
                overview = await self._get_json(
                    "data/Overview.json",
                    referer="html/content/overview/index.html",
                )
                raw.update(overview)

                wlan_basic = await self._get_json(
                    "data/WLANBasic.json",
                    referer="html/content/network/wlan_basic.html",
                )
                raw.update(wlan_basic)

                wlan_settings = await self._get_json(
                    "data/WLANSettings.json",
                    referer="html/content/network/wlan_settings.html",
                )
                raw.update(wlan_settings)

                lan = await self._get_json(
                    "data/LAN.json",
                    referer="html/content/network/lan.html",
                )
                raw.update(lan)

                ip_data = await self._get_json(
                    "data/IPData.json",
                    referer="html/content/internet/con_ipdata.html",
                    auth=True,
                )
                raw.update(ip_data)

            # Heartbeat: Login.json GET fills missing fields regardless of model
            try:
                heartbeat = await self._get_json(
                    "data/Login.json",
                    referer="html/content/overview/index.html",
                )
                for k, v in heartbeat.items():
                    if k not in raw:
                        raw[k] = v
            except Exception as exc:
                _LOGGER.debug("Login.json heartbeat failed: %s", exc)

        except Exception as exc:
            _LOGGER.debug("Error fetching authenticated data: %s", exc)

        _LOGGER.debug("Merged raw keys: %s", list(raw.keys()))

        # Devices (Try multiple endpoints for broad compatibility)
        devices_raw: dict[str, Any] = {}
        for path in (
            "data/DeviceList.json",
            "data/HomeNetwork.json",
            "data/Modules.json",
        ):
            try:
                d_raw = await self._get_json(path)
                if d_raw:
                    devices_raw.update(d_raw)
            except Exception:
                continue

        return self._build_data(raw, devices_raw)

    def _build_data(
        self, raw: dict[str, Any], devices_raw: dict[str, Any]
    ) -> SpeedportData:
        """Build a SpeedportData object from raw API dictionaries."""
        all_data = {**devices_raw, **raw}

        def _int(val: Any, default: int | None = None) -> int | None:
            try:
                if val is None:
                    return default
                return int(val)
            except ValueError, TypeError:
                return default

        def _bool(val: Any) -> bool | None:
            if val is None:
                return None
            return str(val).strip().lower() in ("1", "true", "on", "yes", "online")

        # Parse connected devices
        devices: list[WlanDevice] = []
        device_keys = (
            "addmwlandevice",
            "addmwlandevice_5g",
            "addmwlan5device",
            "addmlandevice",
            "addmdevice",
            "wlandevice",
            "landevice",
            "device",
            "mdevice",
            "homenetwork",
            "lan1_device",
            "lan2_device",
            "lan3_device",
            "lan4_device",
        )
        for key in device_keys:
            entries = all_data.get(key, [])
            if not isinstance(entries, list):
                entries = [entries]
            for dev_entry in entries:
                if isinstance(dev_entry, dict) and any(
                    k in dev_entry
                    for k in (
                        "mdevice_mac",
                        "device_mac",
                        "mac",
                        "mdevice_name",
                        "device_name",
                    )
                ):
                    devices.append(WlanDevice.from_dict(dev_entry))

        # Filter out duplicates by MAC
        seen_macs = set()
        unique_devices: list[WlanDevice] = []
        for d in devices:
            if d.mac and d.mac.lower() not in seen_macs:
                seen_macs.add(d.mac.lower())
                unique_devices.append(d)

        # Extract firmware for legacy models (W 724V)
        firmware = str(raw.get("firmware_version", "")).strip()
        if not firmware and "domain_name" in raw:
            parts = str(raw["domain_name"]).split("_")
            if len(parts) >= 3:
                firmware = ".".join(parts[-3:])

        # Final fallback: look for anything that looks like a firmware version in raw keys
        if not firmware:
            for key, value in raw.items():
                if "firmware" in key.lower() and value and isinstance(value, str):
                    firmware = value
                    break

        _LOGGER.debug(
            "Extracted firmware version: %s (raw keys found: %s)",
            firmware,
            list(raw.keys()),
        )

        is_legacy = any(
            x in str(raw.get("domain_name", "")).upper()
            or x in str(raw.get("device_name", "")).upper()
            or x in str(raw.get("model_name", "")).upper()
            for x in ("W_724V", "W 724V")
        )

        dsl_down = _int(raw.get("dsl_downstream", raw.get("dsl_ds_synchro", 0)))
        dsl_up = _int(raw.get("dsl_upstream", raw.get("dsl_us_synchro", 0)))
        inet_down = _int(raw.get("inet_download", 0))
        inet_up = _int(raw.get("inet_upload", 0))

        if not is_legacy:
            # Modern models return bits/s, convert to kbits/s
            if dsl_down is not None:
                dsl_down = dsl_down // 1000
            if dsl_up is not None:
                dsl_up = dsl_up // 1000
            if inet_down is not None:
                inet_down = inet_down // 1000
            if inet_up is not None:
                inet_up = inet_up // 1000

        return SpeedportData(
            device_name=raw.get("device_name", raw.get("model_name", "Speedport")),
            firmware_version=firmware,
            serial_number=raw.get("serial_number", ""),
            mac=raw.get("mac", raw.get("lan_mac", raw.get("serial_number", ""))),
            online_status=raw.get("onlinestatus", raw.get("online_status", "")),
            router_state=raw.get("router_state", ""),
            # W 724V uses "dsl_link" or "dsl_link_status"
            dsl_link_status=raw.get(
                "dsl_link_status", raw.get("dsl_link", raw.get("status", ""))
            ),
            dsl_downstream=dsl_down,
            dsl_upstream=dsl_up,
            inet_download=inet_down,
            inet_upload=inet_up,
            # W 724V uptime (default to empty string if missing)
            inet_uptime=raw.get("inet_uptime", raw.get("onlinetime", "")),
            dsl_pop=raw.get("dsl_pop", raw.get("dsl_pop_name", "Unknown")),
            use_wlan=_bool(
                raw.get("use_wlan", raw.get("wlan_active", raw.get("wlan_state")))
            ),
            wlan_ssid=raw.get(
                "wlan_ssid",
                raw.get(
                    "ssid_24g", raw.get("ssid", raw.get("wlan_ssid_24g", "Unknown"))
                ),
            ),
            wlan_5ghz_ssid=raw.get(
                "wlan_5ghz_ssid",
                raw.get("ssid_5g", raw.get("wlan_ssid_5g", raw.get("ssid2", ""))),
            ),
            wlan_guest_active=_bool(
                raw.get(
                    "wlan_guest_active",
                    raw.get("use_guest_wlan", raw.get("hsfon_status")),
                )
            ),
            wlan_guest_ssid=raw.get(
                "wlan_guest_ssid",
                raw.get(
                    "ssid_guest",
                    raw.get(
                        "guest_ssid",
                        "Telekom_FON" if raw.get("hsfon_status") == "1" else "Unknown",
                    ),
                ),
            ),
            wlan_office_active=_bool(
                raw.get(
                    "wlan_office_active",
                    raw.get("use_office_wlan", raw.get("wlan_office_state")),
                )
            ),
            wlan_office_ssid=raw.get("wlan_office_ssid", ""),
            public_ip_v4=raw.get(
                "public_ip_v4",
                raw.get("ip_extern", raw.get("srv_ipv4_wan", raw.get("other_ip", ""))),
            ),
            public_ip_v6=raw.get(
                "public_ip_v6", raw.get("ip_v6_extern", raw.get("ip_v6", ""))
            ),
            dns_v4=raw.get(
                "dns_v4",
                raw.get("dns_v4_1", raw.get("dns_server1", raw.get("other_dns", ""))),
            ),
            dns_v6=raw.get("dns_v6", raw.get("dns_v6_1", "")),
            gateway_ip_v4=raw.get("gateway_ip_v4", raw.get("ip_gateway", "")),
            dualstack=_bool(raw.get("dualstack")),
            use_lte=_bool(raw.get("use_lte")),
            dsl_tunnel=_bool(raw.get("dsl_tunnel")),
            lte_tunnel=_bool(raw.get("lte_tunnel")),
            hybrid_tunnel=_bool(raw.get("hybrid_tunnel")),
            ex5g_signal_5g=raw.get("ex5g_signal_5g", ""),
            ex5g_freq_5g=raw.get("ex5g_freq_5g", ""),
            ex5g_signal_lte=raw.get("ex5g_signal_lte", ""),
            ex5g_freq_lte=raw.get("ex5g_freq_lte", ""),
            devices=unique_devices,
            raw=raw,
        )

    # Action methods
    async def reconnect(self) -> bool:
        """Reconnect the internet connection."""
        await self._ensure_auth()
        result = await self._post_json(
            "data/Connect.json",
            {"req_connect": "reconnect"},
            referer="html/content/internet/con_ipdata.html",
            auth=True,
        )
        return result.get("status") == "ok"

    async def reboot(self) -> bool:
        """Reboot the router."""
        await self._ensure_auth()
        result = await self._post_json(
            "data/Reboot.json",
            {"reboot_device": "true"},
            referer="html/content/config/restart.html",
            auth=True,
        )
        return result.get("status") == "ok"

    async def wps_on(self) -> bool:
        """Activate WPS."""
        await self._ensure_auth()
        result = await self._post_json(
            "data/WLANAccess.json",
            {"wlan_add": "on", "wps_key": "connect"},
            referer="html/content/network/wlan_wps.html",
        )
        return result.get("status") == "ok"

    async def get_update_info(self) -> dict[str, Any]:
        """Get firmware update information."""
        await self._ensure_auth()
        # First trigger a check
        await self._post_json(
            "data/Update.json",
            {"req_update": "check"},
            referer="html/content/config/check_for_updates.html",
        )
        # Then get the result
        return await self._get_json(
            "data/Update.json", referer="html/content/config/check_for_updates.html"
        )

    async def install_update(self) -> bool:
        """Trigger firmware update installation."""
        await self._ensure_auth()
        result = await self._post_json(
            "data/Update.json",
            {"req_update": "start"},
            referer="html/content/config/check_for_updates.html",
        )
        return result.get("status") == "ok"
