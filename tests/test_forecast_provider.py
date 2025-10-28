"""Tests for forecast provider."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock

import numpy as np
import pytest

from custom_components.adaptive_thermal_control.forecast_provider import (
    ForecastProvider,
)


class TestForecastProvider:
    """Test ForecastProvider class."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.states = MagicMock()
        return hass

    @pytest.fixture
    def forecast_provider(self, mock_hass):
        """Create forecast provider for testing."""
        return ForecastProvider(
            hass=mock_hass,
            weather_entity="weather.home",
            outdoor_temp_entity="sensor.outdoor_temperature",
        )

    @pytest.mark.asyncio
    async def test_initialization(self, mock_hass):
        """Test forecast provider initialization."""
        provider = ForecastProvider(
            hass=mock_hass,
            weather_entity="weather.home",
            outdoor_temp_entity="sensor.outdoor_temp",
        )

        assert provider._hass is mock_hass
        assert provider._weather_entity == "weather.home"
        assert provider._outdoor_temp_entity == "sensor.outdoor_temp"

    @pytest.mark.asyncio
    async def test_initialization_without_entities(self, mock_hass):
        """Test initialization without weather entities."""
        provider = ForecastProvider(hass=mock_hass)

        assert provider._weather_entity is None
        assert provider._outdoor_temp_entity is None

    @pytest.mark.asyncio
    async def test_get_current_outdoor_temperature_from_sensor(
        self, mock_hass, forecast_provider
    ):
        """Test getting current temperature from outdoor sensor."""
        # Mock outdoor temperature sensor
        mock_state = Mock()
        mock_state.state = "15.5"
        mock_hass.states.get.return_value = mock_state

        temp = await forecast_provider._get_current_outdoor_temperature()

        assert temp == 15.5
        mock_hass.states.get.assert_called_with("sensor.outdoor_temperature")

    @pytest.mark.asyncio
    async def test_get_current_outdoor_temperature_from_weather(self, mock_hass):
        """Test getting current temperature from weather entity."""
        provider = ForecastProvider(
            hass=mock_hass,
            weather_entity="weather.home",
            outdoor_temp_entity=None,  # No sensor
        )

        # Mock weather entity
        mock_state = Mock()
        mock_state.attributes = {"temperature": 12.3}
        mock_hass.states.get.return_value = mock_state

        temp = await provider._get_current_outdoor_temperature()

        assert temp == 12.3

    @pytest.mark.asyncio
    async def test_get_current_outdoor_temperature_fallback(self, mock_hass):
        """Test fallback when no temperature available."""
        provider = ForecastProvider(hass=mock_hass)
        mock_hass.states.get.return_value = None

        temp = await provider._get_current_outdoor_temperature()

        # Should return default fallback value
        assert temp == 10.0

    @pytest.mark.asyncio
    async def test_constant_forecast_when_no_weather_entity(self, mock_hass):
        """Test constant forecast when weather entity not available."""
        provider = ForecastProvider(
            hass=mock_hass, outdoor_temp_entity="sensor.outdoor_temp"
        )

        # Mock current temperature
        mock_state = Mock()
        mock_state.state = "8.5"
        mock_hass.states.get.return_value = mock_state

        forecast = await provider.get_outdoor_temperature_forecast(hours=2.0, dt=600.0)

        # Should return constant forecast
        assert len(forecast) == 12  # 2 hours / 10 minutes = 12 steps
        assert np.all(forecast == 8.5)

    @pytest.mark.asyncio
    async def test_extract_forecast_data(self, forecast_provider):
        """Test extraction of forecast data."""
        now = datetime.now()

        forecast_attr = [
            {
                "datetime": (now + timedelta(hours=1)).isoformat(),
                "temperature": 10.0,
            },
            {
                "datetime": (now + timedelta(hours=2)).isoformat(),
                "temperature": 12.0,
            },
            {
                "datetime": (now + timedelta(hours=3)).isoformat(),
                "temperature": 14.0,
            },
        ]

        temps, times = forecast_provider._extract_forecast_data(forecast_attr, max_hours=4.0)

        assert len(temps) == 3
        assert len(times) == 3
        assert temps == [10.0, 12.0, 14.0]
        assert 0.9 < times[0] < 1.1  # ~1 hour
        assert 1.9 < times[1] < 2.1  # ~2 hours
        assert 2.9 < times[2] < 3.1  # ~3 hours

    @pytest.mark.asyncio
    async def test_extract_forecast_data_with_temp_key(self, forecast_provider):
        """Test extraction with 'temp' key instead of 'temperature'."""
        now = datetime.now()

        forecast_attr = [
            {
                "datetime": (now + timedelta(hours=1)).isoformat(),
                "temp": 15.0,  # Using 'temp' key
            },
        ]

        temps, times = forecast_provider._extract_forecast_data(forecast_attr, max_hours=4.0)

        assert len(temps) == 1
        assert temps[0] == 15.0

    @pytest.mark.asyncio
    async def test_extract_forecast_data_filters_old_data(self, forecast_provider):
        """Test that old forecast data is filtered out."""
        now = datetime.now()

        forecast_attr = [
            {
                "datetime": (now - timedelta(hours=1)).isoformat(),  # Past
                "temperature": 8.0,
            },
            {
                "datetime": (now + timedelta(hours=1)).isoformat(),  # Future
                "temperature": 10.0,
            },
        ]

        temps, times = forecast_provider._extract_forecast_data(forecast_attr, max_hours=4.0)

        # Should only include future data
        assert len(temps) == 1
        assert temps[0] == 10.0

    @pytest.mark.asyncio
    async def test_interpolate_forecast(self, forecast_provider):
        """Test forecast interpolation."""
        temps = [10.0, 15.0, 20.0]
        times = [0.0, 2.0, 4.0]  # Hours
        dt = 3600.0  # 1 hour
        n_steps = 5

        interpolated = forecast_provider._interpolate_forecast(temps, times, dt, n_steps)

        assert len(interpolated) == 5
        assert interpolated[0] == 10.0  # t=0h
        assert 12.0 < interpolated[1] < 13.0  # t=1h (interpolated)
        assert interpolated[2] == 15.0  # t=2h
        assert 17.0 < interpolated[3] < 18.0  # t=3h (interpolated)
        assert interpolated[4] == 20.0  # t=4h

    @pytest.mark.asyncio
    async def test_interpolate_forecast_extrapolates(self, forecast_provider):
        """Test that interpolation extrapolates beyond available data."""
        temps = [10.0, 15.0]
        times = [0.0, 2.0]
        dt = 3600.0  # 1 hour
        n_steps = 5  # Need 5 steps but only have data for 2

        interpolated = forecast_provider._interpolate_forecast(temps, times, dt, n_steps)

        assert len(interpolated) == 5
        # Should extrapolate with last value
        assert interpolated[3] == 15.0
        assert interpolated[4] == 15.0

    @pytest.mark.asyncio
    async def test_get_weather_forecast_with_valid_data(self, mock_hass, forecast_provider):
        """Test getting forecast from weather entity."""
        now = datetime.now()

        # Mock weather entity with forecast
        # Use clearly future times to avoid timing issues
        mock_state = Mock()
        mock_state.attributes = {
            "forecast": [
                {
                    "datetime": (now + timedelta(minutes=30)).isoformat(),
                    "temperature": 10.0,
                },
                {
                    "datetime": (now + timedelta(hours=1, minutes=30)).isoformat(),
                    "temperature": 12.0,
                },
                {
                    "datetime": (now + timedelta(hours=2, minutes=30)).isoformat(),
                    "temperature": 14.0,
                },
                {
                    "datetime": (now + timedelta(hours=3, minutes=30)).isoformat(),
                    "temperature": 16.0,
                },
            ]
        }
        mock_hass.states.get.return_value = mock_state

        forecast = await forecast_provider.get_outdoor_temperature_forecast(
            hours=4.0, dt=3600.0
        )

        # Should have 4 hourly steps
        assert len(forecast) == 4
        # Forecast should be interpolated from source data
        # Values should be reasonable (between 10 and 16)
        assert all(10.0 <= temp <= 16.0 for temp in forecast)
        # Should be monotonically increasing (as source data is)
        assert forecast[0] <= forecast[1] <= forecast[2] <= forecast[3]

    @pytest.mark.asyncio
    async def test_get_weather_forecast_entity_not_found(self, mock_hass, forecast_provider):
        """Test handling when weather entity not found."""
        mock_hass.states.get.return_value = None

        # Should fallback to constant temperature
        forecast = await forecast_provider.get_outdoor_temperature_forecast(
            hours=2.0, dt=600.0
        )

        assert len(forecast) == 12
        # Should be constant (fallback value)
        assert np.all(forecast == forecast[0])

    @pytest.mark.asyncio
    async def test_get_weather_forecast_no_forecast_attribute(
        self, mock_hass, forecast_provider
    ):
        """Test handling when forecast attribute missing."""
        mock_state = Mock()
        mock_state.attributes = {}  # No forecast
        mock_hass.states.get.return_value = mock_state

        # Should fallback to constant temperature
        forecast = await forecast_provider.get_outdoor_temperature_forecast(
            hours=2.0, dt=600.0
        )

        assert len(forecast) == 12
        assert np.all(forecast == forecast[0])

    @pytest.mark.asyncio
    async def test_get_solar_forecast_placeholder(self, forecast_provider):
        """Test solar forecast placeholder."""
        forecast = await forecast_provider.get_solar_forecast(hours=4.0, dt=600.0)

        # Should return zeros (placeholder)
        assert len(forecast) == 24
        assert np.all(forecast == 0.0)

    @pytest.mark.asyncio
    async def test_set_weather_entity(self, forecast_provider):
        """Test updating weather entity."""
        forecast_provider.set_weather_entity("weather.new")

        assert forecast_provider._weather_entity == "weather.new"

    @pytest.mark.asyncio
    async def test_set_outdoor_temp_entity(self, forecast_provider):
        """Test updating outdoor temperature entity."""
        forecast_provider.set_outdoor_temp_entity("sensor.new_outdoor_temp")

        assert forecast_provider._outdoor_temp_entity == "sensor.new_outdoor_temp"

    @pytest.mark.asyncio
    async def test_forecast_with_different_time_steps(self, mock_hass):
        """Test forecast generation with different time steps."""
        provider = ForecastProvider(
            hass=mock_hass, outdoor_temp_entity="sensor.outdoor_temp"
        )

        # Mock current temperature
        mock_state = Mock()
        mock_state.state = "20.0"
        mock_hass.states.get.return_value = mock_state

        # Test different time steps
        forecast_10min = await provider.get_outdoor_temperature_forecast(
            hours=1.0, dt=600.0
        )
        forecast_5min = await provider.get_outdoor_temperature_forecast(
            hours=1.0, dt=300.0
        )

        assert len(forecast_10min) == 6  # 1h / 10min
        assert len(forecast_5min) == 12  # 1h / 5min

    @pytest.mark.asyncio
    async def test_forecast_different_horizons(self, mock_hass):
        """Test forecast generation with different horizons."""
        provider = ForecastProvider(
            hass=mock_hass, outdoor_temp_entity="sensor.outdoor_temp"
        )

        mock_state = Mock()
        mock_state.state = "15.0"
        mock_hass.states.get.return_value = mock_state

        # Test different horizons
        forecast_2h = await provider.get_outdoor_temperature_forecast(
            hours=2.0, dt=600.0
        )
        forecast_8h = await provider.get_outdoor_temperature_forecast(
            hours=8.0, dt=600.0
        )

        assert len(forecast_2h) == 12  # 2h / 10min
        assert len(forecast_8h) == 48  # 8h / 10min
