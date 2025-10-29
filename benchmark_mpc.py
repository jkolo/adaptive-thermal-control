"""Benchmark script for MPC controller performance (T3.4.3).

Measures:
- MPC optimization time per cycle
- Bottlenecks via cProfile
- Memory usage
- Scalability (1 to 20 rooms)

Target: < 2s for 1 room, < 5s for 20 rooms
"""

import cProfile
import io
import pstats
import time
from statistics import mean, stdev

import numpy as np

from custom_components.adaptive_thermal_control.forecast_provider import (
    ForecastProvider,
)
from custom_components.adaptive_thermal_control.mpc_controller import (
    MPCConfig,
    MPCController,
)
from custom_components.adaptive_thermal_control.thermal_model import (
    ThermalModel,
    ThermalModelParameters,
)


def benchmark_single_mpc_cycle(
    n_iterations: int = 100,
) -> tuple[list[float], dict]:
    """Benchmark single MPC optimization cycle.

    Args:
        n_iterations: Number of iterations to run

    Returns:
        Tuple of (execution times, statistics dict)
    """
    # Create thermal model
    params = ThermalModelParameters(R=0.0025, C=4.5e6)
    model = ThermalModel(params=params, dt=600.0)

    # Create MPC controller
    config = MPCConfig(
        Np=24,  # 4 hours
        Nc=12,  # 2 hours
        dt=600.0,
        u_min=0.0,
        u_max=2000.0,
        du_max=500.0,
        w_comfort=1.0,
        w_energy=0.1,
        w_smooth=0.05,
    )
    mpc = MPCController(model=model, config=config)

    # Create forecast
    T_outdoor_forecast = np.linspace(10.0, 12.0, config.Np)

    # Warm up (JIT compilation, cache loading)
    for _ in range(3):
        mpc.compute_control(
            T_current=18.0,
            T_setpoint=21.0,
            T_outdoor_forecast=T_outdoor_forecast,
        )

    # Benchmark iterations
    times = []
    for i in range(n_iterations):
        # Vary conditions slightly to avoid caching
        T_current = 18.0 + np.random.randn() * 0.5
        T_setpoint = 21.0 + np.random.randn() * 0.2
        T_outdoor = T_outdoor_forecast + np.random.randn(config.Np) * 0.5

        start = time.perf_counter()
        result = mpc.compute_control(
            T_current=T_current,
            T_setpoint=T_setpoint,
            T_outdoor_forecast=T_outdoor,
        )
        elapsed = time.perf_counter() - start

        times.append(elapsed)

        if not result.success:
            print(f"⚠️  Iteration {i} failed: {result.message}")

    # Calculate statistics
    stats = {
        "mean": mean(times),
        "stdev": stdev(times) if len(times) > 1 else 0.0,
        "min": min(times),
        "max": max(times),
        "p50": np.percentile(times, 50),
        "p95": np.percentile(times, 95),
        "p99": np.percentile(times, 99),
    }

    return times, stats


def benchmark_with_profiling(n_iterations: int = 20):
    """Run benchmark with cProfile to identify bottlenecks.

    Args:
        n_iterations: Number of iterations to profile
    """
    # Setup
    params = ThermalModelParameters(R=0.0025, C=4.5e6)
    model = ThermalModel(params=params, dt=600.0)

    config = MPCConfig(
        Np=24,
        Nc=12,
        dt=600.0,
        u_min=0.0,
        u_max=2000.0,
        du_max=500.0,
    )
    mpc = MPCController(model=model, config=config)

    T_outdoor_forecast = np.linspace(10.0, 12.0, config.Np)

    # Profile
    profiler = cProfile.Profile()
    profiler.enable()

    for _ in range(n_iterations):
        mpc.compute_control(
            T_current=18.0 + np.random.randn() * 0.5,
            T_setpoint=21.0,
            T_outdoor_forecast=T_outdoor_forecast + np.random.randn(config.Np) * 0.5,
        )

    profiler.disable()

    # Print results
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats(20)  # Top 20 functions

    return s.getvalue()


def benchmark_scalability(max_rooms: int = 10):
    """Benchmark MPC scalability with multiple rooms.

    Args:
        max_rooms: Maximum number of rooms to test

    Returns:
        Dict mapping number of rooms to execution time
    """
    results = {}

    for n_rooms in [1, 2, 5, 10, 20] if max_rooms >= 20 else [1, 2, 5, 10]:
        if n_rooms > max_rooms:
            break

        # Simulate n rooms (each with independent MPC)
        total_time = 0.0

        for room_id in range(n_rooms):
            params = ThermalModelParameters(
                R=0.0025 + np.random.randn() * 0.0002,  # Slight variation
                C=4.5e6 + np.random.randn() * 0.5e6,
            )
            model = ThermalModel(params=params, dt=600.0)

            config = MPCConfig(Np=24, Nc=12, dt=600.0)
            mpc = MPCController(model=model, config=config)

            T_outdoor_forecast = np.linspace(10.0, 12.0, config.Np)

            start = time.perf_counter()
            mpc.compute_control(
                T_current=18.0 + np.random.randn(),
                T_setpoint=21.0,
                T_outdoor_forecast=T_outdoor_forecast,
            )
            elapsed = time.perf_counter() - start

            total_time += elapsed

        results[n_rooms] = total_time

        # Check target
        target = 2.0 if n_rooms == 1 else 5.0
        status = "✓" if total_time < target else "✗"
        print(f"{status} {n_rooms:2d} rooms: {total_time:.3f}s (target: <{target}s)")

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("MPC Controller Benchmark (T3.4.3)")
    print("=" * 70)

    # Benchmark 1: Single cycle performance
    print("\n1. Single MPC Cycle Performance (100 iterations)")
    print("-" * 70)
    times, stats = benchmark_single_mpc_cycle(n_iterations=100)

    print(f"Mean:   {stats['mean']*1000:.2f}ms")
    print(f"Stdev:  {stats['stdev']*1000:.2f}ms")
    print(f"Min:    {stats['min']*1000:.2f}ms")
    print(f"Max:    {stats['max']*1000:.2f}ms")
    print(f"p50:    {stats['p50']*1000:.2f}ms (median)")
    print(f"p95:    {stats['p95']*1000:.2f}ms")
    print(f"p99:    {stats['p99']*1000:.2f}ms")

    # Target check
    if stats["p95"] < 2.0:
        print(f"\n✓ Target achieved: p95={stats['p95']:.3f}s < 2.0s")
    else:
        print(f"\n✗ Target missed: p95={stats['p95']:.3f}s > 2.0s")

    # Benchmark 2: Profiling
    print("\n2. Profiling (Top 20 functions)")
    print("-" * 70)
    profile_output = benchmark_with_profiling(n_iterations=20)
    print(profile_output)

    # Benchmark 3: Scalability
    print("\n3. Scalability Test")
    print("-" * 70)
    scalability_results = benchmark_scalability(max_rooms=20)

    print("\n" + "=" * 70)
    print("Benchmark Complete")
    print("=" * 70)
