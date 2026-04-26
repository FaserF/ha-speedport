"""Tests for the Speedport switch platform."""
from unittest.mock import MagicMock
import pytest
from homeassistant.core import HomeAssistant

from custom_components.speedport.const import DOMAIN, DATA_COORDINATOR, DATA_CLIENT
from custom_components.speedport.switch import async_setup_entry

@pytest.mark.asyncio
async def test_switch_setup(hass: HomeAssistant):
    """Test switch setup."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    
    coordinator = MagicMock()
    coordinator.data = MagicMock()
    coordinator.data.use_wlan = True
    
    client = MagicMock()
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_CLIENT: client
    }
    
    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)
    
    assert async_add_entities.called
    switches = async_add_entities.call_args[0][0]
    wifi_switch = next(s for s in switches if s.entity_description.key == "wifi")
    
    # Test turn on
    await wifi_switch.async_turn_on()
    client.set_wifi.assert_called_with(True)
    
    # Test turn off
    await wifi_switch.async_turn_off()
    client.set_wifi.assert_called_with(False)
