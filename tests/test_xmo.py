"""Offline tests for the Pro Plus extension; no real router is contacted."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.speedport.api import (
    SagemcomXmoClient,
    SpeedportAuthError,
    SpeedportClient,
)


@pytest.mark.asyncio
async def test_xmo_login_uses_session_token_for_following_requests():
    response = MagicMock()
    response.status = 200
    response.text = AsyncMock(
        side_effect=[
            json.dumps(
                {
                    "reply": {
                        "error": {"description": "XMO_REQUEST_NO_ERR"},
                        "actions": [
                            {
                                "callbacks": [
                                    {
                                        "parameters": {
                                            "id": 7,
                                            "nonce": "example-server-nonce",
                                            "token": "example-session-token",
                                        }
                                    }
                                ]
                            }
                        ],
                    }
                }
            ),
            json.dumps(
                {
                    "reply": {
                        "error": {"description": "XMO_REQUEST_NO_ERR"},
                        "actions": [{"callbacks": [{"parameters": {"value": "Up"}}]}],
                    }
                }
            ),
        ]
    )
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    async with aiohttp.ClientSession() as session:
        with patch.object(session, "post", return_value=response) as post:
            client = SagemcomXmoClient("router.example", "example-password", session)
            await client.login()
            values = await client.get_values_by_xpaths({"status": "Device/Status"})

        assert values == {"status": "Up"}
        login = json.loads(post.call_args_list[0].kwargs["data"]["req"])["request"]
        read = json.loads(post.call_args_list[1].kwargs["data"]["req"])["request"]
        assert login["session-id"] == 0
        assert login["actions"][0]["method"] == "logIn"
        assert "example-password" not in json.dumps(login)
        assert read["session-id"] == 7
        assert read["id"] == login["id"] + 1
        assert read["auth-key"] == "example-session-token"


@pytest.mark.asyncio
async def test_xmo_status_preserves_rates_and_prioritizes_guest_and_ssid_aliases():
    hosts = [
        {
            "PhysAddress": f"02:00:00:00:00:{index:02x}",
            "Active": active,
            "InterfaceType": interface,
            "AssociatedDevice": associated,
            "Layer3Interface": layer3,
        }
        for index, (active, interface, associated, layer3) in enumerate(
            [
                (True, "WiFi2.4", "", ""),
                (True, "WiFi", "SSID[Alias='WLAN_2_4']", ""),
                (True, "WiFi2.4", "SSID[Alias='WLAN_5']", ""),
                (True, "WiFi2.4", "SSID[Alias='WLAN_Gaming']", ""),
                (True, "WiFi2.4", "", "Interface[Alias='GUEST']"),
                (False, "WiFi2.4", "", ""),
            ]
        )
    ]
    async with aiohttp.ClientSession() as session:
        client = SpeedportClient("router.example", "example-password", session)
        client._sagemcom_client = MagicMock()
        client._sagemcom_client.get_values_by_xpaths = AsyncMock(
            side_effect=[
                {
                    "model_name": "Speedport Pro Plus",
                    "dsl_downstream": "236593",
                    "dsl_upstream": "39976",
                    "lte_signal": 2,
                },
                {"hosts": hosts},
            ]
        )
        data = await client._get_sagemcom_data()

    assert data.dsl_downstream == 236593
    assert data.dsl_upstream == 39976
    assert len(data.devices) == 6
    assert data.raw["connected_devices_count"] == 5
    assert data.raw["wifi_24_device_count"] == 2
    assert data.raw["wifi_5_device_count"] == 1
    assert data.raw["wifi_gaming_device_count"] == 1
    assert data.raw["wifi_guest_device_count"] == 1
    assert data.raw["lte_signal"] == 2


def test_xmo_session_error_is_not_treated_as_an_optional_missing_path():
    client = SagemcomXmoClient("router.example", "example-password", MagicMock())
    with pytest.raises(SpeedportAuthError):
        client._check_response(
            {
                "reply": {
                    "error": {"description": "XMO_REQUEST_ACTION_ERR"},
                    "actions": [{"error": {"description": "XMO_INVALID_SESSION_ERR"}}],
                }
            },
            ignore_unknown_paths=True,
        )
