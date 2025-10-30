"""Tests for MPC failsafe mechanism (T3.6.1)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from custom_components.adaptive_thermal_control.climate import (
    AdaptiveThermalClimate,
)
from custom_components.adaptive_thermal_control.const import (
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_ENTITY,
    CONF_VALVE_ENTITIES,
    MPC_MAX_FAILURES,
    MPC_SUCCESS_COUNT_TO_RECOVER,
    MPC_TIMEOUT,
)
from custom_components.adaptive_thermal_control.mpc_controller import MPCResult
from custom_components.adaptive_thermal_control.thermal_model import (
    ThermalModel,
    ThermalModelParameters,
)


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock()
    hass.loop = asyncio.get_event_loop()
    hass.services = AsyncMock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def mock_coordinator():
    """Create mock coordinator."""
    coordinator = MagicMock()
    coordinator.forecast_provider = AsyncMock()
    coordinator.forecast_provider.get_outdoor_temperature_forecast = AsyncMock(
        return_value=[10.0] * 24
    )

    # Mock thermal model
    params = ThermalModelParameters(R=0.0025, C=4.5e6)
    thermal_model = ThermalModel(params=params, dt=600.0)
    coordinator.get_thermal_model = Mock(return_value=thermal_model)

    return coordinator


@pytest.fixture
def climate_entity(mock_hass, mock_coordinator):
    """Create climate entity for testing."""
    config = {
        CONF_ROOM_NAME: "Test Room",
        CONF_ROOM_TEMP_ENTITY: "sensor.test_room_temp",
        CONF_VALVE_ENTITIES: ["climate.test_valve"],
    }

    entity = AdaptiveThermalClimate(
        hass=mock_hass,
        coordinator=mock_coordinator,
        config=config,
        unique_id="test_room_thermostat",
    )
    entity._attr_current_temperature = 20.0
    entity._attr_target_temperature = 21.0

    return entity


class TestFailsafeMechanism:
    """Test suite for MPC failsafe mechanism (T3.6.1)."""

    @pytest.mark.asyncio
    async def test_mpc_timeout_protection(self, climate_entity, mock_coordinator):
        """Test that MPC times out if computation takes too long."""
        # Create a mock MPC controller that takes too long
        mock_mpc = MagicMock()

        def slow_compute(*args, **kwargs):
            import time
            time.sleep(MPC_TIMEOUT + 1)  # Sleep longer than timeout
            return MPCResult(
                u_optimal=[50.0],
                u_first=50.0,
                cost=10.0,
                success=True,
                message="Success",
                iterations=10,
            )

        mock_mpc.compute_control = slow_compute
        climate_entity._mpc_controller = mock_mpc

        # Get thermal model
        thermal_model = mock_coordinator.get_thermal_model("climate.test_room")

        # Call MPC control - should timeout
        await climate_entity._async_control_with_mpc(thermal_model)

        # Verify that failsafe was triggered
        assert climate_entity._mpc_failure_count == 1
        assert climate_entity._mpc_status == "degraded"
        assert "Timeout" in climate_entity._mpc_last_failure_reason

    @pytest.mark.asyncio
    async def test_failure_counter_increases(self, climate_entity, mock_coordinator):
        """Test that failure counter increments on consecutive failures."""
        # Mock MPC controller that always fails
        mock_mpc = MagicMock()
        mock_mpc.compute_control = Mock(
            return_value=MPCResult(
                u_optimal=[0.0],
                u_first=0.0,
                cost=0.0,
                success=False,
                message="Optimization failed",
                iterations=0,
            )
        )
        climate_entity._mpc_controller = mock_mpc

        thermal_model = mock_coordinator.get_thermal_model("climate.test_room")

        # Fail 3 times
        for i in range(MPC_MAX_FAILURES):
            await climate_entity._async_control_with_mpc(thermal_model)
            assert climate_entity._mpc_failure_count == i + 1

        # After 3 failures, should be permanently disabled
        assert climate_entity._mpc_permanently_disabled is True
        assert climate_entity._mpc_status == "disabled"

    @pytest.mark.asyncio
    async def test_permanent_fallback_after_max_failures(
        self, climate_entity, mock_coordinator
    ):
        """Test that MPC is permanently disabled after max failures."""
        # Mock failing MPC
        mock_mpc = MagicMock()
        mock_mpc.compute_control = Mock(
            return_value=MPCResult(
                u_optimal=[0.0],
                u_first=0.0,
                cost=0.0,
                success=False,
                message="Optimization failed",
                iterations=0,
            )
        )
        climate_entity._mpc_controller = mock_mpc

        thermal_model = mock_coordinator.get_thermal_model("climate.test_room")

        # Fail max times
        for _ in range(MPC_MAX_FAILURES):
            await climate_entity._async_control_with_mpc(thermal_model)

        # Verify permanent disable
        assert climate_entity._mpc_permanently_disabled is True
        assert climate_entity._mpc_status == "disabled"

        # Verify notification was sent
        assert climate_entity.hass.services.async_call.called
        call_args = climate_entity.hass.services.async_call.call_args_list[-1]
        assert call_args[0][0] == "persistent_notification"
        assert call_args[0][1] == "create"
        assert "MPC Disabled" in call_args[0][2]["title"]

    @pytest.mark.asyncio
    async def test_automatic_recovery_after_successes(
        self, climate_entity, mock_coordinator
    ):
        """Test that MPC recovers after consecutive successes."""
        # Mock successful MPC
        mock_mpc = MagicMock()
        mock_mpc.compute_control = Mock(
            return_value=MPCResult(
                u_optimal=[50.0] * 12,
                u_first=50.0,
                cost=10.0,
                success=True,
                message="Success",
                iterations=10,
            )
        )
        climate_entity._mpc_controller = mock_mpc

        # Start in degraded state
        climate_entity._mpc_status = "degraded"
        climate_entity._mpc_failure_count = 0
        climate_entity._mpc_success_count = 0

        thermal_model = mock_coordinator.get_thermal_model("climate.test_room")

        # Succeed required number of times
        for i in range(MPC_SUCCESS_COUNT_TO_RECOVER):
            await climate_entity._async_control_with_mpc(thermal_model)

            if i < MPC_SUCCESS_COUNT_TO_RECOVER - 1:
                # Still degraded
                assert climate_entity._mpc_status == "degraded"
            else:
                # Should recover
                assert climate_entity._mpc_status == "active"
                assert climate_entity._mpc_success_count == 0  # Reset counter

    @pytest.mark.asyncio
    async def test_failure_resets_success_counter(
        self, climate_entity, mock_coordinator
    ):
        """Test that a failure resets the success counter."""
        # Mock MPC that succeeds then fails
        mock_mpc = MagicMock()
        climate_entity._mpc_controller = mock_mpc

        thermal_model = mock_coordinator.get_thermal_model("climate.test_room")

        # Start with some successes
        mock_mpc.compute_control = Mock(
            return_value=MPCResult(
                u_optimal=[50.0] * 12,
                u_first=50.0,
                cost=10.0,
                success=True,
                message="Success",
                iterations=10,
            )
        )

        for _ in range(3):
            await climate_entity._async_control_with_mpc(thermal_model)

        assert climate_entity._mpc_success_count == 3

        # Now fail once
        mock_mpc.compute_control = Mock(
            return_value=MPCResult(
                u_optimal=[0.0],
                u_first=0.0,
                cost=0.0,
                success=False,
                message="Optimization failed",
                iterations=0,
            )
        )

        await climate_entity._async_control_with_mpc(thermal_model)

        # Success counter should be reset
        assert climate_entity._mpc_success_count == 0
        assert climate_entity._mpc_failure_count == 1

    @pytest.mark.asyncio
    async def test_persistent_notification_on_first_failure(
        self, climate_entity, mock_coordinator
    ):
        """Test that notification is sent on first failure."""
        # Mock failing MPC
        mock_mpc = MagicMock()
        mock_mpc.compute_control = Mock(
            return_value=MPCResult(
                u_optimal=[0.0],
                u_first=0.0,
                cost=0.0,
                success=False,
                message="Optimization failed",
                iterations=0,
            )
        )
        climate_entity._mpc_controller = mock_mpc

        thermal_model = mock_coordinator.get_thermal_model("climate.test_room")

        # First failure
        await climate_entity._async_control_with_mpc(thermal_model)

        # Verify notification was sent
        assert climate_entity.hass.services.async_call.called
        call_args = climate_entity.hass.services.async_call.call_args
        assert call_args[0][0] == "persistent_notification"
        assert call_args[0][1] == "create"
        assert "MPC Degraded" in call_args[0][2]["title"]

    @pytest.mark.asyncio
    async def test_forecast_failure_triggers_failsafe(
        self, climate_entity, mock_coordinator
    ):
        """Test that forecast failures trigger failsafe."""
        # Make forecast fail
        mock_coordinator.forecast_provider.get_outdoor_temperature_forecast.side_effect = Exception(
            "Forecast unavailable"
        )

        thermal_model = mock_coordinator.get_thermal_model("climate.test_room")

        # Call MPC control
        await climate_entity._async_control_with_mpc(thermal_model)

        # Verify failsafe triggered
        assert climate_entity._mpc_failure_count == 1
        assert "Forecast failed" in climate_entity._mpc_last_failure_reason

    @pytest.mark.asyncio
    async def test_mpc_status_attribute_exposed(self, climate_entity):
        """Test that MPC status is exposed as entity attribute."""
        attrs = climate_entity.extra_state_attributes

        assert "mpc_status" in attrs
        assert "mpc_failure_count" in attrs
        assert "mpc_last_failure_reason" in attrs

        assert attrs["mpc_status"] == "active"
        assert attrs["mpc_failure_count"] == 0
        assert attrs["mpc_last_failure_reason"] is None

    @pytest.mark.asyncio
    async def test_retry_after_interval(self, climate_entity, mock_coordinator):
        """Test that MPC retries after retry interval."""
        import time
        from custom_components.adaptive_thermal_control.const import MPC_RETRY_INTERVAL

        # Set to permanently disabled
        climate_entity._mpc_permanently_disabled = True
        climate_entity._mpc_status = "disabled"
        climate_entity._mpc_last_failure_time = time.time() - MPC_RETRY_INTERVAL - 1

        thermal_model = mock_coordinator.get_thermal_model("climate.test_room")

        # Mock successful MPC
        mock_mpc = MagicMock()
        mock_mpc.compute_control = Mock(
            return_value=MPCResult(
                u_optimal=[50.0] * 12,
                u_first=50.0,
                cost=10.0,
                success=True,
                message="Success",
                iterations=10,
            )
        )
        climate_entity._mpc_controller = mock_mpc

        # Call MPC - should retry
        await climate_entity._async_control_with_mpc(thermal_model)

        # Should be re-enabled
        assert climate_entity._mpc_permanently_disabled is False
        assert climate_entity._mpc_failure_count == 0
        assert climate_entity._mpc_status == "active"
