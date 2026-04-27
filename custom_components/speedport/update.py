"""Update platform for Telekom Speedport integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SpeedportDataCoordinator
from .entity import SpeedportEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Speedport update entities."""
    coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities([SpeedportUpdateEntity(coordinator)])


class SpeedportUpdateEntity(SpeedportEntity, UpdateEntity):  # type: ignore[misc]
    """Speedport update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_name = "Firmware Update"
    _attr_should_poll = False

    def __init__(self, coordinator: SpeedportDataCoordinator) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_update"

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        if self.coordinator.data is None:
            return None
        return cast(str | None, self.coordinator.data.firmware_version)

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        if self.coordinator.data is None:
            return None
        return cast(str | None, self.coordinator.data.firmware_version_available)

    @property
    def in_progress(self) -> bool:
        """Return if update is in progress."""
        if self.coordinator.data is None:
            return False
        return cast(bool, self.coordinator.data.firmware_update_state == "downloading")

    @property
    def update_available(self) -> bool:
        """Return True if an update is available."""
        if self.coordinator.data is None:
            return False
        return cast(bool, self.coordinator.data.update_available)

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        _LOGGER.info("Starting firmware update for Speedport")
        await self.coordinator.client.install_update()
        await self.coordinator.async_refresh()
