"""Binary sensor platform for Telekom Speedport integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SpeedportDataCoordinator
from .entity import SpeedportEntity


@dataclass(frozen=True, kw_only=True)
class SpeedportBinarySensorDescription(BinarySensorEntityDescription):
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
        # Filter out features based on what the router supports
        if description.key in ("dsl_tunnel", "lte_tunnel", "hybrid_tunnel") and (
            coordinator.data and coordinator.data.use_lte is False
        ):
            continue
        entities.append(SpeedportBinarySensor(coordinator, description))

    async_add_entities(entities)

    tracked_mesh_nodes: set[str] = set()

    @callback
    def _add_new_mesh_nodes() -> None:
        """Add any new mesh nodes from the latest coordinator data."""
        if coordinator.data is None:
            return

        new_entities = []
        for device in coordinator.data.devices:
            if device.type == "2" or device.slave == "1":
                mac = device.mac.lower()
                if mac and mac not in tracked_mesh_nodes:
                    tracked_mesh_nodes.add(mac)
                    new_entities.append(SpeedportMeshNodeBinarySensor(coordinator, mac))

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_mesh_nodes))
    _add_new_mesh_nodes()


class SpeedportBinarySensor(SpeedportEntity, BinarySensorEntity):
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


class SpeedportMeshNodeBinarySensor(SpeedportEntity, BinarySensorEntity):
    """Speedport mesh node binary sensor entity."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        coordinator: SpeedportDataCoordinator,
        mac: str,
    ) -> None:
        """Initialize the mesh node binary sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._mac = mac.lower()
        config_entry = coordinator.config_entry
        assert config_entry is not None

        device = self._get_device()
        hostname = device.hostname if device and device.hostname else self._mac

        self._attr_unique_id = f"{config_entry.entry_id}_{self._mac}_connected"
        self._attr_translation_key = "mesh_connected"
        self._attr_name = f"{hostname} Online Status"
        self._attr_icon = "mdi:router-wireless"

    def _get_device(self):
        """Get the tracked device from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get_device(self._mac)

    @property
    def is_on(self) -> bool:
        """Return true if the mesh node is connected."""
        device = self._get_device()
        if device is None:
            return False
        return device.connected
