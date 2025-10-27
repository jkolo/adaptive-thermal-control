"""Model training utilities for thermal parameter identification.

This module provides functions to train the thermal model using historical
data from Home Assistant recorder. It combines data preprocessing, RLS
parameter estimation, and model validation.

Main workflow:
1. Fetch historical data from HA recorder (temperature, heating, outdoor temp)
2. Preprocess data (outlier removal, interpolation, resampling)
3. Train RLS estimator on preprocessed data
4. Validate model performance (RMSE, MAE metrics)
5. Return optimized parameters
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from homeassistant.core import HomeAssistant
from numpy.typing import NDArray

from .data_preprocessing import TrainingData, preprocess_training_data
from .history_helper import HistoryHelper
from .parameter_estimator import ParameterEstimator
from .thermal_model import ThermalModel, ThermalModelParameters

_LOGGER = logging.getLogger(__name__)

# Default training parameters
DEFAULT_TRAINING_DAYS = 30
DEFAULT_MIN_SAMPLES = 100


@dataclass
class TrainingMetrics:
    """Metrics for model training evaluation.

    Attributes:
        rmse: Root Mean Square Error [°C]
        mae: Mean Absolute Error [°C]
        max_error: Maximum absolute error [°C]
        r_squared: R² score (coefficient of determination)
        n_samples: Number of training samples used
    """

    rmse: float
    mae: float
    max_error: float
    r_squared: float
    n_samples: int

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "rmse": round(self.rmse, 3),
            "mae": round(self.mae, 3),
            "max_error": round(self.max_error, 3),
            "r_squared": round(self.r_squared, 4),
            "n_samples": self.n_samples,
        }

    def __repr__(self) -> str:
        """String representation.

        Returns:
            Formatted metrics string
        """
        return (
            f"TrainingMetrics(RMSE={self.rmse:.3f}°C, MAE={self.mae:.3f}°C, "
            f"R²={self.r_squared:.4f}, n={self.n_samples})"
        )


@dataclass
class TrainingResult:
    """Result of model training.

    Attributes:
        parameters: Estimated thermal parameters (R, C)
        metrics: Training performance metrics
        training_data: Preprocessed training data used
        success: Whether training was successful
        message: Status message
    """

    parameters: ThermalModelParameters | None
    metrics: TrainingMetrics | None
    training_data: TrainingData | None
    success: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "success": self.success,
            "message": self.message,
            "parameters": self.parameters.to_dict() if self.parameters else None,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "training_data_info": (
                self.training_data.to_dict() if self.training_data else None
            ),
        }


def calculate_metrics(
    y_true: NDArray[np.float64],
    y_pred: NDArray[np.float64],
) -> TrainingMetrics:
    """Calculate training metrics.

    Args:
        y_true: True temperature values [°C]
        y_pred: Predicted temperature values [°C]

    Returns:
        TrainingMetrics object
    """
    # Prediction errors
    errors = y_true - y_pred

    # RMSE: Root Mean Square Error
    rmse = float(np.sqrt(np.mean(errors**2)))

    # MAE: Mean Absolute Error
    mae = float(np.mean(np.abs(errors)))

    # Max error
    max_error = float(np.max(np.abs(errors)))

    # R² score
    ss_res = np.sum(errors**2)  # Residual sum of squares
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)  # Total sum of squares

    if ss_tot > 0:
        r_squared = float(1 - (ss_res / ss_tot))
    else:
        r_squared = 0.0

    return TrainingMetrics(
        rmse=rmse,
        mae=mae,
        max_error=max_error,
        r_squared=r_squared,
        n_samples=len(y_true),
    )


async def train_from_history(
    hass: HomeAssistant,
    room_temp_entity: str,
    outdoor_temp_entity: str,
    heating_power_entity: str | None = None,
    days: int = DEFAULT_TRAINING_DAYS,
    dt: float = 600.0,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> TrainingResult:
    """Train thermal model from historical data.

    This function performs the complete training pipeline:
    1. Fetch historical data from HA recorder
    2. Preprocess data (clean, interpolate, resample)
    3. Train RLS estimator
    4. Validate model performance
    5. Return optimized parameters

    Args:
        hass: Home Assistant instance
        room_temp_entity: Entity ID for room temperature sensor
        outdoor_temp_entity: Entity ID for outdoor temperature sensor
        heating_power_entity: Entity ID for heating power (optional)
        days: Number of days of historical data to use
        dt: Time step for training [seconds]
        min_samples: Minimum number of samples required

    Returns:
        TrainingResult with parameters and metrics
    """
    _LOGGER.info(
        "Starting model training: room=%s, outdoor=%s, days=%d",
        room_temp_entity,
        outdoor_temp_entity,
        days,
    )

    # Step 1: Fetch historical data
    history_helper = HistoryHelper(hass)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    try:
        # Fetch room temperature history
        room_temp_history = await history_helper.get_numeric_history(
            room_temp_entity,
            start_time,
            end_time,
        )

        if not room_temp_history:
            return TrainingResult(
                parameters=None,
                metrics=None,
                training_data=None,
                success=False,
                message=f"No history data found for {room_temp_entity}",
            )

        # Fetch outdoor temperature history
        outdoor_temp_history = await history_helper.get_numeric_history(
            outdoor_temp_entity,
            start_time,
            end_time,
        )

        if not outdoor_temp_history:
            return TrainingResult(
                parameters=None,
                metrics=None,
                training_data=None,
                success=False,
                message=f"No history data found for {outdoor_temp_entity}",
            )

        # Fetch heating power history (if available)
        heating_power_history = []
        if heating_power_entity:
            heating_power_history = await history_helper.get_numeric_history(
                heating_power_entity,
                start_time,
                end_time,
            )

        _LOGGER.info(
            "Fetched history: room=%d samples, outdoor=%d samples, power=%d samples",
            len(room_temp_history),
            len(outdoor_temp_history),
            len(heating_power_history) if heating_power_history else 0,
        )

    except Exception as e:
        _LOGGER.error("Failed to fetch history data: %s", e)
        return TrainingResult(
            parameters=None,
            metrics=None,
            training_data=None,
            success=False,
            message=f"Failed to fetch history: {str(e)}",
        )

    # Step 2: Align timestamps and prepare data
    # Find common timestamps (all three must have data)
    room_dict = {t: v for t, v in room_temp_history}
    outdoor_dict = {t: v for t, v in outdoor_temp_history}
    power_dict = {t: v for t, v in heating_power_history} if heating_power_history else {}

    # Get timestamps where all data is available
    if heating_power_entity and heating_power_history:
        common_timestamps = sorted(
            set(room_dict.keys()) & set(outdoor_dict.keys()) & set(power_dict.keys())
        )
    else:
        common_timestamps = sorted(set(room_dict.keys()) & set(outdoor_dict.keys()))
        # Assume zero heating if no power data
        power_dict = {t: 0.0 for t in common_timestamps}

    if len(common_timestamps) < min_samples:
        return TrainingResult(
            parameters=None,
            metrics=None,
            training_data=None,
            success=False,
            message=f"Insufficient aligned data: {len(common_timestamps)} < {min_samples}",
        )

    # Extract aligned data
    raw_timestamps = common_timestamps
    raw_temperatures = [room_dict[t] for t in raw_timestamps]
    raw_outdoor_temps = [outdoor_dict[t] for t in raw_timestamps]
    raw_heating_powers = [power_dict[t] for t in raw_timestamps]

    # Step 3: Preprocess data
    training_data = preprocess_training_data(
        raw_timestamps,
        raw_temperatures,
        raw_outdoor_temps,
        raw_heating_powers,
        target_dt=dt,
    )

    if training_data is None or training_data.n_samples < min_samples:
        return TrainingResult(
            parameters=None,
            metrics=None,
            training_data=training_data,
            success=False,
            message=f"Insufficient data after preprocessing: {training_data.n_samples if training_data else 0}",
        )

    _LOGGER.info("Preprocessed data: %d samples ready for training", training_data.n_samples)

    # Step 4: Train RLS estimator
    estimator = ParameterEstimator(dt=training_data.dt)

    # Run RLS on all data points
    for i in range(1, training_data.n_samples):
        estimator.update(
            T_measured=training_data.temperatures[i],
            T_outdoor=training_data.outdoor_temps[i - 1],
            P_heating=training_data.heating_powers[i - 1],
            T_previous=training_data.temperatures[i - 1],
        )

    # Extract thermal parameters
    parameters = estimator.get_thermal_parameters()

    if parameters is None:
        return TrainingResult(
            parameters=None,
            metrics=None,
            training_data=training_data,
            success=False,
            message="RLS failed to converge to valid parameters",
        )

    _LOGGER.info("RLS training complete: %s", parameters)

    # Step 5: Validate model performance
    model = ThermalModel(params=parameters, dt=training_data.dt)

    # Predict on training data
    y_pred = np.zeros(training_data.n_samples)
    y_pred[0] = training_data.temperatures[0]

    for i in range(1, training_data.n_samples):
        y_pred[i] = model.simulate_step(
            T_current=y_pred[i - 1],
            u_heating=training_data.heating_powers[i - 1],
            T_outdoor=training_data.outdoor_temps[i - 1],
        )

    # Calculate metrics
    metrics = calculate_metrics(training_data.temperatures, y_pred)

    _LOGGER.info("Training metrics: %s", metrics)

    # Determine success
    success = metrics.rmse < 2.0 and metrics.r_squared > 0.5
    message = "Training successful" if success else "Training completed but metrics poor"

    return TrainingResult(
        parameters=parameters,
        metrics=metrics,
        training_data=training_data,
        success=success,
        message=message,
    )


async def batch_train_multiple_rooms(
    hass: HomeAssistant,
    room_configs: list[dict[str, str]],
    days: int = DEFAULT_TRAINING_DAYS,
) -> dict[str, TrainingResult]:
    """Train models for multiple rooms in batch.

    Args:
        hass: Home Assistant instance
        room_configs: List of room configurations, each with:
            - room_id: Unique room identifier
            - room_temp_entity: Temperature sensor entity ID
            - outdoor_temp_entity: Outdoor temperature entity ID
            - heating_power_entity: Heating power entity ID (optional)
        days: Number of days of historical data

    Returns:
        Dictionary mapping room_id to TrainingResult
    """
    results = {}

    for config in room_configs:
        room_id = config["room_id"]
        _LOGGER.info("Training model for room: %s", room_id)

        result = await train_from_history(
            hass,
            room_temp_entity=config["room_temp_entity"],
            outdoor_temp_entity=config["outdoor_temp_entity"],
            heating_power_entity=config.get("heating_power_entity"),
            days=days,
        )

        results[room_id] = result

        if result.success:
            _LOGGER.info(
                "Room %s: Training successful - R=%.6f, C=%.0f, RMSE=%.3f°C",
                room_id,
                result.parameters.R,
                result.parameters.C,
                result.metrics.rmse,
            )
        else:
            _LOGGER.warning("Room %s: Training failed - %s", room_id, result.message)

    return results
