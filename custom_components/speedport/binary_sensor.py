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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import WlanDevice
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

    entities: list[BinarySensorEntity] = []
    for description in BINARY_SENSORS:
        # Filter out LTE/Hybrid sensors if the router definitely doesn't support them
        if description.key in ("dsl_tunnel", "lte_tunnel", "hybrid_tunnel") and (
            coordinator.data and coordinator.data.use_lte is False
        ):
            continue
        entities.append(SpeedportBinarySensor(coordinator, description))

    tracked_mesh_nodes: set[str] = set()

    @callback
    def _add_new_mesh_nodes() -> None:
        """Add binary sensors for new mesh nodes."""
        if coordinator.data is None:
            return
        new_entities: list[BinarySensorEntity] = []
        for device in coordinator.data.devices:
            if device.is_mesh_node and device.mac:
                mac = device.mac.lower()
                if mac not in tracked_mesh_nodes:
                    tracked_mesh_nodes.add(mac)
                    new_entities.append(
                        SpeedportMeshNodeBinarySensor(
                            coordinator,
                            mac,
                            SpeedportBinarySensorDescription(
                                key=f"mesh_{mac}_connected",
                                translation_key="mesh_connected",
                                name="Connected",
                                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                                data_key="connected",
                            ),
                        )
                    )
        if new_entities:
            async_add_entities(new_entities)

    _add_new_mesh_nodes()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_mesh_nodes))

    async_add_entities(entities)


class SpeedportMeshNodeBinarySensor(SpeedportEntity, BinarySensorEntity):
    """Binary sensor for a Speedport mesh node."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description: SpeedportBinarySensorDescription

    def __init__(
        self,
        coordinator: SpeedportDataCoordinator,
        mac: str,
        description: SpeedportBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self.entity_description = description
        self._mac = mac
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def _device(self) -> WlanDevice | None:
        """Get the mesh node device."""
        if not self.coordinator.data:
            return None
        return next(
            (d for d in self.coordinator.data.devices if d.mac.lower() == self._mac),
            None,
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""
        assert self.coordinator.config_entry is not None
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.config_entry.entry_id}_{self._mac}")},
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac.upper())},
            name=device.hostname if device and device.hostname else "Mesh Repeater",
            manufacturer="Deutsche Telekom",
            model="Speed Home WiFi" if device and "speedhome" in (device.hostname or "").lower() else "Mesh Repeater",
            via_device=(DOMAIN, self.coordinator.config_entry.entry_id),
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        device = self._device
        if not device:
            return False
        val = getattr(device, self.entity_description.data_key, None)
        return bool(val)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device is not None


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
