"""Telekom Speedport API client.

Supports multiple generations of Speedport routers:
- Older models (e.g. W 724V): Plain JSON, MD5 login, httoken CSRF.
- Newer models (e.g. Smart 3/4, Pro): AES-CCM encrypted JSON, SHA256 challenge-response login.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from contextlib import suppress
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
        _LOGGER.debug("Failed to parse JSON response: %s", exc)
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
        self._token: str | None = None  # httoken / _tn for legacy models
        self._cached_httoken: str | None = (
            None  # Cached CSRF token (modern) to avoid per-request HTML page loads
        )
        # ToTR64 / CWMP Byte counter & bandwidth state
        self._totr64_enabled: bool = True
        self._totr64_backoff_until: float = 0.0
        self._totr64_interface_idx: int | None = None
        self._prev_bytes_received: int | None = None
        self._prev_bytes_sent: int | None = None
        self._prev_bytes_time: float | None = None

    async def logout(self) -> None:
        """Log out from the Speedport."""
        if not self._logged_in:
            return
        try:
            # Use unencrypted logout POST — the encrypted variant (auth=True) consistently
            # fails with "MAC check failed" on the Smart 4R Typ B when the session has
            # drifted during a poll cycle.  The plain POST is sufficient to release the
            # router's single-session slot.
            referer = "html/content/overview/index.html"
            with suppress(Exception):
                res = await self._post_json(
                    "data/Login.json",
                    {"logout": "byby"},
                    referer=referer,
                    auth=False,
                )
                _LOGGER.debug("Logout response: %s", res)
        except Exception as exc:
            _LOGGER.debug("Logout failed: %s", exc)
        finally:
            self._logged_in = False
            self._login_key = None
            self._token = None
            self._cached_httoken = None
            if (
                hasattr(self._session, "cookie_jar")
                and self._session.cookie_jar is not None
            ):
                with suppress(Exception):
                    self._session.cookie_jar.clear_domain(self._host)
                with suppress(Exception):
                    self._session.cookie_jar.clear()
            # Close all pooled TCP connections to this router host.
            # The Smart 4R Typ B tracks sessions at the TCP level — an open keep-alive
            # connection keeps the session slot occupied even after a cookie logout.
            # Closing the connector's cached connections ensures the router can
            # immediately free its session slot for the Telekom Zuhause / MeinMagenta app.
            with suppress(Exception):
                connector = getattr(self._session, "connector", None)
                if connector is not None and hasattr(connector, "_conns"):
                    # aiohttp TCPConnector stores connections keyed by (host, port, ssl)
                    keys_to_close = [
                        k for k in connector._conns if self._host in str(k)
                    ]
                    for key in keys_to_close:
                        for proto in connector._conns.pop(key, []):
                            with suppress(Exception):
                                proto.close()

    async def close(self) -> None:
        """Close the client session and resources."""
        await self.logout()
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def is_logged_in(self) -> bool:
        """Return True if authenticated."""
        return self._logged_in

    def _req_kwargs(self) -> dict[str, Any]:
        """Default request kwargs with browser-like headers."""
        return {
            "ssl": False,
            "timeout": aiohttp.ClientTimeout(total=10),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                # Connection: close — force the router to tear down the TCP connection
                # after each response.  The Smart 4R Typ B tracks sessions at the TCP
                # level: while an HTTP keep-alive connection is open to the router the
                # session slot stays occupied, blocking the Telekom Zuhause app even
                # after a cookie-level logout.
                "Connection": "close",
            },
        }

    async def _get_httoken(
        self, page_url: str, force_refresh: bool = False, no_cache: bool = False
    ) -> str:
        """Fetch a page and extract the httoken CSRF value (Legacy & Modern).

        On modern models the token is cached after the first successful fetch
        within a session, reducing HTML page loads from O(N endpoints) to O(1)
        per poll cycle.  Pass force_refresh=True after a login to prime the cache.
        Pass no_cache=True (e.g. for POST action commands) to always fetch fresh
        from the given page without updating the poll-cycle cache.
        """
        # Return cached token if already present to avoid redundant HTML page fetches
        if not force_refresh and not no_cache and self._cached_httoken:
            return self._cached_httoken

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            }
            async with self._session.get(
                page_url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                raw = await resp.read()
                text = raw.decode("latin-1", errors="replace")
                if match := re.search(
                    r"(?:_httoken|httoken|_tn)\s*=\s*['\"]?(\d+)", text
                ):
                    token = match.group(1)
                    _LOGGER.debug("Found httoken from %s", page_url)
                    if not no_cache:
                        self._cached_httoken = token
                    return token
        except Exception as exc:
            _LOGGER.debug("Could not get httoken from %s: %s", page_url, exc)
        return self._cached_httoken or ""

    async def _get_json(
        self, path: str, referer: str = "", auth: bool = False
    ) -> dict[str, Any]:
        """Perform a GET request and parse the JSON response."""
        url = f"{self._base_url}/{path}"
        kwargs = self._req_kwargs()
        headers = dict(kwargs.get("headers", {}))
        headers["X-Requested-With"] = "XMLHttpRequest"

        if referer:
            ref_url = f"{self._base_url}/{referer}"
            headers["Referer"] = ref_url
            if hasattr(self, "_token") and self._token and not self._encrypted_mode:
                url += f"?_tn={self._token}"
            else:
                token = await self._get_httoken(ref_url)
                if not token and hasattr(self, "_token") and self._token:
                    token = self._token
                if token:
                    url += f"?_tn={token}"
        elif hasattr(self, "_token") and self._token:
            url += f"?_tn={self._token}"
            if not referer:
                headers["Referer"] = f"{self._base_url}/html/login/index.html"

        try:
            async with self._session.get(
                url,
                headers=headers,
                **{k: v for k, v in kwargs.items() if k != "headers"},
            ) as resp:
                text = await resp.text(errors="replace")

                # Robust parsing: if it redirects to login, the token has expired.
                # On modern routers (Smart 4R) the session cookie may still be valid,
                # so we only invalidate the cached httoken rather than forcing a full
                # re-login on every poll cycle.
                if (
                    "Document moved" in text
                    or "login/index.html" in text
                    or "login_index_html" in text
                ):
                    _LOGGER.debug("Session expired or redirected to login for %s", path)
                    # Invalidate cached token but keep session alive
                    self._cached_httoken = None
                    return {}

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
        self, path: str, data: dict[str, Any], referer: str = "", auth: bool = True
    ) -> dict[str, Any]:
        """Perform a POST request and parse the JSON response."""
        url = f"{self._base_url}/{path}"
        kwargs = self._req_kwargs()
        headers = dict(kwargs.get("headers", {}))
        headers["X-Requested-With"] = "XMLHttpRequest"

        if referer:
            ref_url = f"{self._base_url}/{referer}"
            headers["Referer"] = ref_url
            if hasattr(self, "_token") and self._token and not self._encrypted_mode:
                data = {**data, "_tn": self._token}
            else:
                # Always fetch httoken fresh from the correct referer page for POST requests.
                # The Smart 4 router validates that the httoken matches the Referer page —
                # a cached token from overview/index.html is silently rejected when the
                # Referer is con_ipdata.html or similar.  The reference implementation
                # (Andre0512/speedport-api) always fetches httoken fresh for every POST.
                token = await self._get_httoken(ref_url, no_cache=True)
                if not token and hasattr(self, "_token") and self._token:
                    token = self._token
                if token:
                    data = {**data, "httoken" if self._encrypted_mode else "_tn": token}
        elif hasattr(self, "_token") and self._token and not self._encrypted_mode:
            data = {**data, "_tn": self._token}

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

                # Detect session expiry in POST responses (router redirects to login)
                if (
                    "Document moved" in text
                    or "login/index.html" in text
                    or "login_index_html" in text
                ):
                    _LOGGER.debug(
                        "POST session expired or redirected to login for %s", path
                    )
                    self._cached_httoken = None
                    self._logged_in = False
                    return {}

                return _parse_response(text, key)
        except aiohttp.ClientError as exc:
            raise SpeedportConnectionError(f"POST {url} failed: {exc}") from exc

    async def set_wifi(self, on: bool) -> bool:
        """Turn WiFi on or off."""
        return await self._set_module_state(
            {"use_wlan": "1" if on else "0"},
            referer="html/content/network/wlan_basic.html",
        )

    async def set_wifi_guest(self, on: bool) -> bool:
        """Turn Guest WiFi on or off."""
        referer = "html/content/network/wlan_guest.html"
        data = {"wlan_guest_active": "1" if on else "0"}
        try:
            res = await self._post_json(
                "data/WLANBasic.json", data, referer=referer, auth=True
            )
            if res.get("status") == "ok":
                return True
        except Exception:
            pass
        return await self._set_module_state(data, referer=referer)

    async def set_wifi_office(self, on: bool) -> bool:
        """Turn Office WiFi on or off."""
        referer = "html/content/network/wlan_office.html"
        data = {"wlan_office_active": "1" if on else "0"}
        try:
            res = await self._post_json(
                "data/WLANBasic.json", data, referer=referer, auth=True
            )
            if res.get("status") == "ok":
                return True
        except Exception:
            pass
        return await self._set_module_state(data, referer=referer)

    async def _set_module_state(
        self, data: dict[str, str], referer: str = "html/content/overview/index.html"
    ) -> bool:
        """Set a module state via Modules.json."""
        await self._ensure_auth()
        result = await self._post_json(
            "data/Modules.json", data, referer=referer, auth=True
        )
        return bool(result) or result.get("status") == "ok"

    async def _get_challenge(self) -> str | None:
        """Get login challenge (Modern)."""
        data = {"getChallenge": "1"}
        # referer="" to avoid producing a double-slash URL (http://router-ip//)
        result = await self._post_json("data/Login.json", data, referer="", auth=False)
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
                    # Prime the httoken cache once after login so that subsequent
                    # _get_json calls don't each need to load a full HTML page.
                    # This reduces HTTP requests per poll from ~18 to ~8.
                    with suppress(Exception):
                        await self._get_httoken(
                            f"{self._base_url}/html/content/overview/index.html",
                            force_refresh=True,
                        )
                    return
        except SpeedportConnectionError:
            # Re-raise connection error immediately to fail fast when host is unreachable
            raise
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
                        async with self._session.get(
                            f"{self._base_url}/html/content/overview/index.html?lang=de",
                            headers=nav_headers,
                            **{k: v for k, v in kwargs.items() if k != "headers"},
                        ):
                            pass
                        self._logged_in = True
                        _LOGGER.info(
                            "Successfully logged in (Legacy mode) to %s", self._host
                        )
                        return
            except aiohttp.ClientError as exc:
                # If we get a connection error, do not loop over other bodies
                raise SpeedportConnectionError(f"Login request failed: {exc}") from exc
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
        device_name = str(raw.get("device_name", ""))
        model_name = str(raw.get("model_name", ""))
        is_legacy_w724v = any(
            x in domain_name or x in device_name or x in model_name
            for x in ("W_724V", "W 724V")
        )
        _LOGGER.debug(
            "Model detection: domain_name=%s, device_name=%s, model_name=%s, is_legacy_w724v=%s",
            domain_name,
            device_name,
            model_name,
            is_legacy_w724v,
        )

        # Auth required for the rest
        await self._ensure_auth()

        if is_legacy_w724v:
            # For W 724V: fetch Status.json again after auth (session cookie may unlock more fields)
            _LOGGER.debug("Legacy W 724V detected — fetching authenticated Status.json")
            try:
                status_auth = await self._get_json(
                    "data/Status.json", referer="html/login/index.html"
                )
                raw.update(status_auth)
            except Exception as exc:
                _LOGGER.debug("Status.json auth fetch failed (W 724V): %s", exc)

            # W 724V fallback endpoints for WLAN and DSL details concurrently
            legacy_eps = [
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
                ("data/PhoneCalls.json", "html/content/phone/phone_list.html"),
            ]
            legacy_results = await asyncio.gather(
                *(self._get_json(ep, referer=ref) for ep, ref in legacy_eps),
                return_exceptions=True,
            )
            for res in legacy_results:
                if isinstance(res, dict):
                    raw.update(res)

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
            # Modern models (Smart 3, Smart 4, Smart 4R, Pro):
            # The router web server handles only ONE authenticated request at a time
            # with the same session token — parallel requests all return "Session expired".
            # We fetch endpoints sequentially; the small latency cost (~200 ms) is
            # far outweighed by eliminating the session conflicts that lock out the
            # Telekom Zuhause / MeinMagenta apps.
            for path, referer, auth in (
                ("data/Overview.json", "html/content/overview/index.html", False),
                (
                    "data/SecureStatus.json",
                    "html/content/overview/index.html",
                    True,
                ),
                (
                    "data/WLANBasic.json",
                    "html/content/network/wlan_basic.html",
                    False,
                ),
                (
                    "data/WLANSettings.json",
                    "html/content/network/wlan_settings.html",
                    False,
                ),
                ("data/LAN.json", "html/content/network/lan.html", False),
                # IPData.json is encrypted with DEFAULT_KEY on modern routers
                # (not with the session login_key), so auth=False is correct here.
                # Using auth=True would pick _login_key for decryption and produce
                # garbage/empty output on Speedport Smart 4 Typ B.
                (
                    "data/IPData.json",
                    "html/content/internet/con_ipdata.html",
                    False,
                ),
                # data/Internet.json is an alternative endpoint used on some firmwares
                (
                    "data/Internet.json",
                    "html/content/internet/con_ipdata.html",
                    False,
                ),
                (
                    "data/PhoneCalls.json",
                    "html/content/phone/phone_list.html",
                    True,
                ),
            ):
                try:
                    result = await self._get_json(path, referer=referer, auth=auth)
                    if result:
                        raw.update(result)
                except Exception as exc:
                    _LOGGER.debug("Failed to fetch %s: %s", path, exc)

            # IPData fallback: if we still didn't get any public IP field, try
            # SecureStatus with auth=True as last resort — some firmwares include
            # IP addresses there.
            _ip_fields = (
                "public_ip_v4",
                "ip_extern",
                "srv_ipv4_wan",
                "wan_ip4_addr",
                "wan_ip_address",
                "wan_ipv4",
                "onlineipv4",
                "other_ip",
                "ip_v4",
            )
            if not any(raw.get(f) for f in _ip_fields):
                try:
                    ip_fallback = await self._get_json(
                        "data/IPData.json",
                        referer="html/content/internet/con_ipdata.html",
                        auth=True,
                    )
                    if ip_fallback:
                        raw.update(ip_fallback)
                except Exception as exc:
                    _LOGGER.debug("IPData auth fallback failed: %s", exc)

        # Heartbeat: Login.json GET fills missing fields regardless of model
        try:
            heartbeat = await self._get_json(
                "data/Login.json",
                referer="html/content/overview/index.html",
            )
            for k, v in heartbeat.items():
                if k not in raw or not raw[k]:
                    raw[k] = v
        except Exception as exc:
            _LOGGER.debug("Login.json heartbeat failed: %s", exc)

        _LOGGER.debug("Merged raw keys: %s", list(raw.keys()))

        # Devices — fetch sequentially to avoid session conflicts on modern routers.
        # Try DeviceList first (most reliable); fall back to HomeNetwork then Modules.
        devices_raw: dict[str, Any] = {}
        for device_path in (
            "data/DeviceList.json",
            "data/HomeNetwork.json",
            "data/Modules.json",
        ):
            try:
                d_raw = await self._get_json(device_path)
                if isinstance(d_raw, dict) and d_raw:
                    devices_raw.update(d_raw)
                    # If DeviceList gave us actual device data, skip the rest
                    if device_path == "data/DeviceList.json" and d_raw:
                        break
            except Exception as exc:
                _LOGGER.debug("Failed to fetch %s: %s", device_path, exc)

        # ToTR64 / CWMP Traffic & Bandwidth stats (Port 5438)
        totr64_stats = await self._get_totr64_stats()

        return self._build_data(raw, devices_raw, totr64_stats=totr64_stats)

    async def _get_totr64_stats(self) -> dict[str, Any]:
        """Fetch byte counters from ToTR64 SOAP endpoint (Port 5438)."""
        now = time.time()
        if not self._totr64_enabled or now < self._totr64_backoff_until:
            return {}

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "urn:telekom-de:device:TO_InternetGatewayDevice:2#GetParameterValues",
            "Connection": "close",
        }

        # Try cached interface index first, or default to 5 (BONDING/habond), fallback candidates
        candidate_indices: list[int] = []
        if self._totr64_interface_idx is not None:
            candidate_indices.append(self._totr64_interface_idx)
        for idx in (5, 1, 2, 3, 4, 6):
            if idx not in candidate_indices:
                candidate_indices.append(idx)

        url = f"http://{self._host}:5438/"

        for idx in candidate_indices:
            # We query the exact 2 parameters that the CWMP schema expects.
            # Querying more or nonexistent parameters causes CWMP server on Smart 4 to return empty / fault.
            body = f"""<soap-env:Envelope
    xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:cwmp="urn:telekom-de.totr64-2-n">
  <soap-env:Body>
    <cwmp:GetParameterValues xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
      <cwmp:ParameterNames length="2">
        <xsd:string>Device.IP.Interface.{idx}.Stats.BytesReceived</xsd:string>
        <xsd:string>Device.IP.Interface.{idx}.Stats.BytesSent</xsd:string>
      </cwmp:ParameterNames>
    </cwmp:GetParameterValues>
  </soap-env:Body>
</soap-env:Envelope>"""
            try:
                async with self._session.post(
                    url,
                    data=body,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    text = await resp.text(errors="replace")

                    if "9801" in text:
                        _LOGGER.debug(
                            "ToTR64 SOAP fault 9801 (session active), backing off for 30s"
                        )
                        self._totr64_backoff_until = now + 30.0
                        return {}

                    # Parse BytesReceived and BytesSent
                    rx_match = re.search(
                        r"BytesReceived</Name>\s*<Value[^>]*>(\d+)</Value>", text
                    )
                    if not rx_match:
                        rx_match = re.search(
                            r"Device\.IP\.Interface\.\d+\.Stats\.BytesReceived.*?(\d+)",
                            text,
                            re.DOTALL,
                        )

                    tx_match = re.search(
                        r"BytesSent</Name>\s*<Value[^>]*>(\d+)</Value>", text
                    )
                    if not tx_match:
                        tx_match = re.search(
                            r"Device\.IP\.Interface\.\d+\.Stats\.BytesSent.*?(\d+)",
                            text,
                            re.DOTALL,
                        )

                    if rx_match and tx_match:
                        rx_bytes = int(rx_match.group(1))
                        tx_bytes = int(tx_match.group(1))
                        self._totr64_interface_idx = idx

                        stats: dict[str, Any] = {
                            "bytes_received": rx_bytes,
                            "bytes_sent": tx_bytes,
                        }

                        # Check for IPv4 / IPv6 addresses in SOAP response
                        ipv4_match = re.search(
                            r"IPv4Address\.\d+\.IPAddress</Name>\s*<Value[^>]*>([0-9\.]+)</Value>",
                            text,
                        )
                        if ipv4_match and ipv4_match.group(1) not in ("0.0.0.0", ""):
                            stats["totr64_ipv4"] = ipv4_match.group(1)

                        ipv6_match = re.search(
                            r"IPv6Address\.\d+\.IPAddress</Name>\s*<Value[^>]*>([0-9a-fA-F:]+)</Value>",
                            text,
                        )
                        if ipv6_match and ipv6_match.group(1) not in ("::", ""):
                            stats["totr64_ipv6"] = ipv6_match.group(1)

                        # Check for DNS Server in SOAP response
                        dns_match = re.search(
                            r"DNSServer(?:s)?</Name>\s*<Value[^>]*>([0-9\., ]+)</Value>",
                            text,
                        )
                        if dns_match and dns_match.group(1).strip() not in (
                            "0.0.0.0",
                            "",
                        ):
                            # Take first DNS if comma-separated
                            stats["totr64_dns_v4"] = (
                                dns_match.group(1).split(",")[0].strip()
                            )

                        # Compute bandwidth rates if we have previous sample
                        if (
                            self._prev_bytes_received is not None
                            and self._prev_bytes_sent is not None
                            and self._prev_bytes_time is not None
                        ):
                            elapsed = now - self._prev_bytes_time

                            if elapsed > 0.5:
                                delta_rx = rx_bytes - self._prev_bytes_received
                                delta_tx = tx_bytes - self._prev_bytes_sent

                                # Check for counter reset / reboot (delta >= 0)
                                if delta_rx >= 0 and delta_tx >= 0:
                                    # Mbit/s = (bytes * 8) / (elapsed * 1_000_000)
                                    stats["bandwidth_download"] = round(
                                        (delta_rx * 8) / (elapsed * 1_000_000), 3
                                    )
                                    stats["bandwidth_upload"] = round(
                                        (delta_tx * 8) / (elapsed * 1_000_000), 3
                                    )

                        self._prev_bytes_received = rx_bytes
                        self._prev_bytes_sent = tx_bytes
                        self._prev_bytes_time = now
                        return stats

            except aiohttp.ClientConnectorError:
                # Port 5438 is closed / not supported on older models like W 724V
                _LOGGER.debug(
                    "ToTR64 port 5438 not available on %s, disabling", self._host
                )
                self._totr64_enabled = False
                return {}
            except Exception as exc:
                _LOGGER.debug("ToTR64 stats fetch failed for index %d: %s", idx, exc)

        return {}

    def _build_data(
        self,
        raw: dict[str, Any],
        devices_raw: dict[str, Any],
        totr64_stats: dict[str, Any] | None = None,
    ) -> SpeedportData:
        """Build a SpeedportData object from raw API dictionaries."""
        all_data = {**devices_raw, **raw}
        totr64_stats = totr64_stats or {}

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
                raw.get(
                    "ip_extern",
                    raw.get(
                        "srv_ipv4_wan",
                        raw.get(
                            "wan_ip4_addr",
                            raw.get(
                                "wan_ip_address",
                                raw.get(
                                    "wan_ipv4",
                                    raw.get(
                                        "other_ip",
                                        raw.get(
                                            "ip_v4",
                                            totr64_stats.get("totr64_ipv4", ""),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            public_ip_v6=raw.get(
                "public_ip_v6",
                raw.get(
                    "ip_v6_extern",
                    raw.get(
                        "srv_ipv6_wan",
                        raw.get(
                            "wan_ip6_addr",
                            raw.get(
                                "wan_ipv6",
                                raw.get(
                                    "transmitted_ip_v6_pool_for_lan",
                                    raw.get(
                                        "used_ip_v6_lan",
                                        raw.get(
                                            "other_ip6",
                                            raw.get(
                                                "ip_v6",
                                                totr64_stats.get("totr64_ipv6", ""),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            dns_v4=raw.get(
                "dns_v4",
                raw.get(
                    "dns_v4_1",
                    raw.get(
                        "dns_server1",
                        raw.get("other_dns", totr64_stats.get("totr64_dns_v4", "")),
                    ),
                ),
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
            bytes_received=totr64_stats.get("bytes_received"),
            bytes_sent=totr64_stats.get("bytes_sent"),
            bandwidth_download=totr64_stats.get("bandwidth_download"),
            bandwidth_upload=totr64_stats.get("bandwidth_upload"),
            devices=unique_devices,
            calls=raw.get("calls", []),
            raw=raw,
        )

    # Action methods
    async def _post_with_retry(
        self,
        path: str,
        data: dict[str, Any],
        referer: str,
        success_keys: dict[str, str],
    ) -> bool:
        """POST an action, re-login once if session has expired, then check success."""
        await self._ensure_auth()
        result = await self._post_json(path, data, referer=referer, auth=True)
        if not result:
            # Session may have expired between polls — force fresh login and retry once
            _LOGGER.debug("POST %s returned empty, forcing re-login and retry", path)
            self._logged_in = False
            await self.login()
            result = await self._post_json(path, data, referer=referer, auth=True)
        return (
            bool(result)
            or result.get("status") == "ok"
            or any(result.get(k) == v for k, v in success_keys.items())
        )

    async def reconnect(self) -> bool:
        """Reconnect the internet connection."""
        return await self._post_with_retry(
            "data/Connect.json",
            {"req_connect": "reconnect"},
            referer="html/content/internet/con_ipdata.html",
            success_keys={"req_connect": "reconnect"},
        )

    async def reboot(self) -> bool:
        """Reboot the router."""
        return await self._post_with_retry(
            "data/Reboot.json",
            {"reboot_device": "true"},
            referer="html/content/config/restart.html",
            success_keys={"reboot_device": "true"},
        )

    async def wps_on(self) -> bool:
        """Activate WPS."""
        return await self._post_with_retry(
            "data/WLANAccess.json",
            {"wlan_add": "on", "wps_key": "connect"},
            referer="html/content/network/wlan_wps.html",
            success_keys={"wlan_add": "on"},
        )

    async def get_update_info(self, check: bool = False) -> dict[str, Any]:
        """Get firmware update information."""
        await self._ensure_auth()
        if check:
            with suppress(Exception):
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
