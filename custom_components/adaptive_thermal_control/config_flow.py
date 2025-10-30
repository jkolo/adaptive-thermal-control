"""Config flow for Adaptive Thermal Control integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ENERGY_CONSUMPTION_ENTITY,
    CONF_ENERGY_PRICE_ENTITY,
    CONF_HEATING_SWITCH_ENTITY,
    CONF_MAX_BOILER_POWER,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NEIGHBORING_ROOMS,
    CONF_OUTDOOR_TEMP_ENTITY,
    CONF_ROOM_AREA,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_ENTITY,
    CONF_SOLAR_IRRADIANCE_ENTITY,
    CONF_VALVE_CLOSE_TIME,
    CONF_VALVE_ENTITIES,
    CONF_VALVE_OPEN_TIME,
    CONF_WATER_TEMP_IN_ENTITY,
    CONF_WATER_TEMP_OUT_ENTITY,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_ORIENTATIONS,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_TARGET_TEMP,
    DEFAULT_VALVE_CLOSE_TIME,
    DEFAULT_VALVE_OPEN_TIME,
    DOMAIN,
    ORIENTATIONS,
)

_LOGGER = logging.getLogger(__name__)

# Step 1: Global configuration schema
STEP_GLOBAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OUTDOOR_TEMP_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
        ),
        vol.Optional(CONF_HEATING_SWITCH_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="switch")
        ),
        vol.Optional(CONF_ENERGY_PRICE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="weather")
        ),
        vol.Optional(CONF_SOLAR_IRRADIANCE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_ENERGY_CONSUMPTION_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_MAX_BOILER_POWER): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.0,
                max=1000.0,
                step=0.1,
                unit_of_measurement="kW",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    }
)


class AdaptiveThermalControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Adaptive Thermal Control."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._global_config: dict[str, Any] = {}
        self._thermostats: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - global configuration.

        Args:
            user_input: User input from the form

        Returns:
            FlowResult for next step or entry creation
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate entities exist
            errors = await self._validate_global_config(user_input)

            if not errors:
                # Store global config
                self._global_config = user_input

                # Move to thermostat configuration
                return await self.async_step_add_thermostat()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_GLOBAL_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "name": "Adaptive Thermal Control",
            },
        )

    async def async_step_add_thermostat(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a thermostat.

        Args:
            user_input: User input from the form

        Returns:
            FlowResult for next step or entry creation
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate thermostat config
            errors = await self._validate_thermostat_config(user_input)

            if not errors:
                # Add thermostat to list
                self._thermostats.append(user_input)

                # Ask if user wants to add another thermostat
                return await self.async_step_add_another()

        # Build thermostat schema
        thermostat_schema = vol.Schema(
            {
                vol.Required(CONF_ROOM_NAME): selector.TextSelector(),
                vol.Required(CONF_ROOM_TEMP_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required(CONF_VALVE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["switch", "number", "valve"],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_WATER_TEMP_IN_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_WATER_TEMP_OUT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(
                    CONF_VALVE_OPEN_TIME, default=DEFAULT_VALVE_OPEN_TIME
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0,
                        max=300.0,
                        step=1.0,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_VALVE_CLOSE_TIME, default=DEFAULT_VALVE_CLOSE_TIME
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0,
                        max=300.0,
                        step=1.0,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_WINDOW_ORIENTATIONS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=ORIENTATIONS,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_ROOM_AREA): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0,
                        max=500.0,
                        step=0.1,
                        unit_of_measurement="m²",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5.0,
                        max=25.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=15.0,
                        max=35.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="add_thermostat",
            data_schema=thermostat_schema,
            errors=errors,
            description_placeholders={
                "count": str(len(self._thermostats)),
            },
        )

    async def async_step_add_another(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask user if they want to add another thermostat.

        Args:
            user_input: User input from the form

        Returns:
            FlowResult for next step or entry creation
        """
        if user_input is not None:
            if user_input.get("add_another", False):
                return await self.async_step_add_thermostat()

            # Create the config entry
            return self.async_create_entry(
                title="Adaptive Thermal Control",
                data={
                    "global": self._global_config,
                    "thermostats": self._thermostats,
                },
            )

        return self.async_show_form(
            step_id="add_another",
            data_schema=vol.Schema(
                {
                    vol.Required("add_another", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={
                "count": str(len(self._thermostats)),
            },
        )

    async def _validate_global_config(
        self, config: dict[str, Any]
    ) -> dict[str, str]:
        """Validate global configuration.

        Args:
            config: Configuration to validate

        Returns:
            Dictionary of errors (empty if valid)
        """
        errors: dict[str, str] = {}

        # Validate entities exist
        for key in [
            CONF_OUTDOOR_TEMP_ENTITY,
            CONF_HEATING_SWITCH_ENTITY,
            CONF_ENERGY_PRICE_ENTITY,
            CONF_WEATHER_ENTITY,
            CONF_SOLAR_IRRADIANCE_ENTITY,
            CONF_ENERGY_CONSUMPTION_ENTITY,
        ]:
            if key in config and config[key]:
                entity_id = config[key]
                if not self.hass.states.get(entity_id):
                    errors[key] = "entity_not_found"
                    _LOGGER.error("Entity %s not found", entity_id)

        return errors

    async def _validate_thermostat_config(
        self, config: dict[str, Any]
    ) -> dict[str, str]:
        """Validate thermostat configuration.

        Args:
            config: Configuration to validate

        Returns:
            Dictionary of errors (empty if valid)
        """
        errors: dict[str, str] = {}

        # Validate required fields
        if not config.get(CONF_ROOM_NAME):
            errors[CONF_ROOM_NAME] = "required"

        if not config.get(CONF_ROOM_TEMP_ENTITY):
            errors[CONF_ROOM_TEMP_ENTITY] = "required"

        if not config.get(CONF_VALVE_ENTITIES):
            errors[CONF_VALVE_ENTITIES] = "required"

        # Validate temperature entity exists
        if CONF_ROOM_TEMP_ENTITY in config:
            entity_id = config[CONF_ROOM_TEMP_ENTITY]
            if not self.hass.states.get(entity_id):
                errors[CONF_ROOM_TEMP_ENTITY] = "entity_not_found"
                _LOGGER.error("Temperature entity %s not found", entity_id)

        # Validate valve entities exist
        if CONF_VALVE_ENTITIES in config:
            valve_entities = config[CONF_VALVE_ENTITIES]
            if isinstance(valve_entities, str):
                valve_entities = [valve_entities]

            for valve_id in valve_entities:
                if not self.hass.states.get(valve_id):
                    errors[CONF_VALVE_ENTITIES] = "entity_not_found"
                    _LOGGER.error("Valve entity %s not found", valve_id)
                    break

        # Validate min/max temp
        if (
            CONF_MIN_TEMP in config
            and CONF_MAX_TEMP in config
            and config[CONF_MIN_TEMP] >= config[CONF_MAX_TEMP]
        ):
            errors[CONF_MIN_TEMP] = "min_max_invalid"

        return errors

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AdaptiveThermalControlOptionsFlow:
        """Get the options flow for this handler.

        Args:
            config_entry: ConfigEntry to create options flow for

        Returns:
            Options flow handler
        """
        return AdaptiveThermalControlOptionsFlow()


class AdaptiveThermalControlOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Adaptive Thermal Control."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options.

        Args:
            user_input: User input from the form

        Returns:
            FlowResult for options update
        """
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # For now, options flow is minimal - will be expanded in future phases
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
