"""Tests for the Speedport API client."""

import re

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.speedport.api import SpeedportClient

ROUTER_HOST = "192.168.178.200"
ROUTER_PASSWORD = "password"


@pytest.mark.asyncio
async def test_login_success_legacy():
    """Test successful legacy login (MD5)."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)

        with aioresponses() as m:
            # 1. Challenge attempt (Modern) - Fail
            m.post(
                re.compile(f"http://{ROUTER_HOST}/data/Login.json.*"),
                status=200,
                body="[]",
            )

            # 2. HTToken fetch
            m.get(
                re.compile(f"http://{ROUTER_HOST}/html/login/index.html.*"),
                status=200,
                body="var _httoken = 123456789;",
            )

            # 3. Login POST
            m.post(
                re.compile(f"http://{ROUTER_HOST}/data/Login.json.*"),
                status=200,
                body='[{"varid":"login","varvalue":"success"}]',
            )

            # 4. Session Activation
            m.get(
                re.compile(f"http://{ROUTER_HOST}/html/content/overview/index.html.*"),
                status=200,
                body="<html></html>",
            )

            await client.login()
            assert client.is_logged_in is True


@pytest.mark.asyncio
async def test_get_all_data_fallback():
    """Test data retrieval with Typ B fallback to Login.json."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)
        client._logged_in = True

        with aioresponses() as m:
            m.get(
                re.compile(f"http://{ROUTER_HOST}/data/Status.json.*"),
                status=200,
                body="[]",
            )
            m.get(
                re.compile(f"http://{ROUTER_HOST}/data/Overview.json.*"),
                status=200,
                body="[]",
            )
            m.get(
                re.compile(f"http://{ROUTER_HOST}/data/LAN.json.*"),
                status=200,
                body="[]",
            )
            m.get(
                re.compile(f"http://{ROUTER_HOST}/data/IPData.json.*"),
                status=200,
                body="[]",
            )
            m.get(
                re.compile(f"http://{ROUTER_HOST}/data/WLANBasic.json.*"),
                status=200,
                body="[]",
            )
            m.get(
                re.compile(f"http://{ROUTER_HOST}/data/Login.json.*"),
                status=200,
                body='[{"varid":"device_name","varvalue":"Speedport W 724V"},{"varid":"onlinestatus","varvalue":"online"}]',
            )

            data = await client.get_all_data()
            assert data.device_name == "Speedport W 724V"
            assert data.online_status == "online"


@pytest.mark.asyncio
async def test_set_wifi():
    """Test switching WiFi."""
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient(ROUTER_HOST, ROUTER_PASSWORD, session)
        client._logged_in = True

        with aioresponses() as m:
            m.get(
                re.compile(f"http://{ROUTER_HOST}/html/content/overview/index.html.*"),
                status=200,
                body="var _httoken = 987654321;",
            )
            m.post(
                re.compile(f"http://{ROUTER_HOST}/data/Modules.json.*"),
                status=200,
                body='[{"varid":"status","varvalue":"ok"}]',
            )

            success = await client.set_wifi(True)
            assert success is True
