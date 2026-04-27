"""Button platform for Telekom Speedport integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SpeedportClient
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from .coordinator import SpeedportDataCoordinator
from .entity import SpeedportEntity


@dataclass(frozen=True, kw_only=True)
class SpeedportButtonDescription(ButtonEntityDescription):
    """Description for Speedport buttons."""

    action: str = ""


BUTTONS: tuple[SpeedportButtonDescription, ...] = (
    SpeedportButtonDescription(
        key="reboot",
        translation_key="reboot",
        name="Reboot Router",
        icon="mdi:restart",
        action="reboot",
    ),
    SpeedportButtonDescription(
        key="reconnect",
        translation_key="reconnect",
        name="Reconnect Internet",
        icon="mdi:connection",
        action="reconnect",
    ),
    SpeedportButtonDescription(
        key="wps_on",
        translation_key="wps_on",
        name="Enable WPS",
        icon="mdi:wifi-plus",
        action="wps_on",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Speedport buttons."""
    coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    client: SpeedportClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    async_add_entities(
        SpeedportButton(coordinator, client, description) for description in BUTTONS
    )


class SpeedportButton(SpeedportEntity, ButtonEntity):
    """Speedport button entity."""

    entity_description: SpeedportButtonDescription

    def __init__(
        self,
        coordinator: SpeedportDataCoordinator,
        client: SpeedportClient,
        description: SpeedportButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._client = client
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        action = self.entity_description.action
        if action == "reboot":
            await self._client.reboot()
        elif action == "reconnect":
            await self._client.reconnect()
        elif action == "wps_on":
            await self._client.wps_on()
