"""Tests for the Speedport API client."""

import re

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.speedport.api import SpeedportClient

from unittest.mock import AsyncMock, MagicMock

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
        mock_response_post_challenge.__aenter__ = AsyncMock(return_value=mock_response_post_challenge)
        mock_response_post_challenge.__aexit__ = AsyncMock(return_value=None)

        mock_response_get_token = MagicMock()
        mock_response_get_token.read = AsyncMock(return_value=b"var _httoken = 123456789;")
        mock_response_get_token.__aenter__ = AsyncMock(return_value=mock_response_get_token)
        mock_response_get_token.__aexit__ = AsyncMock(return_value=None)

        mock_response_post_login = MagicMock()
        mock_response_post_login.text = AsyncMock(return_value='[{"varid":"login","varvalue":"success"}]')
        mock_response_post_login.__aenter__ = AsyncMock(return_value=mock_response_post_login)
        mock_response_post_login.__aexit__ = AsyncMock(return_value=None)

        mock_response_get_activation = MagicMock()
        mock_response_get_activation.text = AsyncMock(return_value="<html></html>")
        mock_response_get_activation.__aenter__ = AsyncMock(return_value=mock_response_get_activation)
        mock_response_get_activation.__aexit__ = AsyncMock(return_value=None)
        # Also make it awaitable directly for the line `await self._session.get(...)`
        mock_response_get_activation_coro = AsyncMock(return_value=mock_response_get_activation)

        def mock_get(url, *args, **kwargs):
            url_str = str(url)
            if "html/login/index.html" in url_str:
                return mock_response_get_token
            if "html/content/overview/index.html" in url_str:
                return mock_response_get_activation_coro()
            return mock_response_get_activation_coro()

        def mock_post(url, *args, **kwargs):
            url_str = str(url)
            data = kwargs.get("data", "")
            if "getChallenge" in str(data):
                return mock_response_post_challenge
            return mock_response_post_login

        session.get = MagicMock(side_effect=mock_get)
        session.post = MagicMock(side_effect=mock_post)

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
        mock_status_unauth.text = AsyncMock(return_value='[{"varid":"domain_name","varvalue":"Speedport_W_724V"}]')
        mock_status_unauth.__aenter__ = AsyncMock(return_value=mock_status_unauth)
        mock_status_unauth.__aexit__ = AsyncMock(return_value=None)

        mock_status_auth = MagicMock()
        mock_status_auth.text = AsyncMock(return_value='[{"varid":"device_name","varvalue":"Speedport W 724V"},{"varid":"domain_name","varvalue":"Speedport_W_724V"}]')
        mock_status_auth.__aenter__ = AsyncMock(return_value=mock_status_auth)
        mock_status_auth.__aexit__ = AsyncMock(return_value=None)

        mock_empty_list = MagicMock()
        mock_empty_list.text = AsyncMock(return_value="[]")
        mock_empty_list.__aenter__ = AsyncMock(return_value=mock_empty_list)
        mock_empty_list.__aexit__ = AsyncMock(return_value=None)

        mock_phone_calls = MagicMock()
        mock_phone_calls.text = AsyncMock(return_value='[{"varid":"calls","varvalue":[{"type":"missed","num":"0176********","date":"25.06.26","time":"10:05","duration":"0:00","line":"0711******"}]}]')
        mock_phone_calls.__aenter__ = AsyncMock(return_value=mock_phone_calls)
        mock_phone_calls.__aexit__ = AsyncMock(return_value=None)

        mock_login_heartbeat = MagicMock()
        mock_login_heartbeat.text = AsyncMock(return_value='[{"varid":"device_name","varvalue":"Speedport W 724V"},{"varid":"domain_name","varvalue":"Speedport_W_724V"},{"varid":"onlinestatus","varvalue":"online"}]')
        mock_login_heartbeat.__aenter__ = AsyncMock(return_value=mock_login_heartbeat)
        mock_login_heartbeat.__aexit__ = AsyncMock(return_value=None)

        client._status_called = False

        def mock_get(url, *args, **kwargs):
            url_str = str(url)
            if "data/Status.json" in url_str:
                if not client._status_called:
                    client._status_called = True
                    return mock_status_unauth
                return mock_status_auth
            if "data/PhoneCalls.json" in url_str:
                return mock_phone_calls
            if "data/Login.json" in url_str:
                return mock_login_heartbeat
            return mock_empty_list

        session.get = MagicMock(side_effect=mock_get)

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
        mock_response_post.text = AsyncMock(return_value='[{"varid":"status","varvalue":"ok"}]')
        mock_response_post.__aenter__ = AsyncMock(return_value=mock_response_post)
        mock_response_post.__aexit__ = AsyncMock(return_value=None)

        session.get = MagicMock(return_value=mock_response_get)
        session.post = MagicMock(return_value=mock_response_post)

        success = await client.set_wifi(True)
        assert success is True

