"""Climate platform for Adaptive Thermal Control integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CONTROLLER_TYPE,
    ATTR_HEATING_DEMAND,
    ATTR_VALVE_POSITION,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_ENTITY,
    CONF_VALVE_ENTITIES,
    CONTROLLER_TYPE_PI,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_MANUAL,
    PRESET_SLEEP,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Adaptive Thermal Control climate entities from a config entry.

    Args:
        hass: Home Assistant instance
        entry: ConfigEntry containing configuration
        async_add_entities: Callback to add entities
    """
    _LOGGER.info("Setting up Adaptive Thermal Control climate platform")

    # Get configuration from entry
    config = hass.data[DOMAIN][entry.entry_id]

    # Create climate entities for each thermostat
    entities = []
    thermostats = config.get("thermostats", [])

    for idx, thermostat_config in enumerate(thermostats):
        entity = AdaptiveThermalClimate(
            hass=hass,
            entry=entry,
            config=thermostat_config,
            unique_id=f"{entry.entry_id}_thermostat_{idx}",
        )
        entities.append(entity)

    # Add entities
    async_add_entities(entities, update_before_add=True)

    _LOGGER.info("Added %d climate entities", len(entities))


class AdaptiveThermalClimate(ClimateEntity):
    """Representation of an Adaptive Thermal Control climate entity."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = [PRESET_HOME, PRESET_AWAY, PRESET_SLEEP, PRESET_MANUAL]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
        unique_id: str,
    ) -> None:
        """Initialize the climate entity.

        Args:
            hass: Home Assistant instance
            entry: ConfigEntry
            config: Thermostat configuration
            unique_id: Unique ID for this entity
        """
        self.hass = hass
        self._entry = entry
        self._config = config
        self._attr_unique_id = unique_id

        # Basic attributes
        self._attr_name = config.get(CONF_ROOM_NAME, "Thermostat")
        self._room_temp_entity = config[CONF_ROOM_TEMP_ENTITY]
        self._valve_entities = config[CONF_VALVE_ENTITIES]

        # Temperature limits
        self._attr_min_temp = config.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)
        self._attr_max_temp = config.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)

        # Current state
        self._attr_current_temperature: float | None = None
        self._attr_target_temperature: float = DEFAULT_TARGET_TEMP
        self._attr_hvac_mode: HVACMode = HVACMode.HEAT
        self._attr_hvac_action: HVACAction = HVACAction.IDLE
        self._attr_preset_mode: str = PRESET_HOME

        # Control state
        self._valve_position: float = 0.0  # 0-100%
        self._heating_demand: float = 0.0  # 0-100%
        self._controller_type: str = CONTROLLER_TYPE_PI

        _LOGGER.info(
            "Initialized climate entity: %s (room temp: %s, valves: %s)",
            self._attr_name,
            self._room_temp_entity,
            self._valve_entities,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dictionary of extra attributes
        """
        return {
            ATTR_VALVE_POSITION: self._valve_position,
            ATTR_HEATING_DEMAND: self._heating_demand,
            ATTR_CONTROLLER_TYPE: self._controller_type,
        }

    async def async_update(self) -> None:
        """Fetch latest state from Home Assistant.

        This method reads sensor values and updates internal state.
        NO blocking I/O should happen here.
        """
        # Read current temperature from sensor
        temp_state = self.hass.states.get(self._room_temp_entity)

        if temp_state and temp_state.state not in ("unknown", "unavailable"):
            try:
                self._attr_current_temperature = float(temp_state.state)
                _LOGGER.debug(
                    "Updated temperature for %s: %.1f°C",
                    self._attr_name,
                    self._attr_current_temperature,
                )
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Failed to parse temperature for %s: %s", self._attr_name, err
                )
                self._attr_current_temperature = None
        else:
            _LOGGER.warning(
                "Temperature sensor %s unavailable for %s",
                self._room_temp_entity,
                self._attr_name,
            )
            self._attr_current_temperature = None

        # Update HVAC action based on valve position
        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        elif self._valve_position > 5.0:  # Threshold: 5% valve opening
            self._attr_hvac_action = HVACAction.HEATING
        else:
            self._attr_hvac_action = HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature.

        Args:
            **kwargs: Keyword arguments containing temperature
        """
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        _LOGGER.info(
            "Setting target temperature for %s to %.1f°C",
            self._attr_name,
            temperature,
        )

        self._attr_target_temperature = temperature

        # Trigger control update
        await self._async_control_heating()

        # Write state to Home Assistant
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode.

        Args:
            hvac_mode: New HVAC mode (OFF or HEAT)
        """
        _LOGGER.info("Setting HVAC mode for %s to %s", self._attr_name, hvac_mode)

        self._attr_hvac_mode = hvac_mode

        if hvac_mode == HVACMode.OFF:
            # Turn off heating
            await self._set_valve_position(0.0)
            self._attr_hvac_action = HVACAction.OFF
        else:
            # Resume heating control
            await self._async_control_heating()

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode.

        Args:
            preset_mode: New preset mode (HOME, AWAY, SLEEP, MANUAL)
        """
        _LOGGER.info("Setting preset mode for %s to %s", self._attr_name, preset_mode)

        self._attr_preset_mode = preset_mode

        # Adjust target temperature based on preset
        if preset_mode == PRESET_AWAY:
            # Lower temperature when away (save energy)
            self._attr_target_temperature = max(
                self._attr_min_temp, self._attr_target_temperature - 3.0
            )
        elif preset_mode == PRESET_SLEEP:
            # Slightly lower temperature for sleeping
            self._attr_target_temperature = max(
                self._attr_min_temp, self._attr_target_temperature - 1.0
            )

        # Trigger control update
        await self._async_control_heating()

        self.async_write_ha_state()

    async def _async_control_heating(self) -> None:
        """Execute heating control logic.

        This is a placeholder - actual PI/MPC control will be implemented later.
        For now, it's a simple proportional control.
        """
        if self._attr_hvac_mode == HVACMode.OFF:
            await self._set_valve_position(0.0)
            return

        if self._attr_current_temperature is None:
            _LOGGER.warning(
                "Cannot control heating for %s: temperature unavailable",
                self._attr_name,
            )
            return

        # Simple proportional control (placeholder for PI/MPC)
        error = self._attr_target_temperature - self._attr_current_temperature
        Kp = 20.0  # Proportional gain (temporary, will be replaced by PI controller)

        # Calculate valve position (0-100%)
        valve_position = max(0.0, min(100.0, Kp * error))

        _LOGGER.debug(
            "Control for %s: error=%.2f°C, valve=%.1f%%",
            self._attr_name,
            error,
            valve_position,
        )

        await self._set_valve_position(valve_position)

    async def _set_valve_position(self, position: float) -> None:
        """Set valve position (0-100%).

        Args:
            position: Valve position in percent (0-100)
        """
        self._valve_position = position
        self._heating_demand = position

        # Ensure valve_entities is a list
        valve_entities = self._valve_entities
        if isinstance(valve_entities, str):
            valve_entities = [valve_entities]

        # Set each valve
        for valve_id in valve_entities:
            await self._set_single_valve(valve_id, position)

    async def _set_single_valve(self, entity_id: str, position: float) -> None:
        """Set a single valve entity.

        Args:
            entity_id: Entity ID of the valve
            position: Valve position in percent (0-100)
        """
        # Determine valve type and set accordingly
        domain = entity_id.split(".")[0]

        try:
            if domain == "number":
                # Number entity - set value directly
                await self.hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": entity_id, "value": position},
                    blocking=True,
                )
            elif domain == "switch":
                # Switch entity - ON/OFF (PWM will be added in Phase 4)
                service = "turn_on" if position > 50.0 else "turn_off"
                await self.hass.services.async_call(
                    "switch",
                    service,
                    {"entity_id": entity_id},
                    blocking=True,
                )
            elif domain == "valve":
                # Valve entity - set position
                await self.hass.services.async_call(
                    "valve",
                    "set_valve_position",
                    {"entity_id": entity_id, "position": position},
                    blocking=True,
                )
            else:
                _LOGGER.warning("Unsupported valve domain: %s", domain)

            _LOGGER.debug(
                "Set valve %s to %.1f%% for %s", entity_id, position, self._attr_name
            )

        except Exception as err:
            _LOGGER.error(
                "Failed to set valve %s for %s: %s", entity_id, self._attr_name, err
            )
