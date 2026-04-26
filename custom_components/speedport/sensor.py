"""Sensor platform for Telekom Speedport integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import pytz

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SpeedportDataCoordinator
from .entity import SpeedportEntity


@dataclass(frozen=True, kw_only=True)
class SpeedportSensorEntityDescription(SensorEntityDescription):
    """Description for Speedport sensors."""

    data_key: str = ""


SENSORS: tuple[SpeedportSensorEntityDescription, ...] = (
    SpeedportSensorEntityDescription(
        key="router_state",
        translation_key="router_state",
        name="Router State",
        icon="mdi:router-wireless",
        data_key="router_state",
    ),
    SpeedportSensorEntityDescription(
        key="online_status",
        translation_key="online_status",
        name="Online Status",
        icon="mdi:web",
        data_key="onlinestatus",
    ),
    SpeedportSensorEntityDescription(
        key="public_ip_v4",
        translation_key="public_ip_v4",
        name="Public IPv4",
        icon="mdi:earth",
        data_key="public_ip_v4",
    ),
    SpeedportSensorEntityDescription(
        key="public_ip_v6",
        translation_key="public_ip_v6",
        name="Public IPv6",
        icon="mdi:earth",
        data_key="public_ip_v6",
    ),
    SpeedportSensorEntityDescription(
        key="dsl_downstream",
        translation_key="dsl_downstream",
        name="DSL Downstream Speed",
        icon="mdi:download",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        data_key="dsl_downstream",
    ),
    SpeedportSensorEntityDescription(
        key="dsl_upstream",
        translation_key="dsl_upstream",
        name="DSL Upstream Speed",
        icon="mdi:upload",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        data_key="dsl_upstream",
    ),
    SpeedportSensorEntityDescription(
        key="inet_download",
        translation_key="inet_download",
        name="Internet Download",
        icon="mdi:download-network",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        data_key="inet_download",
    ),
    SpeedportSensorEntityDescription(
        key="inet_upload",
        translation_key="inet_upload",
        name="Internet Upload",
        icon="mdi:upload-network",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        data_key="inet_upload",
    ),
    SpeedportSensorEntityDescription(
        key="wlan_ssid",
        translation_key="wlan_ssid",
        name="WLAN SSID (2.4 GHz)",
        icon="mdi:wifi",
        data_key="wlan_ssid",
    ),
    SpeedportSensorEntityDescription(
        key="wlan_5ghz_ssid",
        translation_key="wlan_5ghz_ssid",
        name="WLAN SSID (5 GHz)",
        icon="mdi:wifi",
        data_key="wlan_5ghz_ssid",
    ),
    SpeedportSensorEntityDescription(
        key="wlan_guest_ssid",
        translation_key="wlan_guest_ssid",
        name="Guest WLAN SSID",
        icon="mdi:wifi-star",
        data_key="wlan_guest_ssid",
    ),
    SpeedportSensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        name="Firmware Version",
        icon="mdi:chip",
        data_key="firmware_version",
    ),
    SpeedportSensorEntityDescription(
        key="dns_v4",
        translation_key="dns_v4",
        name="DNS Server (IPv4)",
        icon="mdi:dns",
        data_key="dns_v4",
    ),
    SpeedportSensorEntityDescription(
        key="connected_devices_count",
        translation_key="connected_devices_count",
        name="Connected Devices",
        icon="mdi:devices",
        state_class=SensorStateClass.MEASUREMENT,
        data_key="_connected_devices_count",
    ),
    SpeedportSensorEntityDescription(
        key="dsl_link_status",
        translation_key="dsl_link_status",
        name="DSL Link Status",
        icon="mdi:dsl",
        data_key="dsl_link_status",
    ),
    SpeedportSensorEntityDescription(
        key="inet_uptime",
        translation_key="inet_uptime",
        name="Internet Uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="inet_uptime",
    ),
    SpeedportSensorEntityDescription(
        key="dsl_pop",
        translation_key="dsl_pop",
        name="DSL Access Point (PoP)",
        icon="mdi:map-marker-radius",
        data_key="dsl_pop",
    ),
    SpeedportSensorEntityDescription(
        key="ex5g_signal_5g",
        translation_key="ex5g_signal_5g",
        name="5G Signal Strength",
        icon="mdi:signal",
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        data_key="ex5g_signal_5g",
    ),
    SpeedportSensorEntityDescription(
        key="ex5g_freq_5g",
        translation_key="ex5g_freq_5g",
        name="5G Frequency",
        icon="mdi:signal-5g",
        data_key="ex5g_freq_5g",
    ),
    SpeedportSensorEntityDescription(
        key="ex5g_signal_lte",
        translation_key="ex5g_signal_lte",
        name="LTE Signal Strength",
        icon="mdi:signal",
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        data_key="ex5g_signal_lte",
    ),
    SpeedportSensorEntityDescription(
        key="ex5g_freq_lte",
        translation_key="ex5g_freq_lte",
        name="LTE Frequency",
        icon="mdi:signal-4g",
        data_key="ex5g_freq_lte",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Speedport sensors."""
    coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities = []
    for description in SENSORS:
        # Filter out LTE/5G sensors if not supported
        if description.key.startswith("ex5g_"):
            if not coordinator.data or not coordinator.data.use_lte:
                continue
        entities.append(SpeedportSensor(coordinator, description))

    async_add_entities(entities)




class SpeedportSensor(SpeedportEntity, SensorEntity):
    """Speedport sensor entity."""

    entity_description: SpeedportSensorEntityDescription

    def __init__(
        self,
        coordinator: SpeedportDataCoordinator,
        description: SpeedportSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        data = self.coordinator.data
        if data is None:
            return None

        key = self.entity_description.data_key

        # Special computed key
        if key == "_connected_devices_count":
            return len(data.devices)

        # Try direct attribute first
        val = getattr(data, key, None)
        if val is None:
            # Fall back to raw dict
            val = data.raw.get(key)

        if val == "":
            return None

        # For numeric data rate sensors, try to return int
        if self.entity_description.native_unit_of_measurement in (
            UnitOfDataRate.KILOBITS_PER_SECOND,
            UnitOfDataRate.BITS_PER_SECOND,
        ):
            try:
                return int(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        # Handle timestamp sensors
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP and val:
            try:
                # Format is usually YYYY-MM-DD HH:MM:SS
                date = datetime.strptime(str(val), "%Y-%m-%d %H:%M:%S").replace(second=0)
                return pytz.timezone("Europe/Berlin").localize(date)
            except (ValueError, TypeError):
                return None

        return val

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        if self.coordinator.data is None:
            return False
        return True
