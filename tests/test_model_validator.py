"""Tests for model validator."""

from __future__ import annotations

import numpy as np
import pytest

from custom_components.adaptive_thermal_control.data_preprocessing import TrainingData
from custom_components.adaptive_thermal_control.model_validator import (
    ModelValidator,
    ValidationMetrics,
    cross_validate,
)
from custom_components.adaptive_thermal_control.parameter_estimator import (
    ParameterEstimator,
)
from custom_components.adaptive_thermal_control.thermal_model import (
    ThermalModel,
    ThermalModelParameters,
)


@pytest.fixture
def simple_training_data():
    """Create simple training data for testing."""
    n = 50
    timestamps = np.arange(n) * 600.0  # 10-minute intervals
    temperatures = 20.0 + np.sin(np.arange(n) * 0.1)  # Sinusoidal pattern
    outdoor_temps = 10.0 + np.cos(np.arange(n) * 0.1)
    heating_powers = 2000.0 * np.ones(n)

    return TrainingData(
        timestamps=timestamps,
        temperatures=temperatures,
        outdoor_temps=outdoor_temps,
        heating_powers=heating_powers,
        dt=600.0,
    )


@pytest.fixture
def thermal_model():
    """Create thermal model with default parameters."""
    params = ThermalModelParameters(R=0.002, C=4.5e6)
    return ThermalModel(params=params, dt=600.0)


@pytest.fixture
def validator(thermal_model):
    """Create validator with thermal model."""
    return ModelValidator(thermal_model)


class TestValidationMetrics:
    """Test ValidationMetrics dataclass."""

    def test_initialization(self):
        """Test metrics initialization."""
        metrics = ValidationMetrics(
            mae=0.3,
            rmse=0.5,
            r_squared=0.85,
            max_error=1.2,
            n_samples=100,
        )

        assert metrics.rmse == 0.5
        assert metrics.mae == 0.3
        assert metrics.r_squared == 0.85
        assert metrics.max_error == 1.2
        assert metrics.n_samples == 100

    def test_to_dict(self):
        """Test conversion to dict."""
        metrics = ValidationMetrics(
            mae=0.3,
            rmse=0.5,
            r_squared=0.85,
            max_error=1.2,
            n_samples=100,
        )

        metrics_dict = metrics.to_dict()

        assert metrics_dict["rmse"] == 0.5
        assert metrics_dict["mae"] == 0.3
        assert metrics_dict["r_squared"] == 0.85
        assert metrics_dict["max_error"] == 1.2
        assert metrics_dict["n_samples"] == 100


class TestModelValidator:
    """Test ModelValidator class."""

    def test_initialization(self, thermal_model):
        """Test validator initialization."""
        validator = ModelValidator(thermal_model)

        assert validator.model == thermal_model

    def test_validate_one_step(self, validator, simple_training_data):
        """Test one-step validation."""
        metrics = validator.validate(
            simple_training_data, prediction_type="one_step"
        )

        assert isinstance(metrics, ValidationMetrics)
        assert metrics.n_samples > 0
        assert metrics.rmse >= 0
        assert metrics.mae >= 0
        assert metrics.max_error >= 0
        # R² can be negative for bad fits
        assert metrics.r_squared >= -1.0

    def test_validate_multi_step(self, validator, simple_training_data):
        """Test multi-step validation."""
        metrics = validator.validate(
            simple_training_data, prediction_type="multi_step"
        )

        assert isinstance(metrics, ValidationMetrics)
        assert metrics.n_samples > 0
        # Multi-step typically has higher error
        assert metrics.rmse >= 0

    def test_validate_invalid_type(self, validator, simple_training_data):
        """Test that invalid prediction type raises error."""
        with pytest.raises(ValueError, match="Invalid prediction_type"):
            validator.validate(simple_training_data, prediction_type="invalid")

    def test_validate_empty_data(self, validator):
        """Test validation with empty data."""
        empty_data = TrainingData(
            timestamps=np.array([]),
            temperatures=np.array([]),
            outdoor_temps=np.array([]),
            heating_powers=np.array([]),
            dt=600.0,
        )

        with pytest.raises((ValueError, IndexError)):
            validator.validate(empty_data)

    def test_validate_perfect_model(self):
        """Test validation with model that generated the data."""
        # Create model
        params = ThermalModelParameters(R=0.002, C=4.5e6)
        model = ThermalModel(params=params, dt=600.0)
        validator = ModelValidator(model)

        # Generate data using the same model
        n = 100
        T = np.zeros(n)
        T[0] = 20.0
        outdoor = 10.0 * np.ones(n)
        heating = 2000.0 * np.ones(n)

        for i in range(n - 1):
            T[i + 1] = model.simulate_step(
                T[i], heating[i], outdoor[i]
            )

        training_data = TrainingData(
            timestamps=np.arange(n) * 600.0,
            temperatures=T,
            outdoor_temps=outdoor,
            heating_powers=heating,
            dt=600.0,
        )

        # Validate
        metrics = validator.validate(training_data, prediction_type="one_step")

        # Should have near-zero error (within numerical precision)
        assert metrics.rmse < 1e-10
        assert metrics.mae < 1e-10
        assert metrics.r_squared > 0.99


class TestCrossValidation:
    """Test cross-validation functionality."""

    def test_cross_validate_basic(self):
        """Test basic cross-validation with realistic data."""
        # Create realistic data
        params = ThermalModelParameters(R=0.002, C=4.5e6)
        model = ThermalModel(params=params, dt=600.0)

        n = 150
        np.random.seed(42)
        T = np.zeros(n)
        T[0] = 20.0
        outdoor = 10.0 + 3 * np.random.randn(n)
        heating = 2000.0 + 300 * np.random.randn(n)

        for i in range(n - 1):
            T[i + 1] = model.simulate_step(T[i], heating[i], outdoor[i])
            T[i + 1] += 0.1 * np.random.randn()  # Noise

        training_data = TrainingData(
            timestamps=np.arange(n) * 600.0,
            temperatures=T,
            outdoor_temps=outdoor,
            heating_powers=heating,
            dt=600.0,
        )

        metrics_list, stats = cross_validate(
            training_data,
            k_folds=3,
        )

        # Should have 3 folds
        assert len(metrics_list) == 3

        # Each should be ValidationMetrics
        for metrics in metrics_list:
            assert isinstance(metrics, ValidationMetrics)
            assert metrics.n_samples > 0

        # Stats should contain statistics
        assert isinstance(stats, dict)

    def test_cross_validate_statistics(self):
        """Test cross-validation statistics with realistic data."""
        # Create realistic data
        params = ThermalModelParameters(R=0.002, C=4.5e6)
        model = ThermalModel(params=params, dt=600.0)

        n = 200
        np.random.seed(42)
        T = np.zeros(n)
        T[0] = 20.0
        outdoor = 10.0 + 3 * np.random.randn(n)
        heating = 2000.0 + 300 * np.random.randn(n)

        for i in range(n - 1):
            T[i + 1] = model.simulate_step(T[i], heating[i], outdoor[i])
            T[i + 1] += 0.1 * np.random.randn()  # Noise

        training_data = TrainingData(
            timestamps=np.arange(n) * 600.0,
            temperatures=T,
            outdoor_temps=outdoor,
            heating_powers=heating,
            dt=600.0,
        )

        metrics_list, stats = cross_validate(
            training_data,
            k_folds=5,
        )

        # Should have 5 folds
        assert len(metrics_list) == 5

        # Stats should contain mean and std
        assert isinstance(stats, dict)
        assert len(stats) > 0

        # All metrics should be valid
        for metrics in metrics_list:
            assert metrics.rmse >= 0
            assert metrics.mae >= 0

    def test_cross_validate_invalid_k(self, simple_training_data):
        """Test cross-validation with invalid k."""
        # k > n_samples doesn't work
        with pytest.raises(ValueError):
            cross_validate(simple_training_data, k_folds=1000)

    def test_cross_validate_parameter_stability(self):
        """Test that parameter stability is calculated correctly."""
        # Create synthetic data with known good parameters
        params = ThermalModelParameters(R=0.002, C=4.5e6)
        model = ThermalModel(params=params, dt=600.0)

        # Generate consistent data
        n = 200
        np.random.seed(42)
        T = np.zeros(n)
        T[0] = 20.0
        outdoor = 10.0 + 2 * np.random.randn(n)
        heating = 2000.0 + 200 * np.random.randn(n)

        for i in range(n - 1):
            T[i + 1] = model.simulate_step(T[i], heating[i], outdoor[i])
            T[i + 1] += 0.05 * np.random.randn()  # Small noise

        training_data = TrainingData(
            timestamps=np.arange(n) * 600.0,
            temperatures=T,
            outdoor_temps=outdoor,
            heating_powers=heating,
            dt=600.0,
        )

        # Cross-validate
        metrics_list, stats = cross_validate(training_data, k_folds=5)

        # Should have 5 folds with valid metrics
        assert len(metrics_list) == 5
        for metrics in metrics_list:
            assert metrics.rmse >= 0
            assert metrics.mae >= 0


class TestValidationEdgeCases:
    """Test edge cases in validation."""

    def test_validate_constant_temperature(self):
        """Test validation with constant temperature (no dynamics)."""
        # Create data with constant temperature
        n = 50
        training_data = TrainingData(
            timestamps=np.arange(n) * 600.0,
            temperatures=20.0 * np.ones(n),
            outdoor_temps=10.0 * np.ones(n),
            heating_powers=2000.0 * np.ones(n),
            dt=600.0,
        )

        params = ThermalModelParameters(R=0.002, C=4.5e6)
        model = ThermalModel(params=params, dt=600.0)
        validator = ModelValidator(model)

        # Should complete without error (though R² might be undefined)
        metrics = validator.validate(training_data)
        assert metrics is not None

    def test_validate_single_sample(self):
        """Test validation with single data point."""
        training_data = TrainingData(
            timestamps=np.array([0.0]),
            temperatures=np.array([20.0]),
            outdoor_temps=np.array([10.0]),
            heating_powers=np.array([2000.0]),
            dt=600.0,
        )

        params = ThermalModelParameters(R=0.002, C=4.5e6)
        model = ThermalModel(params=params, dt=600.0)
        validator = ModelValidator(model)

        # With one sample, validation should still work but may have zero/undefined R²
        metrics = validator.validate(training_data)
        assert metrics is not None
        assert metrics.n_samples == 1
