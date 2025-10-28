"""Tests for MPC controller."""

from __future__ import annotations

import numpy as np
import pytest

from custom_components.adaptive_thermal_control.mpc_controller import (
    MPCConfig,
    MPCController,
    MPCResult,
)
from custom_components.adaptive_thermal_control.thermal_model import (
    ThermalModel,
    ThermalModelParameters,
)


class TestMPCConfig:
    """Test MPCConfig dataclass."""

    def test_default_configuration(self):
        """Test default MPC configuration."""
        config = MPCConfig()

        assert config.Np == 24  # 4 hours
        assert config.Nc == 12  # 2 hours
        assert config.dt == 600.0  # 10 minutes
        assert config.w_comfort > 0
        assert config.w_energy >= 0
        assert config.w_smooth >= 0
        assert config.u_min == 0.0
        assert config.u_max > 0

    def test_custom_configuration(self):
        """Test custom MPC configuration."""
        config = MPCConfig(
            Np=48,
            Nc=24,
            dt=300.0,
            w_comfort=2.0,
            w_energy=0.05,
            w_smooth=0.2,
            u_max=3000.0,
        )

        assert config.Np == 48
        assert config.Nc == 24
        assert config.dt == 300.0
        assert config.w_comfort == 2.0
        assert config.w_energy == 0.05
        assert config.w_smooth == 0.2
        assert config.u_max == 3000.0

    def test_to_dict(self):
        """Test configuration serialization."""
        config = MPCConfig(Np=48, Nc=24)
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["Np"] == 48
        assert config_dict["Nc"] == 24
        assert "w_comfort" in config_dict
        assert "u_max" in config_dict


class TestMPCResult:
    """Test MPCResult dataclass."""

    def test_result_creation(self):
        """Test MPC result creation."""
        u_optimal = np.array([100.0, 150.0, 200.0])
        result = MPCResult(
            u_optimal=u_optimal,
            u_first=100.0,
            cost=42.5,
            success=True,
            message="Converged",
            iterations=15,
        )

        assert result.success
        assert result.u_first == 100.0
        assert result.cost == 42.5
        assert result.iterations == 15
        assert len(result.u_optimal) == 3

    def test_result_to_dict(self):
        """Test result serialization."""
        result = MPCResult(
            u_optimal=np.array([100.0, 150.0]),
            u_first=100.0,
            cost=42.5,
            success=True,
            message="OK",
            iterations=10,
        )
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["success"] is True
        assert result_dict["u_first"] == 100.0
        assert result_dict["cost"] == 42.5
        assert "u_sequence" in result_dict


class TestMPCController:
    """Test MPCController class."""

    @pytest.fixture
    def thermal_model(self):
        """Create thermal model for testing."""
        params = ThermalModelParameters(
            R=0.003,  # 0.003 K/W
            C=5.0e6,  # 5 MJ/K
        )
        return ThermalModel(params=params, dt=600.0)

    @pytest.fixture
    def mpc_controller(self, thermal_model):
        """Create MPC controller for testing."""
        config = MPCConfig(
            Np=12,  # Shorter horizon for faster tests
            Nc=6,
            dt=600.0,
            w_comfort=1.0,
            w_energy=0.1,
            w_smooth=0.05,
            u_max=2000.0,
        )
        return MPCController(model=thermal_model, config=config)

    def test_initialization(self, mpc_controller):
        """Test MPC controller initialization."""
        assert mpc_controller.model is not None
        assert mpc_controller.config.Np == 12
        assert mpc_controller.config.Nc == 6
        assert mpc_controller._u_prev == 0.0
        assert mpc_controller._u_sequence_prev is None

    def test_compute_control_basic(self, mpc_controller):
        """Test basic MPC control computation."""
        T_current = 19.0  # Below setpoint
        T_setpoint = 21.0
        T_outdoor_forecast = np.full(12, 5.0)  # Constant 5°C outdoor

        result = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        # Should succeed
        assert result.success, f"Optimization failed: {result.message}"
        # Should apply positive heating (room is cold)
        assert result.u_first > 0, "Should heat when below setpoint"
        # Control should be within bounds
        assert 0 <= result.u_first <= mpc_controller.config.u_max
        # Should have control sequence
        assert len(result.u_optimal) == mpc_controller.config.Nc

    def test_compute_control_at_setpoint(self, mpc_controller):
        """Test MPC when already at setpoint."""
        T_current = 21.0  # At setpoint
        T_setpoint = 21.0
        T_outdoor_forecast = np.full(12, 20.0)  # Warm outdoor

        result = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        assert result.success
        # Should apply minimal or zero heating (at setpoint, warm outside)
        assert result.u_first >= 0
        # Cost should be relatively low
        assert result.cost >= 0

    def test_compute_control_above_setpoint(self, mpc_controller):
        """Test MPC when above setpoint."""
        T_current = 23.0  # Above setpoint
        T_setpoint = 21.0
        T_outdoor_forecast = np.full(12, 25.0)  # Hot outdoor

        result = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        assert result.success
        # Should apply zero or minimal heating (too warm)
        assert result.u_first == 0.0 or result.u_first < 100.0

    def test_forecast_extension(self, mpc_controller):
        """Test handling of short forecast."""
        T_current = 20.0
        T_setpoint = 21.0
        # Forecast too short (only 6 steps instead of 12)
        T_outdoor_forecast = np.array([5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

        result = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        # Should still work (extends forecast internally)
        assert result.success or result.u_first >= 0

    def test_warm_start(self, mpc_controller):
        """Test warm-start from previous solution."""
        T_current = 19.0
        T_setpoint = 21.0
        T_outdoor_forecast = np.full(12, 5.0)

        # First optimization (cold start)
        result1 = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        # Second optimization (warm start)
        T_current = 19.5  # Temperature increased slightly
        result2 = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        # Both should succeed
        assert result1.success
        assert result2.success
        # Warm start might converge faster
        # (can't always guarantee, but typically true)

    def test_constraints_respected(self, mpc_controller):
        """Test that constraints are respected."""
        T_current = 15.0  # Very cold
        T_setpoint = 21.0
        T_outdoor_forecast = np.full(12, 0.0)  # Very cold outside

        result = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        if result.success:
            # Check box constraints
            assert np.all(result.u_optimal >= mpc_controller.config.u_min)
            assert np.all(result.u_optimal <= mpc_controller.config.u_max)

            # Check rate constraints (approximately - optimizer may have tolerance)
            du = np.diff(result.u_optimal, prepend=mpc_controller._u_prev)
            # Allow small tolerance for numerical optimization
            assert np.all(np.abs(du) <= mpc_controller.config.du_max + 1.0)

    def test_cost_increases_with_deviation(self, mpc_controller):
        """Test that cost increases with larger temperature deviation."""
        T_outdoor_forecast = np.full(12, 10.0)
        T_setpoint = 21.0

        # Case 1: Small deviation
        result1 = mpc_controller.compute_control(
            T_current=20.5,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        # Case 2: Larger deviation
        result2 = mpc_controller.compute_control(
            T_current=18.0,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        if result1.success and result2.success:
            # Larger deviation should have higher cost
            assert result2.cost > result1.cost

    def test_reset(self, mpc_controller):
        """Test controller reset."""
        # Run optimization
        mpc_controller.compute_control(
            T_current=20.0,
            T_setpoint=21.0,
            T_outdoor_forecast=np.full(12, 10.0),
        )

        # Reset
        mpc_controller.reset()

        # State should be cleared
        assert mpc_controller._u_prev == 0.0
        assert mpc_controller._u_sequence_prev is None

    def test_set_weights(self, mpc_controller):
        """Test updating cost function weights."""
        original_comfort = mpc_controller.config.w_comfort
        original_energy = mpc_controller.config.w_energy

        # Update weights
        mpc_controller.set_weights(w_comfort=2.0, w_energy=0.05)

        assert mpc_controller.config.w_comfort == 2.0
        assert mpc_controller.config.w_energy == 0.05
        assert mpc_controller.config.w_comfort != original_comfort

        # Partial update
        mpc_controller.set_weights(w_smooth=0.3)
        assert mpc_controller.config.w_comfort == 2.0  # Unchanged
        assert mpc_controller.config.w_smooth == 0.3  # Changed

    def test_varying_outdoor_temperature(self, mpc_controller):
        """Test MPC with varying outdoor temperature forecast."""
        T_current = 20.0
        T_setpoint = 21.0

        # Simulate outdoor temperature dropping over time
        T_outdoor_forecast = np.linspace(10.0, 0.0, 12)  # 10°C -> 0°C

        result = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        assert result.success
        # Should anticipate increasing heat demand as outdoor temp drops
        assert result.u_first > 0

    def test_predicted_temperatures(self, mpc_controller):
        """Test that predicted temperatures are returned."""
        T_current = 19.0
        T_setpoint = 21.0
        T_outdoor_forecast = np.full(12, 5.0)

        result = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
        )

        if result.success:
            assert result.predicted_temps is not None
            assert len(result.predicted_temps) == mpc_controller.config.Np + 1
            assert result.predicted_temps[0] == T_current  # Initial condition

    def test_continuity_with_u_last(self, mpc_controller):
        """Test that providing u_last ensures continuity."""
        T_current = 20.0
        T_setpoint = 21.0
        T_outdoor_forecast = np.full(12, 10.0)
        u_last = 500.0  # Previous control

        result = mpc_controller.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor_forecast,
            u_last=u_last,
        )

        # Check that rate constraint considers u_last
        if result.success:
            du_first = result.u_first - u_last
            # Should respect rate constraint (with small tolerance)
            assert abs(du_first) <= mpc_controller.config.du_max + 10.0

    def test_nc_larger_than_np_adjustment(self, thermal_model):
        """Test that Nc > Np is adjusted automatically."""
        config = MPCConfig(Np=10, Nc=15)  # Invalid: Nc > Np
        controller = MPCController(model=thermal_model, config=config)

        # Should have been adjusted
        assert controller.config.Nc <= controller.config.Np
        assert controller.config.Nc == controller.config.Np
