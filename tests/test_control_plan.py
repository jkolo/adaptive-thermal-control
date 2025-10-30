"""Tests for MPC control plan export (T3.3.2)."""

import numpy as np
import pytest
from unittest.mock import Mock, AsyncMock, patch

from custom_components.adaptive_thermal_control.climate import AdaptiveThermalClimate
from custom_components.adaptive_thermal_control.mpc_controller import MPCResult
from custom_components.adaptive_thermal_control.const import (
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_ENTITY,
    CONF_VALVE_ENTITIES,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.states = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_add_listener = Mock()
    return coordinator


@pytest.fixture
def climate_entity(mock_hass, mock_coordinator):
    """Create a climate entity for testing."""
    config = {
        CONF_ROOM_NAME: "Living Room",
        CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
        CONF_VALVE_ENTITIES: ["number.living_room_valve"],
    }

    entity = AdaptiveThermalClimate(
        hass=mock_hass,
        coordinator=mock_coordinator,
        config=config,
        unique_id="test_climate_1",
    )

    return entity


def test_control_plan_initially_none(climate_entity):
    """Test that control_plan is initially None."""
    assert climate_entity._control_plan is None
    assert climate_entity._predicted_temps is None

    # Should not be in extra_state_attributes when None
    attrs = climate_entity.extra_state_attributes
    assert "control_plan" not in attrs
    assert "predicted_temps" not in attrs


def test_control_plan_stored_after_mpc(climate_entity):
    """Test that control_plan is stored after MPC optimization."""
    # Simulate MPC result
    u_optimal = np.array([45.5, 50.2, 55.8, 60.1, 65.3])
    predicted_temps = np.array([20.0, 20.5, 21.0, 21.2, 21.5, 21.6])

    result = MPCResult(
        u_optimal=u_optimal,
        u_first=45.5,
        cost=123.45,
        success=True,
        message="Optimization successful",
        iterations=15,
        predicted_temps=predicted_temps,
    )

    # Manually set the control plan (simulating what _async_control_with_mpc does)
    climate_entity._control_plan = [round(float(u), 2) for u in result.u_optimal]
    climate_entity._predicted_temps = [round(float(t), 2) for t in result.predicted_temps]

    # Verify storage
    assert climate_entity._control_plan == [45.5, 50.2, 55.8, 60.1, 65.3]
    assert climate_entity._predicted_temps == [20.0, 20.5, 21.0, 21.2, 21.5, 21.6]


def test_control_plan_in_extra_attributes(climate_entity):
    """Test that control_plan appears in extra_state_attributes."""
    # Set control plan
    climate_entity._control_plan = [40.0, 45.0, 50.0, 55.0]
    climate_entity._predicted_temps = [20.0, 20.5, 21.0, 21.5]

    # Get attributes
    attrs = climate_entity.extra_state_attributes

    # Verify export
    assert "control_plan" in attrs
    assert attrs["control_plan"] == [40.0, 45.0, 50.0, 55.0]
    assert "predicted_temps" in attrs
    assert attrs["predicted_temps"] == [20.0, 20.5, 21.0, 21.5]


def test_control_plan_without_predictions(climate_entity):
    """Test control_plan without predicted_temps (None case)."""
    # Set only control plan
    climate_entity._control_plan = [40.0, 45.0, 50.0]
    climate_entity._predicted_temps = None

    attrs = climate_entity.extra_state_attributes

    # Control plan should be present
    assert "control_plan" in attrs
    assert attrs["control_plan"] == [40.0, 45.0, 50.0]

    # Predictions should not be present
    assert "predicted_temps" not in attrs


def test_control_plan_rounding(climate_entity):
    """Test that control plan values are properly rounded."""
    # Set control plan with high precision values
    u_optimal = np.array([45.5678, 50.2345, 55.8912])
    climate_entity._control_plan = [round(float(u), 2) for u in u_optimal]

    attrs = climate_entity.extra_state_attributes

    # Should be rounded to 2 decimal places
    assert attrs["control_plan"] == [45.57, 50.23, 55.89]


def test_predicted_temps_rounding(climate_entity):
    """Test that predicted temperatures are properly rounded."""
    # Set predicted temps with high precision values
    predicted_temps = np.array([20.1234, 20.5678, 21.0912])
    climate_entity._predicted_temps = [round(float(t), 2) for t in predicted_temps]

    attrs = climate_entity.extra_state_attributes

    # Should be rounded to 2 decimal places
    assert attrs["predicted_temps"] == [20.12, 20.57, 21.09]


def test_control_plan_length_matches_nc(climate_entity):
    """Test that control_plan length matches control horizon (Nc)."""
    # Typical MPC with Nc=12
    u_optimal = np.array([40.0] * 12)
    climate_entity._control_plan = [round(float(u), 2) for u in u_optimal]

    attrs = climate_entity.extra_state_attributes

    # Should have exactly Nc elements
    assert len(attrs["control_plan"]) == 12


def test_predicted_temps_length_matches_np(climate_entity):
    """Test that predicted_temps length matches prediction horizon (Np+1)."""
    # Typical MPC with Np=24 (includes initial state T(0))
    predicted_temps = np.array([20.0] * 25)  # 25 = Np + 1
    climate_entity._predicted_temps = [round(float(t), 2) for t in predicted_temps]

    attrs = climate_entity.extra_state_attributes

    # Should have Np+1 elements
    assert len(attrs["predicted_temps"]) == 25


def test_control_plan_updates_on_new_mpc(climate_entity):
    """Test that control_plan updates with new MPC optimization."""
    # First optimization
    climate_entity._control_plan = [40.0, 45.0, 50.0]
    attrs1 = climate_entity.extra_state_attributes
    assert attrs1["control_plan"] == [40.0, 45.0, 50.0]

    # Second optimization with different plan
    climate_entity._control_plan = [35.0, 42.0, 48.0]
    attrs2 = climate_entity.extra_state_attributes
    assert attrs2["control_plan"] == [35.0, 42.0, 48.0]


def test_control_plan_json_serializable(climate_entity):
    """Test that control_plan is JSON serializable."""
    import json

    climate_entity._control_plan = [40.0, 45.0, 50.0, 55.0]
    climate_entity._predicted_temps = [20.0, 20.5, 21.0, 21.5]

    attrs = climate_entity.extra_state_attributes

    # Should be serializable to JSON
    json_str = json.dumps(attrs)
    parsed = json.loads(json_str)

    assert parsed["control_plan"] == [40.0, 45.0, 50.0, 55.0]
    assert parsed["predicted_temps"] == [20.0, 20.5, 21.0, 21.5]
