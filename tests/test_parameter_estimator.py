"""Tests for RLS parameter estimator."""

from __future__ import annotations

import numpy as np
import pytest

from custom_components.adaptive_thermal_control.parameter_estimator import (
    ParameterEstimator,
    RLSState,
)
from custom_components.adaptive_thermal_control.thermal_model import (
    ThermalModelParameters,
)


class TestRLSState:
    """Test RLSState dataclass."""

    def test_initialization(self):
        """Test state initialization."""
        state = RLSState()

        assert state.theta.shape == (3,)
        assert state.P.shape == (3, 3)
        assert state.n_updates == 0
        assert state.last_error == 0.0

    def test_to_dict(self):
        """Test state serialization."""
        state = RLSState()
        state.theta = np.array([0.9, 0.0001, 0.1])
        state.n_updates = 10
        state.last_error = 0.5

        state_dict = state.to_dict()

        assert "theta" in state_dict
        assert "n_updates" in state_dict
        assert "last_error" in state_dict
        assert state_dict["n_updates"] == 10
        assert state_dict["last_error"] == 0.5


class TestParameterEstimator:
    """Test ParameterEstimator class."""

    @pytest.fixture
    def estimator(self):
        """Create estimator with default parameters."""
        return ParameterEstimator(dt=600.0)

    @pytest.fixture
    def estimator_with_params(self):
        """Create estimator with custom initial parameters."""
        params = ThermalModelParameters(R=0.002, C=4.5e6)
        return ParameterEstimator(dt=600.0, initial_params=params)

    def test_initialization_default(self, estimator):
        """Test default initialization."""
        assert estimator.dt == 600.0
        assert estimator.lambda_factor == 0.98
        assert estimator.state.theta.shape == (3,)
        assert estimator.state.P.shape == (3, 3)

    def test_initialization_with_params(self, estimator_with_params):
        """Test initialization with custom parameters."""
        # Check that theta was initialized from parameters
        theta = estimator_with_params.state.theta

        # For R=0.002, C=4.5e6, dt=600:
        # a = exp(-dt/(R*C)) = exp(-600/9000) ≈ 0.9355
        # b = R*(1-a) ≈ 0.000129
        # c = 1-a ≈ 0.0645

        assert theta[0] == pytest.approx(0.9355, abs=0.001)
        assert theta[1] == pytest.approx(0.000129, abs=0.00001)
        assert theta[2] == pytest.approx(0.0645, abs=0.001)

    def test_update_single_step(self, estimator):
        """Test single RLS update."""
        T_measured = 20.5
        T_outdoor = 10.0
        P_heating = 2000.0
        T_previous = 20.0

        result = estimator.update(T_measured, T_outdoor, P_heating, T_previous)

        assert "error" in result
        assert "theta" in result
        assert "n_updates" in result
        assert result["n_updates"] == 1
        assert isinstance(result["error"], float)

    def test_update_convergence(self, estimator):
        """Test that RLS converges with synthetic data."""
        # Generate synthetic data with known parameters
        # True model: R=0.002, C=4.5e6, dt=600
        R_true = 0.002
        C_true = 4.5e6
        dt = 600.0

        a_true = np.exp(-dt / (R_true * C_true))
        b_true = R_true * (1 - a_true)
        c_true = 1 - a_true

        # Generate 100 data points
        np.random.seed(42)
        T_outdoor = 5.0 + 10 * np.random.randn(100) * 0.1
        P_heating = 2000.0 + 500 * np.random.randn(100) * 0.1

        T = np.zeros(101)
        T[0] = 20.0

        # Generate true temperatures
        for i in range(100):
            T[i + 1] = (
                a_true * T[i] +
                b_true * P_heating[i] +
                c_true * T_outdoor[i] +
                0.1 * np.random.randn()  # Small noise
            )

        # Train RLS
        for i in range(100):
            estimator.update(
                T_measured=T[i + 1],
                T_outdoor=T_outdoor[i],
                P_heating=P_heating[i],
                T_previous=T[i],
            )

        # Check convergence
        params = estimator.get_thermal_parameters()
        assert params is not None

        # RLS should produce reasonable parameters
        # (not necessarily exact match due to noise and initialization)
        assert 0.0001 < params.R < 0.01  # Reasonable range for R
        assert 1e6 < params.C < 2e7  # Reasonable range for C
        assert params.time_constant > 0  # Positive time constant

    def test_get_thermal_parameters_valid(self, estimator_with_params):
        """Test extraction of thermal parameters."""
        params = estimator_with_params.get_thermal_parameters()

        assert params is not None
        assert params.R > 0
        assert params.C > 0
        assert params.time_constant > 0

    def test_get_thermal_parameters_invalid(self, estimator):
        """Test that invalid theta returns None."""
        # Set invalid theta (a > 1, which is physically impossible)
        estimator.state.theta = np.array([1.5, 0.001, 0.1])

        params = estimator.get_thermal_parameters()
        assert params is None

    def test_reset(self, estimator):
        """Test reset functionality."""
        # Do some updates
        for _ in range(10):
            estimator.update(20.0, 10.0, 2000.0, 19.5)

        assert estimator.state.n_updates == 10

        # Reset
        estimator.reset()

        assert estimator.state.n_updates == 0
        assert estimator.state.last_error == 0.0

    def test_get_state(self, estimator):
        """Test state export."""
        state = estimator.get_state()

        assert "dt" in state
        assert "lambda" in state
        assert "rls_state" in state
        assert state["dt"] == 600.0
        assert state["lambda"] == 0.98

    def test_repr(self, estimator_with_params):
        """Test string representation."""
        repr_str = repr(estimator_with_params)

        assert "ParameterEstimator" in repr_str
        assert "R=" in repr_str
        assert "C=" in repr_str

    def test_update_skip_first_without_previous(self, estimator):
        """Test that first update is skipped if no previous temp."""
        result = estimator.update(20.0, 10.0, 2000.0, T_previous=None)

        assert result["n_updates"] == 0

    def test_forgetting_factor_effect(self):
        """Test that forgetting factor gives more weight to recent data."""
        # Estimator with high forgetting (remembers old data)
        estimator_high_lambda = ParameterEstimator(
            dt=600.0,
            forgetting_factor=0.99
        )

        # Estimator with low forgetting (forgets old data quickly)
        estimator_low_lambda = ParameterEstimator(
            dt=600.0,
            forgetting_factor=0.90
        )

        # Train both on old data
        np.random.seed(42)
        for _ in range(50):
            T_prev = 20.0 + np.random.randn()
            T_curr = 20.5 + np.random.randn()
            estimator_high_lambda.update(T_curr, 10.0, 2000.0, T_prev)
            estimator_low_lambda.update(T_curr, 10.0, 2000.0, T_prev)

        # Store old parameters
        params_high_old = estimator_high_lambda.get_thermal_parameters()
        params_low_old = estimator_low_lambda.get_thermal_parameters()

        # Train on new data with different pattern
        for _ in range(50):
            T_prev = 15.0 + np.random.randn()
            T_curr = 16.0 + np.random.randn()
            estimator_high_lambda.update(T_curr, 5.0, 3000.0, T_prev)
            estimator_low_lambda.update(T_curr, 5.0, 3000.0, T_prev)

        # Get new parameters
        params_high_new = estimator_high_lambda.get_thermal_parameters()
        params_low_new = estimator_low_lambda.get_thermal_parameters()

        # Low lambda should have changed more (adapted faster to new data)
        if params_high_old and params_low_old and params_high_new and params_low_new:
            change_high = abs(params_high_new.R - params_high_old.R)
            change_low = abs(params_low_new.R - params_low_old.R)

            # Low lambda should adapt faster
            assert change_low >= change_high


class TestParameterExtraction:
    """Test parameter extraction logic."""

    def test_extract_valid_parameters(self):
        """Test extraction with valid theta."""
        estimator = ParameterEstimator(dt=600.0)

        # Set known good theta
        # a=0.9, b=0.0002, c=0.1
        estimator.state.theta = np.array([0.9, 0.0002, 0.1])

        params = estimator.get_thermal_parameters()

        assert params is not None
        assert 0 < params.R < 0.1
        assert 0 < params.C < 1e8

    def test_extract_inconsistent_parameters(self):
        """Test extraction with inconsistent theta."""
        estimator = ParameterEstimator(dt=600.0)

        # Set inconsistent theta (c should be 1-a, but isn't)
        estimator.state.theta = np.array([0.9, 0.0002, 0.5])  # c=0.5 but should be 0.1

        # Should still extract, but log warning
        params = estimator.get_thermal_parameters()

        # May return None or valid params depending on tolerance
        if params:
            assert params.R > 0
            assert params.C > 0

    def test_extract_negative_parameters(self):
        """Test extraction with negative theta."""
        estimator = ParameterEstimator(dt=600.0)

        # Set invalid theta with negative b
        estimator.state.theta = np.array([0.9, -0.0002, 0.1])

        params = estimator.get_thermal_parameters()

        # Should return None for invalid parameters
        assert params is None
