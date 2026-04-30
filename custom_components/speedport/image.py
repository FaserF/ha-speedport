"""Image platform for Telekom Speedport integration."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SpeedportDataCoordinator

if TYPE_CHECKING:
    pass


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Speedport image entities from a config entry."""
    coordinator: SpeedportDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    _LOGGER.debug("Setting up Speedport image platform for %s", entry.title)

    @callback
    def _async_add_new_entities() -> None:
        if not coordinator.data:
            return

        new_entities: list[ImageEntity] = []
        tracked_keys = {
            entity.unique_id
            for entity in hass.data[DOMAIN][entry.entry_id].get("image_entities", [])
        }

        # Main Wi-Fi QR Code
        if coordinator.data.wlan_ssid:
            unique_id = f"{entry.entry_id}_wifi_qr_main"
            if unique_id not in tracked_keys:
                tracked_keys.add(unique_id)
                new_entities.append(
                    SpeedportWifiQrImage(hass, coordinator, entry, "main")
                )

        # Guest Wi-Fi QR Code
        if coordinator.data.wlan_guest_ssid:
            unique_id = f"{entry.entry_id}_wifi_qr_guest"
            if unique_id not in tracked_keys:
                tracked_keys.add(unique_id)
                new_entities.append(
                    SpeedportWifiQrImage(hass, coordinator, entry, "guest")
                )

        if new_entities:
            async_add_entities(new_entities)
            if "image_entities" not in hass.data[DOMAIN][entry.entry_id]:
                hass.data[DOMAIN][entry.entry_id]["image_entities"] = []
            hass.data[DOMAIN][entry.entry_id]["image_entities"].extend(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


class SpeedportWifiQrImage(ImageEntity):
    """Wi-Fi QR Code image entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SpeedportDataCoordinator,
        entry: ConfigEntry,
        wifi_type: str,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(hass)
        self.coordinator = coordinator
        self._entry = entry
        self._wifi_type = wifi_type

        name_suffix = "Main" if wifi_type == "main" else "Guest"
        self._attr_unique_id = f"{entry.entry_id}_wifi_qr_{wifi_type}"
        self._attr_name = f"Wi-Fi QR Code ({name_suffix})"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self._attr_image_last_updated = dt_util.utcnow()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if not self.coordinator.data:
            return None

        data = self.coordinator.data
        raw = data.raw

        ssid = ""
        key = ""
        encryption_type = "WPA"

        if self._wifi_type == "main":
            ssid = data.wlan_ssid
            # Try to get WPA key
            key = raw.get("wlan_wpa_key", "")
            if not key:
                key = raw.get("wlan_wep_key", "")
                encryption_type = "WEP" if key else "nopass"
        else:
            ssid = data.wlan_guest_ssid
            # Guest key (varies by model, some models just use wlan_guest_wpa_key)
            key = raw.get("wlan_guest_wpa_key", raw.get("wlan_guest_key", ""))
            if not key:
                # If there's no key available for guest, assume open (e.g., Telekom FON Hotspot)
                encryption_type = "nopass"

        if not ssid:
            return None

        # Build QR code string
        # Format: WIFI:S:<SSID>;T:<WEP|WPA|nopass>;P:<PASSWORD>;H:<true|false>;;
        h = "false"  # Speedport usually broadcasts SSID
        qr_string = f"WIFI:S:{ssid};T:{encryption_type};P:{key};H:{h};;"

        # Generate QR code
        import segno

        qr = segno.make(qr_string)
        buf = io.BytesIO()
        qr.save(buf, kind="png", border=2, scale=10)
        return buf.getvalue()
