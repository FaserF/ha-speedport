"""Data update coordinator for the Speedport integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SpeedportAuthError, SpeedportClient, SpeedportConnectionError, SpeedportData
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SpeedportDataCoordinator(DataUpdateCoordinator[SpeedportData]):
    """Coordinator that fetches data from a Speedport router."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SpeedportClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.config_entry = entry

        update_interval = entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.data.get(CONF_HOST, "Speedport"),
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self) -> SpeedportData:
        """Fetch latest data from the Speedport router."""
        try:
            data = await self.client.get_all_data()
        except SpeedportAuthError:
            # Try re-login once
            try:
                await self.client.login()
                data = await self.client.get_all_data()
            except SpeedportAuthError as retry_err:
                raise UpdateFailed(f"Authentication error: {retry_err}") from retry_err
        except (SpeedportConnectionError, Exception) as err:
            raise UpdateFailed(f"Error fetching Speedport data: {err}") from err

        # Update device registry
        await self._async_update_device_registry(data)
        return data

    async def _async_update_device_registry(self, data: SpeedportData) -> None:
        """Register/update the router in the device registry."""
        device_registry = dr.async_get(self.hass)
        assert self.config_entry is not None
        host = self.config_entry.data[CONF_HOST]

        # Use the config entry ID as a stable identifier for the router device
        identifiers = {(DOMAIN, self.config_entry.entry_id)}

        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers=identifiers,
            manufacturer="Deutsche Telekom",
            model=data.device_name or "Speedport",
            name=data.device_name or "Speedport",
            sw_version=data.firmware_version or None,
            hw_version=data.serial_number or None,
            configuration_url=f"http://{host}",
        )
