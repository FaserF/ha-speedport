"""Tests for the Speedport diagnostics platform."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.speedport.api import SpeedportData, WlanDevice
from custom_components.speedport.const import DATA_COORDINATOR, DOMAIN
from custom_components.speedport.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.mark.asyncio
async def test_diagnostics(hass: HomeAssistant):
    """Test diagnostics extraction and redaction."""
    entry = MagicMock(entry_id="test_entry")
    entry.as_dict.return_value = {
        "entry_id": "test_entry",
        "domain": "speedport",
        "data": {
            "host": "192.168.2.1",
            "password": "secret_router_password",
        },
    }

    data = SpeedportData(
        device_name="Speedport Smart 4",
        firmware_version="010137.4.8.001.1",
        online_status="online",
        router_state="connected",
        dsl_link_status="Synchronous",
        dsl_downstream=204400,
        dsl_upstream=42460,
        dsl_pop="BERX12",
        dualstack=True,
        use_lte=True,
        dsl_tunnel=True,
        lte_tunnel=True,
        hybrid_tunnel=True,
        ex5g_signal_5g="-84",
        ex5g_freq_5g="Band 78 / 3500 MHz",
        ex5g_signal_lte="-85",
        ex5g_freq_lte="Band 3 / 1800 MHz",
        update_available=False,
        latest_version=None,
        devices=[
            WlanDevice(
                mac="AA:BB:CC:DD:EE:FF",
                hostname="Smart-Phone",
                ip="192.168.2.150",
                type="wlan_5g",
                connected=True,
            )
        ],
        calls=[
            {
                "caller_number": "0123456789",
                "called_number": "0987654321",
                "call_type": "in",
                "date": "2026-08-28 12:00:00",
            }
        ],
        update_info={"status": "ok", "version": "010137.4.8.001.1"},
        raw={
            "device_name": "Speedport Smart 4",
            "firmware_version": "010137.4.8.001.1",
            "wlan_ssid": "SecretHomeWiFi",
            "wlan_key": "SuperSecretWPAKey",
            "public_ip_v4": "80.150.10.20",
            "public_ip_v6": "2003:00c0:1234:5678::1",
            "dns_v4": "192.168.2.1",
            "gateway_ip_v4": "217.0.119.1",
            "serial_number": "SP1234567890",
            "mac": "11:22:33:44:55:66",
            "ex5g_signal_5g": "-84",
            "ex5g_freq_5g": "Band 78 / 3500 MHz",
            "dsl_downstream": "204400",
            "dsl_tunnel": "1",
            "hybrid_tunnel": "1",
            "httoken": "abc123token",
        },
    )

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = data

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    diag = await async_get_config_entry_diagnostics(hass, entry)

    # Check top-level structure
    assert "entry" in diag
    assert "router_info" in diag
    assert "data" in diag
    assert "update_info" in diag
    assert "devices" in diag
    assert "calls" in diag

    # Check router_info content
    router_info = diag["router_info"]
    assert router_info["device_name"] == "Speedport Smart 4"
    assert router_info["firmware_version"] == "010137.4.8.001.1"
    assert router_info["ex5g_signal_5g"] == "-84"
    assert router_info["ex5g_freq_5g"] == "Band 78 / 3500 MHz"
    assert router_info["dsl_downstream"] == 204400
    assert router_info["hybrid_tunnel"] is True
    assert router_info["connected_devices_count"] == 1
    assert router_info["calls_count"] == 1
    assert router_info["public_ip_v4"] == "**REDACTED**"
    assert router_info["public_ip_v6"] == "**REDACTED**"
    assert router_info["dns_v4"] == "**REDACTED**"

    # Check redactions in entry data
    assert diag["entry"]["data"]["password"] == "**REDACTED**"
    assert diag["entry"]["data"]["host"] == "**REDACTED**"

    # Check redactions in raw router data
    assert diag["data"]["wlan_ssid"] == "**REDACTED**"
    assert diag["data"]["wlan_key"] == "**REDACTED**"
    assert diag["data"]["public_ip_v4"] == "**REDACTED**"
    assert diag["data"]["public_ip_v6"] == "**REDACTED**"
    assert diag["data"]["dns_v4"] == "**REDACTED**"
    assert diag["data"]["gateway_ip_v4"] == "**REDACTED**"
    assert diag["data"]["serial_number"] == "**REDACTED**"
    assert diag["data"]["mac"] == "**REDACTED**"
    assert diag["data"]["httoken"] == "**REDACTED**"

    # Non-sensitive keys in raw data should remain intact
    assert diag["data"]["ex5g_signal_5g"] == "-84"
    assert diag["data"]["ex5g_freq_5g"] == "Band 78 / 3500 MHz"
    assert diag["data"]["dsl_downstream"] == "204400"
    assert diag["data"]["dsl_tunnel"] == "1"
    assert diag["data"]["hybrid_tunnel"] == "1"

    # Check device redaction
    assert diag["devices"][0]["mac"] == "**REDACTED**"
    assert diag["devices"][0]["ip"] == "**REDACTED**"
    assert diag["devices"][0]["hostname"] == "**REDACTED**"
    assert diag["devices"][0]["type"] == "wlan_5g"
    assert diag["devices"][0]["connected"] is True

    # Check calls redaction
    assert diag["calls"][0]["caller_number"] == "**REDACTED**"
    assert diag["calls"][0]["called_number"] == "**REDACTED**"
    assert diag["calls"][0]["call_type"] == "in"
