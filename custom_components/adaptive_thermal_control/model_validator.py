"""Model validation utilities for thermal model evaluation.

This module provides tools to validate thermal model performance by
comparing predictions against actual measurements. It calculates various
error metrics and can generate diagnostic visualizations.

Validation approach:
- One-step-ahead prediction (predict next temperature from current state)
- Multi-step prediction (simulate entire trajectory)
- Rolling window validation (test on recent data)
- Cross-validation (K-fold)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .data_preprocessing import TrainingData
from .thermal_model import ThermalModel

_LOGGER = logging.getLogger(__name__)


@dataclass
class ValidationMetrics:
    """Metrics for model validation.

    Attributes:
        mae: Mean Absolute Error [°C]
        rmse: Root Mean Square Error [°C]
        r_squared: R² score (coefficient of determination)
        max_error: Maximum absolute error [°C]
        n_samples: Number of samples validated
        prediction_type: Type of prediction ('one_step' or 'multi_step')
    """

    mae: float
    rmse: float
    r_squared: float
    max_error: float
    n_samples: int
    prediction_type: str = "one_step"

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "mae": round(self.mae, 3),
            "rmse": round(self.rmse, 3),
            "r_squared": round(self.r_squared, 4),
            "max_error": round(self.max_error, 3),
            "n_samples": self.n_samples,
            "prediction_type": self.prediction_type,
        }

    def __repr__(self) -> str:
        """String representation.

        Returns:
            Formatted metrics string
        """
        return (
            f"ValidationMetrics({self.prediction_type}: "
            f"MAE={self.mae:.3f}°C, RMSE={self.rmse:.3f}°C, "
            f"R²={self.r_squared:.4f}, max={self.max_error:.3f}°C, n={self.n_samples})"
        )

    def is_good(self, rmse_threshold: float = 1.0, r2_threshold: float = 0.7) -> bool:
        """Check if metrics indicate good model performance.

        Args:
            rmse_threshold: Maximum acceptable RMSE [°C]
            r2_threshold: Minimum acceptable R² score

        Returns:
            True if model performance is good
        """
        return self.rmse <= rmse_threshold and self.r_squared >= r2_threshold


class ModelValidator:
    """Validator for thermal model performance evaluation.

    This class provides methods to validate a thermal model against
    test data and calculate various performance metrics.
    """

    def __init__(self, model: ThermalModel) -> None:
        """Initialize model validator.

        Args:
            model: ThermalModel instance to validate
        """
        self.model = model
        _LOGGER.debug("Initialized ModelValidator for model: %s", model)

    def validate(
        self,
        test_data: TrainingData,
        prediction_type: str = "one_step",
    ) -> ValidationMetrics:
        """Validate model on test data.

        Args:
            test_data: Test dataset (preprocessed)
            prediction_type: Type of prediction:
                - 'one_step': Predict next temperature from actual current (default)
                - 'multi_step': Simulate entire trajectory from initial condition

        Returns:
            ValidationMetrics object

        Raises:
            ValueError: If prediction_type is invalid
        """
        if prediction_type not in ("one_step", "multi_step"):
            raise ValueError(f"Invalid prediction_type: {prediction_type}")

        _LOGGER.info(
            "Validating model on %d samples (%s prediction)",
            test_data.n_samples,
            prediction_type,
        )

        if prediction_type == "one_step":
            return self._validate_one_step(test_data)
        else:
            return self._validate_multi_step(test_data)

    def _validate_one_step(self, test_data: TrainingData) -> ValidationMetrics:
        """Validate using one-step-ahead predictions.

        This tests the model's ability to predict the next temperature
        given the true current temperature (not accumulated errors).

        Args:
            test_data: Test dataset

        Returns:
            ValidationMetrics for one-step prediction
        """
        n = test_data.n_samples
        y_true = test_data.temperatures
        y_pred = np.zeros(n)

        # First prediction
        y_pred[0] = y_true[0]

        # One-step-ahead predictions
        for i in range(1, n):
            y_pred[i] = self.model.simulate_step(
                T_current=y_true[i - 1],  # Use true temperature
                u_heating=test_data.heating_powers[i - 1],
                T_outdoor=test_data.outdoor_temps[i - 1],
            )

        return self._calculate_metrics(
            y_true,
            y_pred,
            prediction_type="one_step",
        )

    def _validate_multi_step(self, test_data: TrainingData) -> ValidationMetrics:
        """Validate using multi-step simulation.

        This tests the model's ability to simulate an entire trajectory
        from an initial condition (errors accumulate over time).

        Args:
            test_data: Test dataset

        Returns:
            ValidationMetrics for multi-step prediction
        """
        n = test_data.n_samples
        y_true = test_data.temperatures

        # Simulate entire trajectory
        y_pred = self.model.predict(
            T_initial=y_true[0],
            u_sequence=test_data.heating_powers[:-1],
            T_outdoor_sequence=test_data.outdoor_temps[:-1],
        )

        # predict() returns n+1 values (includes initial), we want n values
        y_pred = y_pred[1:]  # Skip initial condition

        return self._calculate_metrics(
            y_true[1:],  # Skip first sample (it's the initial condition)
            y_pred,
            prediction_type="multi_step",
        )

    def _calculate_metrics(
        self,
        y_true: NDArray[np.float64],
        y_pred: NDArray[np.float64],
        prediction_type: str,
    ) -> ValidationMetrics:
        """Calculate validation metrics.

        Args:
            y_true: True temperature values [°C]
            y_pred: Predicted temperature values [°C]
            prediction_type: Type of prediction

        Returns:
            ValidationMetrics object
        """
        # Prediction errors
        errors = y_true - y_pred

        # MAE: Mean Absolute Error
        mae = float(np.mean(np.abs(errors)))

        # RMSE: Root Mean Square Error
        rmse = float(np.sqrt(np.mean(errors**2)))

        # Max error
        max_error = float(np.max(np.abs(errors)))

        # R² score
        ss_res = np.sum(errors**2)  # Residual sum of squares
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)  # Total sum of squares

        if ss_tot > 0:
            r_squared = float(1 - (ss_res / ss_tot))
        else:
            r_squared = 0.0

        metrics = ValidationMetrics(
            mae=mae,
            rmse=rmse,
            r_squared=r_squared,
            max_error=max_error,
            n_samples=len(y_true),
            prediction_type=prediction_type,
        )

        _LOGGER.debug("Validation metrics: %s", metrics)

        return metrics

    def compare_models(
        self,
        other_model: ThermalModel,
        test_data: TrainingData,
    ) -> tuple[ValidationMetrics, ValidationMetrics]:
        """Compare two models on the same test data.

        Args:
            other_model: Alternative model to compare
            test_data: Test dataset

        Returns:
            Tuple of (metrics_this_model, metrics_other_model)
        """
        metrics_this = self.validate(test_data, prediction_type="multi_step")

        other_validator = ModelValidator(other_model)
        metrics_other = other_validator.validate(test_data, prediction_type="multi_step")

        _LOGGER.info("Model comparison:")
        _LOGGER.info("  Current model: %s", metrics_this)
        _LOGGER.info("  Other model:   %s", metrics_other)

        return metrics_this, metrics_other

    def rolling_window_validation(
        self,
        test_data: TrainingData,
        window_hours: float = 24.0,
    ) -> list[ValidationMetrics]:
        """Validate model on rolling time windows.

        This tests model stability over different time periods.

        Args:
            test_data: Test dataset
            window_hours: Window size [hours]

        Returns:
            List of ValidationMetrics for each window
        """
        window_samples = int(window_hours * 3600 / test_data.dt)

        if window_samples >= test_data.n_samples:
            _LOGGER.warning(
                "Window size (%d samples) >= dataset size (%d samples)",
                window_samples,
                test_data.n_samples,
            )
            return [self.validate(test_data)]

        results = []
        n_windows = test_data.n_samples - window_samples + 1

        for i in range(0, n_windows, window_samples // 2):  # 50% overlap
            end_idx = min(i + window_samples, test_data.n_samples)

            # Create window data
            window_data = TrainingData(
                timestamps=test_data.timestamps[i:end_idx],
                temperatures=test_data.temperatures[i:end_idx],
                outdoor_temps=test_data.outdoor_temps[i:end_idx],
                heating_powers=test_data.heating_powers[i:end_idx],
                dt=test_data.dt,
            )

            metrics = self.validate(window_data, prediction_type="multi_step")
            results.append(metrics)

        _LOGGER.info(
            "Rolling window validation: %d windows, avg RMSE=%.3f°C",
            len(results),
            np.mean([m.rmse for m in results]),
        )

        return results

    def get_prediction_errors(
        self,
        test_data: TrainingData,
        prediction_type: str = "one_step",
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        """Get detailed prediction errors for analysis.

        Args:
            test_data: Test dataset
            prediction_type: Type of prediction

        Returns:
            Tuple of (y_true, y_pred, errors)
        """
        if prediction_type == "one_step":
            n = test_data.n_samples
            y_true = test_data.temperatures
            y_pred = np.zeros(n)
            y_pred[0] = y_true[0]

            for i in range(1, n):
                y_pred[i] = self.model.simulate_step(
                    T_current=y_true[i - 1],
                    u_heating=test_data.heating_powers[i - 1],
                    T_outdoor=test_data.outdoor_temps[i - 1],
                )
        else:
            y_true = test_data.temperatures
            y_pred = self.model.predict(
                T_initial=y_true[0],
                u_sequence=test_data.heating_powers[:-1],
                T_outdoor_sequence=test_data.outdoor_temps[:-1],
            )
            y_pred = y_pred[1:]  # Skip initial
            y_true = y_true[1:]

        errors = y_true - y_pred

        return y_true, y_pred, errors


def cross_validate(
    training_data: TrainingData,
    k_folds: int = 5,
    estimator_factory: Any = None,
) -> tuple[list[ValidationMetrics], dict[str, Any]]:
    """Perform K-fold cross-validation on training data.

    Args:
        training_data: Complete dataset to validate
        k_folds: Number of folds (default: 5)
        estimator_factory: Factory function to create parameter estimator

    Returns:
        Tuple of (list of metrics for each fold, statistics dict)
    """
    from .model_trainer import calculate_metrics
    from .parameter_estimator import ParameterEstimator

    n = training_data.n_samples
    fold_size = n // k_folds

    if fold_size < 10:
        _LOGGER.error("Insufficient data for %d-fold CV: %d samples", k_folds, n)
        raise ValueError(f"Insufficient data for {k_folds}-fold cross-validation")

    _LOGGER.info("Running %d-fold cross-validation on %d samples", k_folds, n)

    metrics_list = []
    parameters_list = []

    for fold in range(k_folds):
        # Define test fold
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < k_folds - 1 else n

        # Training indices (all except test fold)
        train_indices = list(range(0, test_start)) + list(range(test_end, n))
        test_indices = list(range(test_start, test_end))

        # Create training and test datasets
        train_data = TrainingData(
            timestamps=[training_data.timestamps[i] for i in train_indices],
            temperatures=training_data.temperatures[train_indices],
            outdoor_temps=training_data.outdoor_temps[train_indices],
            heating_powers=training_data.heating_powers[train_indices],
            dt=training_data.dt,
        )

        test_data = TrainingData(
            timestamps=[training_data.timestamps[i] for i in test_indices],
            temperatures=training_data.temperatures[test_indices],
            outdoor_temps=training_data.outdoor_temps[test_indices],
            heating_powers=training_data.heating_powers[test_indices],
            dt=training_data.dt,
        )

        # Train on training fold
        estimator = ParameterEstimator(dt=train_data.dt)

        for i in range(1, train_data.n_samples):
            estimator.update(
                T_measured=train_data.temperatures[i],
                T_outdoor=train_data.outdoor_temps[i - 1],
                P_heating=train_data.heating_powers[i - 1],
                T_previous=train_data.temperatures[i - 1],
            )

        params = estimator.get_thermal_parameters()
        if params is None:
            _LOGGER.warning("Fold %d: RLS failed to converge", fold)
            continue

        parameters_list.append(params)

        # Validate on test fold
        model = ThermalModel(params=params, dt=test_data.dt)

        # Predict on test data
        y_pred = model.predict(
            T_initial=test_data.temperatures[0],
            u_sequence=test_data.heating_powers[:-1],
            T_outdoor_sequence=test_data.outdoor_temps[:-1],
        )

        # Calculate metrics
        metrics = calculate_metrics(test_data.temperatures[1:], y_pred[1:])

        # Convert to ValidationMetrics
        val_metrics = ValidationMetrics(
            mae=metrics.mae,
            rmse=metrics.rmse,
            r_squared=metrics.r_squared,
            max_error=metrics.max_error,
            n_samples=metrics.n_samples,
            prediction_type="multi_step",
        )

        metrics_list.append(val_metrics)

        _LOGGER.info("Fold %d: RMSE=%.3f°C, R²=%.4f", fold, val_metrics.rmse, val_metrics.r_squared)

    # Calculate statistics
    rmse_values = [m.rmse for m in metrics_list]
    r2_values = [m.r_squared for m in metrics_list]
    R_values = [p.R for p in parameters_list]
    C_values = [p.C for p in parameters_list]

    statistics = {
        "mean_rmse": float(np.mean(rmse_values)),
        "std_rmse": float(np.std(rmse_values)),
        "mean_r2": float(np.mean(r2_values)),
        "std_r2": float(np.std(r2_values)),
        "mean_R": float(np.mean(R_values)),
        "std_R": float(np.std(R_values)),
        "mean_C": float(np.mean(C_values)),
        "std_C": float(np.std(C_values)),
        "n_folds": len(metrics_list),
    }

    _LOGGER.info(
        "Cross-validation complete: RMSE=%.3f±%.3f°C, R²=%.4f±%.4f",
        statistics["mean_rmse"],
        statistics["std_rmse"],
        statistics["mean_r2"],
        statistics["std_r2"],
    )

    return metrics_list, statistics
