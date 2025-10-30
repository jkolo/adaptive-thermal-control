"""Tests for temperature prediction sensor (T3.7.2)."""

import pytest
from unittest.mock import Mock

from custom_components.adaptive_thermal_control.sensor import (
    TemperaturePredictionSensor,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.states = Mock()
    return hass


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_add_listener = Mock()
    return coordinator


@pytest.fixture
def sensor(mock_hass, mock_coordinator):
    """Create temperature prediction sensor for testing."""
    sensor = TemperaturePredictionSensor(
        coordinator=mock_coordinator,
        climate_entity="climate.living_room",
        room_id="living_room",
    )
    sensor.hass = mock_hass
    return sensor


def test_sensor_initialization(sensor):
    """Test sensor initialization."""
    assert sensor._attr_name == "living_room Temperature Prediction"
    assert sensor._attr_unique_id == "climate.living_room_temperature_prediction"
    assert sensor._attr_native_unit_of_measurement == "°C"
    assert sensor._attr_icon == "mdi:chart-line"


def test_native_value_no_climate_state(sensor, mock_hass):
    """Test native_value when climate state is unavailable."""
    mock_hass.states.get.return_value = None

    assert sensor.native_value is None


def test_native_value_no_predictions(sensor, mock_hass):
    """Test native_value when predicted_temps attribute is missing."""
    climate_state = Mock()
    climate_state.attributes = {}
    mock_hass.states.get.return_value = climate_state

    assert sensor.native_value is None


def test_native_value_with_predictions(sensor, mock_hass):
    """Test native_value with valid predicted temperatures."""
    climate_state = Mock()
    climate_state.attributes = {
        "predicted_temps": [20.0, 20.5, 21.0, 21.5, 22.0]  # T(0), T(+10min), T(+20min), ...
    }
    mock_hass.states.get.return_value = climate_state

    # Should return T(+10min), skipping T(0)
    assert sensor.native_value == 20.5


def test_native_value_single_prediction(sensor, mock_hass):
    """Test native_value when only current temperature is available."""
    climate_state = Mock()
    climate_state.attributes = {
        "predicted_temps": [20.0]  # Only T(0)
    }
    mock_hass.states.get.return_value = climate_state

    # Not enough predictions
    assert sensor.native_value is None


def test_extra_attributes_no_climate_state(sensor, mock_hass):
    """Test extra_state_attributes when climate state is unavailable."""
    mock_hass.states.get.return_value = None

    assert sensor.extra_state_attributes == {}


def test_extra_attributes_no_predictions(sensor, mock_hass):
    """Test extra_state_attributes when predicted_temps is missing."""
    climate_state = Mock()
    climate_state.attributes = {}
    mock_hass.states.get.return_value = climate_state

    assert sensor.extra_state_attributes == {}


def test_extra_attributes_with_predictions(sensor, mock_hass):
    """Test extra_state_attributes with valid predicted temperatures."""
    climate_state = Mock()
    climate_state.attributes = {
        "predicted_temps": [20.0, 20.5, 21.0, 21.5, 22.0]
    }
    mock_hass.states.get.return_value = climate_state

    attrs = sensor.extra_state_attributes

    # Check forecast structure
    assert "forecast" in attrs
    assert len(attrs["forecast"]) == 5

    # Check first forecast entry
    assert attrs["forecast"][0] == {"time": "+0min", "temperature": 20.0}
    assert attrs["forecast"][1] == {"time": "+10min", "temperature": 20.5}
    assert attrs["forecast"][2] == {"time": "+20min", "temperature": 21.0}

    # Check horizon information
    assert attrs["horizon_minutes"] == 50
    assert attrs["horizon_hours"] == pytest.approx(0.8, rel=0.1)
    assert "description" in attrs


def test_extra_attributes_full_horizon(sensor, mock_hass):
    """Test extra_state_attributes with full 4-hour prediction horizon."""
    # 25 predictions = 250 minutes = 4.17 hours (typical Np=24 + T(0))
    predicted_temps = [20.0 + i * 0.1 for i in range(25)]

    climate_state = Mock()
    climate_state.attributes = {"predicted_temps": predicted_temps}
    mock_hass.states.get.return_value = climate_state

    attrs = sensor.extra_state_attributes

    # Check forecast length
    assert len(attrs["forecast"]) == 25

    # Check last forecast entry
    assert attrs["forecast"][-1]["time"] == "+240min"
    assert attrs["forecast"][-1]["temperature"] == pytest.approx(22.4, rel=0.01)

    # Check horizon information
    assert attrs["horizon_minutes"] == 250
    assert attrs["horizon_hours"] == pytest.approx(4.2, rel=0.1)


def test_forecast_time_format(sensor, mock_hass):
    """Test that forecast time strings are correctly formatted."""
    climate_state = Mock()
    climate_state.attributes = {
        "predicted_temps": [20.0, 20.5, 21.0]
    }
    mock_hass.states.get.return_value = climate_state

    attrs = sensor.extra_state_attributes
    forecast = attrs["forecast"]

    # Check time format
    assert forecast[0]["time"] == "+0min"
    assert forecast[1]["time"] == "+10min"
    assert forecast[2]["time"] == "+20min"


def test_temperature_values_preserved(sensor, mock_hass):
    """Test that temperature values are preserved with correct precision."""
    climate_state = Mock()
    climate_state.attributes = {
        "predicted_temps": [20.12, 20.57, 21.09]
    }
    mock_hass.states.get.return_value = climate_state

    attrs = sensor.extra_state_attributes
    forecast = attrs["forecast"]

    # Temperature values should be preserved
    assert forecast[0]["temperature"] == 20.12
    assert forecast[1]["temperature"] == 20.57
    assert forecast[2]["temperature"] == 21.09


def test_empty_predictions_list(sensor, mock_hass):
    """Test handling of empty predicted_temps list."""
    climate_state = Mock()
    climate_state.attributes = {"predicted_temps": []}
    mock_hass.states.get.return_value = climate_state

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_sensor_updates_with_new_predictions(sensor, mock_hass):
    """Test that sensor value updates when predictions change."""
    climate_state = Mock()

    # First predictions
    climate_state.attributes = {"predicted_temps": [20.0, 20.5, 21.0]}
    mock_hass.states.get.return_value = climate_state
    assert sensor.native_value == 20.5

    # Updated predictions
    climate_state.attributes = {"predicted_temps": [21.0, 21.8, 22.5]}
    assert sensor.native_value == 21.8


def test_sensor_state_class(sensor):
    """Test that sensor has correct state class for statistics."""
    from homeassistant.components.sensor import SensorStateClass

    assert sensor._attr_state_class == SensorStateClass.MEASUREMENT


def test_sensor_device_class(sensor):
    """Test that sensor has correct device class."""
    from homeassistant.components.sensor import SensorDeviceClass

    assert sensor._attr_device_class == SensorDeviceClass.TEMPERATURE
