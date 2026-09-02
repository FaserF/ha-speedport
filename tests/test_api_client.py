from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.speedport.api import SpeedportClient

ROUTER_HOST = "192.168.178.200"
ROUTER_PASSWORD = "password"


@pytest.mark.asyncio
async def test_login_success_legacy():
    """Test successful legacy login (MD5)."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)

        # 1. Challenge attempt (Modern) - returns Empty [] or fails
        # 2. HTToken fetch - returns token
        # 3. Login POST - returns success
        # 4. Session activation - returns HTML

        mock_response_post_challenge = MagicMock()
        mock_response_post_challenge.text = AsyncMock(return_value="[]")
        mock_response_post_challenge.__aenter__ = AsyncMock(
            return_value=mock_response_post_challenge
        )
        mock_response_post_challenge.__aexit__ = AsyncMock(return_value=None)

        mock_response_get_token = MagicMock()
        mock_response_get_token.read = AsyncMock(
            return_value=b"var _httoken = 123456789;"
        )
        mock_response_get_token.__aenter__ = AsyncMock(
            return_value=mock_response_get_token
        )
        mock_response_get_token.__aexit__ = AsyncMock(return_value=None)

        mock_response_post_login = MagicMock()
        mock_response_post_login.text = AsyncMock(
            return_value='[{"varid":"login","varvalue":"success"}]'
        )
        mock_response_post_login.__aenter__ = AsyncMock(
            return_value=mock_response_post_login
        )
        mock_response_post_login.__aexit__ = AsyncMock(return_value=None)

        mock_response_get_activation = MagicMock()
        mock_response_get_activation.text = AsyncMock(return_value="<html></html>")
        mock_response_get_activation.__aenter__ = AsyncMock(
            return_value=mock_response_get_activation
        )
        mock_response_get_activation.__aexit__ = AsyncMock(return_value=None)

        def mock_get(url, *args, **kwargs):
            url_str = str(url)
            if "html/login/index.html" in url_str:
                return mock_response_get_token
            return mock_response_get_activation

        def mock_post(url, *args, **kwargs):
            data = kwargs.get("data", "")
            if "getChallenge" in str(data):
                return mock_response_post_challenge
            return mock_response_post_login

        session.get = MagicMock(side_effect=mock_get)  # type: ignore[method-assign]
        session.post = MagicMock(side_effect=mock_post)  # type: ignore[method-assign]

        await client.login()
        assert client.is_logged_in is True


@pytest.mark.asyncio
async def test_get_all_data_fallback():
    """Test data retrieval with Typ B fallback to Login.json."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)
        client._logged_in = True

        from unittest.mock import AsyncMock, MagicMock

        # We construct mock responses for all requests.
        mock_status_unauth = MagicMock()
        mock_status_unauth.text = AsyncMock(
            return_value='[{"varid":"domain_name","varvalue":"Speedport_W_724V"}]'
        )
        mock_status_unauth.__aenter__ = AsyncMock(return_value=mock_status_unauth)
        mock_status_unauth.__aexit__ = AsyncMock(return_value=None)

        mock_status_auth = MagicMock()
        mock_status_auth.text = AsyncMock(
            return_value='[{"varid":"device_name","varvalue":"Speedport W 724V"},{"varid":"domain_name","varvalue":"Speedport_W_724V"}]'
        )
        mock_status_auth.__aenter__ = AsyncMock(return_value=mock_status_auth)
        mock_status_auth.__aexit__ = AsyncMock(return_value=None)

        mock_empty_list = MagicMock()
        mock_empty_list.text = AsyncMock(return_value="[]")
        mock_empty_list.__aenter__ = AsyncMock(return_value=mock_empty_list)
        mock_empty_list.__aexit__ = AsyncMock(return_value=None)

        mock_phone_calls = MagicMock()
        mock_phone_calls.text = AsyncMock(
            return_value='[{"varid":"calls","varvalue":[{"type":"missed","num":"0176********","date":"25.06.26","time":"10:05","duration":"0:00","line":"0711******"}]}]'
        )
        mock_phone_calls.__aenter__ = AsyncMock(return_value=mock_phone_calls)
        mock_phone_calls.__aexit__ = AsyncMock(return_value=None)

        mock_login_heartbeat = MagicMock()
        mock_login_heartbeat.text = AsyncMock(
            return_value='[{"varid":"device_name","varvalue":"Speedport W 724V"},{"varid":"domain_name","varvalue":"Speedport_W_724V"},{"varid":"onlinestatus","varvalue":"online"}]'
        )
        mock_login_heartbeat.__aenter__ = AsyncMock(return_value=mock_login_heartbeat)
        mock_login_heartbeat.__aexit__ = AsyncMock(return_value=None)

        status_called = [False]

        def mock_get(url, *args, **kwargs):
            url_str = str(url)
            if "data/Status.json" in url_str:
                if not status_called[0]:
                    status_called[0] = True
                    return mock_status_unauth
                return mock_status_auth
            if "data/PhoneCalls.json" in url_str:
                return mock_phone_calls
            if "data/Login.json" in url_str:
                return mock_login_heartbeat
            return mock_empty_list

        session.get = MagicMock(side_effect=mock_get)  # type: ignore[method-assign]
        session.post = MagicMock(return_value=mock_empty_list)  # type: ignore[method-assign]

        data = await client.get_all_data()
        assert data.device_name == "Speedport W 724V"
        assert data.online_status == "online"
        assert len(data.calls) == 1
        assert data.calls[0]["type"] == "missed"


@pytest.mark.asyncio
async def test_set_wifi():
    """Test switching WiFi."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)
        client._logged_in = True

        from unittest.mock import AsyncMock, MagicMock

        mock_response_get = MagicMock()
        mock_response_get.text = AsyncMock(return_value="var _httoken = 987654321;")
        mock_response_get.__aenter__ = AsyncMock(return_value=mock_response_get)
        mock_response_get.__aexit__ = AsyncMock(return_value=None)

        mock_response_post = MagicMock()
        mock_response_post.text = AsyncMock(
            return_value='[{"varid":"status","varvalue":"ok"}]'
        )
        mock_response_post.__aenter__ = AsyncMock(return_value=mock_response_post)
        mock_response_post.__aexit__ = AsyncMock(return_value=None)

        session.get = MagicMock(return_value=mock_response_get)  # type: ignore[method-assign]
        session.post = MagicMock(return_value=mock_response_post)  # type: ignore[method-assign]

        success = await client.set_wifi(True)
        assert success is True


@pytest.mark.asyncio
async def test_logout():
    """Test logout method."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)
        client._logged_in = True
        client._login_key = "dummy_key"

        from unittest.mock import AsyncMock, MagicMock

        mock_response_get = MagicMock()
        mock_response_get.read = AsyncMock(return_value=b"var _httoken = 987654321;")
        mock_response_get.text = AsyncMock(return_value="var _httoken = 987654321;")
        mock_response_get.__aenter__ = AsyncMock(return_value=mock_response_get)
        mock_response_get.__aexit__ = AsyncMock(return_value=None)

        mock_response_post = MagicMock()
        mock_response_post.text = AsyncMock(
            return_value='[{"varid":"status","varvalue":"ok"}]'
        )
        mock_response_post.__aenter__ = AsyncMock(return_value=mock_response_post)
        mock_response_post.__aexit__ = AsyncMock(return_value=None)

        session.get = MagicMock(return_value=mock_response_get)  # type: ignore[method-assign]
        session.post = MagicMock(return_value=mock_response_post)  # type: ignore[method-assign]

        await client.logout()
        assert client.is_logged_in is False
        assert client._login_key is None


@pytest.mark.asyncio
async def test_buttons_actions():
    """Test button actions: reboot, reconnect, wps_on."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)
        client._logged_in = True

        from unittest.mock import AsyncMock, MagicMock

        mock_get = MagicMock()
        mock_get.read = AsyncMock(return_value=b"httoken = 123456789;")
        mock_get.text = AsyncMock(return_value="httoken = 123456789;")
        mock_get.__aenter__ = AsyncMock(return_value=mock_get)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        mock_post = MagicMock()
        mock_post.text = AsyncMock(return_value='[{"varid":"status","varvalue":"ok"}]')
        mock_post.__aenter__ = AsyncMock(return_value=mock_post)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        session.get = MagicMock(return_value=mock_get)  # type: ignore[method-assign]
        session.post = MagicMock(return_value=mock_post)  # type: ignore[method-assign]

        assert await client.reboot() is True
        assert await client.reconnect() is True
        assert await client.wps_on() is True


@pytest.mark.asyncio
async def test_modern_ip_data():
    """Test modern router fetching IPData.json and populating IPv4 & IPv6."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)
        client._logged_in = True

        from unittest.mock import AsyncMock, MagicMock

        mock_token_page = MagicMock()
        mock_token_page.read = AsyncMock(return_value=b"httoken = 555666777;")
        mock_token_page.text = AsyncMock(return_value="httoken = 555666777;")
        mock_token_page.__aenter__ = AsyncMock(return_value=mock_token_page)
        mock_token_page.__aexit__ = AsyncMock(return_value=None)

        mock_status = MagicMock()
        mock_status.text = AsyncMock(
            return_value='[{"varid":"device_name","varvalue":"Speedport Smart 4"}]'
        )
        mock_status.__aenter__ = AsyncMock(return_value=mock_status)
        mock_status.__aexit__ = AsyncMock(return_value=None)

        mock_ip_data = MagicMock()
        mock_ip_data.text = AsyncMock(
            return_value='[{"varid":"public_ip_v4","varvalue":"93.184.216.34"},{"varid":"public_ip_v6","varvalue":"2001:db8::1"}]'
        )
        mock_ip_data.__aenter__ = AsyncMock(return_value=mock_ip_data)
        mock_ip_data.__aexit__ = AsyncMock(return_value=None)

        mock_empty = MagicMock()
        mock_empty.text = AsyncMock(return_value="[]")
        mock_empty.__aenter__ = AsyncMock(return_value=mock_empty)
        mock_empty.__aexit__ = AsyncMock(return_value=None)

        def mock_get_handler(url, *args, **kwargs):
            url_str = str(url)
            if "con_ipdata.html" in url_str:
                return mock_token_page
            if "data/IPData.json" in url_str:
                return mock_ip_data
            if "data/Status.json" in url_str:
                return mock_status
            return mock_empty

        session.get = MagicMock(side_effect=mock_get_handler)  # type: ignore[method-assign]
        session.post = MagicMock(return_value=mock_empty)  # type: ignore[method-assign]

        data = await client.get_all_data()
        assert data.public_ip_v4 == "93.184.216.34"
        assert data.public_ip_v6 == "2001:db8::1"


@pytest.mark.asyncio
async def test_totr64_stats():
    """Test ToTR64 SOAP traffic & bandwidth counter retrieval."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)

        soap_response_1 = """<?xml version="1.0" encoding="UTF-8"?>
<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">
  <soap-env:Body>
    <cwmp:GetParameterValuesResponse xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
      <ParameterList>
        <ParameterValueStruct>
          <Name>Device.IP.Interface.5.Stats.BytesReceived</Name>
          <Value xsi:type="xsd:unsignedLong">10000000</Value>
        </ParameterValueStruct>
        <ParameterValueStruct>
          <Name>Device.IP.Interface.5.Stats.BytesSent</Name>
          <Value xsi:type="xsd:unsignedLong">5000000</Value>
        </ParameterValueStruct>
      </ParameterList>
    </cwmp:GetParameterValuesResponse>
  </soap-env:Body>
</soap-env:Envelope>"""

        soap_response_2 = """<?xml version="1.0" encoding="UTF-8"?>
<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">
  <soap-env:Body>
    <cwmp:GetParameterValuesResponse xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
      <ParameterList>
        <ParameterValueStruct>
          <Name>Device.IP.Interface.5.Stats.BytesReceived</Name>
          <Value xsi:type="xsd:unsignedLong">11250000</Value>
        </ParameterValueStruct>
        <ParameterValueStruct>
          <Name>Device.IP.Interface.5.Stats.BytesSent</Name>
          <Value xsi:type="xsd:unsignedLong">5625000</Value>
        </ParameterValueStruct>
      </ParameterList>
    </cwmp:GetParameterValuesResponse>
  </soap-env:Body>
</soap-env:Envelope>"""

        mock_post_1 = MagicMock()
        mock_post_1.text = AsyncMock(return_value=soap_response_1)
        mock_post_1.__aenter__ = AsyncMock(return_value=mock_post_1)
        mock_post_1.__aexit__ = AsyncMock(return_value=None)

        session.post = MagicMock(return_value=mock_post_1)  # type: ignore[method-assign]

        # First sample
        with patch("custom_components.speedport.api.time.time", return_value=100.0):
            stats1 = await client._get_totr64_stats()
            assert stats1["bytes_received"] == 10000000
            assert stats1["bytes_sent"] == 5000000
            assert "bandwidth_download" not in stats1

        # Second sample after exactly 1.0s
        mock_post_2 = MagicMock()
        mock_post_2.text = AsyncMock(return_value=soap_response_2)
        mock_post_2.__aenter__ = AsyncMock(return_value=mock_post_2)
        mock_post_2.__aexit__ = AsyncMock(return_value=None)

        session.post = MagicMock(return_value=mock_post_2)  # type: ignore[method-assign]

        with patch("custom_components.speedport.api.time.time", return_value=101.0):
            stats2 = await client._get_totr64_stats()
            assert stats2["bytes_received"] == 11250000
            assert stats2["bytes_sent"] == 5625000
            assert (
                stats2["bandwidth_download"] == 10.0
            )  # 1,250,000 bytes * 8 / 1s / 1,000,000 = 10.0 Mbit/s
            assert (
                stats2["bandwidth_upload"] == 5.0
            )  # 625,000 bytes * 8 / 1s / 1,000,000 = 5.0 Mbit/s


@pytest.mark.asyncio
async def test_encrypted_response_key_fallback():
    """Test fallback key decryption when endpoint is encrypted with session key instead of default key."""
    from custom_components.speedport.api import _encode

    session_key = "11223344556677889900aabbccddeeff00112233445566778899aabbccddeeff"
    payload = '[{"varid":"lan_ip","varvalue":"192.168.178.1"},{"varid":"homenetwork","varvalue":"online"}]'
    encrypted_with_session_key = _encode(payload, session_key)

    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)
        client._encrypted_mode = True
        client._login_key = session_key

        mock_resp = MagicMock()
        mock_resp.text = AsyncMock(return_value=encrypted_with_session_key)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        session.get = MagicMock(return_value=mock_resp)  # type: ignore[method-assign]

        # Fetch with auth=False (which uses DEFAULT_KEY as primary key)
        # Should gracefully fall back to _login_key and succeed!
        data = await client._get_json("data/LAN.json", auth=False)
        assert data.get("lan_ip") == "192.168.178.1"
        assert data.get("homenetwork") == "online"


@pytest.mark.asyncio
async def test_per_page_httoken_caching():
    """Test that CSRF tokens are cached per HTML page URL."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)

        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(
            side_effect=[
                b"<html><script>var httoken = '111111';</script></html>",
                b"<html><script>var httoken = '222222';</script></html>",
            ]
        )
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        session.get = MagicMock(return_value=mock_resp)  # type: ignore[method-assign]

        t1 = await client._get_httoken(
            "http://192.168.2.1/html/content/overview/index.html"
        )
        assert t1 == "111111"
        assert (
            client._cached_httokens[
                "http://192.168.2.1/html/content/overview/index.html"
            ]
            == "111111"
        )

        t2 = await client._get_httoken(
            "http://192.168.2.1/html/content/network/devices.html"
        )
        assert t2 == "222222"
        assert (
            client._cached_httokens[
                "http://192.168.2.1/html/content/network/devices.html"
            ]
            == "222222"
        )

        # Subsequent call to same page uses cache
        t1_cached = await client._get_httoken(
            "http://192.168.2.1/html/content/overview/index.html"
        )
        assert t1_cached == "111111"
        assert mock_resp.read.call_count == 2
