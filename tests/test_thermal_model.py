"""Tests for thermal model (1R1C)."""

from __future__ import annotations

import numpy as np
import pytest

from custom_components.adaptive_thermal_control.thermal_model import (
    ThermalModel,
    ThermalModelParameters,
)


class TestThermalModelParameters:
    """Test ThermalModelParameters dataclass."""

    def test_default_parameters(self):
        """Test default parameter values."""
        params = ThermalModelParameters()
        assert params.R > 0
        assert params.C > 0
        assert params.time_constant > 0

    def test_time_constant_calculation(self):
        """Test time constant calculation."""
        params = ThermalModelParameters(R=0.002, C=5e6)
        assert params.time_constant == pytest.approx(0.002 * 5e6)
        assert params.time_constant == pytest.approx(10000.0)

    def test_validate_positive_parameters(self):
        """Test validation rejects non-positive parameters."""
        # Valid parameters
        params = ThermalModelParameters(R=0.001, C=1e6)
        assert params.validate() is True

        # Invalid R
        params_bad_r = ThermalModelParameters(R=-0.001, C=1e6)
        assert params_bad_r.validate() is False

        # Invalid C
        params_bad_c = ThermalModelParameters(R=0.001, C=-1e6)
        assert params_bad_c.validate() is False

        # Zero R
        params_zero_r = ThermalModelParameters(R=0.0, C=1e6)
        assert params_zero_r.validate() is False

    def test_validate_time_constant_range(self):
        """Test validation warns about unreasonable time constants."""
        # Time constant too short (< 1 hour = 3600s)
        params_short = ThermalModelParameters(R=0.0001, C=1e6)
        # Should still validate but log warning
        assert params_short.validate() is True
        assert params_short.time_constant < 3600

        # Time constant too long (> 12 hours = 43200s)
        params_long = ThermalModelParameters(R=0.01, C=5e6)
        # Should still validate but log warning
        assert params_long.validate() is True
        assert params_long.time_constant > 43200

    def test_to_dict(self):
        """Test parameter serialization."""
        params = ThermalModelParameters(R=0.002, C=4.5e6)
        params_dict = params.to_dict()

        assert params_dict["R"] == 0.002
        assert params_dict["C"] == 4.5e6
        assert params_dict["time_constant"] == pytest.approx(9000.0)


class TestThermalModel:
    """Test ThermalModel class."""

    @pytest.fixture
    def default_model(self):
        """Create model with default parameters."""
        return ThermalModel()

    @pytest.fixture
    def custom_model(self):
        """Create model with custom parameters."""
        params = ThermalModelParameters(R=0.002, C=4.5e6)  # τ = 9000s = 2.5h
        return ThermalModel(params=params, dt=600.0)

    def test_initialization(self, default_model):
        """Test model initialization."""
        assert default_model.params is not None
        assert default_model.dt == 600.0
        assert hasattr(default_model, "A")
        assert hasattr(default_model, "B")
        assert hasattr(default_model, "Bd")

    def test_invalid_parameters_raise_error(self):
        """Test that invalid parameters raise ValueError."""
        invalid_params = ThermalModelParameters(R=-0.001, C=1e6)
        with pytest.raises(ValueError, match="Invalid thermal model parameters"):
            ThermalModel(params=invalid_params)

    def test_matrix_calculation(self, custom_model):
        """Test discrete-time matrix calculation."""
        # For R=0.002, C=4.5e6, dt=600
        # τ = R*C = 9000s
        # A = exp(-dt/τ) = exp(-600/9000) = exp(-0.0667) ≈ 0.9355
        # B = R*(1-A) = 0.002*(1-0.9355) ≈ 0.000129
        # Bd = 1-A ≈ 0.0645

        assert custom_model.A == pytest.approx(0.9355, abs=0.001)
        assert custom_model.B == pytest.approx(0.000129, abs=0.00001)
        assert custom_model.Bd == pytest.approx(0.0645, abs=0.001)

    def test_steady_state_constant_outdoor_constant_heating(self, custom_model):
        """Test: constant outdoor temp + constant heating → reaches steady state.

        Criteria from T2.1.3:
        - Constant outdoor temperature
        - Constant heating power
        - Should reach steady state temperature
        """
        T_outdoor = 5.0  # °C
        u_heating = 2000.0  # W
        T_initial = 15.0  # °C

        # Expected steady state: T_ss = T_outdoor + R*u_heating
        # T_ss = 5 + 0.002*2000 = 5 + 4 = 9°C
        T_ss_expected = custom_model.steady_state_temperature(u_heating, T_outdoor)
        assert T_ss_expected == pytest.approx(9.0, abs=0.01)

        # Simulate for 10 time constants (should be > 99% settled)
        tau = custom_model.params.time_constant
        n_steps = int(10 * tau / custom_model.dt)

        T = T_initial
        for _ in range(n_steps):
            T = custom_model.simulate_step(T, u_heating, T_outdoor)

        # Should be very close to steady state (within 1% of settling)
        assert T == pytest.approx(T_ss_expected, abs=0.1)

    def test_step_response_exponential(self, custom_model):
        """Test: step in heating power → exponential response.

        Criteria from T2.1.3:
        - Step change in heating power
        - Response should be exponential
        - Time constant should match τ = R*C
        """
        T_outdoor = 10.0  # °C
        T_initial = 10.0  # Start at outdoor temp
        u_heating = 3000.0  # W (step input)

        # Expected final temperature
        T_ss = custom_model.steady_state_temperature(u_heating, T_outdoor)
        # T_ss = 10 + 0.002*3000 = 16°C

        # After 1 time constant, should reach 63.2% of final value
        tau = custom_model.params.time_constant
        n_steps_1tau = int(tau / custom_model.dt)

        T = T_initial
        for _ in range(n_steps_1tau):
            T = custom_model.simulate_step(T, u_heating, T_outdoor)

        # After 1τ: T ≈ T_initial + 0.632*(T_ss - T_initial)
        expected_1tau = T_initial + 0.632 * (T_ss - T_initial)
        assert T == pytest.approx(expected_1tau, abs=0.2)

        # After 3 time constants, should reach 95% of final value
        n_steps_3tau = int(3 * tau / custom_model.dt)
        T = T_initial
        for _ in range(n_steps_3tau):
            T = custom_model.simulate_step(T, u_heating, T_outdoor)

        expected_3tau = T_initial + 0.95 * (T_ss - T_initial)
        assert T == pytest.approx(expected_3tau, abs=0.3)

    def test_time_constant_matches_theory(self, custom_model):
        """Test: time constant τ = R*C matches theoretical value.

        Criteria from T2.1.3:
        - Verify τ = R*C
        - Verify settling time
        """
        R = custom_model.params.R
        C = custom_model.params.C
        tau_expected = R * C

        assert custom_model.params.time_constant == pytest.approx(tau_expected)
        assert tau_expected == pytest.approx(9000.0)  # 2.5 hours

    def test_24h_simulation_no_numerical_errors(self, custom_model):
        """Test: 24h simulation runs without numerical errors.

        Criteria from T2.1.3:
        - Simulate for 24 hours
        - No NaN, Inf, or numerical instability
        - Temperature stays in reasonable bounds
        """
        T_outdoor = 5.0  # °C
        u_heating = 2500.0  # W
        T_initial = 20.0  # °C

        # Simulate 24 hours
        n_steps = int(24 * 3600 / custom_model.dt)  # 24h / 600s = 144 steps

        temperatures = []
        T = T_initial
        for _ in range(n_steps):
            T = custom_model.simulate_step(T, u_heating, T_outdoor)
            temperatures.append(T)

            # Check for numerical issues
            assert not np.isnan(T), "Temperature became NaN"
            assert not np.isinf(T), "Temperature became infinite"
            assert -50 < T < 100, f"Temperature out of bounds: {T}°C"

        # Verify convergence to steady state
        T_ss = custom_model.steady_state_temperature(u_heating, T_outdoor)
        assert temperatures[-1] == pytest.approx(T_ss, abs=0.1)

    def test_predict_multi_step(self, custom_model):
        """Test multi-step prediction."""
        T_initial = 18.0
        N = 10

        u_sequence = np.full(N, 2000.0)  # Constant 2000W
        T_outdoor_sequence = np.full(N, 5.0)  # Constant 5°C

        T_pred = custom_model.predict(T_initial, u_sequence, T_outdoor_sequence)

        # Should return N+1 values (initial + N predictions)
        assert len(T_pred) == N + 1
        assert T_pred[0] == T_initial

        # Each step should be physically reasonable
        for i in range(1, len(T_pred)):
            assert not np.isnan(T_pred[i])
            assert not np.isinf(T_pred[i])
            assert -50 < T_pred[i] < 100

    def test_predict_with_disturbances(self, custom_model):
        """Test prediction with disturbance sequence."""
        T_initial = 20.0
        N = 5

        u_sequence = np.full(N, 1500.0)
        T_outdoor_sequence = np.full(N, 10.0)
        Q_disturbances_sequence = np.full(N, 500.0)  # Extra 500W (e.g., solar)

        T_pred = custom_model.predict(
            T_initial, u_sequence, T_outdoor_sequence, Q_disturbances_sequence
        )

        # With disturbances, final temp should be higher
        T_pred_no_dist = custom_model.predict(
            T_initial, u_sequence, T_outdoor_sequence
        )

        assert T_pred[-1] > T_pred_no_dist[-1]

    def test_predict_mismatched_lengths_raises_error(self, custom_model):
        """Test that mismatched input lengths raise ValueError."""
        T_initial = 20.0
        u_sequence = np.full(10, 2000.0)
        T_outdoor_sequence = np.full(5, 10.0)  # Wrong length!

        with pytest.raises(ValueError, match="must match"):
            custom_model.predict(T_initial, u_sequence, T_outdoor_sequence)

    def test_steady_state_temperature(self, custom_model):
        """Test steady-state temperature calculation."""
        u_heating = 2500.0
        T_outdoor = 8.0
        Q_disturbances = 300.0

        T_ss = custom_model.steady_state_temperature(
            u_heating, T_outdoor, Q_disturbances
        )

        # T_ss = T_outdoor + R*(u_heating + Q_disturbances)
        # T_ss = 8 + 0.002*(2500 + 300) = 8 + 5.6 = 13.6°C
        expected = 8.0 + 0.002 * (2500.0 + 300.0)
        assert T_ss == pytest.approx(expected, abs=0.01)

    def test_heating_power_for_target(self, custom_model):
        """Test calculation of required heating power."""
        T_target = 22.0
        T_outdoor = 5.0

        u_required = custom_model.heating_power_for_target(T_target, T_outdoor)

        # u = (T_target - T_outdoor) / R
        # u = (22 - 5) / 0.002 = 17 / 0.002 = 8500W
        expected = (22.0 - 5.0) / 0.002
        assert u_required == pytest.approx(expected, abs=0.1)

    def test_heating_power_for_target_never_negative(self, custom_model):
        """Test that heating power is clamped to >= 0."""
        T_target = 15.0
        T_outdoor = 25.0  # Outdoor warmer than target!

        u_required = custom_model.heating_power_for_target(T_target, T_outdoor)

        # Should return 0, not negative
        assert u_required == 0.0

    def test_set_parameters_updates_matrices(self, default_model):
        """Test that changing parameters updates matrices."""
        old_A = default_model.A

        new_params = ThermalModelParameters(R=0.003, C=3e6)
        default_model.set_parameters(new_params)

        assert default_model.params.R == 0.003
        assert default_model.params.C == 3e6
        assert default_model.A != old_A

    def test_get_state(self, custom_model):
        """Test state dictionary retrieval."""
        state = custom_model.get_state()

        assert "parameters" in state
        assert "dt" in state
        assert "matrices" in state

        assert state["parameters"]["R"] == 0.002
        assert state["parameters"]["C"] == 4.5e6
        assert state["dt"] == 600.0

        assert "A" in state["matrices"]
        assert "B" in state["matrices"]
        assert "Bd" in state["matrices"]

    def test_repr(self, custom_model):
        """Test string representation."""
        repr_str = repr(custom_model)

        assert "ThermalModel" in repr_str
        assert "R=0.002" in repr_str
        assert "C=4500000" in repr_str
        assert "dt=600" in repr_str


class TestThermalModelPhysics:
    """Test physical correctness of the model."""

    def test_no_heating_converges_to_outdoor(self):
        """With no heating, room should eventually reach outdoor temperature."""
        params = ThermalModelParameters(R=0.002, C=4e6)
        model = ThermalModel(params=params, dt=600.0)

        T_outdoor = 5.0
        T_initial = 20.0
        u_heating = 0.0  # No heating

        # Simulate for 10 time constants
        tau = params.time_constant
        n_steps = int(10 * tau / model.dt)

        T = T_initial
        for _ in range(n_steps):
            T = model.simulate_step(T, u_heating, T_outdoor)

        # Should converge to outdoor temperature
        assert T == pytest.approx(T_outdoor, abs=0.1)

    def test_higher_power_higher_temperature(self):
        """Higher heating power should result in higher steady-state temperature."""
        model = ThermalModel()
        T_outdoor = 10.0

        T_ss_low = model.steady_state_temperature(1000.0, T_outdoor)
        T_ss_high = model.steady_state_temperature(3000.0, T_outdoor)

        assert T_ss_high > T_ss_low

    def test_thermal_inertia(self):
        """Higher thermal capacity should slow down temperature changes."""
        # Low thermal capacity (fast response)
        params_low_c = ThermalModelParameters(R=0.002, C=2e6)
        model_low_c = ThermalModel(params=params_low_c, dt=600.0)

        # High thermal capacity (slow response)
        params_high_c = ThermalModelParameters(R=0.002, C=8e6)
        model_high_c = ThermalModel(params=params_high_c, dt=600.0)

        T_outdoor = 10.0
        T_initial = 10.0
        u_heating = 3000.0

        # Simulate 1 hour
        n_steps = int(3600 / 600)

        T_low = T_initial
        T_high = T_initial
        for _ in range(n_steps):
            T_low = model_low_c.simulate_step(T_low, u_heating, T_outdoor)
            T_high = model_high_c.simulate_step(T_high, u_heating, T_outdoor)

        # Low C should have changed more
        assert abs(T_low - T_initial) > abs(T_high - T_initial)

    def test_better_insulation_higher_temperature(self):
        """Better insulation (higher R) should result in higher steady-state temp."""
        # Poor insulation
        params_low_r = ThermalModelParameters(R=0.001, C=4e6)
        model_low_r = ThermalModel(params=params_low_r)

        # Good insulation
        params_high_r = ThermalModelParameters(R=0.004, C=4e6)
        model_high_r = ThermalModel(params=params_high_r)

        T_outdoor = 5.0
        u_heating = 2000.0

        T_ss_low_r = model_low_r.steady_state_temperature(u_heating, T_outdoor)
        T_ss_high_r = model_high_r.steady_state_temperature(u_heating, T_outdoor)

        # Better insulation → higher temperature for same heating power
        assert T_ss_high_r > T_ss_low_r
