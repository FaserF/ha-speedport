"""Base entity for Speedport integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SpeedportDataCoordinator


class SpeedportEntity(CoordinatorEntity[SpeedportDataCoordinator]):
    """Base entity for Speedport."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SpeedportDataCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        data = coordinator.data
        host = coordinator.config_entry.data.get("host", "speedport.ip")
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        data = self.coordinator.data
        host = self.coordinator.config_entry.data.get("host", "speedport.ip")
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=data.device_name if data and data.device_name else "Speedport",
            manufacturer="Deutsche Telekom",
            model=data.device_name if data and data.device_name else "Speedport",
            sw_version=data.firmware_version if data and data.firmware_version else None,
            configuration_url=f"http://{host}",
        )
