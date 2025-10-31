"""Tests for climate entity temperature sensor subscription mechanism."""

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

    # Mock async_write_ha_state to avoid entity_id requirements in unit tests
    entity.async_write_ha_state = Mock()

    return entity


@pytest.mark.asyncio
async def test_async_added_to_hass_subscribes_to_sensor(climate_entity, mock_hass):
    """Test that async_added_to_hass subscribes to temperature sensor changes."""
    with patch(
        "custom_components.adaptive_thermal_control.climate.async_track_state_change_event"
    ) as mock_track:
        # Call async_added_to_hass
        await climate_entity.async_added_to_hass()

        # Verify subscription was created
        mock_track.assert_called_once_with(
            mock_hass,
            ["sensor.living_room_temp"],
            climate_entity._async_sensor_state_changed,
        )


@pytest.mark.asyncio
async def test_sensor_state_changed_updates_temperature(climate_entity):
    """Test that sensor state changes update the temperature."""
    # Initial temperature is None
    assert climate_entity._attr_current_temperature is None

    # Create mock event with new temperature
    mock_event = Mock()
    mock_state = Mock()
    mock_state.state = "22.5"
    mock_event.data = {"new_state": mock_state}

    # Call the callback
    climate_entity._async_sensor_state_changed(mock_event)

    # Verify temperature was updated
    assert climate_entity._attr_current_temperature == 22.5


@pytest.mark.asyncio
async def test_sensor_state_changed_handles_unavailable(climate_entity):
    """Test that sensor unavailability is handled correctly."""
    # Set initial temperature
    climate_entity._attr_current_temperature = 22.5

    # Create mock event with unavailable state
    mock_event = Mock()
    mock_state = Mock()
    mock_state.state = "unavailable"
    mock_event.data = {"new_state": mock_state}

    # Call the callback
    climate_entity._async_sensor_state_changed(mock_event)

    # Verify temperature was set to None
    assert climate_entity._attr_current_temperature is None


@pytest.mark.asyncio
async def test_sensor_recovery_triggers_control(climate_entity, mock_hass):
    """Test that sensor recovery triggers heating control."""
    # Temperature is initially None (sensor was unavailable)
    climate_entity._attr_current_temperature = None

    # Create mock event with recovered temperature
    mock_event = Mock()
    mock_state = Mock()
    mock_state.state = "21.0"
    mock_event.data = {"new_state": mock_state}

    # Call the callback
    climate_entity._async_sensor_state_changed(mock_event)

    # Verify temperature was updated
    assert climate_entity._attr_current_temperature == 21.0

    # Verify control update was triggered
    mock_hass.async_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_sensor_state_changed_handles_invalid_value(climate_entity):
    """Test that invalid temperature values are handled gracefully."""
    # Set initial temperature
    climate_entity._attr_current_temperature = 22.0

    # Create mock event with invalid temperature
    mock_event = Mock()
    mock_state = Mock()
    mock_state.state = "not_a_number"
    mock_event.data = {"new_state": mock_state}

    # Call the callback
    climate_entity._async_sensor_state_changed(mock_event)

    # Verify temperature was set to None (error case)
    assert climate_entity._attr_current_temperature is None


@pytest.mark.asyncio
async def test_sensor_state_changed_handles_none_state(climate_entity):
    """Test that None state is handled correctly."""
    # Set initial temperature
    climate_entity._attr_current_temperature = 22.0

    # Create mock event with None state
    mock_event = Mock()
    mock_event.data = {"new_state": None}

    # Call the callback
    climate_entity._async_sensor_state_changed(mock_event)

    # Verify temperature was set to None
    assert climate_entity._attr_current_temperature is None


@pytest.mark.asyncio
async def test_sensor_normal_update_no_control_trigger(climate_entity, mock_hass):
    """Test that normal temperature updates don't trigger control (only recovery does)."""
    # Set initial temperature (sensor was available)
    climate_entity._attr_current_temperature = 22.0

    # Create mock event with new temperature
    mock_event = Mock()
    mock_state = Mock()
    mock_state.state = "22.5"
    mock_event.data = {"new_state": mock_state}

    # Call the callback
    climate_entity._async_sensor_state_changed(mock_event)

    # Verify temperature was updated
    assert climate_entity._attr_current_temperature == 22.5

    # Verify control update was NOT triggered (only recovery triggers control)
    mock_hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_sensor_state_changed_calls_async_write_ha_state(climate_entity):
    """Test that sensor state changes trigger state write."""
    # Reset the mock to track calls
    climate_entity.async_write_ha_state.reset_mock()

    # Create mock event
    mock_event = Mock()
    mock_state = Mock()
    mock_state.state = "23.0"
    mock_event.data = {"new_state": mock_state}

    # Call the callback
    climate_entity._async_sensor_state_changed(mock_event)

    # Verify state was written
    climate_entity.async_write_ha_state.assert_called_once()
