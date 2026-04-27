"""Switch platform for Telekom Speedport integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SpeedportClient
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from .coordinator import SpeedportDataCoordinator
from .entity import SpeedportEntity


@dataclass(frozen=True, kw_only=True)
class SpeedportSwitchDescription(SwitchEntityDescription):
    """Description for Speedport switches."""

    data_key: str = ""
    turn_on_fn: str = ""
    turn_off_fn: str = ""


SWITCHES: tuple[SpeedportSwitchDescription, ...] = (
    SpeedportSwitchDescription(
        key="wifi",
        translation_key="wifi",
        name="WiFi",
        icon="mdi:wifi",
        data_key="use_wlan",
        turn_on_fn="set_wifi_on",
        turn_off_fn="set_wifi_off",
    ),
    SpeedportSwitchDescription(
        key="wifi_guest",
        translation_key="wifi_guest",
        name="Guest WiFi",
        icon="mdi:wifi-star",
        data_key="wlan_guest_active",
        turn_on_fn="set_wifi_guest_on",
        turn_off_fn="set_wifi_guest_off",
    ),
    SpeedportSwitchDescription(
        key="wifi_office",
        translation_key="wifi_office",
        name="Office WiFi",
        icon="mdi:wifi",
        data_key="wlan_office_active",
        turn_on_fn="set_wifi_office_on",
        turn_off_fn="set_wifi_office_off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Speedport switches."""
    coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    client: SpeedportClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities = []
    for description in SWITCHES:
        # Filter out Office WiFi if not supported by the router
        if (
            description.key == "wifi_office"
            and coordinator.data
            and coordinator.data.wlan_office_active is None
        ):
            continue
        entities.append(SpeedportSwitch(coordinator, client, description))

    async_add_entities(entities)


class SpeedportSwitch(SpeedportEntity, SwitchEntity):
    """Speedport switch entity."""

    _attr_should_poll = False
    entity_description: SpeedportSwitchDescription

    def __init__(
        self,
        coordinator: SpeedportDataCoordinator,
        client: SpeedportClient,
        description: SpeedportSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._client = client
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        data = self.coordinator.data
        if data is None:
            return None
        val = getattr(data, self.entity_description.data_key, None)
        if val is None:
            return None
        return bool(val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        if self.entity_description.key == "wifi":
            await self._client.set_wifi(True)
        elif self.entity_description.key == "wifi_guest":
            await self._client.set_wifi_guest(True)
        elif self.entity_description.key == "wifi_office":
            await self._client.set_wifi_office(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        if self.entity_description.key == "wifi":
            await self._client.set_wifi(False)
        elif self.entity_description.key == "wifi_guest":
            await self._client.set_wifi_guest(False)
        elif self.entity_description.key == "wifi_office":
            await self._client.set_wifi_office(False)
        await self.coordinator.async_request_refresh()
