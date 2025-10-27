"""Thermal model (1R1C) for room temperature dynamics.

This module implements a first-order thermal model (1 Resistance, 1 Capacitance)
for modeling room temperature dynamics. The model captures the essential physics
of heat transfer while remaining simple enough for real-time MPC applications.

Physical Interpretation:
- R (Thermal Resistance): Heat flow resistance [K/W]
  Represents insulation quality, wall thermal properties
- C (Thermal Capacity): Heat storage capacity [J/K]
  Represents thermal mass of room (air, furniture, walls)

Model Equation (Continuous):
    C·dT/dt = Q_heating - (T - T_outdoor)/R + Q_disturbances

Discretized (Euler):
    T(k+1) = A·T(k) + B·u(k) + Bd·d(k)

Where:
    A = exp(-dt/(R·C))          # State transition matrix
    B = R·(1 - A)                # Input gain matrix
    Bd = (1 - A)                 # Disturbance gain matrix
    u(k) = heating power [W]
    d(k) = [T_outdoor, ...]      # Disturbances
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .const import THERMAL_MODEL_C_DEFAULT, THERMAL_MODEL_R_DEFAULT

_LOGGER = logging.getLogger(__name__)


@dataclass
class ThermalModelParameters:
    """Parameters for the 1R1C thermal model.

    Attributes:
        R: Thermal resistance [K/W]
        C: Thermal capacity [J/K]
        time_constant: Time constant Ä = R·C [seconds]
    """

    R: float = THERMAL_MODEL_R_DEFAULT  # [K/W]
    C: float = THERMAL_MODEL_C_DEFAULT  # [J/K]

    @property
    def time_constant(self) -> float:
        """Calculate time constant Ä = R·C.

        Returns:
            Time constant in seconds
        """
        return self.R * self.C

    def validate(self) -> bool:
        """Validate parameters are physically reasonable.

        Returns:
            True if parameters are valid
        """
        if self.R <= 0:
            _LOGGER.error("Thermal resistance R must be positive: R=%.6f", self.R)
            return False

        if self.C <= 0:
            _LOGGER.error("Thermal capacity C must be positive: C=%.6f", self.C)
            return False

        # Typical time constant for floor heating: 1-12 hours
        tau = self.time_constant
        if tau < 3600 or tau > 43200:
            _LOGGER.warning(
                "Time constant Ä=%.1fh outside typical range [1h, 12h]",
                tau / 3600,
            )

        return True

    def to_dict(self) -> dict[str, float]:
        """Convert parameters to dictionary.

        Returns:
            Dictionary with parameter values
        """
        return {
            "R": self.R,
            "C": self.C,
            "time_constant": self.time_constant,
        }


class ThermalModel:
    """1R1C thermal model for room temperature dynamics.

    This model captures the essential heat transfer physics:
    - Heat input from heating system (Q_heating)
    - Heat loss to outdoor (T - T_outdoor)/R
    - Heat storage in thermal mass C·dT/dt

    The model is discretized using Euler method for real-time simulation.
    """

    def __init__(
        self,
        params: ThermalModelParameters | None = None,
        dt: float = 600.0,
    ) -> None:
        """Initialize thermal model.

        Args:
            params: Model parameters (R, C). If None, use defaults.
            dt: Sampling time [seconds] (default: 600s = 10 min)
        """
        self.params = params or ThermalModelParameters()
        self.dt = dt

        # Validate parameters
        if not self.params.validate():
            raise ValueError("Invalid thermal model parameters")

        # Calculate discrete-time matrices
        self._update_matrices()

        _LOGGER.info(
            "Initialized ThermalModel: R=%.6f K/W, C=%.0f J/K, Ä=%.1f hours, dt=%.0fs",
            self.params.R,
            self.params.C,
            self.params.time_constant / 3600,
            self.dt,
        )

    def _update_matrices(self) -> None:
        """Update discrete-time state-space matrices.

        Calculates A, B, Bd matrices from continuous-time parameters.
        """
        R = self.params.R
        C = self.params.C
        dt = self.dt

        # State transition: A = exp(-dt/(R·C))
        self.A = np.exp(-dt / (R * C))

        # Input gain: B = R·(1 - A)
        self.B = R * (1 - self.A)

        # Disturbance gain: Bd = (1 - A)
        self.Bd = 1 - self.A

        _LOGGER.debug(
            "Updated matrices: A=%.6f, B=%.6f, Bd=%.6f",
            self.A,
            self.B,
            self.Bd,
        )

    def set_parameters(self, params: ThermalModelParameters) -> None:
        """Update model parameters.

        Args:
            params: New model parameters
        """
        if not params.validate():
            raise ValueError("Invalid thermal model parameters")

        self.params = params
        self._update_matrices()

        _LOGGER.info(
            "Updated model parameters: R=%.6f K/W, C=%.0f J/K, Ä=%.1f hours",
            self.params.R,
            self.params.C,
            self.params.time_constant / 3600,
        )

    def simulate_step(
        self,
        T_current: float,
        u_heating: float,
        T_outdoor: float,
        Q_disturbances: float = 0.0,
    ) -> float:
        """Simulate one time step of the thermal model.

        Args:
            T_current: Current room temperature [°C]
            u_heating: Heating power [W]
            T_outdoor: Outdoor temperature [°C]
            Q_disturbances: Additional disturbances [W] (e.g., solar, neighbors)

        Returns:
            Next room temperature T(k+1) [°C]
        """
        # State equation: T(k+1) = A·T(k) + B·u(k) + Bd·d(k)
        # Where d(k) combines outdoor temp and other disturbances

        # Temperature dynamics
        T_next = self.A * T_current + self.B * u_heating + self.Bd * T_outdoor

        # Additional disturbances (converted to equivalent temperature)
        if Q_disturbances != 0:
            T_next += self.B * Q_disturbances

        return T_next

    def predict(
        self,
        T_initial: float,
        u_sequence: NDArray[np.float64],
        T_outdoor_sequence: NDArray[np.float64],
        Q_disturbances_sequence: NDArray[np.float64] | None = None,
    ) -> NDArray[np.float64]:
        """Predict temperature trajectory over multiple time steps.

        Args:
            T_initial: Initial room temperature [°C]
            u_sequence: Heating power sequence [W] (length N)
            T_outdoor_sequence: Outdoor temperature sequence [°C] (length N)
            Q_disturbances_sequence: Disturbance power sequence [W] (length N, optional)

        Returns:
            Temperature predictions [°C] (length N+1, includes initial)
        """
        N = len(u_sequence)

        # Validate input lengths
        if len(T_outdoor_sequence) != N:
            raise ValueError(
                f"T_outdoor_sequence length {len(T_outdoor_sequence)} "
                f"must match u_sequence length {N}"
            )

        if Q_disturbances_sequence is None:
            Q_disturbances_sequence = np.zeros(N)
        elif len(Q_disturbances_sequence) != N:
            raise ValueError(
                f"Q_disturbances_sequence length {len(Q_disturbances_sequence)} "
                f"must match u_sequence length {N}"
            )

        # Initialize prediction array
        T_pred = np.zeros(N + 1)
        T_pred[0] = T_initial

        # Simulate forward
        for k in range(N):
            T_pred[k + 1] = self.simulate_step(
                T_current=T_pred[k],
                u_heating=u_sequence[k],
                T_outdoor=T_outdoor_sequence[k],
                Q_disturbances=Q_disturbances_sequence[k],
            )

        _LOGGER.debug(
            "Predicted %d steps: T_initial=%.1f°C ’ T_final=%.1f°C",
            N,
            T_initial,
            T_pred[-1],
        )

        return T_pred

    def steady_state_temperature(
        self,
        u_heating: float,
        T_outdoor: float,
        Q_disturbances: float = 0.0,
    ) -> float:
        """Calculate steady-state temperature for constant inputs.

        At steady state: dT/dt = 0, so:
            T_ss = T_outdoor + R·(u_heating + Q_disturbances)

        Args:
            u_heating: Constant heating power [W]
            T_outdoor: Constant outdoor temperature [°C]
            Q_disturbances: Constant disturbance power [W]

        Returns:
            Steady-state room temperature [°C]
        """
        T_ss = T_outdoor + self.params.R * (u_heating + Q_disturbances)

        _LOGGER.debug(
            "Steady state: u=%.1fW, T_out=%.1f°C ’ T_ss=%.1f°C",
            u_heating,
            T_outdoor,
            T_ss,
        )

        return T_ss

    def heating_power_for_target(
        self,
        T_target: float,
        T_outdoor: float,
        Q_disturbances: float = 0.0,
    ) -> float:
        """Calculate heating power needed to reach target temperature at steady state.

        From steady state equation:
            u_heating = (T_target - T_outdoor)/R - Q_disturbances

        Args:
            T_target: Target room temperature [°C]
            T_outdoor: Outdoor temperature [°C]
            Q_disturbances: Disturbance power [W] (positive = heating)

        Returns:
            Required heating power [W]
        """
        u_heating = (T_target - T_outdoor) / self.params.R - Q_disturbances

        _LOGGER.debug(
            "Required heating: T_target=%.1f°C, T_out=%.1f°C ’ u=%.1fW",
            T_target,
            T_outdoor,
            u_heating,
        )

        return max(0.0, u_heating)  # Cannot have negative heating

    def get_state(self) -> dict[str, Any]:
        """Get current model state and parameters.

        Returns:
            Dictionary with model information
        """
        return {
            "parameters": self.params.to_dict(),
            "dt": self.dt,
            "matrices": {
                "A": float(self.A),
                "B": float(self.B),
                "Bd": float(self.Bd),
            },
        }

    def __repr__(self) -> str:
        """String representation of the model.

        Returns:
            String with model parameters
        """
        return (
            f"ThermalModel(R={self.params.R:.6f} K/W, "
            f"C={self.params.C:.0f} J/K, "
            f"Ä={self.params.time_constant/3600:.1f}h, "
            f"dt={self.dt:.0f}s)"
        )
