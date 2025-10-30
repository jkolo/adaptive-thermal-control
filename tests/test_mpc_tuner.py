"""Tests for MPC parameter tuning tools (T3.5.1)."""

from __future__ import annotations

import numpy as np
import pytest

from custom_components.adaptive_thermal_control.mpc_controller import MPCConfig
from custom_components.adaptive_thermal_control.mpc_tuner import (
    MPCTuner,
    TuningResult,
)
from custom_components.adaptive_thermal_control.thermal_model import (
    ThermalModel,
    ThermalModelParameters,
)


@pytest.fixture
def thermal_model():
    """Create test thermal model."""
    params = ThermalModelParameters(
        R=0.01,  # K/W
        C=50e6,  # J/K → tau = R*C = 0.01 * 50e6 = 500,000s ≈ 5.8 days
    )
    return ThermalModel(params)


@pytest.fixture
def test_scenario():
    """Create test scenario for tuning."""
    # 24h scenario with sinusoidal outdoor temperature
    hours = 24
    steps = int(hours * 3600 / 600)  # 10-minute steps
    outdoor_temps = 5.0 + 5.0 * np.sin(np.linspace(0, 2 * np.pi, steps))

    return {
        "initial_temp": 18.0,  # °C
        "setpoint": 21.0,  # °C
        "outdoor_temps": outdoor_temps,
        "duration_hours": hours,
    }


class TestTuningResult:
    """Test suite for TuningResult dataclass."""

    def test_tuning_result_creation(self):
        """Test TuningResult creation and attributes."""
        result = TuningResult(
            weights={"w_comfort": 0.7, "w_energy": 0.2, "w_smooth": 0.1},
            rmse=1.5,
            total_energy=25.0,
            smoothness=5.0,
            cost_function_value=10.5,
        )

        assert result.weights["w_comfort"] == 0.7
        assert result.weights["w_energy"] == 0.2
        assert result.weights["w_smooth"] == 0.1
        assert result.rmse == 1.5
        assert result.total_energy == 25.0
        assert result.smoothness == 5.0
        assert result.cost_function_value == 10.5

    def test_tuning_result_score(self):
        """Test combined score calculation."""
        result = TuningResult(
            weights={"w_comfort": 0.7, "w_energy": 0.2, "w_smooth": 0.1},
            rmse=1.0,  # °C
            total_energy=100.0,  # Wh
            smoothness=10.0,
            cost_function_value=0.0,
        )

        # Score = 0.7*rmse + 0.2*(energy/100) + 0.1*(smooth/10)
        #       = 0.7*1.0 + 0.2*1.0 + 0.1*1.0
        #       = 0.7 + 0.2 + 0.1 = 1.0
        assert abs(result.score - 1.0) < 0.01

    def test_tuning_result_score_prioritizes_comfort(self):
        """Test that score prioritizes comfort (RMSE) with 70% weight."""
        result_high_rmse = TuningResult(
            weights={},
            rmse=2.0,
            total_energy=0.0,
            smoothness=0.0,
            cost_function_value=0.0,
        )

        result_low_rmse = TuningResult(
            weights={},
            rmse=1.0,
            total_energy=0.0,
            smoothness=0.0,
            cost_function_value=0.0,
        )

        # Lower RMSE should have better (lower) score
        assert result_low_rmse.score < result_high_rmse.score

        # Difference should be proportional to 70% weight
        score_diff = result_high_rmse.score - result_low_rmse.score
        expected_diff = 0.7 * (2.0 - 1.0)  # 0.7 * RMSE difference
        assert abs(score_diff - expected_diff) < 0.01


class TestMPCTuner:
    """Test suite for MPCTuner."""

    def test_tuner_initialization(self, thermal_model):
        """Test MPCTuner initialization."""
        tuner = MPCTuner(thermal_model)

        assert tuner.model == thermal_model
        assert tuner.base_config is not None
        assert isinstance(tuner.base_config, MPCConfig)

    def test_tuner_with_custom_config(self, thermal_model):
        """Test MPCTuner with custom base config."""
        custom_config = MPCConfig(
            Np=48,
            Nc=24,
        )

        tuner = MPCTuner(thermal_model, custom_config)

        assert tuner.base_config.Np == 48
        assert tuner.base_config.Nc == 24

    def test_grid_search_returns_results(self, thermal_model, test_scenario):
        """Test that grid search returns non-empty results."""
        tuner = MPCTuner(thermal_model)

        # Small grid for fast test
        param_grid = {
            "w_comfort": [0.7, 0.8],
            "w_energy": [0.15, 0.2],
            "w_smooth": [0.05, 0.1],
        }

        results = tuner.grid_search(test_scenario, param_grid)

        assert len(results) > 0
        assert all(isinstance(r, TuningResult) for r in results)

    def test_grid_search_filters_invalid_weights(self, thermal_model, test_scenario):
        """Test that grid search skips invalid weight combinations."""
        tuner = MPCTuner(thermal_model)

        # Grid with weights that don't sum to ~1.0
        param_grid = {
            "w_comfort": [0.5, 0.9],  # 0.5 won't work with others
            "w_energy": [0.3],
            "w_smooth": [0.3],
        }

        results = tuner.grid_search(test_scenario, param_grid)

        # Only (0.9, 0.3, 0.3) is invalid (sum=1.5)
        # Only valid: none! All should be skipped or normalized
        # After normalization: (0.5,0.3,0.3) → sum=1.1 → normalized
        #                      (0.9,0.3,0.3) → sum=1.5 → normalized
        # Both should pass the 0.95-1.05 check after normalization? No!
        # The code checks sum BEFORE normalization.
        # (0.5, 0.3, 0.3) sums to 1.1 → skipped
        # (0.9, 0.3, 0.3) sums to 1.5 → skipped
        assert len(results) == 0

    def test_grid_search_results_sorted_by_score(self, thermal_model, test_scenario):
        """Test that results are sorted by score (best first)."""
        tuner = MPCTuner(thermal_model)

        param_grid = {
            "w_comfort": [0.6, 0.7, 0.8],
            "w_energy": [0.15, 0.2],
            "w_smooth": [0.05, 0.1],
        }

        results = tuner.grid_search(test_scenario, param_grid)

        # Check that results are sorted by score (ascending)
        scores = [r.score for r in results]
        assert scores == sorted(scores)

    def test_grid_search_with_default_grid(self, thermal_model, test_scenario):
        """Test grid search with default parameter grid."""
        tuner = MPCTuner(thermal_model)

        results = tuner.grid_search(test_scenario)  # No param_grid specified

        # Default grid: 3x3x3 = 27 combinations (some may be filtered)
        assert len(results) > 0
        assert len(results) <= 27

    def test_evaluate_parameters_returns_valid_metrics(self, thermal_model, test_scenario):
        """Test that _evaluate_parameters returns valid metrics."""
        tuner = MPCTuner(thermal_model)

        weights = {
            "w_comfort": 0.7,
            "w_energy": 0.2,
            "w_smooth": 0.1,
        }

        result = tuner._evaluate_parameters(weights, test_scenario)

        assert result.rmse > 0
        assert result.total_energy >= 0
        assert result.smoothness >= 0
        assert result.weights == weights

    def test_evaluate_parameters_rmse_decreases_with_comfort_weight(
        self, thermal_model, test_scenario
    ):
        """Test that higher comfort weight leads to lower RMSE."""
        tuner = MPCTuner(thermal_model)

        # High comfort weight
        weights_high_comfort = {
            "w_comfort": 0.9,
            "w_energy": 0.05,
            "w_smooth": 0.05,
        }

        # Low comfort weight
        weights_low_comfort = {
            "w_comfort": 0.5,
            "w_energy": 0.25,
            "w_smooth": 0.25,
        }

        result_high = tuner._evaluate_parameters(weights_high_comfort, test_scenario)
        result_low = tuner._evaluate_parameters(weights_low_comfort, test_scenario)

        # Higher comfort weight should lead to lower RMSE
        assert result_high.rmse < result_low.rmse

    def test_find_pareto_optimal_returns_subset(self, thermal_model, test_scenario):
        """Test that Pareto optimal set is a subset of all results."""
        tuner = MPCTuner(thermal_model)

        param_grid = {
            "w_comfort": [0.6, 0.7, 0.8],
            "w_energy": [0.15, 0.2],
            "w_smooth": [0.05, 0.1],
        }

        results = tuner.grid_search(test_scenario, param_grid)
        pareto_set = tuner.find_pareto_optimal(results)

        assert len(pareto_set) <= len(results)
        assert all(r in results for r in pareto_set)

    def test_find_pareto_optimal_with_rmse_vs_energy(self, thermal_model, test_scenario):
        """Test Pareto optimal selection with RMSE vs energy objectives."""
        tuner = MPCTuner(thermal_model)

        results = tuner.grid_search(test_scenario)
        pareto_set = tuner.find_pareto_optimal(
            results, objective1="rmse", objective2="total_energy"
        )

        # Pareto set should contain at least the best RMSE and best energy results
        best_rmse = min(results, key=lambda r: r.rmse)
        best_energy = min(results, key=lambda r: r.total_energy)

        assert best_rmse in pareto_set or any(
            r.rmse <= best_rmse.rmse and r.total_energy <= best_rmse.total_energy
            for r in pareto_set
        )

    def test_recommend_parameters_balanced(self, thermal_model, test_scenario):
        """Test parameter recommendation with balanced preference."""
        tuner = MPCTuner(thermal_model)

        results = tuner.grid_search(test_scenario)
        recommended = tuner.recommend_parameters(results, preference="balanced")

        assert "w_comfort" in recommended
        assert "w_energy" in recommended
        assert "w_smooth" in recommended

        # Weights should sum to approximately 1.0
        weight_sum = sum(recommended.values())
        assert abs(weight_sum - 1.0) < 0.01

    def test_recommend_parameters_comfort_priority(self, thermal_model, test_scenario):
        """Test parameter recommendation with comfort priority."""
        tuner = MPCTuner(thermal_model)

        results = tuner.grid_search(test_scenario)
        recommended = tuner.recommend_parameters(results, preference="comfort")

        # Should select result with lowest RMSE
        best_rmse = min(results, key=lambda r: r.rmse)
        assert recommended == best_rmse.weights

    def test_recommend_parameters_energy_priority(self, thermal_model, test_scenario):
        """Test parameter recommendation with energy priority."""
        tuner = MPCTuner(thermal_model)

        results = tuner.grid_search(test_scenario)
        recommended = tuner.recommend_parameters(results, preference="energy")

        # Should select result with lowest energy consumption
        best_energy = min(results, key=lambda r: r.total_energy)
        assert recommended == best_energy.weights

    def test_recommend_parameters_with_empty_results(self, thermal_model):
        """Test parameter recommendation with no results returns defaults."""
        tuner = MPCTuner(thermal_model)

        recommended = tuner.recommend_parameters([], preference="balanced")

        # Should return default weights
        assert recommended == {
            "w_comfort": 0.7,
            "w_energy": 0.2,
            "w_smooth": 0.1,
        }

    def test_tuning_simulation_reaches_setpoint(self, thermal_model, test_scenario):
        """Test that tuning simulation shows temperature approaching setpoint."""
        tuner = MPCTuner(thermal_model)

        weights = {
            "w_comfort": 0.9,  # Very high comfort weight
            "w_energy": 0.05,
            "w_smooth": 0.05,
        }

        result = tuner._evaluate_parameters(weights, test_scenario)

        # With very high comfort weight, RMSE should be relatively low
        # (though exact value depends on model dynamics)
        assert result.rmse < 5.0  # Should track setpoint reasonably well


class TestTunerIntegration:
    """Integration tests for MPC tuner."""

    def test_full_tuning_workflow(self, thermal_model, test_scenario):
        """Test complete tuning workflow from grid search to recommendation."""
        tuner = MPCTuner(thermal_model)

        # 1. Run grid search
        results = tuner.grid_search(test_scenario)
        assert len(results) > 0

        # 2. Find Pareto optimal solutions
        pareto_set = tuner.find_pareto_optimal(results)
        assert len(pareto_set) > 0

        # 3. Get recommendations for different preferences
        balanced = tuner.recommend_parameters(results, "balanced")
        comfort = tuner.recommend_parameters(results, "comfort")
        energy = tuner.recommend_parameters(results, "energy")

        # All should be valid weight dictionaries
        for weights in [balanced, comfort, energy]:
            assert abs(sum(weights.values()) - 1.0) < 0.01

        # All recommendations should be from the result set
        # (When multiple solutions have identical metrics, any can be selected)
        for weights in [balanced, comfort, energy]:
            assert any(
                r.weights == weights for r in results
            ), f"Recommended weights {weights} not in results"
