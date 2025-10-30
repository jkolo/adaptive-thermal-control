"""Tests for control quality monitoring (T3.6.2)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from custom_components.adaptive_thermal_control.climate import (
    AdaptiveThermalClimate,
)
from custom_components.adaptive_thermal_control.const import (
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_ENTITY,
    CONF_VALVE_ENTITIES,
)


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock()
    hass.services = AsyncMock()
    hass.services.async_call = AsyncMock()
    hass.states = MagicMock()
    return hass


@pytest.fixture
def mock_coordinator():
    """Create mock coordinator."""
    coordinator = MagicMock()
    coordinator.forecast_provider = AsyncMock()
    coordinator.get_thermal_model = Mock(return_value=None)
    return coordinator


@pytest.fixture
def climate_entity(mock_hass, mock_coordinator):
    """Create climate entity for testing."""
    config = {
        CONF_ROOM_NAME: "Test Room",
        CONF_ROOM_TEMP_ENTITY: "sensor.test_room_temp",
        CONF_VALVE_ENTITIES: ["climate.test_valve"],
    }

    entity = AdaptiveThermalClimate(
        hass=mock_hass,
        coordinator=mock_coordinator,
        config=config,
        unique_id="test_room_thermostat",
    )
    entity._attr_current_temperature = 20.0
    entity._attr_target_temperature = 21.0

    return entity


class TestControlQualityTracking:
    """Test suite for control quality monitoring (T3.6.2)."""

    def test_rmse_returns_none_when_no_data(self, climate_entity):
        """Test that RMSE returns None when no error data is available."""
        rmse = climate_entity.get_control_quality_rmse()
        assert rmse is None

    def test_rmse_returns_none_with_insufficient_data(self, climate_entity):
        """Test that RMSE requires at least 1 hour of data (6 samples)."""
        # Add only 5 samples (less than 1 hour)
        current_time = time.time()
        for i in range(5):
            climate_entity._temperature_errors.append((current_time - i * 600, 1.0))

        rmse = climate_entity.get_control_quality_rmse()
        assert rmse is None

    def test_rmse_calculates_correctly_with_constant_error(self, climate_entity):
        """Test RMSE calculation with constant error."""
        # Add 12 samples with constant 1.0°C error
        current_time = time.time()
        for i in range(12):
            climate_entity._temperature_errors.append((current_time - i * 600, 1.0))

        rmse = climate_entity.get_control_quality_rmse()

        # RMSE of constant 1.0 should be 1.0
        assert rmse is not None
        assert abs(rmse - 1.0) < 0.01

    def test_rmse_calculates_correctly_with_varying_errors(self, climate_entity):
        """Test RMSE calculation with varying errors."""
        # Add samples with known errors: [0, 1, 0, 1, 0, 1, ...]
        current_time = time.time()
        for i in range(12):
            error = 1.0 if i % 2 == 1 else 0.0
            climate_entity._temperature_errors.append((current_time - i * 600, error))

        rmse = climate_entity.get_control_quality_rmse()

        # RMSE = sqrt((0^2 + 1^2 + 0^2 + 1^2 + ...) / 12) = sqrt(6/12) = sqrt(0.5) ≈ 0.707
        assert rmse is not None
        assert abs(rmse - 0.707) < 0.01

    def test_rolling_window_filters_old_data(self, climate_entity):
        """Test that rolling window only includes recent 24h data."""
        current_time = time.time()

        # Add old errors (25 hours ago) - should be excluded
        for i in range(6):
            old_time = current_time - (25 * 3600) - (i * 600)
            climate_entity._temperature_errors.append((old_time, 5.0))

        # Add recent errors (within 24h) - should be included
        for i in range(12):
            recent_time = current_time - (i * 600)
            climate_entity._temperature_errors.append((recent_time, 1.0))

        rmse = climate_entity.get_control_quality_rmse(time_window_hours=24.0)

        # Should only use recent data (error=1.0)
        assert rmse is not None
        assert abs(rmse - 1.0) < 0.01

    def test_temperature_error_tracking_in_extra_attributes(self, climate_entity):
        """Test that RMSE appears in extra_state_attributes."""
        # Add some error data
        current_time = time.time()
        for i in range(12):
            climate_entity._temperature_errors.append((current_time - i * 600, 1.0))

        attrs = climate_entity.extra_state_attributes

        assert "control_quality_rmse" in attrs
        assert abs(attrs["control_quality_rmse"] - 1.0) < 0.01

    def test_deque_maxlen_limits_storage(self, climate_entity):
        """Test that deque maxlen prevents unlimited growth."""
        # maxlen is 144 (24h of 10-minute samples)
        assert climate_entity._temperature_errors.maxlen == 144

        # Add more than maxlen samples
        current_time = time.time()
        for i in range(200):
            climate_entity._temperature_errors.append((current_time - i * 600, 1.0))

        # Should only keep last 144
        assert len(climate_entity._temperature_errors) == 144

    def test_rmse_updates_over_time(self, climate_entity):
        """Test that RMSE updates as new errors are added."""
        current_time = time.time()

        # Add errors with 1.0°C deviation
        for i in range(12):
            climate_entity._temperature_errors.append((current_time - i * 600, 1.0))

        rmse1 = climate_entity.get_control_quality_rmse()
        assert rmse1 is not None
        assert abs(rmse1 - 1.0) < 0.01

        # Add more errors with 0.5°C deviation
        for i in range(12):
            climate_entity._temperature_errors.append((current_time - i * 600, 0.5))

        rmse2 = climate_entity.get_control_quality_rmse()

        # New RMSE should be lower (mix of 1.0 and 0.5)
        assert rmse2 is not None
        assert rmse2 < rmse1

    @pytest.mark.asyncio
    async def test_errors_tracked_during_control(self, climate_entity, mock_coordinator):
        """Test that errors are tracked during normal control operation."""
        # Set temperature values
        climate_entity._attr_current_temperature = 20.0
        climate_entity._attr_target_temperature = 21.0

        # Initially no errors
        assert len(climate_entity._temperature_errors) == 0

        # Run control
        await climate_entity._async_control_heating()

        # Should have recorded one error
        assert len(climate_entity._temperature_errors) == 1

        # Error should be (target - current) = 21 - 20 = 1.0°C
        timestamp, error = climate_entity._temperature_errors[0]
        assert abs(error - 1.0) < 0.01
