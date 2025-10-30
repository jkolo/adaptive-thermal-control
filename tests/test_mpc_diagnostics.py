"""Tests for MPC diagnostic sensors (T3.7.1)."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.adaptive_thermal_control.sensor import (
    MPCControlHorizonSensor,
    MPCOptimizationTimeSensor,
    MPCPredictionHorizonSensor,
    MPCWeightsSensor,
)


@pytest.fixture
def hass_mock():
    """Create mock Home Assistant instance."""
    hass = Mock()
    hass.states = Mock()
    return hass


@pytest.fixture
def coordinator_mock():
    """Create mock coordinator."""
    return Mock()


@pytest.fixture
def climate_state_mock():
    """Create mock climate entity state with MPC attributes."""
    state = Mock()
    state.attributes = {
        "mpc_prediction_horizon": 24,
        "mpc_control_horizon": 12,
        "mpc_weights": {
            "comfort": 0.7,
            "energy": 0.2,
            "smooth": 0.1,
        },
        "mpc_optimization_time": 0.0042,  # 4.2ms
    }
    return state


class TestMPCPredictionHorizonSensor:
    """Test suite for MPCPredictionHorizonSensor."""

    def test_sensor_initialization(self, coordinator_mock):
        """Test sensor initialization."""
        sensor = MPCPredictionHorizonSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.living_room",
            room_id="Living Room",
        )

        assert sensor._attr_name == "Living Room MPC Prediction Horizon"
        assert sensor._attr_unique_id == "climate.living_room_mpc_prediction_horizon"
        assert sensor._attr_native_unit_of_measurement == "steps"
        assert sensor._attr_icon == "mdi:timeline-clock"

    def test_native_value_returns_Np(self, hass_mock, coordinator_mock, climate_state_mock):
        """Test that native_value returns Np from climate entity."""
        sensor = MPCPredictionHorizonSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.living_room",
            room_id="Living Room",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = climate_state_mock

        assert sensor.native_value == 24

    def test_native_value_returns_none_when_climate_unavailable(
        self, hass_mock, coordinator_mock
    ):
        """Test that native_value returns None when climate entity not available."""
        sensor = MPCPredictionHorizonSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.living_room",
            room_id="Living Room",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = None

        assert sensor.native_value is None

    def test_extra_attributes_includes_horizon_hours(
        self, hass_mock, coordinator_mock, climate_state_mock
    ):
        """Test that extra attributes include horizon in hours."""
        sensor = MPCPredictionHorizonSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.living_room",
            room_id="Living Room",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = climate_state_mock

        attrs = sensor.extra_state_attributes

        # Np=24, dt=600s → 24 * 600 / 3600 = 4.0 hours
        assert attrs["horizon_hours"] == 4.0
        assert attrs["timestep_seconds"] == 600
        assert "description" in attrs


class TestMPCControlHorizonSensor:
    """Test suite for MPCControlHorizonSensor."""

    def test_sensor_initialization(self, coordinator_mock):
        """Test sensor initialization."""
        sensor = MPCControlHorizonSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.bedroom",
            room_id="Bedroom",
        )

        assert sensor._attr_name == "Bedroom MPC Control Horizon"
        assert sensor._attr_unique_id == "climate.bedroom_mpc_control_horizon"
        assert sensor._attr_native_unit_of_measurement == "steps"
        assert sensor._attr_icon == "mdi:timeline-clock-outline"

    def test_native_value_returns_Nc(self, hass_mock, coordinator_mock, climate_state_mock):
        """Test that native_value returns Nc from climate entity."""
        sensor = MPCControlHorizonSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.bedroom",
            room_id="Bedroom",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = climate_state_mock

        assert sensor.native_value == 12

    def test_extra_attributes_includes_horizon_hours(
        self, hass_mock, coordinator_mock, climate_state_mock
    ):
        """Test that extra attributes include horizon in hours."""
        sensor = MPCControlHorizonSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.bedroom",
            room_id="Bedroom",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = climate_state_mock

        attrs = sensor.extra_state_attributes

        # Nc=12, dt=600s → 12 * 600 / 3600 = 2.0 hours
        assert attrs["horizon_hours"] == 2.0
        assert attrs["timestep_seconds"] == 600


class TestMPCWeightsSensor:
    """Test suite for MPCWeightsSensor."""

    def test_sensor_initialization(self, coordinator_mock):
        """Test sensor initialization."""
        sensor = MPCWeightsSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.kitchen",
            room_id="Kitchen",
        )

        assert sensor._attr_name == "Kitchen MPC Weights"
        assert sensor._attr_unique_id == "climate.kitchen_mpc_weights"
        assert sensor._attr_icon == "mdi:weight"

    def test_native_value_formats_weights_as_string(
        self, hass_mock, coordinator_mock, climate_state_mock
    ):
        """Test that native_value returns formatted weight string."""
        sensor = MPCWeightsSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.kitchen",
            room_id="Kitchen",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = climate_state_mock

        value = sensor.native_value

        assert value == "comfort: 0.70, energy: 0.20, smooth: 0.10"

    def test_native_value_returns_none_when_no_weights(
        self, hass_mock, coordinator_mock
    ):
        """Test that native_value returns None when weights unavailable."""
        sensor = MPCWeightsSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.kitchen",
            room_id="Kitchen",
        )
        sensor.hass = hass_mock

        # Climate state exists but no weights
        state = Mock()
        state.attributes = {}
        hass_mock.states.get.return_value = state

        assert sensor.native_value is None

    def test_extra_attributes_includes_individual_weights(
        self, hass_mock, coordinator_mock, climate_state_mock
    ):
        """Test that extra attributes include individual weight values."""
        sensor = MPCWeightsSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.kitchen",
            room_id="Kitchen",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = climate_state_mock

        attrs = sensor.extra_state_attributes

        assert attrs["comfort_weight"] == 0.7
        assert attrs["energy_weight"] == 0.2
        assert attrs["smooth_weight"] == 0.1
        assert "description" in attrs


class TestMPCOptimizationTimeSensor:
    """Test suite for MPCOptimizationTimeSensor."""

    def test_sensor_initialization(self, coordinator_mock):
        """Test sensor initialization."""
        sensor = MPCOptimizationTimeSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.office",
            room_id="Office",
        )

        assert sensor._attr_name == "Office MPC Optimization Time"
        assert sensor._attr_unique_id == "climate.office_mpc_optimization_time"
        assert sensor._attr_native_unit_of_measurement == "s"
        assert sensor._attr_icon == "mdi:timer-outline"
        assert sensor._attr_suggested_display_precision == 4

    def test_native_value_returns_optimization_time(
        self, hass_mock, coordinator_mock, climate_state_mock
    ):
        """Test that native_value returns optimization time in seconds."""
        sensor = MPCOptimizationTimeSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.office",
            room_id="Office",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = climate_state_mock

        assert sensor.native_value == 0.0042

    def test_native_value_returns_none_when_no_time(
        self, hass_mock, coordinator_mock
    ):
        """Test that native_value returns None when time unavailable."""
        sensor = MPCOptimizationTimeSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.office",
            room_id="Office",
        )
        sensor.hass = hass_mock

        # Climate state exists but no optimization time
        state = Mock()
        state.attributes = {}
        hass_mock.states.get.return_value = state

        assert sensor.native_value is None

    def test_extra_attributes_includes_milliseconds(
        self, hass_mock, coordinator_mock, climate_state_mock
    ):
        """Test that extra attributes include time in milliseconds."""
        sensor = MPCOptimizationTimeSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.office",
            room_id="Office",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = climate_state_mock

        attrs = sensor.extra_state_attributes

        # 0.0042s = 4.2ms
        assert attrs["milliseconds"] == 4.2
        assert "description" in attrs
        assert "target" in attrs

    def test_extra_attributes_returns_empty_when_no_time(
        self, hass_mock, coordinator_mock
    ):
        """Test that extra attributes are empty when no time available."""
        sensor = MPCOptimizationTimeSensor(
            coordinator=coordinator_mock,
            climate_entity="climate.office",
            room_id="Office",
        )
        sensor.hass = hass_mock
        hass_mock.states.get.return_value = None

        attrs = sensor.extra_state_attributes

        assert attrs == {}


class TestMPCDiagnosticsIntegration:
    """Integration tests for MPC diagnostic sensors."""

    def test_all_sensors_handle_missing_climate_entity(
        self, hass_mock, coordinator_mock
    ):
        """Test that all sensors handle missing climate entity gracefully."""
        sensors = [
            MPCPredictionHorizonSensor(
                coordinator_mock, "climate.test", "Test"
            ),
            MPCControlHorizonSensor(
                coordinator_mock, "climate.test", "Test"
            ),
            MPCWeightsSensor(
                coordinator_mock, "climate.test", "Test"
            ),
            MPCOptimizationTimeSensor(
                coordinator_mock, "climate.test", "Test"
            ),
        ]

        hass_mock.states.get.return_value = None

        for sensor in sensors:
            sensor.hass = hass_mock
            assert sensor.native_value is None

    def test_all_sensors_unique_ids_are_unique(self, coordinator_mock):
        """Test that all sensors have unique IDs."""
        sensors = [
            MPCPredictionHorizonSensor(
                coordinator_mock, "climate.test", "Test"
            ),
            MPCControlHorizonSensor(
                coordinator_mock, "climate.test", "Test"
            ),
            MPCWeightsSensor(
                coordinator_mock, "climate.test", "Test"
            ),
            MPCOptimizationTimeSensor(
                coordinator_mock, "climate.test", "Test"
            ),
        ]

        unique_ids = [s._attr_unique_id for s in sensors]
        assert len(unique_ids) == len(set(unique_ids)), "Unique IDs must be unique"

    def test_sensors_work_with_partial_attributes(
        self, hass_mock, coordinator_mock
    ):
        """Test that sensors handle partial attributes gracefully."""
        # Only some MPC attributes present
        state = Mock()
        state.attributes = {
            "mpc_prediction_horizon": 24,
            # Missing: control_horizon, weights, optimization_time
        }
        hass_mock.states.get.return_value = state

        # Prediction horizon sensor should work
        sensor_Np = MPCPredictionHorizonSensor(
            coordinator_mock, "climate.test", "Test"
        )
        sensor_Np.hass = hass_mock
        assert sensor_Np.native_value == 24

        # Other sensors should return None
        sensor_Nc = MPCControlHorizonSensor(
            coordinator_mock, "climate.test", "Test"
        )
        sensor_Nc.hass = hass_mock
        assert sensor_Nc.native_value is None

        sensor_weights = MPCWeightsSensor(
            coordinator_mock, "climate.test", "Test"
        )
        sensor_weights.hass = hass_mock
        assert sensor_weights.native_value is None

        sensor_time = MPCOptimizationTimeSensor(
            coordinator_mock, "climate.test", "Test"
        )
        sensor_time.hass = hass_mock
        assert sensor_time.native_value is None
