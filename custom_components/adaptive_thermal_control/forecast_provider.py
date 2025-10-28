"""Forecast provider for MPC predictions.

This module provides weather and disturbance forecasts for Model Predictive
Control. It fetches forecast data from Home Assistant entities and processes
them into the format required by the MPC controller.

Key features:
- Outdoor temperature forecast from weather entities
- Interpolation to controller time step (typically 10 minutes)
- Fallback to current temperature if forecast unavailable
- Extrapolation if forecast horizon too short
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.template import Template
from numpy.typing import NDArray

_LOGGER = logging.getLogger(__name__)


class ForecastProvider:
    """Provider for weather and disturbance forecasts.

    This class fetches forecast data from Home Assistant entities and
    processes them for use by the MPC controller. It handles interpolation,
    extrapolation, and fallback scenarios.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        weather_entity: str | None = None,
        outdoor_temp_entity: str | None = None,
    ) -> None:
        """Initialize forecast provider.

        Args:
            hass: Home Assistant instance
            weather_entity: Weather entity ID (e.g., "weather.home")
            outdoor_temp_entity: Outdoor temperature sensor entity ID
        """
        self._hass = hass
        self._weather_entity = weather_entity
        self._outdoor_temp_entity = outdoor_temp_entity

        if not weather_entity and not outdoor_temp_entity:
            _LOGGER.warning(
                "Neither weather_entity nor outdoor_temp_entity provided. "
                "Forecasts will use constant temperature."
            )

        _LOGGER.info(
            "Initialized ForecastProvider: weather=%s, outdoor_temp=%s",
            weather_entity,
            outdoor_temp_entity,
        )

    async def get_outdoor_temperature_forecast(
        self,
        hours: float = 4.0,
        dt: float = 600.0,
    ) -> NDArray[np.float64]:
        """Get outdoor temperature forecast.

        Fetches temperature forecast from weather entity and interpolates
        to the specified time step. Falls back to current temperature if
        forecast unavailable.

        Args:
            hours: Forecast horizon in hours
            dt: Time step in seconds (default: 600s = 10 min)

        Returns:
            Temperature forecast array [°C] for requested horizon
        """
        n_steps = int((hours * 3600) / dt)

        # Try to get forecast from weather entity
        if self._weather_entity:
            try:
                forecast = await self._get_weather_forecast(hours, dt, n_steps)
                if forecast is not None:
                    return forecast
            except Exception as e:
                _LOGGER.warning(
                    "Failed to get weather forecast from %s: %s",
                    self._weather_entity,
                    e,
                )

        # Fallback: use current outdoor temperature as constant
        current_temp = await self._get_current_outdoor_temperature()
        _LOGGER.debug(
            "Using constant temperature forecast: %.1f°C for %d steps",
            current_temp,
            n_steps,
        )
        return np.full(n_steps, current_temp)

    async def _get_weather_forecast(
        self,
        hours: float,
        dt: float,
        n_steps: int,
    ) -> NDArray[np.float64] | None:
        """Get forecast from weather entity.

        Args:
            hours: Forecast horizon in hours
            dt: Time step in seconds
            n_steps: Number of forecast steps

        Returns:
            Temperature forecast array or None if unavailable
        """
        # Get weather entity state
        state = self._hass.states.get(self._weather_entity)
        if state is None:
            _LOGGER.warning("Weather entity %s not found", self._weather_entity)
            return None

        # Get forecast attribute
        forecast_attr = state.attributes.get("forecast")
        if not forecast_attr:
            _LOGGER.debug("No forecast attribute in %s", self._weather_entity)
            return None

        # Extract temperature from forecast
        try:
            forecast_temps, forecast_times = self._extract_forecast_data(
                forecast_attr, hours
            )

            if len(forecast_temps) == 0:
                _LOGGER.debug("Empty forecast data")
                return None

            # Interpolate to controller time step
            interpolated = self._interpolate_forecast(
                forecast_temps, forecast_times, dt, n_steps
            )

            _LOGGER.debug(
                "Weather forecast: %d raw points -> %d interpolated steps",
                len(forecast_temps),
                len(interpolated),
            )

            return interpolated

        except Exception as e:
            _LOGGER.error("Error processing weather forecast: %s", e, exc_info=True)
            return None

    def _extract_forecast_data(
        self,
        forecast_attr: list[dict[str, Any]],
        max_hours: float,
    ) -> tuple[list[float], list[float]]:
        """Extract temperature and time data from forecast attribute.

        Args:
            forecast_attr: Forecast attribute from weather entity
            max_hours: Maximum forecast horizon in hours

        Returns:
            Tuple of (temperatures, relative_times_in_hours)
        """
        temps = []
        times = []
        now = datetime.now()

        for item in forecast_attr:
            # Get temperature (try different keys)
            temp = item.get("temperature")
            if temp is None:
                temp = item.get("temp")
            if temp is None:
                continue

            # Get datetime
            dt_str = item.get("datetime")
            if dt_str is None:
                continue

            try:
                # Parse datetime
                if isinstance(dt_str, str):
                    # Try ISO format
                    try:
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    except ValueError:
                        # Try other common formats
                        dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
                elif isinstance(dt_str, datetime):
                    dt = dt_str
                else:
                    continue

                # Calculate relative time in hours
                time_delta = (dt - now).total_seconds() / 3600

                # Only include future forecasts within horizon
                if 0 <= time_delta <= max_hours:
                    temps.append(float(temp))
                    times.append(time_delta)

            except Exception as e:
                _LOGGER.debug("Error parsing forecast item: %s", e)
                continue

        return temps, times

    def _interpolate_forecast(
        self,
        temps: list[float],
        times: list[float],
        dt: float,
        n_steps: int,
    ) -> NDArray[np.float64]:
        """Interpolate forecast to controller time step.

        Args:
            temps: Temperature values [°C]
            times: Time values [hours from now]
            dt: Controller time step [seconds]
            n_steps: Number of steps needed

        Returns:
            Interpolated temperature array
        """
        if len(temps) == 0:
            raise ValueError("Empty forecast data")

        # Convert controller time step to hours
        dt_hours = dt / 3600

        # Create target time points
        target_times = np.arange(n_steps) * dt_hours

        # Sort by time
        sorted_indices = np.argsort(times)
        times_sorted = np.array(times)[sorted_indices]
        temps_sorted = np.array(temps)[sorted_indices]

        # Interpolate (linear)
        interpolated = np.interp(
            target_times,
            times_sorted,
            temps_sorted,
            left=temps_sorted[0],  # Extrapolate with first value
            right=temps_sorted[-1],  # Extrapolate with last value
        )

        return interpolated

    async def _get_current_outdoor_temperature(self) -> float:
        """Get current outdoor temperature.

        Returns:
            Current outdoor temperature [°C]
        """
        # Try outdoor temperature sensor first
        if self._outdoor_temp_entity:
            state = self._hass.states.get(self._outdoor_temp_entity)
            if state and state.state not in ["unknown", "unavailable"]:
                try:
                    return float(state.state)
                except (ValueError, TypeError):
                    pass

        # Try weather entity current temperature
        if self._weather_entity:
            state = self._hass.states.get(self._weather_entity)
            if state:
                temp = state.attributes.get("temperature")
                if temp is not None:
                    try:
                        return float(temp)
                    except (ValueError, TypeError):
                        pass

        # Default fallback
        _LOGGER.warning(
            "Could not get current outdoor temperature, using default 10°C"
        )
        return 10.0

    async def get_solar_forecast(
        self,
        hours: float = 4.0,
        dt: float = 600.0,
    ) -> NDArray[np.float64]:
        """Get solar irradiance forecast (placeholder for Phase 4).

        Args:
            hours: Forecast horizon in hours
            dt: Time step in seconds

        Returns:
            Solar irradiance forecast array [W/m²]
        """
        n_steps = int((hours * 3600) / dt)
        # Placeholder: return zeros
        _LOGGER.debug("Solar forecast not implemented yet, returning zeros")
        return np.zeros(n_steps)

    def set_weather_entity(self, weather_entity: str) -> None:
        """Update weather entity.

        Args:
            weather_entity: New weather entity ID
        """
        self._weather_entity = weather_entity
        _LOGGER.info("Updated weather entity to: %s", weather_entity)

    def set_outdoor_temp_entity(self, outdoor_temp_entity: str) -> None:
        """Update outdoor temperature entity.

        Args:
            outdoor_temp_entity: New outdoor temperature entity ID
        """
        self._outdoor_temp_entity = outdoor_temp_entity
        _LOGGER.info("Updated outdoor temp entity to: %s", outdoor_temp_entity)
