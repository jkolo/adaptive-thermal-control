"""Model Predictive Control (MPC) controller for adaptive thermal control.

This module implements a Model Predictive Control algorithm for floor heating
systems. It uses a thermal model to predict future temperature behavior and
optimizes the heating control sequence to minimize a cost function while
maintaining comfort.

Key features:
- Prediction horizon (Np): 4-8 hours ahead
- Control horizon (Nc): 2 hours of optimization
- Multi-objective cost: comfort + energy + smoothness
- Constraint handling: power limits, rate limits
- Fallback to PI controller if optimization fails
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize, OptimizeResult

from .const import (
    MPC_CONTROL_HORIZON,
    MPC_PREDICTION_HORIZON,
    MPC_WEIGHT_COMFORT,
    MPC_WEIGHT_ENERGY,
)
from .thermal_model import ThermalModel

_LOGGER = logging.getLogger(__name__)


@dataclass
class MPCConfig:
    """Configuration for MPC controller.

    Attributes:
        Np: Prediction horizon [steps]
        Nc: Control horizon [steps]
        dt: Time step [seconds]
        w_comfort: Weight for comfort term in cost function
        w_energy: Weight for energy term in cost function
        w_smooth: Weight for smoothness term in cost function
        u_min: Minimum control input [W]
        u_max: Maximum control input [W]
        du_max: Maximum control rate change [W/step]
    """

    Np: int = MPC_PREDICTION_HORIZON  # 24 steps = 4 hours
    Nc: int = MPC_CONTROL_HORIZON  # 12 steps = 2 hours
    dt: float = 600.0  # 10 minutes
    w_comfort: float = MPC_WEIGHT_COMFORT
    w_energy: float = MPC_WEIGHT_ENERGY
    w_smooth: float = 0.1
    u_min: float = 0.0  # Minimum heating power [W]
    u_max: float = 2000.0  # Maximum heating power [W]
    du_max: float = 500.0  # Maximum power change per step [W]

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "Np": self.Np,
            "Nc": self.Nc,
            "dt": self.dt,
            "w_comfort": self.w_comfort,
            "w_energy": self.w_energy,
            "w_smooth": self.w_smooth,
            "u_min": self.u_min,
            "u_max": self.u_max,
            "du_max": self.du_max,
        }


@dataclass
class MPCResult:
    """Result of MPC optimization.

    Attributes:
        u_optimal: Optimal control sequence [W]
        u_first: First control action to apply [W]
        cost: Total cost value
        success: Whether optimization succeeded
        message: Status message
        iterations: Number of optimizer iterations
        predicted_temps: Predicted temperature trajectory [°C]
    """

    u_optimal: NDArray[np.float64]
    u_first: float
    cost: float
    success: bool
    message: str
    iterations: int
    predicted_temps: NDArray[np.float64] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "u_first": float(self.u_first),
            "cost": float(self.cost),
            "success": self.success,
            "message": self.message,
            "iterations": self.iterations,
            "u_sequence": self.u_optimal.tolist() if self.u_optimal is not None else None,
            "predicted_temps": (
                self.predicted_temps.tolist() if self.predicted_temps is not None else None
            ),
        }


class MPCController:
    """Model Predictive Control controller.

    This controller uses a thermal model to predict future temperature
    evolution and optimizes the heating control sequence to minimize
    a cost function while respecting constraints.

    The optimization problem:
        min J(u) = Σ[k=0..Np] {w_comfort·(T(k)-Tsp)² + w_energy·u(k)² + w_smooth·(u(k)-u(k-1))²}
        s.t. u_min ≤ u(k) ≤ u_max
             |u(k) - u(k-1)| ≤ du_max
    """

    def __init__(
        self,
        model: ThermalModel,
        config: MPCConfig | None = None,
    ) -> None:
        """Initialize MPC controller.

        Args:
            model: Thermal model for predictions
            config: MPC configuration (uses defaults if None)
        """
        self.model = model
        self.config = config or MPCConfig()

        # Validate configuration
        if self.config.Nc > self.config.Np:
            _LOGGER.warning(
                "Control horizon Nc=%d > prediction horizon Np=%d, "
                "setting Nc=Np",
                self.config.Nc,
                self.config.Np,
            )
            self.config.Nc = self.config.Np

        # State
        self._u_prev: float = 0.0  # Previous control action
        self._u_sequence_prev: NDArray[np.float64] | None = None  # For warm-start

        _LOGGER.info(
            "Initialized MPCController: Np=%d (%.1fh), Nc=%d (%.1fh), dt=%.0fs",
            self.config.Np,
            self.config.Np * self.config.dt / 3600,
            self.config.Nc,
            self.config.Nc * self.config.dt / 3600,
            self.config.dt,
        )

    def compute_control(
        self,
        T_current: float,
        T_setpoint: float,
        T_outdoor_forecast: NDArray[np.float64],
        u_last: float | None = None,
    ) -> MPCResult:
        """Compute optimal control action using MPC.

        Args:
            T_current: Current room temperature [°C]
            T_setpoint: Desired temperature [°C]
            T_outdoor_forecast: Outdoor temperature forecast [°C] for Np steps
            u_last: Last applied control [W] (for continuity)

        Returns:
            MPCResult with optimal control and status
        """
        # Update previous control
        if u_last is not None:
            self._u_prev = u_last

        # Validate forecast length
        if len(T_outdoor_forecast) < self.config.Np:
            _LOGGER.warning(
                "Forecast too short (%d < %d), extending with last value",
                len(T_outdoor_forecast),
                self.config.Np,
            )
            # Extend forecast by repeating last value
            T_outdoor_forecast = np.pad(
                T_outdoor_forecast,
                (0, self.config.Np - len(T_outdoor_forecast)),
                mode="edge",
            )

        # Initial guess for optimization (warm-start if available)
        u_init = self._get_initial_guess()

        # Set up optimization bounds (box constraints)
        bounds = [(self.config.u_min, self.config.u_max)] * self.config.Nc

        # Optimize
        try:
            result = minimize(
                fun=self._cost_function,
                x0=u_init,
                args=(T_current, T_setpoint, T_outdoor_forecast),
                method="SLSQP",
                bounds=bounds,
                constraints=self._get_constraints(),
                options={
                    "maxiter": 100,
                    "ftol": 1e-6,
                    "disp": False,
                },
            )

            if result.success:
                u_optimal = result.x
                u_first = float(u_optimal[0])

                # Simulate to get predicted temperatures
                predicted_temps = self._simulate_trajectory(
                    T_current, u_optimal, T_outdoor_forecast
                )

                # Save for warm-start next time
                self._u_sequence_prev = u_optimal

                _LOGGER.debug(
                    "MPC optimization successful: cost=%.3f, u_first=%.1fW, "
                    "iterations=%d",
                    result.fun,
                    u_first,
                    result.nit,
                )

                return MPCResult(
                    u_optimal=u_optimal,
                    u_first=u_first,
                    cost=float(result.fun),
                    success=True,
                    message="Optimization converged",
                    iterations=result.nit,
                    predicted_temps=predicted_temps,
                )
            else:
                _LOGGER.warning(
                    "MPC optimization failed: %s (iterations=%d)",
                    result.message,
                    result.nit,
                )
                # Return safe fallback value
                return MPCResult(
                    u_optimal=u_init,
                    u_first=float(u_init[0]),
                    cost=float("inf"),
                    success=False,
                    message=f"Optimization failed: {result.message}",
                    iterations=result.nit,
                )

        except Exception as e:
            _LOGGER.error("MPC optimization error: %s", e, exc_info=True)
            return MPCResult(
                u_optimal=u_init,
                u_first=float(u_init[0]),
                cost=float("inf"),
                success=False,
                message=f"Exception: {str(e)}",
                iterations=0,
            )

    def _get_initial_guess(self) -> NDArray[np.float64]:
        """Get initial guess for optimization.

        Uses warm-start if previous solution available, otherwise
        uses last control action.

        Returns:
            Initial control sequence
        """
        if self._u_sequence_prev is not None:
            # Warm-start: shift previous solution and append last value
            u_init = np.roll(self._u_sequence_prev, -1)
            u_init[-1] = self._u_sequence_prev[-1]
            # Extend or trim to Nc
            if len(u_init) < self.config.Nc:
                u_init = np.pad(
                    u_init, (0, self.config.Nc - len(u_init)), mode="edge"
                )
            else:
                u_init = u_init[: self.config.Nc]
        else:
            # Cold start: use previous control action
            u_init = np.full(self.config.Nc, self._u_prev)

        return u_init

    def _cost_function(
        self,
        u_sequence: NDArray[np.float64],
        T_current: float,
        T_setpoint: float,
        T_outdoor_forecast: NDArray[np.float64],
    ) -> float:
        """Compute total cost function.

        Args:
            u_sequence: Control sequence [W] for Nc steps
            T_current: Current temperature [°C]
            T_setpoint: Desired temperature [°C]
            T_outdoor_forecast: Outdoor temperature forecast [°C]

        Returns:
            Total cost value
        """
        # Extend control sequence to Np (hold last value)
        u_full = np.pad(
            u_sequence, (0, self.config.Np - self.config.Nc), mode="edge"
        )

        # Simulate temperature trajectory
        T = T_current
        cost = 0.0

        for k in range(self.config.Np):
            # Predict next temperature
            T_next = self.model.simulate_step(
                T_current=T,
                u_heating=u_full[k],
                T_outdoor=T_outdoor_forecast[k],
            )

            # Comfort cost: penalize deviation from setpoint
            comfort_error = T_next - T_setpoint
            cost_comfort = self.config.w_comfort * (comfort_error**2)

            # Energy cost: penalize high power usage
            # Normalize by 1e6 to keep same scale as comfort
            cost_energy = self.config.w_energy * (u_full[k] ** 2) / 1e6

            # Smoothness cost: penalize rapid changes
            if k > 0:
                du = u_full[k] - u_full[k - 1]
                cost_smooth = self.config.w_smooth * (du**2) / 1e6
            else:
                du = u_full[k] - self._u_prev
                cost_smooth = self.config.w_smooth * (du**2) / 1e6

            # Accumulate cost
            cost += cost_comfort + cost_energy + cost_smooth

            # Update temperature for next step
            T = T_next

        return cost

    def _get_constraints(self) -> list[dict[str, Any]]:
        """Get constraints for optimizer.

        Returns:
            List of constraint dictionaries for scipy.optimize
        """
        constraints = []

        # Rate constraint: |u(k) - u(k-1)| ≤ du_max
        def rate_constraint_pos(u: NDArray[np.float64]) -> NDArray[np.float64]:
            """Positive rate constraint: u(k) - u(k-1) ≤ du_max."""
            du = np.diff(u, prepend=self._u_prev)
            return self.config.du_max - du

        def rate_constraint_neg(u: NDArray[np.float64]) -> NDArray[np.float64]:
            """Negative rate constraint: -(u(k) - u(k-1)) ≤ du_max."""
            du = np.diff(u, prepend=self._u_prev)
            return self.config.du_max + du

        constraints.append({"type": "ineq", "fun": rate_constraint_pos})
        constraints.append({"type": "ineq", "fun": rate_constraint_neg})

        return constraints

    def _simulate_trajectory(
        self,
        T_current: float,
        u_sequence: NDArray[np.float64],
        T_outdoor_forecast: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Simulate temperature trajectory with given control sequence.

        Args:
            T_current: Initial temperature [°C]
            u_sequence: Control sequence [W]
            T_outdoor_forecast: Outdoor temperature forecast [°C]

        Returns:
            Predicted temperature trajectory [°C]
        """
        # Extend control sequence to Np
        u_full = np.pad(
            u_sequence, (0, self.config.Np - len(u_sequence)), mode="edge"
        )

        # Simulate
        temps = np.zeros(self.config.Np + 1)
        temps[0] = T_current

        for k in range(self.config.Np):
            temps[k + 1] = self.model.simulate_step(
                T_current=temps[k],
                u_heating=u_full[k],
                T_outdoor=T_outdoor_forecast[k],
            )

        return temps

    def reset(self) -> None:
        """Reset controller state."""
        self._u_prev = 0.0
        self._u_sequence_prev = None
        _LOGGER.debug("MPC controller state reset")

    def set_weights(
        self, w_comfort: float | None = None, w_energy: float | None = None, w_smooth: float | None = None
    ) -> None:
        """Update cost function weights.

        Args:
            w_comfort: New comfort weight
            w_energy: New energy weight
            w_smooth: New smoothness weight
        """
        if w_comfort is not None:
            self.config.w_comfort = w_comfort
        if w_energy is not None:
            self.config.w_energy = w_energy
        if w_smooth is not None:
            self.config.w_smooth = w_smooth

        _LOGGER.info(
            "Updated MPC weights: comfort=%.2f, energy=%.2f, smooth=%.2f",
            self.config.w_comfort,
            self.config.w_energy,
            self.config.w_smooth,
        )
