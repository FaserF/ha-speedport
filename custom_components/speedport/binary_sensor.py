"""Binary sensor platform for Telekom Speedport integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SpeedportDataCoordinator
from .entity import SpeedportEntity


@dataclass(frozen=True, kw_only=True)
class SpeedportBinarySensorDescription(BinarySensorEntityDescription):  # type: ignore[misc]
    """Description for Speedport binary sensors."""

    data_key: str = ""
    true_value: str | None = None  # if None, check data_key attribute directly as bool


BINARY_SENSORS: tuple[SpeedportBinarySensorDescription, ...] = (
    SpeedportBinarySensorDescription(
        key="online",
        translation_key="online",
        name="Internet Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        data_key="onlinestatus",
        true_value="online",
    ),
    SpeedportBinarySensorDescription(
        key="dsl_link",
        translation_key="dsl_link",
        name="DSL Link",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        data_key="dsl_link_status",
        true_value="online",
    ),
    SpeedportBinarySensorDescription(
        key="use_wlan",
        translation_key="use_wlan",
        name="WiFi Active",
        device_class=BinarySensorDeviceClass.POWER,
        data_key="use_wlan",
        true_value="1",
    ),
    SpeedportBinarySensorDescription(
        key="dualstack",
        translation_key="dualstack",
        name="Dual Stack (IPv4+IPv6)",
        data_key="dualstack",
        true_value=None,
    ),
    SpeedportBinarySensorDescription(
        key="dsl_tunnel",
        translation_key="dsl_tunnel",
        name="DSL Tunnel",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        data_key="dsl_tunnel",
        true_value="1",
    ),
    SpeedportBinarySensorDescription(
        key="lte_tunnel",
        translation_key="lte_tunnel",
        name="LTE Tunnel",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        data_key="lte_tunnel",
        true_value="1",
    ),
    SpeedportBinarySensorDescription(
        key="hybrid_tunnel",
        translation_key="hybrid_tunnel",
        name="Hybrid Tunnel",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        data_key="hybrid_tunnel",
        true_value="1",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Speedport binary sensors."""
    coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities = []
    for description in BINARY_SENSORS:
        # Filter out LTE/Hybrid sensors if the router definitely doesn't support them
        if description.key in ("dsl_tunnel", "lte_tunnel", "hybrid_tunnel") and (
            coordinator.data and coordinator.data.use_lte is False
        ):
            continue
        entities.append(SpeedportBinarySensor(coordinator, description))

    async_add_entities(entities)


class SpeedportBinarySensor(SpeedportEntity, BinarySensorEntity):  # type: ignore[misc]
    """Speedport binary sensor entity."""

    _attr_should_poll = False
    entity_description: SpeedportBinarySensorDescription

    def __init__(
        self,
        coordinator: SpeedportDataCoordinator,
        description: SpeedportBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

        # Disable rarely used binary sensors by default
        if description.key in (
            "dualstack",
            "dsl_tunnel",
            "lte_tunnel",
            "hybrid_tunnel",
        ):
            self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.data is not None and self.coordinator.last_update_success
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        data = self.coordinator.data
        if data is None:
            return None

        key = self.entity_description.data_key
        true_value = self.entity_description.true_value

        # Get value from attribute or raw
        val = getattr(data, key, None)
        if val is None:
            val = data.raw.get(key)

        if val is None:
            return None

        if true_value is None or isinstance(val, bool):
            # Treat as boolean directly if it is one or no true_value provided
            return bool(val)

        return str(val).lower() == str(true_value).lower()
