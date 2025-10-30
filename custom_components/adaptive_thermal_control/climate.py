"""Climate platform for Adaptive Thermal Control integration."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CONTROLLER_TYPE,
    ATTR_HEATING_DEMAND,
    ATTR_MPC_FAILURE_COUNT,
    ATTR_MPC_LAST_FAILURE_REASON,
    ATTR_MPC_STATUS,
    ATTR_VALVE_POSITION,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_ENTITY,
    CONF_VALVE_ENTITIES,
    CONTROLLER_TYPE_MPC,
    CONTROLLER_TYPE_PI,
    DEFAULT_DT,
    DEFAULT_KP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_TARGET_TEMP,
    DEFAULT_TI,
    DOMAIN,
    MPC_CONTROL_HORIZON,
    MPC_MAX_FAILURES,
    MPC_PREDICTION_HORIZON,
    MPC_RETRY_INTERVAL,
    MPC_SUCCESS_COUNT_TO_RECOVER,
    MPC_TIMEOUT,
    MPC_WEIGHT_COMFORT,
    MPC_WEIGHT_ENERGY,
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_MANUAL,
    PRESET_SLEEP,
    UPDATE_INTERVAL,
)
from .coordinator import AdaptiveThermalCoordinator
from .mpc_controller import MPCConfig, MPCController
from .pi_controller import PIController

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

    # Get coordinator from hass.data
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Create climate entities for each thermostat
    entities = []
    thermostats = coordinator.thermostats_config

    for idx, thermostat_config in enumerate(thermostats):
        entity = AdaptiveThermalClimate(
            hass=hass,
            coordinator=coordinator,
            config=thermostat_config,
            unique_id=f"{entry.entry_id}_thermostat_{idx}",
        )
        entities.append(entity)

    # Add entities
    async_add_entities(entities, update_before_add=True)

    _LOGGER.info("Added %d climate entities", len(entities))


class AdaptiveThermalClimate(CoordinatorEntity, ClimateEntity):
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
        coordinator: AdaptiveThermalCoordinator,
        config: dict[str, Any],
        unique_id: str,
    ) -> None:
        """Initialize the climate entity.

        Args:
            hass: Home Assistant instance
            coordinator: Data update coordinator
            config: Thermostat configuration
            unique_id: Unique ID for this entity
        """
        super().__init__(coordinator)

        self.hass = hass
        self.coordinator = coordinator
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
        self._last_control_output: float | None = None  # For MPC warm-start

        # Failsafe state (T3.6.1)
        self._mpc_status: str = "active"  # "active", "degraded", "disabled"
        self._mpc_failure_count: int = 0  # Consecutive MPC failures
        self._mpc_success_count: int = 0  # Consecutive MPC successes (for recovery)
        self._mpc_last_failure_reason: str | None = None
        self._mpc_last_failure_time: float | None = None  # Unix timestamp
        self._mpc_permanently_disabled: bool = False

        # Control quality tracking (T3.6.2)
        # Store (timestamp, error) tuples for last 24h
        # 144 samples = 24h at 10-minute intervals
        self._temperature_errors: deque = deque(maxlen=144)

        # MPC diagnostics (T3.7.1)
        self._mpc_optimization_time: float | None = None  # Last MPC computation time [s]

        # Initialize PI controller (fallback)
        self._pi_controller = PIController(
            kp=DEFAULT_KP,
            ti=DEFAULT_TI,
            dt=DEFAULT_DT,
            output_min=0.0,
            output_max=100.0,
        )

        # Initialize MPC controller (will be used when model is trained)
        # Get entity_id for this climate entity (construct from config)
        self._entity_id = f"climate.{config.get(CONF_ROOM_NAME, 'thermostat').lower().replace(' ', '_')}"

        # MPC configuration
        mpc_config = MPCConfig(
            Np=MPC_PREDICTION_HORIZON,
            Nc=MPC_CONTROL_HORIZON,
            dt=UPDATE_INTERVAL,
            u_min=0.0,
            u_max=100.0,
            du_max=50.0,  # Max change per step: 50%
            w_comfort=MPC_WEIGHT_COMFORT,
            w_energy=MPC_WEIGHT_ENERGY,
            w_smooth=0.05,  # Small weight for smooth control
        )

        self._mpc_controller: MPCController | None = None
        self._mpc_config = mpc_config

        _LOGGER.info(
            "Initialized climate entity: %s (entity_id: %s, room temp: %s, valves: %s)",
            self._attr_name,
            self._entity_id,
            self._room_temp_entity,
            self._valve_entities,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dictionary of extra attributes
        """
        attrs = {
            ATTR_VALVE_POSITION: self._valve_position,
            ATTR_HEATING_DEMAND: self._heating_demand,
            ATTR_CONTROLLER_TYPE: self._controller_type,
            ATTR_MPC_STATUS: self._mpc_status,
            ATTR_MPC_FAILURE_COUNT: self._mpc_failure_count,
            ATTR_MPC_LAST_FAILURE_REASON: self._mpc_last_failure_reason,
        }

        # Add control quality RMSE (T3.6.2)
        rmse = self.get_control_quality_rmse()
        if rmse is not None:
            attrs["control_quality_rmse"] = round(rmse, 3)

        # Add MPC diagnostics (T3.7.1)
        if self._mpc_config:
            attrs["mpc_prediction_horizon"] = self._mpc_config.Np
            attrs["mpc_control_horizon"] = self._mpc_config.Nc
            attrs["mpc_weights"] = {
                "comfort": round(self._mpc_config.w_comfort, 3),
                "energy": round(self._mpc_config.w_energy, 3),
                "smooth": round(self._mpc_config.w_smooth, 3),
            }

        if self._mpc_optimization_time is not None:
            attrs["mpc_optimization_time"] = round(self._mpc_optimization_time, 4)

        return attrs

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        This is called automatically when coordinator updates its data.
        """
        # Update current temperature from coordinator data
        if self.coordinator.data:
            sensor_data = self.coordinator.data.get("sensor_data", {})
            room_temps = sensor_data.get("room_temperatures", {})

            room_name = self._config.get(CONF_ROOM_NAME)
            if room_name and room_name in room_temps:
                self._attr_current_temperature = room_temps[room_name]

        # Update HVAC action based on valve position
        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        elif self._valve_position > 5.0:  # Threshold: 5% valve opening
            self._attr_hvac_action = HVACAction.HEATING
        else:
            self._attr_hvac_action = HVACAction.IDLE

        # Write updated state
        self.async_write_ha_state()

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
        """Execute heating control logic using MPC or PI controller.

        This method automatically switches between:
        - MPC: When thermal model is trained and available
        - PI: Fallback when model is not yet trained

        The switch is logged for debugging and monitoring.
        """
        if self._attr_hvac_mode == HVACMode.OFF:
            await self._set_valve_position(0.0)
            # Reset controllers when heating is off
            self._pi_controller.reset()
            self._last_control_output = None
            return

        if self._attr_current_temperature is None:
            _LOGGER.warning(
                "Cannot control heating for %s: temperature unavailable",
                self._attr_name,
            )
            return

        # Check if thermal model is available and trained
        thermal_model = self.coordinator.get_thermal_model(self._entity_id)
        old_controller_type = self._controller_type

        if thermal_model is not None:
            # Model is trained - use MPC
            await self._async_control_with_mpc(thermal_model)
        else:
            # No trained model - use PI fallback
            await self._async_control_with_pi()

        # Log controller switch if it changed
        if self._controller_type != old_controller_type:
            _LOGGER.info(
                "Controller switch for %s: %s → %s",
                self._attr_name,
                old_controller_type,
                self._controller_type,
            )

        # Track temperature error for control quality monitoring (T3.6.2)
        if self._attr_target_temperature is not None and self._attr_current_temperature is not None:
            error = self._attr_target_temperature - self._attr_current_temperature
            self._temperature_errors.append((time.time(), error))

    async def _async_control_with_pi(self) -> None:
        """Control heating using PI controller (fallback).

        The PI controller provides smooth, stable temperature control with
        anti-windup protection. Used when MPC is not available.
        """
        self._controller_type = CONTROLLER_TYPE_PI

        # Use PI controller to calculate valve position
        valve_position = self._pi_controller.update(
            setpoint=self._attr_target_temperature,
            measurement=self._attr_current_temperature,
            dt=UPDATE_INTERVAL,
        )

        # Log control decision
        _LOGGER.info(
            "PI control for %s: target=%.1f°C, current=%.1f°C, valve=%.1f%%",
            self._attr_name,
            self._attr_target_temperature,
            self._attr_current_temperature,
            valve_position,
        )

        await self._set_valve_position(valve_position)
        self._last_control_output = valve_position

    async def _async_control_with_mpc(self, thermal_model) -> None:
        """Control heating using Model Predictive Control with failsafe mechanism (T3.6.1).

        Features:
        - Timeout protection (> 10s)
        - Failure counter (3 consecutive failures → permanent PI fallback)
        - Automatic recovery (5 consecutive successes → back to MPC)
        - Persistent notifications on failures

        Args:
            thermal_model: Trained thermal model for this zone
        """
        # Check if MPC is permanently disabled
        if self._mpc_permanently_disabled:
            # Check if we should retry MPC after retry interval
            if (
                self._mpc_last_failure_time
                and (time.time() - self._mpc_last_failure_time) > MPC_RETRY_INTERVAL
            ):
                _LOGGER.info(
                    "Retry interval elapsed for %s. Attempting to re-enable MPC.",
                    self._attr_name,
                )
                self._mpc_permanently_disabled = False
                self._mpc_failure_count = 0
                self._mpc_status = "active"
            else:
                # Still in retry interval, use PI
                await self._async_control_with_pi()
                return

        self._controller_type = CONTROLLER_TYPE_MPC

        # Initialize MPC controller if not already done
        if self._mpc_controller is None:
            self._mpc_controller = MPCController(
                model=thermal_model,
                config=self._mpc_config,
            )
            _LOGGER.info("Initialized MPC controller for %s", self._attr_name)

        # Get outdoor temperature forecast
        try:
            T_outdoor_forecast = await self.coordinator.forecast_provider.get_outdoor_temperature_forecast(
                hours=self._mpc_config.Np * self._mpc_config.dt / 3600.0,
                dt=self._mpc_config.dt,
            )
        except Exception as err:
            await self._handle_mpc_failure(f"Forecast failed: {err}")
            return

        # Compute MPC control with timeout protection
        try:
            start_time = time.time()

            # Run MPC with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._mpc_controller.compute_control,
                    T_current=self._attr_current_temperature,
                    T_setpoint=self._attr_target_temperature,
                    T_outdoor_forecast=T_outdoor_forecast,
                    u_last=self._last_control_output,
                ),
                timeout=MPC_TIMEOUT,
            )

            computation_time = time.time() - start_time
            self._mpc_optimization_time = computation_time  # Store for diagnostics (T3.7.1)

            # Check if optimization succeeded
            if not result.success:
                await self._handle_mpc_failure(f"Optimization failed: {result.message}")
                return

            # MPC succeeded - update success counter
            self._mpc_failure_count = 0
            self._mpc_success_count += 1
            self._mpc_last_failure_reason = None

            # Check if we should update status back to "active" after recovery
            if (
                self._mpc_status == "degraded"
                and self._mpc_success_count >= MPC_SUCCESS_COUNT_TO_RECOVER
            ):
                _LOGGER.info(
                    "MPC recovered for %s after %d successful cycles. Status: degraded → active",
                    self._attr_name,
                    self._mpc_success_count,
                )
                self._mpc_status = "active"
                self._mpc_success_count = 0

                # Send recovery notification
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": f"MPC Recovered: {self._attr_name}",
                        "message": f"Model Predictive Control has successfully recovered for {self._attr_name} "
                        f"after {MPC_SUCCESS_COUNT_TO_RECOVER} successful control cycles.",
                        "notification_id": f"{DOMAIN}_mpc_recovered_{self._entity_id}",
                    },
                )

            # Apply first control action (receding horizon)
            valve_position = result.u_optimal[0]

            # Log control decision
            _LOGGER.info(
                "MPC control for %s: target=%.1f°C, current=%.1f°C, valve=%.1f%%, "
                "cost=%.3f, iterations=%d, time=%.3fs",
                self._attr_name,
                self._attr_target_temperature,
                self._attr_current_temperature,
                valve_position,
                result.cost,
                result.iterations,
                computation_time,
            )

            await self._set_valve_position(valve_position)
            self._last_control_output = valve_position

        except asyncio.TimeoutError:
            await self._handle_mpc_failure(f"Timeout (>{MPC_TIMEOUT}s)")

        except Exception as err:
            await self._handle_mpc_failure(f"Exception: {err}")

    async def _handle_mpc_failure(self, reason: str) -> None:
        """Handle MPC failure with failsafe logic (T3.6.1).

        Args:
            reason: Reason for the failure
        """
        self._mpc_failure_count += 1
        self._mpc_success_count = 0  # Reset success counter
        self._mpc_last_failure_reason = reason
        self._mpc_last_failure_time = time.time()

        _LOGGER.warning(
            "MPC failure #%d for %s: %s. Falling back to PI.",
            self._mpc_failure_count,
            self._attr_name,
            reason,
        )

        # Check if we've exceeded maximum failures
        if self._mpc_failure_count >= MPC_MAX_FAILURES:
            _LOGGER.error(
                "MPC permanently disabled for %s after %d consecutive failures. "
                "Will retry in %d seconds.",
                self._attr_name,
                self._mpc_failure_count,
                MPC_RETRY_INTERVAL,
            )
            self._mpc_permanently_disabled = True
            self._mpc_status = "disabled"

            # Send persistent notification about permanent failure
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"⚠️ MPC Disabled: {self._attr_name}",
                    "message": f"Model Predictive Control has been disabled for {self._attr_name} "
                    f"after {MPC_MAX_FAILURES} consecutive failures.\n\n"
                    f"**Last failure:** {reason}\n\n"
                    f"System will retry MPC in {MPC_RETRY_INTERVAL // 60} minutes. "
                    f"Currently using PI controller as fallback.\n\n"
                    f"**Recommended actions:**\n"
                    f"- Check sensor availability\n"
                    f"- Verify thermal model quality\n"
                    f"- Review logs for details",
                    "notification_id": f"{DOMAIN}_mpc_disabled_{self._entity_id}",
                },
            )
        else:
            # Degraded but not disabled yet
            self._mpc_status = "degraded"

            # Send notification about degradation (but not every time, only on first failure)
            if self._mpc_failure_count == 1:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": f"⚠️ MPC Degraded: {self._attr_name}",
                        "message": f"Model Predictive Control encountered an issue for {self._attr_name}.\n\n"
                        f"**Reason:** {reason}\n\n"
                        f"System will fall back to PI controller and retry MPC on next cycle.\n"
                        f"Failures: {self._mpc_failure_count}/{MPC_MAX_FAILURES}",
                        "notification_id": f"{DOMAIN}_mpc_degraded_{self._entity_id}",
                    },
                )

        # Fall back to PI controller
        await self._async_control_with_pi()

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
                # Valve entity - check if it supports set_position
                state = self.hass.states.get(entity_id)
                if state is None:
                    _LOGGER.warning("Valve entity %s not found", entity_id)
                    return

                # Check supported features
                supported_features = state.attributes.get("supported_features", 0)
                # ValveEntityFeature.SET_POSITION = 4
                supports_set_position = (supported_features & 4) != 0

                if supports_set_position:
                    # Valve supports set_position
                    await self.hass.services.async_call(
                        "valve",
                        "set_valve_position",
                        {"entity_id": entity_id, "position": position},
                        blocking=True,
                    )
                else:
                    # Valve only supports open/close - use simple on/off control
                    # Position > 50% = open, <= 50% = close
                    service = "open_valve" if position > 50.0 else "close_valve"
                    await self.hass.services.async_call(
                        "valve",
                        service,
                        {"entity_id": entity_id},
                        blocking=True,
                    )
                    _LOGGER.debug(
                        "Valve %s does not support set_position, using %s instead",
                        entity_id, service
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

    def get_control_quality_rmse(self, time_window_hours: float = 24.0) -> float | None:
        """Calculate rolling RMSE for control quality monitoring (T3.6.2).

        Args:
            time_window_hours: Time window in hours (default: 24h)

        Returns:
            RMSE in °C, or None if insufficient data
        """
        if not self._temperature_errors:
            return None

        current_time = time.time()
        cutoff_time = current_time - (time_window_hours * 3600)

        # Filter errors within time window
        recent_errors = [
            error for timestamp, error in self._temperature_errors
            if timestamp >= cutoff_time
        ]

        if len(recent_errors) < 6:  # Need at least 1 hour of data
            return None

        # Calculate RMSE
        import math
        squared_errors = [e ** 2 for e in recent_errors]
        mse = sum(squared_errors) / len(squared_errors)
        rmse = math.sqrt(mse)

        return rmse
