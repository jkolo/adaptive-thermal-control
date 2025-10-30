"""Tests for config flow (T1.2.4)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from custom_components.adaptive_thermal_control.config_flow import (
    AdaptiveThermalControlConfigFlow,
)
from custom_components.adaptive_thermal_control.const import (
    DOMAIN,
    CONF_OUTDOOR_TEMP_ENTITY,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_ENTITY,
    CONF_VALVE_ENTITIES,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.states = Mock()
    hass.config_entries = Mock()
    return hass


@pytest.fixture
def config_flow(mock_hass):
    """Create a config flow instance."""
    flow = AdaptiveThermalControlConfigFlow()
    flow.hass = mock_hass
    return flow


def test_config_flow_initialization(config_flow):
    """Test config flow initialization."""
    assert config_flow.VERSION == 1
    assert config_flow._global_config == {}
    assert config_flow._thermostats == []


@pytest.mark.asyncio
async def test_user_step_show_form(config_flow):
    """Test that user step shows form."""
    result = await config_flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert "data_schema" in result


@pytest.mark.asyncio
async def test_user_step_valid_config(config_flow, mock_hass):
    """Test user step with valid global configuration."""
    # Mock entity exists
    mock_hass.states.get.return_value = Mock()

    result = await config_flow.async_step_user(
        {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}
    )

    # Should move to add_thermostat step
    assert result["type"] == "form"
    assert result["step_id"] == "add_thermostat"
    assert config_flow._global_config == {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}


@pytest.mark.asyncio
async def test_user_step_invalid_entity(config_flow, mock_hass):
    """Test user step with invalid (non-existent) entity."""
    # Mock entity doesn't exist
    mock_hass.states.get.return_value = None

    result = await config_flow.async_step_user(
        {CONF_OUTDOOR_TEMP_ENTITY: "sensor.non_existent"}
    )

    # Should show form again with error
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert CONF_OUTDOOR_TEMP_ENTITY in result["errors"]
    assert result["errors"][CONF_OUTDOOR_TEMP_ENTITY] == "entity_not_found"


@pytest.mark.asyncio
async def test_add_thermostat_show_form(config_flow):
    """Test that add_thermostat step shows form."""
    config_flow._global_config = {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}

    result = await config_flow.async_step_add_thermostat()

    assert result["type"] == "form"
    assert result["step_id"] == "add_thermostat"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_add_thermostat_valid(config_flow, mock_hass):
    """Test adding a thermostat with valid configuration."""
    config_flow._global_config = {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}
    mock_hass.states.get.return_value = Mock()

    result = await config_flow.async_step_add_thermostat(
        {
            CONF_ROOM_NAME: "Living Room",
            CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
            CONF_VALVE_ENTITIES: ["number.living_room_valve"],
        }
    )

    # Should move to add_another step
    assert result["type"] == "form"
    assert result["step_id"] == "add_another"
    assert len(config_flow._thermostats) == 1
    assert config_flow._thermostats[0][CONF_ROOM_NAME] == "Living Room"


@pytest.mark.asyncio
async def test_add_thermostat_invalid_temp_range(config_flow, mock_hass):
    """Test adding thermostat with invalid temperature range (min > max)."""
    config_flow._global_config = {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}
    mock_hass.states.get.return_value = Mock()

    result = await config_flow.async_step_add_thermostat(
        {
            CONF_ROOM_NAME: "Living Room",
            CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
            CONF_VALVE_ENTITIES: ["number.living_room_valve"],
            CONF_MIN_TEMP: 25.0,
            CONF_MAX_TEMP: 20.0,  # Lower than min!
        }
    )

    # Should show form again with error
    assert result["type"] == "form"
    assert result["step_id"] == "add_thermostat"
    assert CONF_MIN_TEMP in result["errors"]
    assert result["errors"][CONF_MIN_TEMP] == "min_max_invalid"


@pytest.mark.asyncio
async def test_add_another_yes(config_flow):
    """Test choosing to add another thermostat."""
    config_flow._global_config = {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}
    config_flow._thermostats = [
        {
            CONF_ROOM_NAME: "Living Room",
            CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
            CONF_VALVE_ENTITIES: ["number.living_room_valve"],
        }
    ]

    result = await config_flow.async_step_add_another({"add_another": True})

    # Should go back to add_thermostat
    assert result["type"] == "form"
    assert result["step_id"] == "add_thermostat"


@pytest.mark.asyncio
async def test_add_another_no_creates_entry(config_flow):
    """Test choosing not to add another thermostat creates entry."""
    config_flow._global_config = {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}
    config_flow._thermostats = [
        {
            CONF_ROOM_NAME: "Living Room",
            CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
            CONF_VALVE_ENTITIES: ["number.living_room_valve"],
        }
    ]

    result = await config_flow.async_step_add_another({"add_another": False})

    # Should create entry
    assert result["type"] == "create_entry"
    assert result["title"] == "Adaptive Thermal Control"
    assert "data" in result
    assert "thermostats" in result["data"]
    assert len(result["data"]["thermostats"]) == 1


@pytest.mark.asyncio
async def test_complete_flow_multiple_thermostats(config_flow, mock_hass):
    """Test complete flow with multiple thermostats."""
    mock_hass.states.get.return_value = Mock()

    # Global config
    result = await config_flow.async_step_user(
        {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}
    )
    assert result["step_id"] == "add_thermostat"

    # First thermostat
    result = await config_flow.async_step_add_thermostat(
        {
            CONF_ROOM_NAME: "Living Room",
            CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
            CONF_VALVE_ENTITIES: ["number.living_room_valve"],
        }
    )
    assert result["step_id"] == "add_another"

    # Add another
    result = await config_flow.async_step_add_another({"add_another": True})
    assert result["step_id"] == "add_thermostat"

    # Second thermostat
    result = await config_flow.async_step_add_thermostat(
        {
            CONF_ROOM_NAME: "Bedroom",
            CONF_ROOM_TEMP_ENTITY: "sensor.bedroom_temp",
            CONF_VALVE_ENTITIES: ["number.bedroom_valve"],
        }
    )
    assert result["step_id"] == "add_another"

    # Don't add more
    result = await config_flow.async_step_add_another({"add_another": False})

    # Should create entry with 2 thermostats
    assert result["type"] == "create_entry"
    assert len(result["data"]["thermostats"]) == 2
    assert result["data"]["thermostats"][0][CONF_ROOM_NAME] == "Living Room"
    assert result["data"]["thermostats"][1][CONF_ROOM_NAME] == "Bedroom"


@pytest.mark.asyncio
async def test_validation_empty_room_name(config_flow, mock_hass):
    """Test validation rejects empty room name."""
    config_flow._global_config = {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}
    mock_hass.states.get.return_value = Mock()

    result = await config_flow.async_step_add_thermostat(
        {
            CONF_ROOM_NAME: "",  # Empty name
            CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
            CONF_VALVE_ENTITIES: ["number.living_room_valve"],
        }
    )

    # Should show form again with error
    assert result["type"] == "form"
    assert result["step_id"] == "add_thermostat"
    assert CONF_ROOM_NAME in result["errors"]


@pytest.mark.asyncio
async def test_global_config_stored(config_flow, mock_hass):
    """Test that global config is stored correctly."""
    mock_hass.states.get.return_value = Mock()

    await config_flow.async_step_user(
        {
            CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp",
            "heating_switch_entity": "switch.heating",
        }
    )

    assert CONF_OUTDOOR_TEMP_ENTITY in config_flow._global_config
    assert config_flow._global_config[CONF_OUTDOOR_TEMP_ENTITY] == "sensor.outdoor_temp"
    assert config_flow._global_config["heating_switch_entity"] == "switch.heating"


@pytest.mark.asyncio
async def test_thermostat_with_all_fields(config_flow, mock_hass):
    """Test adding thermostat with all optional fields."""
    config_flow._global_config = {CONF_OUTDOOR_TEMP_ENTITY: "sensor.outdoor_temp"}
    mock_hass.states.get.return_value = Mock()

    result = await config_flow.async_step_add_thermostat(
        {
            CONF_ROOM_NAME: "Living Room",
            CONF_ROOM_TEMP_ENTITY: "sensor.living_room_temp",
            CONF_VALVE_ENTITIES: ["number.living_room_valve"],
            "water_temp_in_entity": "sensor.water_in_temp",
            "water_temp_out_entity": "sensor.water_out_temp",
            CONF_MIN_TEMP: 15.0,
            CONF_MAX_TEMP: 30.0,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_another"
    assert len(config_flow._thermostats) == 1

    thermostat = config_flow._thermostats[0]
    assert thermostat["water_temp_in_entity"] == "sensor.water_in_temp"
    assert thermostat["water_temp_out_entity"] == "sensor.water_out_temp"
    assert thermostat[CONF_MIN_TEMP] == 15.0
    assert thermostat[CONF_MAX_TEMP] == 30.0
