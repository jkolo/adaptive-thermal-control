"""PWM Controller for ON/OFF valves.

This module implements Pulse Width Modulation (PWM) control for valves that only
support ON/OFF commands (switch.* entities), converting a continuous position
signal (0-100%) into a time-proportioned ON/OFF signal.

For example, with a 30-minute PWM period:
- 65% duty cycle → ON for 19.5 min, OFF for 10.5 min
- 50% duty cycle → ON for 15 min, OFF for 15 min
- 25% duty cycle → ON for 7.5 min, OFF for 22.5 min

This is particularly useful for floor heating systems where thermal inertia
allows for long PWM periods (20-60 minutes) without noticeable temperature
oscillations, while providing much better control than simple ON/OFF switching.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


class PWMController:
    """PWM (Pulse Width Modulation) controller for ON/OFF valves.

    Converts continuous position commands (0-100%) to time-proportioned
    ON/OFF signals suitable for switch-based valve control.

    Attributes:
        hass: Home Assistant instance
        period: PWM period in seconds (default: 1800s = 30 min)
        min_on_time: Minimum ON time to avoid rapid switching (seconds)
        min_off_time: Minimum OFF time to avoid rapid switching (seconds)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        period: float = 1800.0,
        min_on_time: float = 300.0,  # 5 minutes
        min_off_time: float = 300.0,  # 5 minutes
    ) -> None:
        """Initialize PWM controller.

        Args:
            hass: Home Assistant instance
            period: PWM period in seconds (default: 1800 = 30 min)
            min_on_time: Minimum ON time in seconds (prevents rapid cycling)
            min_off_time: Minimum OFF time in seconds (prevents rapid cycling)
        """
        self.hass = hass
        self.period = period
        self.min_on_time = min_on_time
        self.min_off_time = min_off_time

        # Track scheduled tasks per valve
        # Structure: {valve_entity: {"on_cancel": callable, "off_cancel": callable, "duty": float}}
        self._schedules: dict[str, dict[str, Any]] = {}

        _LOGGER.debug(
            "PWM Controller initialized: period=%.1fs (%.1f min), "
            "min_on=%.1fs, min_off=%.1fs",
            self.period,
            self.period / 60.0,
            self.min_on_time,
            self.min_off_time,
        )

    async def set_duty_cycle(
        self,
        valve_entity: str,
        duty_cycle: float,
        valve_delay: float = 0.0,
    ) -> None:
        """Set PWM duty cycle for a valve.

        This method schedules ON and OFF commands for the valve based on the
        requested duty cycle. The duty cycle is the percentage of time the valve
        should be ON during each PWM period.

        Args:
            valve_entity: Entity ID of the valve (must be switch.* domain)
            duty_cycle: Desired duty cycle, 0-100%
                - 0% = always OFF
                - 100% = always ON
                - 50% = ON for half the period, OFF for half
            valve_delay: Time for valve to fully open/close in seconds
                (currently not used, reserved for future enhancement)

        Raises:
            ValueError: If duty_cycle is outside [0, 100] range
            ValueError: If valve_entity is not a switch entity

        Example:
            >>> pwm = PWMController(hass, period=1800)  # 30 min period
            >>> await pwm.set_duty_cycle("switch.living_room_valve", 65.0)
            # Valve will be ON for 19.5 min, OFF for 10.5 min, repeating
        """
        # Validate inputs
        if not 0.0 <= duty_cycle <= 100.0:
            raise ValueError(f"Duty cycle must be 0-100%, got {duty_cycle}")

        domain = valve_entity.split(".")[0]
        if domain != "switch":
            raise ValueError(
                f"PWM controller only supports switch entities, got {domain}"
            )

        _LOGGER.debug(
            "Setting PWM duty cycle for %s: %.1f%% (period=%.1fs)",
            valve_entity,
            duty_cycle,
            self.period,
        )

        # Cancel any existing schedule for this valve
        await self.cancel_schedule(valve_entity)

        # Handle edge cases
        if duty_cycle <= 0.0:
            # Always OFF
            _LOGGER.debug("%s: duty=0%%, turning OFF permanently", valve_entity)
            await self._turn_valve(valve_entity, False)
            return

        if duty_cycle >= 100.0:
            # Always ON
            _LOGGER.debug("%s: duty=100%%, turning ON permanently", valve_entity)
            await self._turn_valve(valve_entity, True)
            return

        # Calculate ON and OFF times
        on_time = (duty_cycle / 100.0) * self.period
        off_time = self.period - on_time

        # Enforce minimum times (prevents rapid switching)
        if on_time < self.min_on_time:
            _LOGGER.warning(
                "%s: ON time %.1fs < min %.1fs, extending period",
                valve_entity,
                on_time,
                self.min_on_time,
            )
            on_time = self.min_on_time

        if off_time < self.min_off_time:
            _LOGGER.warning(
                "%s: OFF time %.1fs < min %.1fs, extending period",
                valve_entity,
                off_time,
                self.min_off_time,
            )
            off_time = self.min_off_time

        _LOGGER.info(
            "%s: PWM cycle starting: ON=%.1fs (%.1fmin), OFF=%.1fs (%.1fmin)",
            valve_entity,
            on_time,
            on_time / 60.0,
            off_time,
            off_time / 60.0,
        )

        # Start the PWM cycle
        await self._start_pwm_cycle(valve_entity, on_time, off_time, duty_cycle)

    async def _start_pwm_cycle(
        self,
        valve_entity: str,
        on_time: float,
        off_time: float,
        duty_cycle: float,
    ) -> None:
        """Start a PWM cycle for a valve.

        Args:
            valve_entity: Entity ID of the valve
            on_time: Time to keep valve ON (seconds)
            off_time: Time to keep valve OFF (seconds)
            duty_cycle: Original duty cycle for tracking
        """
        # Turn valve ON immediately
        await self._turn_valve(valve_entity, True)

        # Schedule OFF command after on_time
        now = dt_util.utcnow()
        off_time_point = now + timedelta(seconds=on_time)

        # Create cancel token for OFF command
        off_cancel = async_track_point_in_time(
            self.hass,
            lambda _: asyncio.create_task(
                self._handle_off_event(valve_entity, off_time, duty_cycle)
            ),
            off_time_point,
        )

        # Store schedule
        self._schedules[valve_entity] = {
            "on_cancel": None,  # ON already executed
            "off_cancel": off_cancel,
            "duty": duty_cycle,
            "on_time": on_time,
            "off_time": off_time,
        }

        _LOGGER.debug(
            "%s: PWM cycle scheduled - OFF at %s (in %.1fs)",
            valve_entity,
            off_time_point.strftime("%H:%M:%S"),
            on_time,
        )

    async def _handle_off_event(
        self, valve_entity: str, off_time: float, duty_cycle: float
    ) -> None:
        """Handle the OFF event in PWM cycle.

        This is called when it's time to turn the valve OFF. After turning
        it OFF, we schedule the next ON event to continue the PWM cycle.

        Args:
            valve_entity: Entity ID of the valve
            off_time: Time to keep valve OFF (seconds)
            duty_cycle: Original duty cycle (for next cycle)
        """
        # Turn valve OFF
        await self._turn_valve(valve_entity, False)

        # Schedule next ON command after off_time
        now = dt_util.utcnow()
        on_time_point = now + timedelta(seconds=off_time)

        # Get ON time from stored schedule
        schedule = self._schedules.get(valve_entity, {})
        on_time = schedule.get("on_time", 0.0)

        # Create cancel token for ON command
        on_cancel = async_track_point_in_time(
            self.hass,
            lambda _: asyncio.create_task(
                self._handle_on_event(valve_entity, on_time, off_time, duty_cycle)
            ),
            on_time_point,
        )

        # Update schedule
        if valve_entity in self._schedules:
            self._schedules[valve_entity]["on_cancel"] = on_cancel
            self._schedules[valve_entity]["off_cancel"] = None

        _LOGGER.debug(
            "%s: PWM OFF complete - next ON at %s (in %.1fs)",
            valve_entity,
            on_time_point.strftime("%H:%M:%S"),
            off_time,
        )

    async def _handle_on_event(
        self,
        valve_entity: str,
        on_time: float,
        off_time: float,
        duty_cycle: float,
    ) -> None:
        """Handle the ON event in PWM cycle.

        This is called when it's time to turn the valve ON again, starting
        a new PWM cycle.

        Args:
            valve_entity: Entity ID of the valve
            on_time: Time to keep valve ON (seconds)
            off_time: Time to keep valve OFF (seconds)
            duty_cycle: Original duty cycle
        """
        # Start a new PWM cycle
        await self._start_pwm_cycle(valve_entity, on_time, off_time, duty_cycle)

    async def _turn_valve(self, valve_entity: str, state: bool) -> None:
        """Turn valve ON or OFF.

        Args:
            valve_entity: Entity ID of the valve
            state: True for ON, False for OFF
        """
        service = "turn_on" if state else "turn_off"

        try:
            await self.hass.services.async_call(
                "switch",
                service,
                {"entity_id": valve_entity},
                blocking=True,
            )
            _LOGGER.debug(
                "%s: Valve turned %s", valve_entity, "ON" if state else "OFF"
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to turn %s %s: %s",
                valve_entity,
                "ON" if state else "OFF",
                err,
            )

    async def cancel_schedule(self, valve_entity: str) -> None:
        """Cancel PWM schedule for a valve.

        This cancels any pending ON/OFF commands and stops the PWM cycle.

        Args:
            valve_entity: Entity ID of the valve
        """
        if valve_entity not in self._schedules:
            return

        schedule = self._schedules[valve_entity]

        # Cancel pending ON command
        if schedule.get("on_cancel"):
            schedule["on_cancel"]()
            _LOGGER.debug("%s: Cancelled pending ON command", valve_entity)

        # Cancel pending OFF command
        if schedule.get("off_cancel"):
            schedule["off_cancel"]()
            _LOGGER.debug("%s: Cancelled pending OFF command", valve_entity)

        # Remove from schedules
        del self._schedules[valve_entity]
        _LOGGER.debug("%s: PWM schedule cancelled", valve_entity)

    async def cancel_all_schedules(self) -> None:
        """Cancel all PWM schedules (cleanup on shutdown)."""
        valve_entities = list(self._schedules.keys())
        for valve_entity in valve_entities:
            await self.cancel_schedule(valve_entity)

        _LOGGER.info("All PWM schedules cancelled")

    def get_schedule(self, valve_entity: str) -> dict[str, Any] | None:
        """Get current PWM schedule for a valve.

        Returns:
            Dictionary with schedule info, or None if no schedule exists
            Keys: "duty", "on_time", "off_time", "on_cancel", "off_cancel"
        """
        return self._schedules.get(valve_entity)

    def get_all_schedules(self) -> dict[str, dict[str, Any]]:
        """Get all PWM schedules.

        Returns:
            Dictionary mapping valve_entity to schedule info
        """
        return self._schedules.copy()
