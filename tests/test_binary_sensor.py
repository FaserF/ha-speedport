"""Tests for the Speedport binary sensor platform."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.speedport.api import WlanDevice
from custom_components.speedport.binary_sensor import (
    SpeedportMeshNodeBinarySensor,
    async_setup_entry,
)
from custom_components.speedport.const import DATA_COORDINATOR, DOMAIN


@pytest.mark.asyncio
async def test_binary_sensor_setup(hass: HomeAssistant):
    """Test binary sensor setup."""
    entry = MagicMock(entry_id="test_entry")
    entry.data = {"host": "192.168.178.200"}

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = MagicMock()
    coordinator.data.device_name = "Speedport W 724V"
    coordinator.data.onlinestatus = "online"
    mesh_node = WlanDevice(
        mac="AA:BB:CC:DD:EE:FF",
        hostname="Speed Home WiFi",
        is_mesh_node=True,
        connected=True,
    )
    coordinator.data.devices = [mesh_node]
    coordinator.data.raw = {}

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    assert async_add_entities.called

    binary_sensors = async_add_entities.call_args_list[1][0][0]
    assert len(binary_sensors) > 0

    mesh_sensors = async_add_entities.call_args_list[0][0][0]
    assert len(mesh_sensors) == 1
    assert all(isinstance(s, SpeedportMeshNodeBinarySensor) for s in mesh_sensors)

    # Check one binary sensor
    online_sensor = next(
        s for s in binary_sensors if s.entity_description.key == "online"
    )
    assert online_sensor.unique_id == "test_entry_online"

    # Check mesh node sensor
    mesh_sensor = mesh_sensors[0]
    assert mesh_sensor.unique_id == "test_entry_mesh_aa:bb:cc:dd:ee:ff_connected"
    assert mesh_sensor.is_on is True
