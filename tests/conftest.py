"""Pytest configuration and fixtures for the Speedport integration tests."""

import asyncio
import inspect
import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest


def pytest_pyfunc_call(pyfuncitem):
    """Run async test functions."""
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        asyncio.run(
            pyfuncitem.obj(
                *[pyfuncitem.funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames]
            )
        )
        return True


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

    def __init__(self, *args, **kwargs):
        pass

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
    "homeassistant.components.device_tracker",
    {
        "ScannerEntity": MockEntity,
        "SourceType": MagicMock(ROUTER="router"),
    },
)


class MockCoordinatorEntity(MockEntity):
    """Base class for mocked CoordinatorEntity."""

    def __init__(self, coordinator, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coordinator = coordinator
        self.hass = getattr(coordinator, "hass", None)

    def __class_getitem__(cls, item):
        return cls

    @property
    def available(self) -> bool:
        return getattr(self.coordinator, "last_update_success", True)


create_mock_module(
    "homeassistant.helpers.update_coordinator",
    {
        "DataUpdateCoordinator": MockCoordinator,
        "CoordinatorEntity": MockCoordinatorEntity,
        "UpdateFailed": Exception,
    },
)


class MockSegnoQR:
    def save(self, buf, kind="png", border=2, scale=10):
        buf.write(b"\x89PNG\r\n\x1a\nfake_png_data")


mock_segno = create_mock_module(
    "segno",
    {
        "make": lambda s: MockSegnoQR(),
    },
)


def _mock_redact(data: Any, to_redact: set[str]) -> Any:
    if isinstance(data, dict):
        return {
            k: ("**REDACTED**" if k in to_redact else _mock_redact(v, to_redact))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_mock_redact(item, to_redact) for item in data]
    return data


create_mock_module(
    "homeassistant.components.diagnostics",
    {
        "async_redact_data": _mock_redact,
    },
)


# Mock other essential modules
essential_modules = [
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

create_mock_module(
    "homeassistant.helpers.device_registry",
    {
        "DeviceInfo": dict,
        "CONNECTION_NETWORK_MAC": "mac",
        "async_get": MagicMock(),
    },
)

for mod in essential_modules:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# homeassistant.core.callback should be a pass-through decorator
core_mock = create_mock_module("homeassistant.core", {})
core_mock.callback = lambda x: x


@pytest.fixture
def hass():
    """Mock hass fixture."""
    mock = MagicMock()
    mock.data = {}
    return mock
