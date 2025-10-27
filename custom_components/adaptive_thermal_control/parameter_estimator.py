"""Parameter estimation using Recursive Least Squares (RLS) algorithm.

This module implements online parameter identification for the thermal model.
The RLS algorithm estimates the thermal resistance R and capacity C from
historical temperature and heating power measurements.

Algorithm:
    Recursive Least Squares with forgetting factor
    - Estimates parameters online (incrementally)
    - Forgetting factor λ gives more weight to recent data
    - Suitable for time-varying systems (e.g., seasonal changes)

Model:
    T(k+1) = a·T(k) + b·u(k) + c·T_outdoor(k)

    Where:
        a = exp(-dt/(R·C))
        b = R·(1 - a)
        c = (1 - a)

    Regression form:
        y(k) = φ(k)ᵀ·θ + e(k)

    Where:
        y(k) = T(k+1)                    # Next temperature (output)
        φ(k) = [T(k), u(k), T_out(k)]    # Regressor vector
        θ = [a, b, c]                     # Parameters to estimate
        e(k) = prediction error
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .thermal_model import ThermalModelParameters

_LOGGER = logging.getLogger(__name__)

# RLS algorithm constants
DEFAULT_FORGETTING_FACTOR = 0.98  # Higher = more weight to old data
DEFAULT_INITIAL_COVARIANCE = 1000.0  # Large initial uncertainty


@dataclass
class RLSState:
    """State of the RLS estimator.

    Attributes:
        theta: Parameter vector [a, b, c]
        P: Covariance matrix (3x3)
        n_updates: Number of updates performed
        last_error: Last prediction error
    """

    theta: NDArray[np.float64] = field(default_factory=lambda: np.zeros(3))
    P: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(3) * DEFAULT_INITIAL_COVARIANCE
    )
    n_updates: int = 0
    last_error: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary with state information
        """
        return {
            "theta": self.theta.tolist(),
            "n_updates": self.n_updates,
            "last_error": self.last_error,
        }


class ParameterEstimator:
    """Recursive Least Squares parameter estimator for thermal model.

    This class estimates the thermal model parameters (R, C) from
    measurements of temperature, heating power, and outdoor temperature.

    The estimation is performed online using the RLS algorithm with
    a forgetting factor to adapt to changing conditions.
    """

    def __init__(
        self,
        dt: float = 600.0,
        forgetting_factor: float = DEFAULT_FORGETTING_FACTOR,
        initial_params: ThermalModelParameters | None = None,
    ) -> None:
        """Initialize parameter estimator.

        Args:
            dt: Sampling time [seconds] (default: 600s = 10 min)
            forgetting_factor: RLS forgetting factor λ ∈ (0, 1]
                - λ = 1.0: all data equally weighted (standard LS)
                - λ < 1.0: exponential forgetting of old data
                - Typical: 0.95-0.99
            initial_params: Initial guess for parameters (optional)
        """
        self.dt = dt
        self.lambda_factor = forgetting_factor

        # Initialize RLS state
        self.state = RLSState()

        # If initial parameters provided, use them to initialize theta
        if initial_params:
            self._initialize_from_params(initial_params)
        else:
            # Use reasonable defaults
            self._initialize_default()

        _LOGGER.info(
            "Initialized ParameterEstimator: dt=%.0fs, λ=%.3f, θ₀=%s",
            self.dt,
            self.lambda_factor,
            self.state.theta,
        )

    def _initialize_from_params(self, params: ThermalModelParameters) -> None:
        """Initialize theta from thermal parameters.

        Args:
            params: Thermal model parameters (R, C)
        """
        R = params.R
        C = params.C

        # Calculate discrete-time parameters
        a = np.exp(-self.dt / (R * C))
        b = R * (1 - a)
        c = 1 - a

        self.state.theta = np.array([a, b, c])

        _LOGGER.debug(
            "Initialized from R=%.6f, C=%.0f → θ=[%.6f, %.6f, %.6f]",
            R, C, a, b, c,
        )

    def _initialize_default(self) -> None:
        """Initialize with reasonable default values."""
        # Default: R=0.002, C=4.5e6
        R = 0.002
        C = 4.5e6

        a = np.exp(-self.dt / (R * C))
        b = R * (1 - a)
        c = 1 - a

        self.state.theta = np.array([a, b, c])

        _LOGGER.debug("Initialized with defaults: θ=%s", self.state.theta)

    def update(
        self,
        T_measured: float,
        T_outdoor: float,
        P_heating: float,
        T_previous: float | None = None,
    ) -> dict[str, float]:
        """Update parameter estimates with new measurement.

        RLS Algorithm:
            1. Compute regressor: φ(k) = [T(k-1), u(k-1), T_out(k-1)]
            2. Prediction: ŷ(k) = φ(k)ᵀ·θ(k-1)
            3. Error: e(k) = y(k) - ŷ(k)
            4. Gain: K(k) = P(k-1)·φ(k) / (λ + φ(k)ᵀ·P(k-1)·φ(k))
            5. Update: θ(k) = θ(k-1) + K(k)·e(k)
            6. Covariance: P(k) = (P(k-1) - K(k)·φ(k)ᵀ·P(k-1)) / λ

        Args:
            T_measured: Current measured temperature [°C]
            T_outdoor: Outdoor temperature [°C]
            P_heating: Heating power [W]
            T_previous: Previous temperature [°C] (if None, use prediction)

        Returns:
            Dictionary with update statistics:
                - error: Prediction error [°C]
                - theta: Current parameter vector
                - n_updates: Total number of updates
        """
        # If no previous temperature, skip this update
        if T_previous is None and self.state.n_updates == 0:
            _LOGGER.debug("Skipping first update (no previous temperature)")
            return self._get_update_stats(0.0)

        # Construct regressor vector φ(k) = [T(k-1), u(k-1), T_out(k-1)]
        if T_previous is None:
            # Use model prediction as previous temperature
            T_previous = self._predict_from_theta(
                self.state.theta, T_measured, P_heating, T_outdoor
            )

        phi = np.array([T_previous, P_heating, T_outdoor])

        # Prediction: ŷ(k) = φ(k)ᵀ·θ(k-1)
        y_pred = np.dot(phi, self.state.theta)

        # Prediction error: e(k) = y(k) - ŷ(k)
        error = T_measured - y_pred
        self.state.last_error = error

        # RLS update
        # Gain: K(k) = P(k-1)·φ(k) / (λ + φ(k)ᵀ·P(k-1)·φ(k))
        P_phi = self.state.P @ phi
        denominator = self.lambda_factor + phi.T @ P_phi

        if abs(denominator) < 1e-10:
            _LOGGER.warning("RLS denominator near zero, skipping update")
            return self._get_update_stats(error)

        K = P_phi / denominator

        # Update parameters: θ(k) = θ(k-1) + K(k)·e(k)
        self.state.theta = self.state.theta + K * error

        # Update covariance: P(k) = (P(k-1) - K(k)·φ(k)ᵀ·P(k-1)) / λ
        self.state.P = (self.state.P - np.outer(K, P_phi)) / self.lambda_factor

        # Increment update counter
        self.state.n_updates += 1

        if self.state.n_updates % 100 == 0:
            _LOGGER.debug(
                "RLS update #%d: error=%.3f°C, θ=%s",
                self.state.n_updates,
                error,
                self.state.theta,
            )

        return self._get_update_stats(error)

    def _predict_from_theta(
        self,
        theta: NDArray[np.float64],
        T_current: float,
        P_heating: float,
        T_outdoor: float,
    ) -> float:
        """Predict next temperature using current theta.

        Args:
            theta: Parameter vector [a, b, c]
            T_current: Current temperature [°C]
            P_heating: Heating power [W]
            T_outdoor: Outdoor temperature [°C]

        Returns:
            Predicted next temperature [°C]
        """
        a, b, c = theta
        return a * T_current + b * P_heating + c * T_outdoor

    def _get_update_stats(self, error: float) -> dict[str, float]:
        """Get statistics about the last update.

        Args:
            error: Prediction error

        Returns:
            Dictionary with update statistics
        """
        return {
            "error": error,
            "theta": self.state.theta.tolist(),
            "n_updates": self.state.n_updates,
        }

    def get_thermal_parameters(self) -> ThermalModelParameters | None:
        """Extract thermal model parameters (R, C) from estimated theta.

        From the estimated parameters:
            a = exp(-dt/(R·C))
            b = R·(1 - a)
            c = (1 - a)

        We can solve for R and C:
            c = 1 - a  →  a = 1 - c
            b = R·c  →  R = b/c
            a = exp(-dt/(R·C))  →  C = -dt / (R·ln(a))

        Returns:
            ThermalModelParameters if valid, None otherwise
        """
        a, b, c = self.state.theta

        # Validate parameter ranges
        if not (0 < a < 1):
            _LOGGER.warning("Invalid a parameter: %.6f (must be in (0,1))", a)
            return None

        if not (b > 0):
            _LOGGER.warning("Invalid b parameter: %.6f (must be > 0)", b)
            return None

        if not (0 < c < 1):
            _LOGGER.warning("Invalid c parameter: %.6f (must be in (0,1))", c)
            return None

        # Check consistency: c should be close to (1 - a)
        c_expected = 1 - a
        if abs(c - c_expected) > 0.1:
            _LOGGER.warning(
                "Inconsistent parameters: c=%.6f, expected %.6f from a=%.6f",
                c, c_expected, a,
            )

        # Solve for R and C
        try:
            R = b / c

            # C = -dt / (R·ln(a))
            ln_a = np.log(a)
            if ln_a >= 0:
                _LOGGER.error("Invalid ln(a)=%.6f (should be negative)", ln_a)
                return None

            C = -self.dt / (R * ln_a)

            # Create parameters object
            params = ThermalModelParameters(R=R, C=C)

            # Validate
            if not params.validate():
                _LOGGER.warning("Extracted parameters failed validation")
                return None

            _LOGGER.debug(
                "Extracted parameters: R=%.6f K/W, C=%.0f J/K, τ=%.1fh",
                R, C, params.time_constant / 3600,
            )

            return params

        except (ValueError, ZeroDivisionError) as e:
            _LOGGER.error("Failed to extract parameters: %s", e)
            return None

    def reset(self) -> None:
        """Reset estimator to initial state."""
        self.state = RLSState()
        self._initialize_default()
        _LOGGER.info("Reset parameter estimator")

    def get_state(self) -> dict[str, Any]:
        """Get current estimator state.

        Returns:
            Dictionary with state information
        """
        return {
            "dt": self.dt,
            "lambda": self.lambda_factor,
            "rls_state": self.state.to_dict(),
            "thermal_params": (
                self.get_thermal_parameters().to_dict()
                if self.get_thermal_parameters()
                else None
            ),
        }

    def __repr__(self) -> str:
        """String representation of the estimator.

        Returns:
            String with estimator info
        """
        params = self.get_thermal_parameters()
        if params:
            return (
                f"ParameterEstimator(R={params.R:.6f} K/W, "
                f"C={params.C:.0f} J/K, "
                f"updates={self.state.n_updates}, "
                f"λ={self.lambda_factor:.3f})"
            )
        else:
            return (
                f"ParameterEstimator(θ={self.state.theta}, "
                f"updates={self.state.n_updates}, "
                f"λ={self.lambda_factor:.3f})"
            )
