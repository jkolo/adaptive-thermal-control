"""Tests for lazy valve detection when valve entities are not available during init."""

from unittest.mock import AsyncMock, Mock, patch

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
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.states = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    hass.async_create_task = Mock()
    return hass


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_add_listener = Mock()
    return coordinator


@pytest.mark.asyncio
async def test_valve_not_available_during_init_defaults_to_position_mode(
    mock_hass, mock_coordinator
):
    """Test that when valve is not available during init, mode defaults to 'position' not 'pwm'."""
    # Setup: valve entity doesn't exist during init
    mock_hass.states.get.return_value = None

    config = {
        CONF_ROOM_NAME: "Living Room",
        CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
        CONF_VALVE_ENTITIES: ["valve.living_room_valve"],  # valve.* entity
    }

    entity = AdaptiveThermalClimate(
        hass=mock_hass,
        coordinator=mock_coordinator,
        config=config,
        unique_id="test_climate_1",
    )

    # Verify: mode should be "position" (not "pwm") because we skip unavailable valves
    assert entity._valve_control_mode == "position"


@pytest.mark.asyncio
async def test_valve_appears_later_with_set_position_uses_position_control(
    mock_hass, mock_coordinator
):
    """Test that valve appearing later with set_position support uses position control."""
    # Setup: valve entity doesn't exist during init
    mock_hass.states.get.return_value = None

    config = {
        CONF_ROOM_NAME: "Living Room",
        CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
        CONF_VALVE_ENTITIES: ["valve.living_room_valve"],
    }

    entity = AdaptiveThermalClimate(
        hass=mock_hass,
        coordinator=mock_coordinator,
        config=config,
        unique_id="test_climate_1",
    )

    # Verify mode is "position"
    assert entity._valve_control_mode == "position"

    # Now valve appears with set_position support
    mock_valve_state = Mock()
    mock_valve_state.attributes = {"supported_features": 4}  # SET_POSITION = 4
    mock_hass.states.get.return_value = mock_valve_state

    # Set valve position
    await entity._set_single_valve("valve.living_room_valve", 65.0)

    # Verify: should use set_valve_position service (not PWM)
    mock_hass.services.async_call.assert_called_once_with(
        "valve",
        "set_valve_position",
        {"entity_id": "valve.living_room_valve", "position": 65.0},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_valve_appears_later_without_set_position_uses_pwm_fallback(
    mock_hass, mock_coordinator
):
    """Test that valve appearing later without set_position falls back to PWM."""
    # Setup: valve entity doesn't exist during init
    mock_hass.states.get.return_value = None

    config = {
        CONF_ROOM_NAME: "Living Room",
        CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
        CONF_VALVE_ENTITIES: ["valve.living_room_valve"],
    }

    entity = AdaptiveThermalClimate(
        hass=mock_hass,
        coordinator=mock_coordinator,
        config=config,
        unique_id="test_climate_1",
    )

    # Verify mode is "position" (because valve was skipped during init)
    assert entity._valve_control_mode == "position"

    # Now valve appears WITHOUT set_position support
    mock_valve_state = Mock()
    mock_valve_state.attributes = {"supported_features": 0}  # No SET_POSITION
    mock_hass.states.get.return_value = mock_valve_state

    with patch.object(entity._pwm_controller, "set_duty_cycle", new_callable=AsyncMock) as mock_pwm:
        # Set valve position
        await entity._set_single_valve("valve.living_room_valve", 65.0)

        # Verify: should fallback to PWM (not set_valve_position)
        mock_pwm.assert_called_once_with(
            valve_entity="valve.living_room_valve",
            duty_cycle=65.0,
            valve_delay=0.0,
        )


@pytest.mark.asyncio
async def test_switch_entity_not_in_init_uses_pwm_fallback(mock_hass, mock_coordinator):
    """Test that switch entity uses PWM fallback even if mode is 'position'."""
    # Setup: switch entity doesn't exist during init (hypothetical edge case)
    mock_hass.states.get.return_value = None

    config = {
        CONF_ROOM_NAME: "Living Room",
        CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
        CONF_VALVE_ENTITIES: ["switch.living_room_valve"],  # switch.* entity
    }

    entity = AdaptiveThermalClimate(
        hass=mock_hass,
        coordinator=mock_coordinator,
        config=config,
        unique_id="test_climate_1",
    )

    # Note: switch entities are detected immediately during init (line 298-306)
    # so this would normally set mode to "pwm". But if somehow mode is "position",
    # the fallback should still work.

    # Force mode to "position" for testing fallback
    entity._valve_control_mode = "position"

    with patch.object(entity._pwm_controller, "set_duty_cycle", new_callable=AsyncMock) as mock_pwm:
        # Set valve position
        await entity._set_single_valve("switch.living_room_valve", 50.0)

        # Verify: should use PWM fallback
        mock_pwm.assert_called_once_with(
            valve_entity="switch.living_room_valve",
            duty_cycle=50.0,
            valve_delay=0.0,
        )


@pytest.mark.asyncio
async def test_number_entity_always_uses_position_control(mock_hass, mock_coordinator):
    """Test that number.* entities always use position control regardless of mode."""
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

    # Verify mode is "position" for number entities
    assert entity._valve_control_mode == "position"

    # Set valve position
    await entity._set_single_valve("number.living_room_valve", 75.0)

    # Verify: should use set_value service
    mock_hass.services.async_call.assert_called_once_with(
        "number",
        "set_value",
        {"entity_id": "number.living_room_valve", "value": 75.0},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_mixed_valves_some_missing_during_init(mock_hass, mock_coordinator):
    """Test detection with multiple valves where some are missing during init."""

    def mock_states_get(entity_id):
        """Mock that only returns state for first valve."""
        if entity_id == "valve.valve1":
            mock_state = Mock()
            mock_state.attributes = {"supported_features": 4}  # Has set_position
            return mock_state
        elif entity_id == "valve.valve2":
            # This valve doesn't exist yet
            return None
        return None

    mock_hass.states.get.side_effect = mock_states_get

    config = {
        CONF_ROOM_NAME: "Living Room",
        CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
        CONF_VALVE_ENTITIES: ["valve.valve1", "valve.valve2"],
    }

    entity = AdaptiveThermalClimate(
        hass=mock_hass,
        coordinator=mock_coordinator,
        config=config,
        unique_id="test_climate_1",
    )

    # Should be "position" mode because valve1 has set_position and valve2 is skipped
    assert entity._valve_control_mode == "position"
