"""Pytest configuration and fixtures for the Speedport integration tests."""

import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest


# Provide minimal real classes for common HA base classes to support dataclasses
@dataclass(frozen=True)
class MockEntityDescription:
    key: str = ""
    name: str | None = None
    icon: str | None = None
    entity_category: Any | None = None
    translation_key: str | None = None
    device_class: Any | None = None
    state_class: Any | None = None
    native_unit_of_measurement: str | None = None


class MockEntity:
    """Base class for all mocked HA entities."""

    _attr_unique_id: str | None = None
    _attr_name: str | None = None
    _attr_available: bool = True

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id

    @property
    def name(self) -> str | None:
        return self._attr_name

    @property
    def available(self) -> bool:
        return self._attr_available

    async def async_added_to_hass(self) -> None:
        pass

    def async_write_ha_state(self) -> None:
        pass

    def async_on_remove(self, func) -> None:
        pass


class MockCoordinator:
    """Base class for all mocked HA coordinators."""

    def __init__(self, *args, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls


# Create a module factory to avoid MagicMock issues
def create_mock_module(name, attributes):
    mock = MagicMock()
    for attr, val in attributes.items():
        setattr(mock, attr, val)
    sys.modules[name] = mock
    return mock


# Setup mocks
create_mock_module("homeassistant.helpers.entity", {"Entity": MockEntity})
create_mock_module(
    "homeassistant.components.sensor",
    {
        "SensorEntity": MockEntity,
        "SensorEntityDescription": MockEntityDescription,
        "SensorDeviceClass": MagicMock(),
        "SensorStateClass": MagicMock(),
    },
)
create_mock_module(
    "homeassistant.components.binary_sensor",
    {
        "BinarySensorEntity": MockEntity,
        "BinarySensorEntityDescription": MockEntityDescription,
        "BinarySensorDeviceClass": MagicMock(),
    },
)
create_mock_module(
    "homeassistant.components.switch",
    {
        "SwitchEntity": MockEntity,
        "SwitchEntityDescription": MockEntityDescription,
    },
)
create_mock_module(
    "homeassistant.components.image",
    {
        "ImageEntity": MockEntity,
    },
)
create_mock_module(
    "homeassistant.helpers.update_coordinator",
    {
        "DataUpdateCoordinator": MockCoordinator,
        "CoordinatorEntity": MockCoordinator,
        "UpdateFailed": Exception,
    },
)

# Mock other essential modules
essential_modules = [
    "homeassistant.core",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.typing",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.config_validation",
    "homeassistant.util",
]

for mod in essential_modules:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


@pytest.fixture
def hass():
    """Mock hass fixture."""
    mock = MagicMock()
    mock.data = {}
    return mock
