"""Constants for the Telekom Speedport integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "speedport"

# Configuration keys
CONF_HOST: Final = "host"
CONF_PASSWORD: Final = "password"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_USE_HTTPS: Final = "use_https"

# Defaults
DEFAULT_HOST: Final = "speedport.ip"
DEFAULT_UPDATE_INTERVAL: Final = 60

# Platform list
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

# Data keys
DATA_COORDINATOR: Final = "coordinator"
DATA_CLIENT: Final = "client"

# AES key (same for all Speedport devices)
SPEEDPORT_DEFAULT_KEY: Final = (
    "cdc0cac1280b516e674f0057e4929bca84447cca8425007e33a88a5cf598a190"
)

# Services
SERVICE_REBOOT: Final = "reboot"
SERVICE_RECONNECT: Final = "reconnect"
SERVICE_WPS_ON: Final = "wps_on"
