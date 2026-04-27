"""Device tracker platform for Telekom Speedport integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import WlanDevice
from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SpeedportDataCoordinator
from .entity import SpeedportEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Speedport device trackers."""
    coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    tracked: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        """Add any new devices from the latest coordinator data."""
        if coordinator.data is None:
            return
        new_entities = []
        for device in coordinator.data.devices:
            mac = device.mac.lower()
            if mac and mac not in tracked:
                tracked.add(mac)
                new_entities.append(SpeedportDeviceTracker(coordinator, mac))
        if new_entities:
            async_add_entities(new_entities)

    # Register callback to add new devices on each update
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))

    # Add devices from initial data
    _add_new_devices()


class SpeedportDeviceTracker(ScannerEntity, SpeedportEntity):
    """Speedport device tracker entity."""

    def __init__(self, coordinator: SpeedportDataCoordinator, mac: str) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._mac = mac.lower()
        config_entry = self.coordinator.config_entry
        assert config_entry is not None
        self._attr_unique_id = f"{config_entry.entry_id}_tracker_{self._mac}"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac)},
            identifiers={(DOMAIN, self._mac)},
            via_device=(DOMAIN, config_entry.entry_id),
        )

    def _get_device(self) -> WlanDevice | None:
        """Get the tracked device from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get_device(self._mac)

    @property
    def name(self) -> str:
        """Return the device name."""
        device = self._get_device()
        if device and device.hostname:
            return device.hostname
        return self._mac

    @property
    def is_connected(self) -> bool:
        """Return True if the device is currently connected."""
        device = self._get_device()
        if device is None:
            return False
        return device.connected

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.ROUTER

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        device = self._get_device()
        return device.ip if device else None

    @property
    def mac_address(self) -> str | None:
        """Return the MAC address of the device."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        device = self._get_device()
        return device.hostname if device else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        device = self._get_device()
        if device is None:
            return {}
        return {
            "connection_type": device.type,
            "speed": device.speed,
            "rssi": device.rssi,
            "downspeed": device.downspeed,
            "upspeed": device.upspeed,
            "ipv6": device.ipv6,
            "fixed_dhcp": device.fix_dhcp,
        }
