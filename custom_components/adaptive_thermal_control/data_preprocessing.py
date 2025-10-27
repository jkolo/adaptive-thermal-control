"""Data preprocessing utilities for parameter identification.

This module provides functions to clean and prepare historical data
for training the thermal model using RLS parameter estimation.

Processing steps:
1. Outlier removal: Remove physically impossible values
2. Interpolation: Fill gaps in time series
3. Resampling: Convert to fixed time step
4. Filtering: Reduce measurement noise
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from numpy.typing import NDArray

_LOGGER = logging.getLogger(__name__)

# Default preprocessing parameters
DEFAULT_TEMP_MIN = 0.0  # °C
DEFAULT_TEMP_MAX = 50.0  # °C
DEFAULT_POWER_MAX = 10000.0  # W
DEFAULT_MAX_GAP_MINUTES = 30  # minutes
DEFAULT_TARGET_DT = 600.0  # seconds (10 min)
DEFAULT_FILTER_WINDOW = 3  # samples


@dataclass
class TrainingData:
    """Structured training data for parameter identification.

    Attributes:
        timestamps: Array of timestamps
        temperatures: Room temperature measurements [°C]
        outdoor_temps: Outdoor temperature measurements [°C]
        heating_powers: Heating power values [W]
        dt: Time step [seconds]
        n_samples: Number of samples
    """

    timestamps: list[datetime]
    temperatures: NDArray[np.float64]
    outdoor_temps: NDArray[np.float64]
    heating_powers: NDArray[np.float64]
    dt: float

    @property
    def n_samples(self) -> int:
        """Get number of samples."""
        return len(self.temperatures)

    def validate(self) -> bool:
        """Validate data consistency.

        Returns:
            True if data is valid
        """
        n = self.n_samples
        if len(self.outdoor_temps) != n:
            _LOGGER.error("Outdoor temps length mismatch: %d vs %d", len(self.outdoor_temps), n)
            return False

        if len(self.heating_powers) != n:
            _LOGGER.error("Heating powers length mismatch: %d vs %d", len(self.heating_powers), n)
            return False

        if len(self.timestamps) != n:
            _LOGGER.error("Timestamps length mismatch: %d vs %d", len(self.timestamps), n)
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "n_samples": self.n_samples,
            "dt": self.dt,
            "temperature_range": [float(self.temperatures.min()), float(self.temperatures.max())],
            "outdoor_temp_range": [float(self.outdoor_temps.min()), float(self.outdoor_temps.max())],
            "heating_power_range": [float(self.heating_powers.min()), float(self.heating_powers.max())],
            "start_time": self.timestamps[0].isoformat() if self.timestamps else None,
            "end_time": self.timestamps[-1].isoformat() if self.timestamps else None,
        }


def remove_outliers(
    data: NDArray[np.float64],
    min_value: float | None = None,
    max_value: float | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Remove outliers from data.

    Args:
        data: Input data array
        min_value: Minimum valid value (inclusive)
        max_value: Maximum valid value (inclusive)

    Returns:
        Tuple of (cleaned_data, mask) where mask indicates valid samples
    """
    mask = np.ones(len(data), dtype=bool)

    if min_value is not None:
        mask &= data >= min_value

    if max_value is not None:
        mask &= data <= max_value

    # Also remove NaN and Inf
    mask &= np.isfinite(data)

    n_removed = (~mask).sum()
    if n_removed > 0:
        _LOGGER.debug(
            "Removed %d outliers (%.1f%% of data)",
            n_removed,
            100 * n_removed / len(data),
        )

    return data.copy(), mask


def interpolate_gaps(
    timestamps: list[datetime],
    data: NDArray[np.float64],
    max_gap_minutes: int = DEFAULT_MAX_GAP_MINUTES,
) -> tuple[list[datetime], NDArray[np.float64]]:
    """Interpolate missing data using linear interpolation.

    Only interpolates gaps smaller than max_gap_minutes. Larger gaps
    are left as NaN and will be removed later.

    Args:
        timestamps: List of timestamps
        data: Data array (may contain NaN)
        max_gap_minutes: Maximum gap to interpolate [minutes]

    Returns:
        Tuple of (timestamps, interpolated_data)
    """
    if len(data) == 0:
        return timestamps, data

    # Convert to numpy array for easier manipulation
    data_interp = data.copy()

    # Find NaN positions
    nan_mask = np.isnan(data_interp)
    n_nans = nan_mask.sum()

    if n_nans == 0:
        return timestamps, data_interp

    _LOGGER.debug("Interpolating %d NaN values", n_nans)

    # Find valid data indices
    valid_indices = np.where(~nan_mask)[0]

    if len(valid_indices) < 2:
        _LOGGER.warning("Not enough valid data points for interpolation")
        return timestamps, data_interp

    # Interpolate each gap
    for i in range(len(valid_indices) - 1):
        start_idx = valid_indices[i]
        end_idx = valid_indices[i + 1]

        # Check gap size
        gap_duration = timestamps[end_idx] - timestamps[start_idx]
        gap_minutes = gap_duration.total_seconds() / 60

        if gap_minutes <= max_gap_minutes:
            # Linear interpolation
            gap_size = end_idx - start_idx
            if gap_size > 1:
                start_val = data_interp[start_idx]
                end_val = data_interp[end_idx]

                for j in range(1, gap_size):
                    alpha = j / gap_size
                    data_interp[start_idx + j] = (1 - alpha) * start_val + alpha * end_val
        else:
            _LOGGER.debug(
                "Gap too large to interpolate: %.1f min (max: %d min)",
                gap_minutes,
                max_gap_minutes,
            )

    # Count remaining NaNs
    n_remaining = np.isnan(data_interp).sum()
    if n_remaining > 0:
        _LOGGER.debug("%d NaN values remain after interpolation", n_remaining)

    return timestamps, data_interp


def resample_to_fixed_dt(
    timestamps: list[datetime],
    data_dict: dict[str, NDArray[np.float64]],
    target_dt: float = DEFAULT_TARGET_DT,
) -> tuple[list[datetime], dict[str, NDArray[np.float64]]]:
    """Resample data to fixed time step.

    Uses linear interpolation to resample all signals to a uniform time grid.

    Args:
        timestamps: List of timestamps (may be irregularly spaced)
        data_dict: Dictionary of data arrays {name: array}
        target_dt: Target time step [seconds]

    Returns:
        Tuple of (resampled_timestamps, resampled_data_dict)
    """
    if len(timestamps) < 2:
        _LOGGER.warning("Not enough data for resampling")
        return timestamps, data_dict

    # Create uniform time grid
    start_time = timestamps[0]
    end_time = timestamps[-1]
    duration = (end_time - start_time).total_seconds()

    n_samples = int(duration / target_dt) + 1
    resampled_timestamps = [
        start_time + timedelta(seconds=i * target_dt)
        for i in range(n_samples)
    ]

    # Convert original timestamps to seconds since start
    original_times = np.array([
        (t - start_time).total_seconds() for t in timestamps
    ])

    # Target times
    target_times = np.array([
        (t - start_time).total_seconds() for t in resampled_timestamps
    ])

    # Resample each data array
    resampled_data = {}
    for name, data in data_dict.items():
        # Remove NaN before interpolation
        valid_mask = np.isfinite(data)
        if valid_mask.sum() < 2:
            _LOGGER.warning("Not enough valid data for resampling: %s", name)
            resampled_data[name] = np.full(n_samples, np.nan)
            continue

        # Interpolate
        resampled_data[name] = np.interp(
            target_times,
            original_times[valid_mask],
            data[valid_mask],
        )

    _LOGGER.debug(
        "Resampled from %d samples to %d samples (dt=%.0fs)",
        len(timestamps),
        n_samples,
        target_dt,
    )

    return resampled_timestamps, resampled_data


def apply_moving_average_filter(
    data: NDArray[np.float64],
    window_size: int = DEFAULT_FILTER_WINDOW,
) -> NDArray[np.float64]:
    """Apply moving average filter to reduce noise.

    Args:
        data: Input data array
        window_size: Filter window size (odd number recommended)

    Returns:
        Filtered data array
    """
    if window_size < 2:
        return data.copy()

    # Ensure window size is odd for symmetry
    if window_size % 2 == 0:
        window_size += 1

    # Apply uniform filter (moving average)
    filtered = np.convolve(
        data,
        np.ones(window_size) / window_size,
        mode='same',
    )

    _LOGGER.debug("Applied moving average filter (window=%d)", window_size)

    return filtered


def preprocess_training_data(
    raw_timestamps: list[datetime],
    raw_temperatures: list[float],
    raw_outdoor_temps: list[float],
    raw_heating_powers: list[float],
    temp_min: float = DEFAULT_TEMP_MIN,
    temp_max: float = DEFAULT_TEMP_MAX,
    power_max: float = DEFAULT_POWER_MAX,
    max_gap_minutes: int = DEFAULT_MAX_GAP_MINUTES,
    target_dt: float = DEFAULT_TARGET_DT,
    filter_window: int = DEFAULT_FILTER_WINDOW,
) -> TrainingData | None:
    """Complete preprocessing pipeline for training data.

    Steps:
    1. Remove outliers (temperature out of bounds, invalid power)
    2. Interpolate small gaps (< max_gap_minutes)
    3. Resample to fixed time step (target_dt)
    4. Apply noise filtering (moving average)

    Args:
        raw_timestamps: List of timestamps
        raw_temperatures: Room temperature measurements [°C]
        raw_outdoor_temps: Outdoor temperature measurements [°C]
        raw_heating_powers: Heating power values [W]
        temp_min: Minimum valid temperature [°C]
        temp_max: Maximum valid temperature [°C]
        power_max: Maximum valid heating power [W]
        max_gap_minutes: Maximum gap to interpolate [minutes]
        target_dt: Target time step [seconds]
        filter_window: Moving average window size

    Returns:
        TrainingData object if successful, None if data insufficient
    """
    _LOGGER.info(
        "Preprocessing %d raw samples (%.1f hours)",
        len(raw_timestamps),
        (raw_timestamps[-1] - raw_timestamps[0]).total_seconds() / 3600 if raw_timestamps else 0,
    )

    # Convert to numpy arrays
    temperatures = np.array(raw_temperatures, dtype=float)
    outdoor_temps = np.array(raw_outdoor_temps, dtype=float)
    heating_powers = np.array(raw_heating_powers, dtype=float)

    # Step 1: Remove outliers
    _, temp_mask = remove_outliers(temperatures, temp_min, temp_max)
    _, outdoor_mask = remove_outliers(outdoor_temps, temp_min, temp_max)
    _, power_mask = remove_outliers(heating_powers, 0.0, power_max)

    # Combine masks (all must be valid)
    valid_mask = temp_mask & outdoor_mask & power_mask

    n_removed = (~valid_mask).sum()
    if n_removed > 0:
        _LOGGER.info("Removed %d outliers (%.1f%%)", n_removed, 100 * n_removed / len(valid_mask))

    # Apply mask
    timestamps = [t for i, t in enumerate(raw_timestamps) if valid_mask[i]]
    temperatures = temperatures[valid_mask]
    outdoor_temps = outdoor_temps[valid_mask]
    heating_powers = heating_powers[valid_mask]

    if len(timestamps) < 10:
        _LOGGER.error("Insufficient data after outlier removal: %d samples", len(timestamps))
        return None

    # Step 2: Interpolate gaps (mark large gaps as NaN)
    timestamps, temperatures = interpolate_gaps(timestamps, temperatures, max_gap_minutes)
    _, outdoor_temps = interpolate_gaps(timestamps, outdoor_temps, max_gap_minutes)
    _, heating_powers = interpolate_gaps(timestamps, heating_powers, max_gap_minutes)

    # Remove any remaining NaN
    final_mask = (
        np.isfinite(temperatures) &
        np.isfinite(outdoor_temps) &
        np.isfinite(heating_powers)
    )
    timestamps = [t for i, t in enumerate(timestamps) if final_mask[i]]
    temperatures = temperatures[final_mask]
    outdoor_temps = outdoor_temps[final_mask]
    heating_powers = heating_powers[final_mask]

    if len(timestamps) < 10:
        _LOGGER.error("Insufficient data after interpolation: %d samples", len(timestamps))
        return None

    # Step 3: Resample to fixed time step
    data_dict = {
        "temperatures": temperatures,
        "outdoor_temps": outdoor_temps,
        "heating_powers": heating_powers,
    }

    timestamps, resampled = resample_to_fixed_dt(timestamps, data_dict, target_dt)
    temperatures = resampled["temperatures"]
    outdoor_temps = resampled["outdoor_temps"]
    heating_powers = resampled["heating_powers"]

    # Step 4: Apply noise filtering
    if filter_window > 1:
        temperatures = apply_moving_average_filter(temperatures, filter_window)
        outdoor_temps = apply_moving_average_filter(outdoor_temps, filter_window)
        # Note: Don't filter heating powers (they may have step changes)

    # Create TrainingData object
    training_data = TrainingData(
        timestamps=timestamps,
        temperatures=temperatures,
        outdoor_temps=outdoor_temps,
        heating_powers=heating_powers,
        dt=target_dt,
    )

    if not training_data.validate():
        _LOGGER.error("Training data validation failed")
        return None

    _LOGGER.info(
        "Preprocessing complete: %d samples, dt=%.0fs, duration=%.1fh",
        training_data.n_samples,
        training_data.dt,
        (timestamps[-1] - timestamps[0]).total_seconds() / 3600,
    )

    return training_data
