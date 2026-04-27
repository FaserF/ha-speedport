"""Base entity for Speedport integration."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import SpeedportDataCoordinator


class SpeedportEntity:
    """Base entity for Speedport."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SpeedportDataCoordinator) -> None:
        """Initialize the entity."""
        self.coordinator = coordinator
        assert coordinator.config_entry is not None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""
        data = self.coordinator.data
        config_entry = self.coordinator.config_entry
        assert config_entry is not None
        host = config_entry.data.get("host", "speedport.ip")

        connections: set[tuple[str, str]] = set()
        if data and data.mac:
            connections = {(dr.CONNECTION_NETWORK_MAC, data.mac)}

        return DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            connections=connections,
            name=data.device_name if data and data.device_name else "Speedport",
            manufacturer="Deutsche Telekom",
            model=data.device_name if data and data.device_name else "Speedport",
            sw_version=data.firmware_version
            if data and data.firmware_version
            else None,
            configuration_url=f"http://{host}",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is not None
