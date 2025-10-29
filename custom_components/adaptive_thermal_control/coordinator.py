"""DataUpdateCoordinator for Adaptive Thermal Control.

This module implements the central coordinator that manages:
- Periodic data updates from sensors
- Control algorithm execution (PI or MPC)
- Zone coordination (fair-share power allocation)
- State synchronization across all climate entities
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_MAX_BOILER_POWER,
    CONF_OUTDOOR_TEMP_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .forecast_provider import ForecastProvider
from .model_storage import ModelStorage
from .thermal_model import ThermalModel, ThermalModelParameters

_LOGGER = logging.getLogger(__name__)


class AdaptiveThermalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data updates for Adaptive Thermal Control.

    This coordinator runs periodically (every 10 minutes by default) and:
    1. Fetches current sensor readings
    2. Runs control algorithms (PI/MPC) for each zone
    3. Applies fair-share power allocation if needed
    4. Updates all climate entities with new valve positions
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            entry: ConfigEntry for this integration
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.entry = entry
        self.config = entry.data

        # Global configuration
        self.global_config = self.config.get("global", {})
        self.thermostats_config = self.config.get("thermostats", [])

        # Outdoor temperature entity
        self.outdoor_temp_entity = self.global_config.get(CONF_OUTDOOR_TEMP_ENTITY)

        # Weather entity (for forecasts)
        self.weather_entity = self.global_config.get(CONF_WEATHER_ENTITY)

        # Maximum boiler power (for fair-share allocation)
        self.max_boiler_power = self.global_config.get(CONF_MAX_BOILER_POWER)

        # Runtime state
        self.total_power_usage: float = 0.0
        self.zone_demands: dict[str, float] = {}  # zone_id -> heating demand (%)

        # Model storage
        self.model_storage = ModelStorage(hass)
        self.thermal_models: dict[str, ThermalModel] = {}  # entity_id -> ThermalModel

        # Forecast provider (for MPC)
        self.forecast_provider = ForecastProvider(
            hass=hass,
            weather_entity=self.weather_entity,
            outdoor_temp_entity=self.outdoor_temp_entity,
        )

        _LOGGER.info(
            "Initialized coordinator with %d thermostats (max power: %s kW, weather: %s)",
            len(self.thermostats_config),
            self.max_boiler_power if self.max_boiler_power else "unlimited",
            self.weather_entity if self.weather_entity else "not configured",
        )

    async def async_load_models(self) -> None:
        """Load thermal models from storage.

        This should be called after coordinator initialization.
        Loads stored parameters for each configured thermostat.
        """
        # Load storage data
        await self.model_storage.async_load()

        # Load model for each thermostat
        for thermostat_config in self.thermostats_config:
            entity_id = thermostat_config.get("climate_entity")
            if not entity_id:
                continue

            # Try to load stored parameters
            parameters, metrics = await self.model_storage.async_load_model(entity_id)

            if parameters:
                # Create thermal model with loaded parameters
                model = ThermalModel(params=parameters, dt=UPDATE_INTERVAL)
                self.thermal_models[entity_id] = model

                _LOGGER.info(
                    "Loaded thermal model for %s: R=%.6f, C=%.0f, τ=%.1fh, RMSE=%.3f°C",
                    entity_id,
                    parameters.R,
                    parameters.C,
                    parameters.time_constant / 3600,
                    metrics.get("rmse", 0.0) if metrics else 0.0,
                )
            else:
                # Use default parameters
                _LOGGER.info(
                    "No stored model for %s, will use defaults or train on first run",
                    entity_id,
                )

    async def async_save_model(
        self,
        entity_id: str,
        parameters: ThermalModelParameters,
        metrics: dict[str, float] | None = None,
    ) -> None:
        """Save thermal model parameters.

        Args:
            entity_id: Entity ID
            parameters: Model parameters to save
            metrics: Optional training metrics
        """
        await self.model_storage.async_save_model(entity_id, parameters, metrics)

        # Update loaded model
        model = ThermalModel(params=parameters, dt=UPDATE_INTERVAL)
        self.thermal_models[entity_id] = model

    def get_thermal_model(self, entity_id: str) -> ThermalModel | None:
        """Get thermal model for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            ThermalModel or None if not available
        """
        return self.thermal_models.get(entity_id)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and compute control outputs.

        This method is called periodically by the coordinator.

        Returns:
            Dictionary with updated sensor data and control outputs

        Raises:
            UpdateFailed: If update fails
        """
        try:
            _LOGGER.debug("Starting coordinator update cycle")

            # Fetch sensor data
            sensor_data = await self._fetch_sensor_data()

            # Calculate heating demands (done by climate entities via PI/MPC)
            # Here we just collect the demands for fair-share allocation
            demands = await self._collect_heating_demands()

            # Apply fair-share power allocation if needed
            if self.max_boiler_power is not None:
                demands = self._apply_fair_share(demands)

            # Calculate total power usage (rough estimate)
            self.total_power_usage = self._estimate_power_usage(demands)

            _LOGGER.info(
                "Coordinator update complete: %d zones, %.1f kW total power",
                len(demands),
                self.total_power_usage,
            )

            return {
                "sensor_data": sensor_data,
                "demands": demands,
                "total_power": self.total_power_usage,
                "timestamp": self.hass.loop.time(),
            }

        except Exception as err:
            _LOGGER.error("Error updating coordinator data: %s", err)
            raise UpdateFailed(f"Failed to update coordinator: {err}") from err

    async def _fetch_sensor_data(self) -> dict[str, Any]:
        """Fetch current readings from all sensors.

        Returns:
            Dictionary with sensor data
        """
        sensor_data: dict[str, Any] = {}

        # Fetch outdoor temperature if configured
        if self.outdoor_temp_entity:
            outdoor_state = self.hass.states.get(self.outdoor_temp_entity)
            if outdoor_state and outdoor_state.state not in ("unknown", "unavailable"):
                try:
                    sensor_data["outdoor_temperature"] = float(outdoor_state.state)
                    _LOGGER.debug(
                        "Outdoor temperature: %.1f°C",
                        sensor_data["outdoor_temperature"],
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid outdoor temperature: %s", outdoor_state.state
                    )

        # Fetch room temperatures
        room_temps: dict[str, float] = {}
        for thermostat_config in self.thermostats_config:
            room_name = thermostat_config.get("room_name")
            temp_entity = thermostat_config.get("room_temp_entity")

            if temp_entity:
                temp_state = self.hass.states.get(temp_entity)
                if temp_state and temp_state.state not in ("unknown", "unavailable"):
                    try:
                        room_temps[room_name] = float(temp_state.state)
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            "Invalid temperature for %s: %s",
                            room_name,
                            temp_state.state,
                        )

        sensor_data["room_temperatures"] = room_temps

        _LOGGER.debug("Fetched data for %d rooms", len(room_temps))

        return sensor_data

    async def _collect_heating_demands(self) -> dict[str, float]:
        """Collect heating demands from all climate entities.

        Returns:
            Dictionary mapping zone ID to heating demand (0-100%)
        """
        # This is a placeholder - actual demands are calculated by climate entities
        # In the future, we'll collect demands from climate entities via their state
        demands: dict[str, float] = {}

        for idx, thermostat_config in enumerate(self.thermostats_config):
            room_name = thermostat_config.get("room_name", f"zone_{idx}")
            # For now, set demand to 0 - will be updated by climate entities
            demands[room_name] = 0.0

        return demands

    def _apply_fair_share(self, demands: dict[str, float]) -> dict[str, float]:
        """Apply fair-share power allocation.

        If total demand exceeds max boiler power, scale down all demands
        proportionally to fit within the power budget.

        Args:
            demands: Dictionary of zone demands (0-100%)

        Returns:
            Adjusted demands after fair-share allocation
        """
        if not self.max_boiler_power:
            return demands

        # Estimate total power demand (rough calculation)
        # Assume each zone at 100% demand uses ~1 kW (configurable later)
        total_demand_power = sum(demands.values()) / 100.0 * 1.0  # kW

        if total_demand_power <= self.max_boiler_power:
            # Within budget, no adjustment needed
            return demands

        # Scale down all demands proportionally
        scale_factor = self.max_boiler_power / total_demand_power

        adjusted_demands = {
            zone: demand * scale_factor for zone, demand in demands.items()
        }

        _LOGGER.warning(
            "Power limit exceeded: %.1f kW > %.1f kW, scaling demands by %.2f",
            total_demand_power,
            self.max_boiler_power,
            scale_factor,
        )

        return adjusted_demands

    def _estimate_power_usage(self, demands: dict[str, float]) -> float:
        """Estimate current power usage based on demands.

        Args:
            demands: Dictionary of zone demands (0-100%)

        Returns:
            Estimated power usage in kW
        """
        # Rough estimate: each zone at 100% demand uses ~1 kW
        # This should be calibrated per installation
        total_power = sum(demands.values()) / 100.0 * 1.0  # kW

        return total_power

    def register_zone_demand(self, zone_id: str, demand: float) -> None:
        """Register heating demand from a climate entity.

        This allows climate entities to report their heating demands
        to the coordinator for fair-share allocation.

        Args:
            zone_id: Unique identifier for the zone
            demand: Heating demand in percent (0-100)
        """
        self.zone_demands[zone_id] = demand
        _LOGGER.debug("Registered demand for %s: %.1f%%", zone_id, demand)

    def get_adjusted_demand(self, zone_id: str) -> float:
        """Get adjusted heating demand after fair-share allocation.

        Args:
            zone_id: Unique identifier for the zone

        Returns:
            Adjusted demand in percent (0-100)
        """
        if not self.max_boiler_power:
            # No power limit, return original demand
            return self.zone_demands.get(zone_id, 0.0)

        # Apply fair-share if needed
        adjusted = self._apply_fair_share(self.zone_demands)
        return adjusted.get(zone_id, 0.0)

    async def async_check_ready(self) -> None:
        """Check if coordinator is ready to operate.

        Raises:
            ConfigEntryNotReady: If essential sensors are unavailable
        """
        # Check if outdoor temp sensor exists (if configured)
        if self.outdoor_temp_entity:
            outdoor_state = self.hass.states.get(self.outdoor_temp_entity)
            if outdoor_state is None:
                raise ConfigEntryNotReady(
                    f"Outdoor temperature sensor {self.outdoor_temp_entity} not found"
                )

        # Check room temperature sensors
        for thermostat_config in self.thermostats_config:
            room_name = thermostat_config.get("room_name")
            temp_entity = thermostat_config.get("room_temp_entity")

            if temp_entity:
                temp_state = self.hass.states.get(temp_entity)
                if temp_state is None:
                    raise ConfigEntryNotReady(
                        f"Temperature sensor {temp_entity} for {room_name} not found"
                    )

        _LOGGER.info("Coordinator ready check passed")
