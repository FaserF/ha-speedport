"""Test the Speedport image platform."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.speedport.const import DATA_COORDINATOR, DOMAIN
from custom_components.speedport.image import async_setup_entry


@pytest.mark.asyncio
async def test_image_setup(hass: HomeAssistant):
    """Test image entities creation and image retrieval."""
    
    entry = MagicMock(entry_id="test_entry", title="Speedport")
    entry.data = {"host": "192.168.178.200"}

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = MagicMock()
    coordinator.data.wlan_ssid = "MyMainWiFi"
    coordinator.data.wlan_guest_ssid = "MyGuestWiFi"
    coordinator.data.raw = {
        "wlan_wpa_key": "supersecretmain",
        "wlan_guest_wpa_key": "supersecretguest",
    }
    # Success state for availability
    coordinator.last_update_success = True
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    async_add_entities = MagicMock()
    
    # Run setup
    await async_setup_entry(hass, entry, async_add_entities)

    # The setup calls _async_add_new_entities once at the end
    assert async_add_entities.called
    images = async_add_entities.call_args[0][0]
    
    assert len(images) == 2
    
    main_image = next(img for img in images if img._wifi_type == "main")
    guest_image = next(img for img in images if img._wifi_type == "guest")
    
    assert main_image.unique_id == "test_entry_wifi_qr_main"
    assert guest_image.unique_id == "test_entry_wifi_qr_guest"
    assert main_image.available is True

    # Test main image generation
    main_image_bytes = await main_image.async_image()
    assert main_image_bytes is not None
    assert b"PNG" in main_image_bytes

    # Test guest image generation
    guest_image_bytes = await guest_image.async_image()
    assert guest_image_bytes is not None
    assert b"PNG" in guest_image_bytes
