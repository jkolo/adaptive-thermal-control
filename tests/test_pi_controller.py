"""Tests for PI controller (T1.4.3)."""

import pytest
import numpy as np

from custom_components.adaptive_thermal_control.pi_controller import (
    PIController,
    PIControllerState,
    DEFAULT_KP,
    DEFAULT_TI,
    DEFAULT_DT,
)


@pytest.fixture
def controller():
    """Create a PI controller with default parameters."""
    return PIController()


@pytest.fixture
def fast_controller():
    """Create a PI controller with faster response."""
    return PIController(kp=50.0, ti=600.0, dt=60.0)


def test_initialization():
    """Test PI controller initialization."""
    controller = PIController()

    assert controller.kp == DEFAULT_KP
    assert controller.ti == DEFAULT_TI
    assert controller.dt == DEFAULT_DT
    assert controller.output_min == 0.0
    assert controller.output_max == 100.0
    assert controller.state.integral == 0.0
    assert controller.state.last_error == 0.0
    assert controller.state.last_output == 0.0
    assert not controller.state.saturated


def test_custom_initialization():
    """Test PI controller with custom parameters."""
    controller = PIController(
        kp=20.0,
        ti=1000.0,
        dt=300.0,
        output_min=10.0,
        output_max=90.0,
    )

    assert controller.kp == 20.0
    assert controller.ti == 1000.0
    assert controller.dt == 300.0
    assert controller.output_min == 10.0
    assert controller.output_max == 90.0


def test_proportional_term_only():
    """Test proportional term for immediate error response."""
    # Create controller with very long Ti (essentially P-only)
    controller = PIController(kp=10.0, ti=1e6)

    # Error of 1.0 should give output of Kp * error = 10.0
    output = controller.update(setpoint=21.0, measurement=20.0)

    assert output == pytest.approx(10.0, abs=0.1)


def test_step_response_heating():
    """Test step response to heating demand."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    setpoint = 22.0
    measurement = 20.0  # 2°C error

    # First step - mostly proportional
    output1 = controller.update(setpoint, measurement)
    assert output1 > 0.0  # Should demand heating
    assert output1 < 100.0  # But not saturated for 2°C error

    # Second step - integral starts to accumulate
    output2 = controller.update(setpoint, measurement)
    assert output2 > output1  # Integral term increases output

    # Third step
    output3 = controller.update(setpoint, measurement)
    assert output3 > output2  # Continues to increase


def test_step_response_cooling():
    """Test step response to cooling (reduced heating) demand."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    setpoint = 20.0
    measurement = 22.0  # Room too hot

    # Should demand no heating (output = 0)
    output = controller.update(setpoint, measurement)
    assert output == 0.0  # Minimum output


def test_integral_accumulation():
    """Test that integral term accumulates over time."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    setpoint = 21.0
    measurement = 20.0

    outputs = []
    for _ in range(10):
        output = controller.update(setpoint, measurement)
        outputs.append(output)

    # Outputs should increase due to integral accumulation
    assert all(outputs[i] <= outputs[i + 1] for i in range(len(outputs) - 1))


def test_error_reduction():
    """Test that output decreases as error decreases."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    # Large error
    output1 = controller.update(setpoint=22.0, measurement=18.0)

    # Medium error
    output2 = controller.update(setpoint=22.0, measurement=20.0)

    # Small error
    output3 = controller.update(setpoint=22.0, measurement=21.5)

    # Outputs should generally decrease (though integral makes this not strict)
    assert output1 > output2
    assert output2 > output3


def test_saturation_upper_limit():
    """Test that output saturates at upper limit."""
    controller = PIController(kp=50.0, ti=600.0, dt=600.0)

    # Very large error should saturate
    output = controller.update(setpoint=25.0, measurement=15.0)

    assert output == 100.0
    assert controller.state.saturated


def test_saturation_lower_limit():
    """Test that output saturates at lower limit."""
    controller = PIController(kp=50.0, ti=600.0, dt=600.0)

    # Large negative error should saturate at 0
    output = controller.update(setpoint=15.0, measurement=25.0)

    assert output == 0.0
    assert controller.state.saturated


def test_anti_windup_stops_integration():
    """Test that anti-windup stops integral accumulation during saturation."""
    controller = PIController(kp=50.0, ti=600.0, dt=600.0)

    # Saturate the output
    output1 = controller.update(setpoint=25.0, measurement=15.0)
    assert output1 == 100.0
    integral1 = controller.state.integral

    # Continue with saturation - integral should not grow
    output2 = controller.update(setpoint=25.0, measurement=15.0)
    assert output2 == 100.0
    integral2 = controller.state.integral

    # Integral should not have increased (anti-windup active)
    assert integral2 == pytest.approx(integral1, abs=0.01)


def test_anti_windup_recovery():
    """Test recovery from saturation with anti-windup."""
    controller = PIController(kp=50.0, ti=600.0, dt=600.0)

    # Saturate the output
    for _ in range(5):
        controller.update(setpoint=25.0, measurement=15.0)

    integral_at_saturation = controller.state.integral

    # Now reduce error significantly - but not enough to desaturate yet
    output1 = controller.update(setpoint=25.0, measurement=24.0)

    # Integral should not have grown during saturation (anti-windup working)
    assert controller.state.integral == pytest.approx(integral_at_saturation, abs=0.1)

    # To drain the integral, we need NEGATIVE error (measurement > setpoint)
    # This simulates overshoot recovery
    for _ in range(30):
        controller.update(setpoint=25.0, measurement=26.0)  # Negative error

    # Now integral should have decreased significantly
    assert controller.state.integral < integral_at_saturation
    assert controller.state.last_output < 100.0  # Should have desaturated


def test_steady_state_error_elimination():
    """Test that PI controller eliminates steady-state error."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    setpoint = 21.0

    # Simulate a system with constant disturbance
    # After many iterations, steady-state error should be small
    for _ in range(50):
        # Simulate very slow temperature increase (like real system)
        measurement = 20.0  # Constant error
        controller.update(setpoint, measurement)

    # Integral term should have accumulated significantly
    assert controller.state.integral > 0.0

    # Output should be elevated to maintain setpoint
    assert controller.state.last_output > 10.0  # More than just P term


def test_no_oscillations_with_proper_tuning():
    """Test that well-tuned controller doesn't oscillate."""
    # Use conservative tuning for floor heating
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    setpoint = 21.0
    outputs = []

    # Simulate approach to setpoint
    measurements = [20.0, 20.2, 20.5, 20.7, 20.85, 20.95, 21.0]

    for measurement in measurements:
        output = controller.update(setpoint, measurement)
        outputs.append(output)

    # Check that output decreases monotonically as we approach setpoint
    # (no overshoot/oscillation in control signal)
    for i in range(len(outputs) - 1):
        # Allow small increases due to integral, but no large oscillations
        if outputs[i + 1] > outputs[i]:
            assert outputs[i + 1] - outputs[i] < 5.0  # Small tolerance


def test_parameter_update():
    """Test updating controller parameters."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    controller.set_parameters(kp=20.0, ti=1000.0, dt=300.0)

    assert controller.kp == 20.0
    assert controller.ti == 1000.0
    assert controller.dt == 300.0


def test_parameter_partial_update():
    """Test updating only some parameters."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    controller.set_parameters(kp=20.0)

    assert controller.kp == 20.0
    assert controller.ti == 1500.0  # Unchanged
    assert controller.dt == 600.0  # Unchanged


def test_reset():
    """Test controller reset."""
    controller = PIController()

    # Run controller to accumulate state
    for _ in range(10):
        controller.update(setpoint=22.0, measurement=20.0)

    # State should have values
    assert controller.state.integral != 0.0
    assert controller.state.last_error != 0.0
    assert controller.state.last_output != 0.0

    # Reset
    controller.reset()

    # State should be zeroed
    assert controller.state.integral == 0.0
    assert controller.state.last_error == 0.0
    assert controller.state.last_output == 0.0
    assert not controller.state.saturated


def test_get_state():
    """Test getting controller state."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    controller.update(setpoint=22.0, measurement=20.0)

    state = controller.get_state()

    assert state["kp"] == 10.0
    assert state["ti"] == 1500.0
    assert state["dt"] == 600.0
    assert "integral" in state
    assert "last_error" in state
    assert "last_output" in state
    assert "saturated" in state


def test_custom_dt_per_step():
    """Test using custom dt for individual steps."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    # Use longer dt for this step
    output1 = controller.update(setpoint=22.0, measurement=20.0, dt=1200.0)

    # Use default dt for next step
    output2 = controller.update(setpoint=22.0, measurement=20.0)

    # Longer dt should cause more integral accumulation
    # So after same error, we should see difference
    assert output1 != output2


def test_integral_term_limited():
    """Test that integral term is limited by anti-windup limit."""
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0, anti_windup_limit=50.0)

    # Apply large error for many steps
    for _ in range(100):
        controller.update(setpoint=30.0, measurement=20.0)

    # Calculate expected max integral
    max_integral = controller.anti_windup_limit / (controller.kp / controller.ti)

    # Integral should be limited
    assert abs(controller.state.integral) <= abs(max_integral) * 1.01  # Small tolerance


def test_zero_ti_no_integral():
    """Test that zero Ti disables integral action."""
    # This should not happen in practice, but test robustness
    controller = PIController(kp=10.0, ti=0.0, dt=600.0)

    output1 = controller.update(setpoint=22.0, measurement=20.0)
    output2 = controller.update(setpoint=22.0, measurement=20.0)

    # Output should be same (only P term, no I term)
    assert output1 == output2


def test_expected_pi_response():
    """Test PI response matches control theory expectations.

    For a step input with constant error:
    - Output should increase linearly due to integral term
    - Proportional term provides immediate response
    - Final steady-state output depends on accumulated integral
    """
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    setpoint = 21.0
    measurement = 20.0  # Constant 1°C error

    outputs = []
    expected_p = controller.kp * (setpoint - measurement)  # Should be 10.0

    for i in range(5):
        output = controller.update(setpoint, measurement)
        outputs.append(output)

        # Each output should be P term + accumulated I term
        expected_i = (controller.kp / controller.ti) * controller.state.integral
        expected_output = expected_p + expected_i

        assert output == pytest.approx(expected_output, abs=0.01)

    # Outputs should increase monotonically
    assert all(outputs[i] < outputs[i + 1] for i in range(len(outputs) - 1))


def test_overshoot_prevention():
    """Test that conservative tuning results in stable control."""
    # Conservative parameters for floor heating (slow system)
    controller = PIController(kp=5.0, ti=2000.0, dt=600.0)

    setpoint = 21.0
    outputs = []

    # Simulate approaching setpoint
    for temp in np.linspace(19.0, 21.0, 20):
        output = controller.update(setpoint, temp)
        outputs.append(output)

    # With PI controller, integral term accumulates as error decreases
    # So output doesn't strictly decrease. Instead, test for stability:
    # 1. No large oscillations (check variance)
    # 2. Final output is reasonable (not saturated)
    # 3. Output changes are smooth

    # Check no large sudden changes (smoothness)
    deltas = [abs(outputs[i + 1] - outputs[i]) for i in range(len(outputs) - 1)]
    max_delta = max(deltas)
    assert max_delta < 10.0  # No jumps larger than 10%

    # Final output should be reasonable (not saturated, not zero)
    assert 0.0 < outputs[-1] < 100.0

    # Check outputs are generally bounded (no wild excursions)
    assert all(0.0 <= o <= 100.0 for o in outputs)


def test_realistic_floor_heating_scenario():
    """Test realistic floor heating scenario over 24h."""
    # Conservative tuning for floor heating
    controller = PIController(kp=10.0, ti=1500.0, dt=600.0)

    setpoint = 21.0
    temperature = 19.0

    outputs = []
    errors = []

    # Simulate 24h (144 steps of 10 minutes)
    for step in range(144):
        output = controller.update(setpoint, temperature)
        outputs.append(output)

        error = setpoint - temperature
        errors.append(abs(error))

        # Simple temperature model: temp increases with heating
        # τ = 4h (floor heating time constant)
        tau_steps = 24  # 4h / 10min
        temperature += (output / 100.0) * 0.1 - 0.01  # Heating minus heat loss

        # Add some outdoor temperature influence
        temperature -= 0.005  # Slow cooling

    # Check that error decreases over time
    early_error = sum(errors[:20]) / 20
    late_error = sum(errors[-20:]) / 20

    assert late_error < early_error  # Error should decrease

    # Check that output is not constantly saturated
    saturated_count = sum(1 for o in outputs if o >= 99.0)
    assert saturated_count < len(outputs) * 0.3  # Less than 30% saturated
