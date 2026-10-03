"""Tests for the Speedport sensor platform."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.speedport.const import DATA_COORDINATOR, DOMAIN
from custom_components.speedport.sensor import (
    ROUTER_TIME_ZONE,
    SENSORS,
    SpeedportSensor,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_sensor_setup(hass: HomeAssistant):
    """Test sensor setup."""
    entry = MagicMock(entry_id="test_entry")
    entry.data = {"host": "192.168.178.200"}

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = MagicMock()
    coordinator.data.device_name = "Speedport W 724V"
    coordinator.data.onlinestatus = "online"
    coordinator.data.devices = []
    coordinator.data.raw = {}

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    assert async_add_entities.called
    sensors = async_add_entities.call_args[0][0]
    assert len(sensors) > 0

    # Check one sensor
    router_state_sensor = next(
        s for s in sensors if s.entity_description.key == "router_state"
    )
    assert router_state_sensor.unique_id == "test_entry_router_state"

    calls_sensor = next(s for s in sensors if s.entity_description.key == "calls")
    assert calls_sensor.unique_id == "test_entry_calls"


def _uptime_sensor(value: str) -> SpeedportSensor:
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock(entry_id="test_entry")
    coordinator.data.inet_uptime = value
    description = next(d for d in SENSORS if d.key == "inet_uptime")
    return SpeedportSensor(coordinator, description)


@pytest.mark.parametrize(
    ("value", "expected", "utc_offset"),
    [
        # Summer time (CEST)
        ("2026-07-01 12:34:56", datetime(2026, 7, 1, 12, 34), timedelta(hours=2)),
        # Winter time (CET)
        ("2026-01-15 08:00:10", datetime(2026, 1, 15, 8, 0), timedelta(hours=1)),
    ],
)
def test_inet_uptime_is_aware_berlin_time(
    value: str, expected: datetime, utc_offset: timedelta
) -> None:
    """The uptime timestamp is router-local Berlin time, truncated to minutes."""
    result = _uptime_sensor(value).native_value

    assert isinstance(result, datetime)
    assert result.tzinfo is ROUTER_TIME_ZONE
    assert result.replace(tzinfo=None) == expected
    assert result.utcoffset() == utc_offset


@pytest.mark.parametrize("value", ["", "not a date", "2026-13-01 00:00:00"])
def test_inet_uptime_invalid_value_is_none(value: str) -> None:
    """Empty or unparsable timestamps give no value."""
    assert _uptime_sensor(value).native_value is None
