"""PI Controller implementation for Adaptive Thermal Control.

This module implements a discrete-time PI (Proportional-Integral) controller
with anti-windup protection. It serves as a fallback controller before MPC is
available or when MPC cannot be used.

The controller uses the velocity form with back-calculation anti-windup:
    u(k) = Kp * e(k) + (Kp/Ti) * sum(e(j)*dt)

Where:
    - e(k) = setpoint - measurement (error)
    - Kp = proportional gain
    - Ti = integral time constant [seconds]
    - dt = sampling time [seconds]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

_LOGGER = logging.getLogger(__name__)

# Default parameters optimized for floor heating
DEFAULT_KP: Final = 10.0  # Proportional gain
DEFAULT_TI: Final = 1500.0  # Integral time constant [seconds] (25 minutes)
DEFAULT_DT: Final = 600.0  # Sampling time [seconds] (10 minutes)
DEFAULT_ANTI_WINDUP_LIMIT: Final = 100.0  # Anti-windup limit [%]


@dataclass
class PIControllerState:
    """State of the PI controller.

    Attributes:
        integral: Integral term accumulator
        last_error: Last error value (for derivative calculation if needed)
        last_output: Last output value (for anti-windup)
        saturated: Whether output was saturated last cycle
    """

    integral: float = 0.0
    last_error: float = 0.0
    last_output: float = 0.0
    saturated: bool = False


class PIController:
    """Discrete-time PI controller with anti-windup.

    This controller is designed for floor heating systems with long time constants.
    It uses back-calculation anti-windup to prevent integral windup when the
    output saturates.

    Typical parameters for floor heating:
        - Kp = 10.0 (moderate proportional gain)
        - Ti = 1500s (25 min, slow integral action)
        - dt = 600s (10 min update interval)
    """

    def __init__(
        self,
        kp: float = DEFAULT_KP,
        ti: float = DEFAULT_TI,
        dt: float = DEFAULT_DT,
        output_min: float = 0.0,
        output_max: float = 100.0,
        anti_windup_limit: float = DEFAULT_ANTI_WINDUP_LIMIT,
    ) -> None:
        """Initialize the PI controller.

        Args:
            kp: Proportional gain
            ti: Integral time constant [seconds]
            dt: Sampling time [seconds]
            output_min: Minimum output value [%]
            output_max: Maximum output value [%]
            anti_windup_limit: Anti-windup limit [%]
        """
        self.kp = kp
        self.ti = ti
        self.dt = dt
        self.output_min = output_min
        self.output_max = output_max
        self.anti_windup_limit = anti_windup_limit

        # Controller state
        self.state = PIControllerState()

        _LOGGER.info(
            "Initialized PI controller: Kp=%.2f, Ti=%.1fs, dt=%.1fs, "
            "output=[%.1f, %.1f]%%",
            kp,
            ti,
            dt,
            output_min,
            output_max,
        )

    def update(
        self,
        setpoint: float,
        measurement: float,
        dt: float | None = None,
    ) -> float:
        """Compute PI controller output.

        Args:
            setpoint: Desired value (target temperature)
            measurement: Current value (measured temperature)
            dt: Sampling time for this step (optional, uses default if not provided)

        Returns:
            Control output [%] (0-100 for valve position)
        """
        # Use provided dt or default
        if dt is None:
            dt = self.dt

        # Calculate error
        error = setpoint - measurement

        # Proportional term
        p_term = self.kp * error

        # Integral term (with anti-windup)
        if not self.state.saturated:
            # Only integrate if output is not saturated
            self.state.integral += error * dt

        # Limit integral term to prevent excessive accumulation
        max_integral = self.anti_windup_limit / (self.kp / self.ti) if self.ti > 0 else 0
        self.state.integral = max(-max_integral, min(max_integral, self.state.integral))

        i_term = (self.kp / self.ti) * self.state.integral if self.ti > 0 else 0

        # Total output
        output = p_term + i_term

        # Saturate output
        output_saturated = max(self.output_min, min(self.output_max, output))

        # Check if output is saturated
        self.state.saturated = output != output_saturated

        # Store state for next iteration
        self.state.last_error = error
        self.state.last_output = output_saturated

        _LOGGER.debug(
            "PI update: e=%.2f, P=%.2f, I=%.2f (int=%.2f), u=%.2f%s",
            error,
            p_term,
            i_term,
            self.state.integral,
            output_saturated,
            " (saturated)" if self.state.saturated else "",
        )

        return output_saturated

    def reset(self) -> None:
        """Reset controller state.

        This should be called when:
        - Controller is first enabled
        - Setpoint changes dramatically
        - System undergoes a major disturbance
        """
        _LOGGER.info("Resetting PI controller state")
        self.state = PIControllerState()

    def set_parameters(
        self,
        kp: float | None = None,
        ti: float | None = None,
        dt: float | None = None,
    ) -> None:
        """Update controller parameters.

        Args:
            kp: New proportional gain (optional)
            ti: New integral time constant (optional)
            dt: New sampling time (optional)
        """
        if kp is not None:
            self.kp = kp
            _LOGGER.info("Updated Kp to %.2f", kp)

        if ti is not None:
            self.ti = ti
            _LOGGER.info("Updated Ti to %.1fs", ti)

        if dt is not None:
            self.dt = dt
            _LOGGER.info("Updated dt to %.1fs", dt)

    def get_state(self) -> dict[str, float]:
        """Get current controller state.

        Returns:
            Dictionary with controller state information
        """
        return {
            "kp": self.kp,
            "ti": self.ti,
            "dt": self.dt,
            "integral": self.state.integral,
            "last_error": self.state.last_error,
            "last_output": self.state.last_output,
            "saturated": self.state.saturated,
        }
