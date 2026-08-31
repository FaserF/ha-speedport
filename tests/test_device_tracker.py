"""Tests for the Speedport device tracker platform."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.speedport.api import WlanDevice
from custom_components.speedport.const import (
    CONF_ENABLE_DEVICE_TRACKER,
    DATA_COORDINATOR,
    DOMAIN,
)
from custom_components.speedport.device_tracker import async_setup_entry


@pytest.mark.asyncio
async def test_device_tracker_setup(hass: HomeAssistant):
    """Test device tracker setup with connected devices."""
    entry = MagicMock(entry_id="test_entry", title="Speedport")
    entry.options = {CONF_ENABLE_DEVICE_TRACKER: True}
    entry.data = {"host": "192.168.178.1"}

    dev1 = WlanDevice(
        mac="AA:BB:CC:DD:EE:01",
        hostname="MyPhone",
        ip="192.168.178.20",
        type="wlan",
        connected=True,
        rssi="-55",
        speed="866",
        downspeed="500",
        upspeed="200",
        ipv6="fe80::1",
    )
    dev2 = WlanDevice(
        mac="AA:BB:CC:DD:EE:02",
        hostname="MyLaptop",
        ip="192.168.178.21",
        type="lan",
        connected=False,
    )

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = MagicMock()
    coordinator.data.devices = [dev1, dev2]
    coordinator.data.get_device = lambda mac: next(
        (d for d in [dev1, dev2] if d.mac.lower() == mac.lower()), None
    )
    coordinator.last_update_success = True

    listeners = []
    coordinator.async_add_listener = lambda cb: listeners.append(cb)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    assert async_add_entities.called
    trackers = async_add_entities.call_args[0][0]
    assert len(trackers) == 2

    t1 = next(t for t in trackers if t.mac_address == "aa:bb:cc:dd:ee:01")
    assert t1.unique_id == "test_entry_tracker_aa:bb:cc:dd:ee:01"
    assert t1.name is None
    assert t1._attr_has_entity_name is True
    assert t1._attr_entity_registry_enabled_default is True
    assert t1.is_connected is True
    assert t1.ip_address == "192.168.178.20"
    assert t1.hostname == "MyPhone"
    assert t1.source_type == "router"
    assert t1.extra_state_attributes["connection_type"] == "wlan"
    t2 = next(t for t in trackers if t.mac_address == "aa:bb:cc:dd:ee:02")
    assert t2.is_connected is False
    assert t2.hostname == "MyLaptop"


@pytest.mark.asyncio
async def test_device_tracker_disabled_option(hass: HomeAssistant):
    """Test device tracker setup when disabled in entry options."""
    entry = MagicMock(entry_id="test_entry_disabled", title="Speedport")
    entry.options = {CONF_ENABLE_DEVICE_TRACKER: False}
    entry.data = {"host": "192.168.178.1"}

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = MagicMock()
    coordinator.data.devices = [
        WlanDevice(mac="AA:BB:CC:DD:EE:01", hostname="MyPhone", connected=True)
    ]

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    assert not async_add_entities.called


@pytest.mark.asyncio
async def test_device_tracker_dynamic_device_added(hass: HomeAssistant):
    """Test dynamic addition of devices via coordinator listener callback."""
    entry = MagicMock(entry_id="test_entry_dynamic", title="Speedport")
    entry.options = {CONF_ENABLE_DEVICE_TRACKER: True}
    entry.data = {"host": "192.168.178.1"}

    dev1 = WlanDevice(mac="AA:BB:CC:DD:EE:01", hostname="Device1", connected=True)
    dev2 = WlanDevice(mac="AA:BB:CC:DD:EE:02", hostname="Device2", connected=True)

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = MagicMock()
    coordinator.data.devices = [dev1]
    coordinator.data.get_device = lambda mac: next(
        (d for d in coordinator.data.devices if d.mac.lower() == mac.lower()), None
    )

    listeners = []
    coordinator.async_add_listener = lambda cb: (listeners.append(cb), lambda: None)[1]

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    assert len(async_add_entities.call_args[0][0]) == 1

    # Simulate coordinator update with a new device
    coordinator.data.devices = [dev1, dev2]
    for cb in listeners:
        cb()

    # async_add_entities should be called again with only the new device
    assert async_add_entities.call_count == 2
    new_added = async_add_entities.call_args[0][0]
    assert len(new_added) == 1
    assert new_added[0].mac_address == "aa:bb:cc:dd:ee:02"
