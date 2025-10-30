"""MPC parameter tuning tools (T3.5.1).

This module provides tools for tuning MPC controller parameters
using grid search over different weight combinations.

The tuner evaluates different parameter sets by simulating control
performance and measuring:
- RMSE (temperature tracking error)
- Total energy consumption
- Control smoothness (sum of Δu²)

It helps find Pareto-optimal parameters that balance comfort vs energy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from .mpc_controller import MPCConfig, MPCController
from .thermal_model import ThermalModel

_LOGGER = logging.getLogger(__name__)


@dataclass
class TuningResult:
    """Result of MPC parameter tuning."""

    weights: dict[str, float]
    rmse: float
    total_energy: float
    smoothness: float
    cost_function_value: float

    @property
    def score(self) -> float:
        """Combined score (lower is better).

        Weighted combination of metrics:
        - 70% RMSE (comfort priority)
        - 20% energy
        - 10% smoothness
        """
        # Normalize metrics to comparable scales
        norm_rmse = self.rmse  # already in °C
        norm_energy = self.total_energy / 100.0  # scale to 0-1 range
        norm_smoothness = self.smoothness / 10.0  # scale to 0-1 range

        return 0.7 * norm_rmse + 0.2 * norm_energy + 0.1 * norm_smoothness


class MPCTuner:
    """MPC parameter tuning tool using grid search."""

    def __init__(
        self,
        model: ThermalModel,
        base_config: MPCConfig | None = None,
    ) -> None:
        """Initialize MPC tuner.

        Args:
            model: Thermal model for simulation
            base_config: Base MPC configuration (optional)
        """
        self.model = model
        self.base_config = base_config or MPCConfig()

    def grid_search(
        self,
        test_scenario: dict[str, Any],
        param_grid: dict[str, list[float]] | None = None,
    ) -> list[TuningResult]:
        """Perform grid search over MPC parameters.

        Args:
            test_scenario: Scenario for testing:
                - initial_temp: float - starting temperature [°C]
                - setpoint: float - target temperature [°C]
                - outdoor_temps: np.ndarray - outdoor temp forecast [°C]
                - duration_hours: int - simulation duration [h]
            param_grid: Grid of parameters to search:
                - w_comfort: list[float]
                - w_energy: list[float]
                - w_smooth: list[float]
                Default: predefined grid with 27 combinations

        Returns:
            List of TuningResult objects sorted by score (best first)
        """
        if param_grid is None:
            # Default grid: 3x3x3 = 27 combinations
            param_grid = {
                "w_comfort": [0.5, 0.7, 0.9],
                "w_energy": [0.1, 0.2, 0.3],
                "w_smooth": [0.05, 0.1, 0.15],
            }

        results = []

        # Iterate over all combinations
        for w_c in param_grid["w_comfort"]:
            for w_e in param_grid["w_energy"]:
                for w_s in param_grid["w_smooth"]:
                    # Skip invalid combinations (weights don't sum to ~1.0)
                    weight_sum = w_c + w_e + w_s
                    if not (0.95 <= weight_sum <= 1.05):
                        continue

                    # Normalize weights to sum to 1.0
                    total = w_c + w_e + w_s
                    weights = {
                        "w_comfort": w_c / total,
                        "w_energy": w_e / total,
                        "w_smooth": w_s / total,
                    }

                    # Run simulation with these weights
                    result = self._evaluate_parameters(weights, test_scenario)
                    results.append(result)

                    _LOGGER.debug(
                        "Tested weights: comfort=%.2f, energy=%.2f, smooth=%.2f "
                        "→ RMSE=%.2f°C, Energy=%.1f, Smoothness=%.2f, Score=%.3f",
                        weights["w_comfort"],
                        weights["w_energy"],
                        weights["w_smooth"],
                        result.rmse,
                        result.total_energy,
                        result.smoothness,
                        result.score,
                    )

        # Sort by score (best first)
        results.sort(key=lambda r: r.score)

        _LOGGER.info(
            "Grid search complete: tested %d combinations, best score: %.3f",
            len(results),
            results[0].score if results else 0.0,
        )

        return results

    def _evaluate_parameters(
        self,
        weights: dict[str, float],
        test_scenario: dict[str, Any],
    ) -> TuningResult:
        """Evaluate MPC parameters on a test scenario.

        Args:
            weights: Weight configuration to test
            test_scenario: Test scenario parameters

        Returns:
            TuningResult with performance metrics
        """
        # Create MPC config with these weights
        config = MPCConfig(
            Np=self.base_config.Np,
            Nc=self.base_config.Nc,
            dt=self.base_config.dt,
            u_min=self.base_config.u_min,
            u_max=self.base_config.u_max,
            du_max=self.base_config.du_max,
            w_comfort=weights["w_comfort"],
            w_energy=weights["w_energy"],
            w_smooth=weights["w_smooth"],
        )

        controller = MPCController(self.model, config)

        # Extract scenario parameters
        initial_temp = test_scenario["initial_temp"]
        setpoint = test_scenario["setpoint"]
        outdoor_temps = test_scenario["outdoor_temps"]
        duration_hours = test_scenario.get("duration_hours", 24)

        # Simulation
        steps = int(duration_hours * 3600 / config.dt)  # number of timesteps
        current_temp = initial_temp
        errors_squared = []
        control_sequence = []
        energy_consumption = 0.0

        for step in range(steps):
            # Get outdoor temp for this step
            outdoor_idx = min(step, len(outdoor_temps) - 1)
            outdoor_temp = outdoor_temps[outdoor_idx]

            # Compute control
            forecast = outdoor_temps[outdoor_idx : outdoor_idx + config.Np]

            # Pad forecast if needed
            if len(forecast) < config.Np:
                forecast = np.pad(
                    forecast,
                    (0, config.Np - len(forecast)),
                    mode="edge",
                )

            try:
                result = controller.compute_control(
                    T_current=current_temp,
                    T_setpoint=setpoint,
                    T_outdoor_forecast=forecast,
                )

                u_optimal = result.u_first  # Use first control action (scalar)
            except Exception as e:
                _LOGGER.warning(
                    "MPC failed at step %d: %s, using zero control", step, e
                )
                u_optimal = 0.0

            # Track metrics
            error = setpoint - current_temp
            errors_squared.append(error**2)
            control_sequence.append(u_optimal)

            # Simulate system response
            # Using simplified 1R1C discrete-time model:
            # T(k+1) = a*T(k) + b*u(k) + bd*T_outdoor
            a = np.exp(-config.dt / self.model.params.time_constant)
            b = self.model.params.R * (1 - a)
            bd = 1 - a

            current_temp = a * current_temp + b * u_optimal + bd * outdoor_temp

            # Track energy (integral of control power)
            energy_consumption += u_optimal * config.dt / 3600.0  # Wh

        # Calculate metrics
        rmse = float(np.sqrt(np.mean(errors_squared)))

        # Control smoothness (sum of squared control changes)
        control_changes = np.diff(control_sequence)
        smoothness = float(np.sum(control_changes**2))

        # Cost function value (last computed)
        cost_value = rmse**2 + weights["w_energy"] * energy_consumption + weights["w_smooth"] * smoothness

        return TuningResult(
            weights=weights,
            rmse=rmse,
            total_energy=energy_consumption,
            smoothness=smoothness,
            cost_function_value=cost_value,
        )

    def find_pareto_optimal(
        self,
        results: list[TuningResult],
        objective1: str = "rmse",
        objective2: str = "total_energy",
    ) -> list[TuningResult]:
        """Find Pareto-optimal solutions from tuning results.

        A solution is Pareto-optimal if no other solution is better
        in both objectives simultaneously.

        Args:
            results: List of tuning results
            objective1: First objective to minimize (default: rmse)
            objective2: Second objective to minimize (default: total_energy)

        Returns:
            List of Pareto-optimal solutions
        """
        pareto_set = []

        for r1 in results:
            is_dominated = False

            # Check if r1 is dominated by any other result
            for r2 in results:
                if r1 == r2:
                    continue

                # r2 dominates r1 if it's better or equal in both objectives
                # and strictly better in at least one
                obj1_r1 = getattr(r1, objective1)
                obj1_r2 = getattr(r2, objective1)
                obj2_r1 = getattr(r1, objective2)
                obj2_r2 = getattr(r2, objective2)

                if (
                    obj1_r2 <= obj1_r1
                    and obj2_r2 <= obj2_r1
                    and (obj1_r2 < obj1_r1 or obj2_r2 < obj2_r1)
                ):
                    is_dominated = True
                    break

            if not is_dominated:
                pareto_set.append(r1)

        _LOGGER.info(
            "Found %d Pareto-optimal solutions out of %d total",
            len(pareto_set),
            len(results),
        )

        return pareto_set

    def recommend_parameters(
        self,
        results: list[TuningResult],
        preference: str = "balanced",
    ) -> dict[str, float]:
        """Recommend MPC parameters based on user preference.

        Args:
            results: List of tuning results (sorted by score)
            preference: User preference:
                - "comfort": Prioritize comfort (minimize RMSE)
                - "energy": Prioritize energy savings
                - "balanced": Balance comfort and energy (default)

        Returns:
            Recommended weight configuration
        """
        if not results:
            _LOGGER.warning("No tuning results available, using defaults")
            return {
                "w_comfort": 0.7,
                "w_energy": 0.2,
                "w_smooth": 0.1,
            }

        if preference == "comfort":
            # Choose result with lowest RMSE
            best = min(results, key=lambda r: r.rmse)
        elif preference == "energy":
            # Choose result with lowest energy consumption
            best = min(results, key=lambda r: r.total_energy)
        else:  # balanced
            # Choose result with best combined score
            best = results[0]  # already sorted by score

        _LOGGER.info(
            "Recommended parameters (preference=%s): comfort=%.3f, energy=%.3f, smooth=%.3f "
            "(RMSE=%.2f°C, Energy=%.1f, Score=%.3f)",
            preference,
            best.weights["w_comfort"],
            best.weights["w_energy"],
            best.weights["w_smooth"],
            best.rmse,
            best.total_energy,
            best.score,
        )

        return best.weights
