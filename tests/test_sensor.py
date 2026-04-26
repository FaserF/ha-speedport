"""Tests for the Speedport sensor platform."""
from unittest.mock import MagicMock
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.speedport.const import DOMAIN, DATA_COORDINATOR
from custom_components.speedport.sensor import async_setup_entry

@pytest.mark.asyncio
async def test_sensor_setup(hass: HomeAssistant):
    """Test sensor setup."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"host": "192.168.178.200"}
    
    coordinator = MagicMock()
    coordinator.data = MagicMock()
    coordinator.data.device_name = "Speedport W 724V"
    coordinator.data.onlinestatus = "online"
    coordinator.data.devices = []
    coordinator.data.raw = {}
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator
    }
    
    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)
    
    assert async_add_entities.called
    sensors = async_add_entities.call_args[0][0]
    assert len(sensors) > 0
    
    # Check one sensor
    router_state_sensor = next(s for s in sensors if s.entity_description.key == "router_state")
    assert router_state_sensor.unique_id == "test_entry_router_state"
