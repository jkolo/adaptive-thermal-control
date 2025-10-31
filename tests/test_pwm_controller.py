"""Tests for PWM Controller (T4.5.4)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.adaptive_thermal_control.pwm_controller import PWMController


@pytest.fixture
def hass_mock():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def pwm_controller(hass_mock):
    """Create a PWM controller instance."""
    return PWMController(
        hass=hass_mock,
        period=1800.0,  # 30 minutes
        min_on_time=300.0,  # 5 minutes
        min_off_time=300.0,  # 5 minutes
    )


@pytest.mark.asyncio
async def test_pwm_initialization(pwm_controller):
    """Test PWM controller initialization."""
    assert pwm_controller.period == 1800.0
    assert pwm_controller.min_on_time == 300.0
    assert pwm_controller.min_off_time == 300.0
    assert len(pwm_controller._schedules) == 0


@pytest.mark.asyncio
async def test_pwm_duty_cycle_zero(hass_mock):
    """Test that 0% duty cycle turns valve permanently OFF."""
    pwm = PWMController(hass_mock, period=1800.0)

    await pwm.set_duty_cycle("switch.test_valve", 0.0)

    # Should have called turn_off once
    hass_mock.services.async_call.assert_called_once_with(
        "switch",
        "turn_off",
        {"entity_id": "switch.test_valve"},
        blocking=True,
    )

    # No schedule should be created
    assert len(pwm._schedules) == 0


@pytest.mark.asyncio
async def test_pwm_duty_cycle_hundred(hass_mock):
    """Test that 100% duty cycle turns valve permanently ON."""
    pwm = PWMController(hass_mock, period=1800.0)

    await pwm.set_duty_cycle("switch.test_valve", 100.0)

    # Should have called turn_on once
    hass_mock.services.async_call.assert_called_once_with(
        "switch",
        "turn_on",
        {"entity_id": "switch.test_valve"},
        blocking=True,
    )

    # No schedule should be created
    assert len(pwm._schedules) == 0


@pytest.mark.asyncio
async def test_pwm_duty_cycle_fifty_percent(hass_mock):
    """Test that 50% duty cycle creates proper schedule."""
    pwm = PWMController(hass_mock, period=1800.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()  # Cancel function

        await pwm.set_duty_cycle("switch.test_valve", 50.0)

        # Should turn valve ON immediately
        assert hass_mock.services.async_call.call_count == 1
        hass_mock.services.async_call.assert_called_with(
            "switch",
            "turn_on",
            {"entity_id": "switch.test_valve"},
            blocking=True,
        )

        # Should have scheduled OFF command
        assert mock_track.call_count == 1

        # Should have created schedule
        assert "switch.test_valve" in pwm._schedules
        schedule = pwm._schedules["switch.test_valve"]
        assert schedule["duty"] == 50.0
        assert schedule["on_time"] == 900.0  # 50% of 1800s
        assert schedule["off_time"] == 900.0


@pytest.mark.asyncio
async def test_pwm_duty_cycle_calculation(hass_mock):
    """Test that duty cycle calculations are correct."""
    pwm = PWMController(hass_mock, period=1800.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()

        # Test 65% duty cycle
        await pwm.set_duty_cycle("switch.test_valve", 65.0)

        schedule = pwm._schedules["switch.test_valve"]
        assert schedule["on_time"] == pytest.approx(1170.0, abs=0.1)  # 65% of 1800
        assert schedule["off_time"] == pytest.approx(630.0, abs=0.1)  # 35% of 1800


@pytest.mark.asyncio
async def test_pwm_minimum_on_time_enforcement(hass_mock):
    """Test that minimum ON time is enforced."""
    pwm = PWMController(hass_mock, period=1800.0, min_on_time=300.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()

        # 10% duty cycle = 180s ON time, but min is 300s
        await pwm.set_duty_cycle("switch.test_valve", 10.0)

        schedule = pwm._schedules["switch.test_valve"]
        assert schedule["on_time"] >= 300.0  # Should be enforced to minimum


@pytest.mark.asyncio
async def test_pwm_minimum_off_time_enforcement(hass_mock):
    """Test that minimum OFF time is enforced."""
    pwm = PWMController(hass_mock, period=1800.0, min_off_time=300.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()

        # 95% duty cycle = 90s OFF time, but min is 300s
        await pwm.set_duty_cycle("switch.test_valve", 95.0)

        schedule = pwm._schedules["switch.test_valve"]
        assert schedule["off_time"] >= 300.0  # Should be enforced to minimum


@pytest.mark.asyncio
async def test_pwm_cancel_existing_schedule(hass_mock):
    """Test that setting new duty cycle cancels existing schedule."""
    pwm = PWMController(hass_mock, period=1800.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_cancel_1 = MagicMock()
        mock_cancel_2 = MagicMock()
        mock_track.side_effect = [mock_cancel_1, mock_cancel_2]

        # Set first duty cycle
        await pwm.set_duty_cycle("switch.test_valve", 50.0)

        # Set second duty cycle (should cancel first)
        await pwm.set_duty_cycle("switch.test_valve", 70.0)

        # First cancel should have been called
        mock_cancel_1.assert_called_once()

        # Should have new schedule
        schedule = pwm._schedules["switch.test_valve"]
        assert schedule["duty"] == 70.0


@pytest.mark.asyncio
async def test_pwm_invalid_duty_cycle():
    """Test that invalid duty cycle raises ValueError."""
    hass_mock = MagicMock()
    pwm = PWMController(hass_mock, period=1800.0)

    with pytest.raises(ValueError, match="Duty cycle must be 0-100%"):
        await pwm.set_duty_cycle("switch.test_valve", 150.0)

    with pytest.raises(ValueError, match="Duty cycle must be 0-100%"):
        await pwm.set_duty_cycle("switch.test_valve", -10.0)


@pytest.mark.asyncio
async def test_pwm_invalid_entity_domain():
    """Test that non-switch entity raises ValueError."""
    hass_mock = MagicMock()
    pwm = PWMController(hass_mock, period=1800.0)

    with pytest.raises(ValueError, match="PWM controller only supports switch entities"):
        await pwm.set_duty_cycle("number.test_valve", 50.0)


@pytest.mark.asyncio
async def test_pwm_cancel_schedule(hass_mock):
    """Test manual schedule cancellation."""
    pwm = PWMController(hass_mock, period=1800.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_cancel_off = MagicMock()
        mock_track.return_value = mock_cancel_off

        # Create schedule
        await pwm.set_duty_cycle("switch.test_valve", 50.0)

        assert "switch.test_valve" in pwm._schedules

        # Cancel schedule
        await pwm.cancel_schedule("switch.test_valve")

        # Cancel function should have been called
        mock_cancel_off.assert_called_once()

        # Schedule should be removed
        assert "switch.test_valve" not in pwm._schedules


@pytest.mark.asyncio
async def test_pwm_cancel_all_schedules(hass_mock):
    """Test cancelling all schedules."""
    pwm = PWMController(hass_mock, period=1800.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_cancel_1 = MagicMock()
        mock_cancel_2 = MagicMock()
        mock_track.side_effect = [mock_cancel_1, mock_cancel_2]

        # Create two schedules
        await pwm.set_duty_cycle("switch.valve1", 50.0)
        await pwm.set_duty_cycle("switch.valve2", 70.0)

        assert len(pwm._schedules) == 2

        # Cancel all
        await pwm.cancel_all_schedules()

        # Both cancel functions should have been called
        mock_cancel_1.assert_called_once()
        mock_cancel_2.assert_called_once()

        # No schedules should remain
        assert len(pwm._schedules) == 0


@pytest.mark.asyncio
async def test_pwm_get_schedule(hass_mock):
    """Test retrieving schedule information."""
    pwm = PWMController(hass_mock, period=1800.0)

    # No schedule initially
    assert pwm.get_schedule("switch.test_valve") is None

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()

        await pwm.set_duty_cycle("switch.test_valve", 60.0)

        # Get schedule
        schedule = pwm.get_schedule("switch.test_valve")
        assert schedule is not None
        assert schedule["duty"] == 60.0
        assert schedule["on_time"] == pytest.approx(1080.0, abs=0.1)
        assert schedule["off_time"] == pytest.approx(720.0, abs=0.1)


@pytest.mark.asyncio
async def test_pwm_get_all_schedules(hass_mock):
    """Test retrieving all schedules."""
    pwm = PWMController(hass_mock, period=1800.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()

        await pwm.set_duty_cycle("switch.valve1", 50.0)
        await pwm.set_duty_cycle("switch.valve2", 75.0)

        all_schedules = pwm.get_all_schedules()
        assert len(all_schedules) == 2
        assert "switch.valve1" in all_schedules
        assert "switch.valve2" in all_schedules
        assert all_schedules["switch.valve1"]["duty"] == 50.0
        assert all_schedules["switch.valve2"]["duty"] == 75.0


@pytest.mark.asyncio
async def test_pwm_service_call_failure(hass_mock):
    """Test PWM handles service call failures gracefully."""
    hass_mock.services.async_call = AsyncMock(side_effect=Exception("Service failed"))
    pwm = PWMController(hass_mock, period=1800.0)

    # Should not raise exception, just log error
    await pwm.set_duty_cycle("switch.test_valve", 100.0)

    # Verify service was attempted
    hass_mock.services.async_call.assert_called_once()


@pytest.mark.asyncio
async def test_pwm_multiple_valves_independent(hass_mock):
    """Test that multiple valves have independent schedules."""
    pwm = PWMController(hass_mock, period=1800.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()

        # Set different duty cycles for different valves
        await pwm.set_duty_cycle("switch.valve1", 30.0)
        await pwm.set_duty_cycle("switch.valve2", 70.0)

        schedule1 = pwm.get_schedule("switch.valve1")
        schedule2 = pwm.get_schedule("switch.valve2")

        assert schedule1["duty"] == 30.0
        assert schedule2["duty"] == 70.0
        assert schedule1["on_time"] == pytest.approx(540.0, abs=0.1)  # 30% of 1800
        assert schedule2["on_time"] == pytest.approx(1260.0, abs=0.1)  # 70% of 1800


@pytest.mark.asyncio
async def test_pwm_custom_period(hass_mock):
    """Test PWM with custom period (60 minutes)."""
    pwm = PWMController(hass_mock, period=3600.0)  # 60 minutes

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()

        await pwm.set_duty_cycle("switch.test_valve", 50.0)

        schedule = pwm.get_schedule("switch.test_valve")
        assert schedule["on_time"] == 1800.0  # 50% of 3600
        assert schedule["off_time"] == 1800.0


@pytest.mark.asyncio
async def test_pwm_short_period(hass_mock):
    """Test PWM with short period (10 minutes)."""
    pwm = PWMController(hass_mock, period=600.0, min_on_time=60.0, min_off_time=60.0)

    with patch(
        "custom_components.adaptive_thermal_control.pwm_controller.async_track_point_in_time"
    ) as mock_track:
        mock_track.return_value = MagicMock()

        await pwm.set_duty_cycle("switch.test_valve", 50.0)

        schedule = pwm.get_schedule("switch.test_valve")
        assert schedule["on_time"] == 300.0  # 50% of 600
        assert schedule["off_time"] == 300.0
