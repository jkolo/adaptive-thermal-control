"""History data helper for Adaptive Thermal Control.

This module provides utilities to fetch and process historical data from
Home Assistant's recorder. The data is used for training thermal models
and identifying system parameters.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import numpy as np
from numpy.typing import NDArray

from homeassistant.components import recorder
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .const import MIN_TRAINING_DAYS, OPTIMAL_TRAINING_DAYS

_LOGGER = logging.getLogger(__name__)


class HistoryHelper:
    """Helper class for fetching and processing historical data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the history helper.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self._cache: dict[str, tuple[datetime, list[State]]] = {}

    async def get_history(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        use_cache: bool = True,
    ) -> list[State]:
        """Get historical states for an entity.

        Args:
            entity_id: Entity ID to fetch history for
            start_time: Start of time range
            end_time: End of time range
            use_cache: Whether to use cached data if available

        Returns:
            List of State objects for the entity in the time range
        """
        # Check cache
        cache_key = f"{entity_id}_{start_time.isoformat()}_{end_time.isoformat()}"
        if use_cache and cache_key in self._cache:
            cached_time, cached_states = self._cache[cache_key]
            # Cache valid for 5 minutes
            if datetime.now() - cached_time < timedelta(minutes=5):
                _LOGGER.debug(
                    "Using cached history for %s (%d states)",
                    entity_id,
                    len(cached_states),
                )
                return cached_states

        # Fetch from recorder
        _LOGGER.debug(
            "Fetching history for %s from %s to %s",
            entity_id,
            start_time,
            end_time,
        )

        # Use executor to avoid blocking event loop
        history_list = await self.hass.async_add_executor_job(
            self._get_history_sync,
            entity_id,
            start_time,
            end_time,
        )

        # Filter invalid states
        valid_states = [
            state
            for state in history_list
            if state.state not in ("unknown", "unavailable", "")
            and state.state is not None
        ]

        _LOGGER.info(
            "Fetched %d valid states for %s (filtered from %d)",
            len(valid_states),
            entity_id,
            len(history_list),
        )

        # Cache result
        self._cache[cache_key] = (datetime.now(), valid_states)

        return valid_states

    def _get_history_sync(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[State]:
        """Synchronous version of get_history for executor.

        Args:
            entity_id: Entity ID to fetch history for
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of State objects
        """
        # Get history from recorder
        history_dict = recorder.history.get_significant_states(
            self.hass,
            start_time,
            end_time,
            entity_ids=[entity_id],
            significant_changes_only=False,
        )

        return history_dict.get(entity_id, [])

    async def get_numeric_history(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
        resample_seconds: int | None = None,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Get numerical history data as NumPy arrays.

        Args:
            entity_id: Entity ID to fetch history for
            start_time: Start of time range
            end_time: End of time range
            resample_seconds: If provided, resample data to this interval

        Returns:
            Tuple of (timestamps, values) as NumPy arrays
        """
        states = await self.get_history(entity_id, start_time, end_time)

        if not states:
            _LOGGER.warning("No history data found for %s", entity_id)
            return np.array([]), np.array([])

        # Extract timestamps and values
        timestamps: list[float] = []
        values: list[float] = []

        for state in states:
            try:
                value = float(state.state)
                timestamp = state.last_changed.timestamp()
                timestamps.append(timestamp)
                values.append(value)
            except (ValueError, TypeError) as err:
                _LOGGER.debug(
                    "Skipping invalid state for %s: %s (%s)",
                    entity_id,
                    state.state,
                    err,
                )
                continue

        if not timestamps:
            _LOGGER.warning("No valid numeric data found for %s", entity_id)
            return np.array([]), np.array([])

        # Convert to NumPy arrays
        timestamps_array = np.array(timestamps)
        values_array = np.array(values)

        # Resample if requested
        if resample_seconds is not None:
            timestamps_array, values_array = self._resample_data(
                timestamps_array, values_array, resample_seconds
            )

        _LOGGER.info(
            "Extracted %d numeric samples for %s", len(values_array), entity_id
        )

        return timestamps_array, values_array

    def _resample_data(
        self,
        timestamps: NDArray[np.float64],
        values: NDArray[np.float64],
        interval_seconds: int,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Resample data to regular time intervals.

        Uses linear interpolation for missing values.

        Args:
            timestamps: Array of timestamps
            values: Array of values
            interval_seconds: Target sampling interval in seconds

        Returns:
            Tuple of (resampled_timestamps, resampled_values)
        """
        if len(timestamps) == 0:
            return timestamps, values

        # Create regular time grid
        start_time = timestamps[0]
        end_time = timestamps[-1]
        num_samples = int((end_time - start_time) / interval_seconds) + 1

        new_timestamps = np.linspace(start_time, end_time, num_samples)

        # Interpolate values
        new_values = np.interp(new_timestamps, timestamps, values)

        _LOGGER.debug(
            "Resampled data from %d to %d samples (interval: %ds)",
            len(timestamps),
            len(new_timestamps),
            interval_seconds,
        )

        return new_timestamps, new_values

    async def collect_training_data(
        self,
        room_temp_entity: str,
        outdoor_temp_entity: str | None = None,
        valve_entities: list[str] | None = None,
        days: int = OPTIMAL_TRAINING_DAYS,
    ) -> dict[str, Any]:
        """Collect training data for thermal model identification.

        Args:
            room_temp_entity: Room temperature sensor entity
            outdoor_temp_entity: Outdoor temperature sensor entity (optional)
            valve_entities: List of valve control entities (optional)
            days: Number of days of historical data to collect

        Returns:
            Dictionary with training data arrays
        """
        end_time = dt_util.now()
        start_time = end_time - timedelta(days=days)

        _LOGGER.info(
            "Collecting training data for %s (%d days)",
            room_temp_entity,
            days,
        )

        # Collect room temperature data
        room_timestamps, room_temps = await self.get_numeric_history(
            room_temp_entity,
            start_time,
            end_time,
            resample_seconds=600,  # 10-minute intervals
        )

        if len(room_temps) == 0:
            _LOGGER.error(
                "No room temperature data available for %s", room_temp_entity
            )
            return {}

        training_data: dict[str, Any] = {
            "timestamps": room_timestamps,
            "room_temperature": room_temps,
            "days": days,
            "num_samples": len(room_temps),
        }

        # Collect outdoor temperature if available
        if outdoor_temp_entity:
            outdoor_timestamps, outdoor_temps = await self.get_numeric_history(
                outdoor_temp_entity,
                start_time,
                end_time,
                resample_seconds=600,
            )

            if len(outdoor_temps) > 0:
                training_data["outdoor_temperature"] = outdoor_temps
                _LOGGER.info("Collected outdoor temperature data: %d samples", len(outdoor_temps))

        # Collect valve position data if available
        if valve_entities:
            valve_data = {}
            for valve_entity in valve_entities:
                valve_timestamps, valve_positions = await self.get_numeric_history(
                    valve_entity,
                    start_time,
                    end_time,
                    resample_seconds=600,
                )

                if len(valve_positions) > 0:
                    valve_data[valve_entity] = valve_positions
                    _LOGGER.info(
                        "Collected valve data for %s: %d samples",
                        valve_entity,
                        len(valve_positions),
                    )

            if valve_data:
                training_data["valve_positions"] = valve_data

        _LOGGER.info(
            "Training data collection complete: %d samples over %d days",
            len(room_temps),
            days,
        )

        return training_data

    async def check_data_availability(
        self,
        entity_id: str,
        min_days: int = MIN_TRAINING_DAYS,
    ) -> tuple[bool, int, str]:
        """Check if sufficient historical data is available.

        Args:
            entity_id: Entity ID to check
            min_days: Minimum required days of data

        Returns:
            Tuple of (sufficient, actual_days, status_message)
        """
        end_time = dt_util.now()
        start_time = end_time - timedelta(days=min_days)

        states = await self.get_history(entity_id, start_time, end_time)

        if not states:
            return False, 0, f"No historical data found for {entity_id}"

        # Calculate actual data span
        first_state = states[0]
        last_state = states[-1]
        data_span = (last_state.last_changed - first_state.last_changed).days

        if data_span < min_days:
            return (
                False,
                data_span,
                f"Insufficient data: {data_span} days (minimum: {min_days} days)",
            )

        if data_span < OPTIMAL_TRAINING_DAYS:
            return (
                True,
                data_span,
                f"Sufficient data available: {data_span} days (learning in progress)",
            )

        return (
            True,
            data_span,
            f"Optimal data available: {data_span} days (ready for MPC)",
        )

    def clear_cache(self) -> None:
        """Clear the history cache."""
        self._cache.clear()
        _LOGGER.info("History cache cleared")
