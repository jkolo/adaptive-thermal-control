"""Diagnostic sensors for Adaptive Thermal Control.

This module provides diagnostic sensors that expose thermal model
parameters and training metrics for monitoring and debugging.

Sensors created:
- Model parameters: R, C, tau
- Prediction error: RMSE
- Model status: training state
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AdaptiveThermalCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Adaptive Thermal Control sensors from config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    coordinator: AdaptiveThermalCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []

    # Create sensors for each configured thermostat
    for thermostat_config in coordinator.thermostats_config:
        room_id = thermostat_config.get("room_id", "unknown")
        climate_entity = thermostat_config.get("climate_entity")

        if not climate_entity:
            continue

        # Model parameter sensors
        sensors.append(
            ThermalResistanceSensor(coordinator, climate_entity, room_id)
        )
        sensors.append(
            ThermalCapacitanceSensor(coordinator, climate_entity, room_id)
        )
        sensors.append(
            TimeConstantSensor(coordinator, climate_entity, room_id)
        )

        # Prediction error sensor
        sensors.append(
            PredictionErrorSensor(coordinator, climate_entity, room_id)
        )

        # Model status sensor
        sensors.append(
            ModelStatusSensor(coordinator, climate_entity, room_id)
        )

        # Control quality sensor (T3.6.2)
        sensors.append(
            ControlQualitySensor(coordinator, climate_entity, room_id)
        )

        # MPC diagnostic sensors (T3.7.1)
        sensors.append(
            MPCPredictionHorizonSensor(coordinator, climate_entity, room_id)
        )
        sensors.append(
            MPCControlHorizonSensor(coordinator, climate_entity, room_id)
        )
        sensors.append(
            MPCWeightsSensor(coordinator, climate_entity, room_id)
        )
        sensors.append(
            MPCOptimizationTimeSensor(coordinator, climate_entity, room_id)
        )

        # Temperature prediction sensor (T3.7.2)
        sensors.append(
            TemperaturePredictionSensor(coordinator, climate_entity, room_id)
        )

    async_add_entities(sensors)

    _LOGGER.info("Set up %d diagnostic sensors", len(sensors))


class ThermalModelSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for thermal model diagnostic sensors."""

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data coordinator
            climate_entity: Associated climate entity ID
            room_id: Room identifier
        """
        super().__init__(coordinator)

        self._climate_entity = climate_entity
        self._room_id = room_id
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info to link sensors to the climate entity."""
        return {
            "identifiers": {(DOMAIN, self._climate_entity)},
            "name": f"Adaptive Thermal Control - {self._room_id}",
            "manufacturer": "Adaptive Thermal Control",
            "model": "Thermal Model 1R1C",
        }


class ThermalResistanceSensor(ThermalModelSensorBase):
    """Sensor for thermal resistance R."""

    _attr_icon = "mdi:resistor"
    _attr_native_unit_of_measurement = "K/W"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} Model R"
        self._attr_unique_id = f"{climate_entity}_model_r"

    @property
    def native_value(self) -> float | None:
        """Return the thermal resistance value."""
        model = self.coordinator.get_thermal_model(self._climate_entity)
        if model:
            return round(model.params.R, 6)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        model_info = self.coordinator.model_storage.get_model_info(
            self._climate_entity
        )
        if model_info:
            return {
                "last_update": model_info.get("last_update"),
                "version": model_info.get("version"),
            }
        return {}


class ThermalCapacitanceSensor(ThermalModelSensorBase):
    """Sensor for thermal capacitance C."""

    _attr_icon = "mdi:battery-charging"
    _attr_native_unit_of_measurement = "MJ/K"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} Model C"
        self._attr_unique_id = f"{climate_entity}_model_c"

    @property
    def native_value(self) -> float | None:
        """Return the thermal capacitance value in MJ/K."""
        model = self.coordinator.get_thermal_model(self._climate_entity)
        if model:
            # Convert J/K to MJ/K
            return round(model.params.C / 1e6, 3)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        model_info = self.coordinator.model_storage.get_model_info(
            self._climate_entity
        )
        if model_info:
            return {
                "C_joules_per_kelvin": model_info.get("C"),
                "last_update": model_info.get("last_update"),
                "version": model_info.get("version"),
            }
        return {}


class TimeConstantSensor(ThermalModelSensorBase):
    """Sensor for thermal time constant tau."""

    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} Model Tau"
        self._attr_unique_id = f"{climate_entity}_model_tau"

    @property
    def native_value(self) -> float | None:
        """Return the time constant in hours."""
        model = self.coordinator.get_thermal_model(self._climate_entity)
        if model:
            # Convert seconds to hours
            return round(model.params.time_constant / 3600, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        model = self.coordinator.get_thermal_model(self._climate_entity)
        model_info = self.coordinator.model_storage.get_model_info(
            self._climate_entity
        )

        attrs = {}
        if model:
            attrs["tau_seconds"] = round(model.params.time_constant, 0)
        if model_info:
            attrs["last_update"] = model_info.get("last_update")
            attrs["version"] = model_info.get("version")

        return attrs


class PredictionErrorSensor(ThermalModelSensorBase):
    """Sensor for model prediction error (RMSE)."""

    _attr_icon = "mdi:chart-bell-curve"
    _attr_native_unit_of_measurement = "°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} Prediction Error"
        self._attr_unique_id = f"{climate_entity}_prediction_error"

    @property
    def native_value(self) -> float | None:
        """Return the RMSE value."""
        model_info = self.coordinator.model_storage.get_model_info(
            self._climate_entity
        )
        if model_info and "metrics" in model_info:
            return model_info["metrics"].get("rmse")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional error metrics."""
        model_info = self.coordinator.model_storage.get_model_info(
            self._climate_entity
        )

        if model_info and "metrics" in model_info:
            metrics = model_info["metrics"]
            return {
                "mae": metrics.get("mae"),
                "r_squared": metrics.get("r_squared"),
                "last_update": model_info.get("last_update"),
            }
        return {}


class ModelStatusSensor(ThermalModelSensorBase):
    """Sensor for model training status."""

    _attr_icon = "mdi:brain"

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} Model Status"
        self._attr_unique_id = f"{climate_entity}_model_status"

    @property
    def native_value(self) -> str:
        """Return the model status.

        States:
        - not_trained: No model parameters stored, using defaults
        - learning: Model trained but with limited data (< 30 days)
        - trained: Model well-trained with sufficient data
        - degraded: Model performance has degraded (drift detected)
        """
        model_info = self.coordinator.model_storage.get_model_info(
            self._climate_entity
        )

        if not model_info:
            return "not_trained"

        # Check metrics
        metrics = model_info.get("metrics", {})
        rmse = metrics.get("rmse", 999)
        r_squared = metrics.get("r_squared", 0)

        # Check if model is degraded (poor performance)
        if rmse > 2.0 or r_squared < 0.5:
            return "degraded"

        # Check training data age/amount
        # TODO: Implement actual training data tracking
        # For now, just check if we have good metrics
        if rmse < 1.0 and r_squared > 0.7:
            return "trained"
        else:
            return "learning"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional status information."""
        model_info = self.coordinator.model_storage.get_model_info(
            self._climate_entity
        )

        attrs = {}
        if model_info:
            attrs["last_update"] = model_info.get("last_update")
            attrs["version"] = model_info.get("version")

            metrics = model_info.get("metrics", {})
            if metrics:
                attrs["rmse"] = metrics.get("rmse")
                attrs["mae"] = metrics.get("mae")
                attrs["r_squared"] = metrics.get("r_squared")

            # Add model parameters
            attrs["R"] = model_info.get("R")
            attrs["C_MJ_per_K"] = round(model_info.get("C", 0) / 1e6, 3)
            attrs["tau_hours"] = model_info.get("tau_hours")

        return attrs

    @property
    def icon(self) -> str:
        """Return icon based on status."""
        status = self.native_value

        if status == "not_trained":
            return "mdi:brain-off"
        elif status == "learning":
            return "mdi:brain"
        elif status == "trained":
            return "mdi:check-circle"
        elif status == "degraded":
            return "mdi:alert-circle"

        return "mdi:help-circle"


class ControlQualitySensor(ThermalModelSensorBase):
    """Sensor for control quality monitoring (T3.6.2).

    Monitors rolling 24h RMSE and reports quality status:
    - excellent: RMSE < 0.5°C
    - good: RMSE < 1.0°C
    - poor: RMSE >= 1.0°C
    """

    _attr_icon = "mdi:chart-line-variant"

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} Control Quality"
        self._attr_unique_id = f"{climate_entity}_control_quality"

    @property
    def native_value(self) -> str:
        """Return the control quality status.

        States:
        - excellent: RMSE < 0.5°C (target achieved)
        - good: RMSE < 1.0°C (acceptable performance)
        - fair: RMSE < 2.0°C (degraded but functional)
        - poor: RMSE >= 2.0°C (significant deviation)
        - unknown: Not enough data (< 1 hour)
        """
        rmse = self._get_rmse()

        if rmse is None:
            return "unknown"
        elif rmse < 0.5:
            return "excellent"
        elif rmse < 1.0:
            return "good"
        elif rmse < 2.0:
            return "fair"
        else:
            return "poor"

    def _get_rmse(self) -> float | None:
        """Get RMSE from climate entity state attributes."""
        # Get climate entity state
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return None

        # Get RMSE from attributes
        return climate_state.attributes.get("control_quality_rmse")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        rmse = self._get_rmse()

        attrs = {}
        if rmse is not None:
            attrs["rmse"] = round(rmse, 3)
            attrs["unit"] = "°C"

            # Add quality thresholds for reference
            attrs["threshold_excellent"] = 0.5
            attrs["threshold_good"] = 1.0
            attrs["threshold_fair"] = 2.0

        return attrs

    @property
    def icon(self) -> str:
        """Return icon based on quality."""
        quality = self.native_value

        if quality == "excellent":
            return "mdi:check-circle"
        elif quality == "good":
            return "mdi:check"
        elif quality == "fair":
            return "mdi:alert"
        elif quality == "poor":
            return "mdi:alert-circle"
        else:
            return "mdi:help-circle"


class MPCPredictionHorizonSensor(ThermalModelSensorBase):
    """Sensor for MPC prediction horizon (T3.7.1)."""

    _attr_icon = "mdi:timeline-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} MPC Prediction Horizon"
        self._attr_unique_id = f"{climate_entity}_mpc_prediction_horizon"
        self._attr_native_unit_of_measurement = "steps"

    @property
    def native_value(self) -> int | None:
        """Return the MPC prediction horizon (Np)."""
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return None

        return climate_state.attributes.get("mpc_prediction_horizon")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return {}

        Np = climate_state.attributes.get("mpc_prediction_horizon")
        if Np is None:
            return {}

        # Assume dt=600s (10 minutes) from config
        dt = 600  # seconds
        hours = (Np * dt) / 3600

        return {
            "description": "Number of future timesteps predicted by MPC",
            "horizon_hours": round(hours, 1),
            "timestep_seconds": dt,
        }


class MPCControlHorizonSensor(ThermalModelSensorBase):
    """Sensor for MPC control horizon (T3.7.1)."""

    _attr_icon = "mdi:timeline-clock-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} MPC Control Horizon"
        self._attr_unique_id = f"{climate_entity}_mpc_control_horizon"
        self._attr_native_unit_of_measurement = "steps"

    @property
    def native_value(self) -> int | None:
        """Return the MPC control horizon (Nc)."""
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return None

        return climate_state.attributes.get("mpc_control_horizon")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return {}

        Nc = climate_state.attributes.get("mpc_control_horizon")
        if Nc is None:
            return {}

        # Assume dt=600s (10 minutes) from config
        dt = 600  # seconds
        hours = (Nc * dt) / 3600

        return {
            "description": "Number of future control actions optimized by MPC",
            "horizon_hours": round(hours, 1),
            "timestep_seconds": dt,
        }


class MPCWeightsSensor(ThermalModelSensorBase):
    """Sensor for MPC cost function weights (T3.7.1)."""

    _attr_icon = "mdi:weight"

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} MPC Weights"
        self._attr_unique_id = f"{climate_entity}_mpc_weights"

    @property
    def native_value(self) -> str | None:
        """Return the weight configuration as a formatted string."""
        weights = self._get_weights()
        if not weights:
            return None

        # Format as "comfort: 0.70, energy: 0.20, smooth: 0.10"
        return f"comfort: {weights['comfort']:.2f}, energy: {weights['energy']:.2f}, smooth: {weights['smooth']:.2f}"

    def _get_weights(self) -> dict[str, float] | None:
        """Get weights from climate entity."""
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return None

        return climate_state.attributes.get("mpc_weights")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return weight values as separate attributes."""
        weights = self._get_weights()
        if not weights:
            return {}

        return {
            "comfort_weight": weights.get("comfort"),
            "energy_weight": weights.get("energy"),
            "smooth_weight": weights.get("smooth"),
            "description": "Cost function weights: comfort (tracking error), energy (consumption), smooth (control changes)",
        }


class MPCOptimizationTimeSensor(ThermalModelSensorBase):
    """Sensor for MPC optimization computation time (T3.7.1)."""

    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} MPC Optimization Time"
        self._attr_unique_id = f"{climate_entity}_mpc_optimization_time"
        self._attr_native_unit_of_measurement = "s"

    @property
    def native_value(self) -> float | None:
        """Return the last MPC optimization time in seconds."""
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return None

        return climate_state.attributes.get("mpc_optimization_time")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        opt_time = self.native_value
        if opt_time is None:
            return {}

        # Convert to milliseconds for readability
        ms = opt_time * 1000

        return {
            "milliseconds": round(ms, 2),
            "description": "Time taken for last MPC optimization",
            "target": "< 2000 ms (2 seconds)",
        }


class TemperaturePredictionSensor(ThermalModelSensorBase):
    """Sensor for MPC predicted temperature trajectory (T3.7.2)."""

    _attr_icon = "mdi:chart-line"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: AdaptiveThermalCoordinator,
        climate_entity: str,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, climate_entity, room_id)

        self._attr_name = f"{room_id} Temperature Prediction"
        self._attr_unique_id = f"{climate_entity}_temperature_prediction"
        self._attr_native_unit_of_measurement = "°C"

    @property
    def native_value(self) -> float | None:
        """Return the next predicted temperature (10 minutes ahead)."""
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return None

        predicted_temps = climate_state.attributes.get("predicted_temps")
        if not predicted_temps or len(predicted_temps) < 2:
            return None

        # Return first prediction (T(+10min), skip T(0) which is current)
        return predicted_temps[1]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full prediction trajectory as attributes."""
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            return {}

        predicted_temps = climate_state.attributes.get("predicted_temps")
        if not predicted_temps:
            return {}

        # Create forecast with timestamps
        # Assuming 10-minute intervals (dt=600s)
        forecast = []
        for i, temp in enumerate(predicted_temps):
            minutes_ahead = i * 10
            forecast.append({
                "time": f"+{minutes_ahead}min",
                "temperature": temp,
            })

        return {
            "forecast": forecast,
            "horizon_minutes": len(predicted_temps) * 10,
            "horizon_hours": round(len(predicted_temps) * 10 / 60, 1),
            "description": "Predicted temperature trajectory from MPC",
        }
