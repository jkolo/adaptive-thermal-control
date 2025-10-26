# Coding Standards for Home Assistant Integration

## Table of Contents
1. [Introduction](#introduction)
2. [Integration Quality Scale](#integration-quality-scale)
3. [Architecture & Design Patterns](#architecture--design-patterns)
4. [File Structure](#file-structure)
5. [Coding Standards](#coding-standards)
6. [Climate Entity Implementation](#climate-entity-implementation)
7. [Testing Standards](#testing-standards)
8. [Documentation Requirements](#documentation-requirements)
9. [Best Practices Checklist](#best-practices-checklist)

---

## Introduction

This document defines the coding standards for the Adaptive Thermal Control integration for Home Assistant. The standards are based on official Home Assistant developer documentation and best practices from the Home Assistant core project.

**Key References:**
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Climate Entity Documentation](https://developers.home-assistant.io/docs/core/entity/climate/)

---

## Integration Quality Scale

Home Assistant uses a four-tier quality scale to grade integrations. Our target is **Gold Tier** for production release.

### Bronze Tier (Minimum Baseline)
**All new integrations must meet these requirements:**

- ✅ UI-based setup (config flow)
- ✅ Source code adheres to basic coding standards
- ✅ Automated tests demonstrating proper configuration
- ✅ Basic end-user documentation

### Silver Tier (Reliability & Robustness)
**Enhancements for stable user experience:**

- ✅ One or more active code owners
- ✅ Automatic recovery from connection errors or offline devices
- ✅ Automatic re-authentication on failure
- ✅ No log spam on errors
- ✅ Comprehensive feature documentation with troubleshooting

### Gold Tier (Excellence - Our Target)
**Professional-grade integration:**

- ✅ Automatic device discovery
- ✅ Logical, translatable entity names
- ✅ Full automated test coverage
- ✅ Extensive non-technical user documentation
- ✅ UI reconfiguration support
- ✅ Diagnostic tools and troubleshooting guides
- ✅ Full type annotations
- ✅ Fully asynchronous codebase

---

## Architecture & Design Patterns

### Core Principles

Home Assistant is designed as a **modular embedded system**, not just an application. Integrations should:

1. **Operate as loosely-coupled modules** that function independently
2. **Prioritize consumer-grade usability** with intuitive onboarding
3. **Follow the event loop architecture** - never block the main thread
4. **Separate concerns** between data fetching, state management, and UI

### System Layers

```
┌─────────────────────────────────────┐
│         User Interface (UI)         │
│    (Config Flow, Entity Cards)      │
├─────────────────────────────────────┤
│      Integration Layer (Core)       │
│   (Coordinator, Entities, Services) │
├─────────────────────────────────────┤
│        External Systems Layer       │
│ (API Clients, Data Sources, Devices)│
└─────────────────────────────────────┘
```

### Design Patterns

#### DataUpdateCoordinator Pattern
Use `DataUpdateCoordinator` for managing data updates:

```python
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class AdaptiveThermalCoordinator(DataUpdateCoordinator):
    """Manage fetching data from external sources."""

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API or sensors."""
        try:
            # Fetch data asynchronously
            return await self._fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Error communicating: {err}") from err
```

**Benefits:**
- Centralized update logic
- Automatic retry on failure
- Prevents duplicate requests
- Built-in error handling

---

## File Structure

### Minimum Required Files

```
custom_components/adaptive_thermal_control/
├── __init__.py              # Integration setup
├── manifest.json            # Integration metadata
├── const.py                 # Constants and configuration
├── config_flow.py           # UI configuration flow
├── coordinator.py           # DataUpdateCoordinator
├── climate.py               # Climate entity platform
├── sensor.py                # Sensor entities (temperatures, etc.)
├── strings.json             # UI strings (translatable)
├── translations/
│   ├── en.json             # English translations
│   └── pl.json             # Polish translations
└── tests/
    ├── __init__.py
    ├── conftest.py         # Pytest fixtures
    ├── test_config_flow.py
    ├── test_climate.py
    └── fixtures/           # Test data fixtures
```

### manifest.json Requirements

```json
{
  "domain": "adaptive_thermal_control",
  "name": "Adaptive Thermal Control",
  "codeowners": ["@owner"],
  "config_flow": true,
  "documentation": "https://github.com/owner/adaptive-thermal-control",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/owner/adaptive-thermal-control/issues",
  "requirements": [],
  "version": "1.0.0",
  "dependencies": [],
  "after_dependencies": ["sensor", "weather"]
}
```

**Key Fields:**
- `config_flow: true` - Enables UI setup
- `version` - **Required for custom components**
- `iot_class` - Defines interaction model (local_polling, cloud_polling, local_push, etc.)
- `after_dependencies` - Load after these integrations

---

## Coding Standards

### 1. Async/Await Patterns

**Golden Rule:** Home Assistant runs on a single event loop. Never block it.

#### Use Async Methods for HA Core

When calling Home Assistant core from callbacks or coroutines, use `async_` prefixed methods:

```python
# ✅ Correct
await hass.async_add_executor_job(blocking_function)
hass.states.async_set("climate.living_room", "heat")
await hass.config_entries.async_setup(entry.entry_id)

# ❌ Incorrect - blocks event loop
hass.states.set("climate.living_room", "heat")
time.sleep(5)  # Never do this!
```

#### Entity Implementation

```python
from homeassistant.helpers.entity import Entity

class AdaptiveThermostatEntity(Entity):
    """Adaptive thermostat entity."""

    async def async_update(self) -> None:
        """Fetch latest state asynchronously."""
        # All data fetching happens here
        self._attr_current_temperature = await self._fetch_temperature()
        self._attr_target_temperature = self._calculate_target()

    @property
    def current_temperature(self) -> float | None:
        """Return cached temperature - NO I/O here!"""
        return self._attr_current_temperature
```

**Critical Rules:**
- ✅ Use `async def async_update()` for data fetching
- ✅ Properties return cached data only (no I/O)
- ✅ All external communication happens in update methods

#### Calling Sync from Async

For blocking operations (file I/O, synchronous libraries):

```python
# ✅ Correct - runs in executor thread pool
result = await hass.async_add_executor_job(
    blocking_library_call,
    arg1,
    arg2
)

# ❌ Incorrect - blocks event loop
result = blocking_library_call(arg1, arg2)
```

**Warning:** Be careful with `asyncio.run_coroutine_threadsafe()` - it can deadlock if the async function uses executor jobs.

#### Fire-and-Forget Tasks

For independent parallel tasks:

```python
# ✅ Correct - non-blocking
hass.async_create_task(
    self._async_send_notification()
)

# Continue immediately - don't wait
```

### 2. Type Hints (Required for Gold Tier)

**All functions and methods must have full type annotations:**

```python
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    coordinator: AdaptiveThermalCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        AdaptiveThermostat(coordinator, room_id)
        for room_id in coordinator.data["rooms"]
    ])
```

**Modern Type Hints (Python 3.10+):**

```python
# ✅ Use PEP 604 union syntax
def get_temperature(self) -> float | None:
    """Return temperature or None."""
    return self._temperature

# ✅ Use built-in generics
def get_rooms(self) -> list[str]:
    """Return list of room IDs."""
    return self._rooms

def get_config(self) -> dict[str, Any]:
    """Return configuration dictionary."""
    return self._config
```

### 3. Error Handling

**Never let exceptions crash Home Assistant:**

```python
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

async def _async_update_data(self) -> dict[str, Any]:
    """Fetch data with proper error handling."""
    try:
        return await self._api_client.fetch_data()
    except ConnectionError as err:
        raise UpdateFailed(f"Connection error: {err}") from err
    except ValueError as err:
        raise UpdateFailed(f"Invalid data received: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error fetching data")
        raise UpdateFailed(f"Unexpected error: {err}") from err
```

**Logging Levels:**
- `_LOGGER.debug()` - Detailed diagnostic information
- `_LOGGER.info()` - Confirmation of normal operation
- `_LOGGER.warning()` - Recoverable issues
- `_LOGGER.error()` - Serious problems
- `_LOGGER.exception()` - Errors with full stack trace

**Never spam logs:**
```python
# ✅ Correct - log once, then suppress
if not self._connection_error_logged:
    _LOGGER.error("Connection lost to heating controller")
    self._connection_error_logged = True

# ❌ Incorrect - will spam logs every update
_LOGGER.error("Connection lost to heating controller")
```

### 4. Code Formatting

**Use Black formatter (configured in PyCharm):**

```bash
# Format code
black custom_components/adaptive_thermal_control/

# Check formatting
black --check custom_components/adaptive_thermal_control/
```

**Line Length:** 88 characters (Black default)

**Import Organization:**

```python
"""Climate platform for Adaptive Thermal Control."""
from __future__ import annotations

# Standard library imports
from datetime import timedelta
import logging
from typing import Any

# Third-party imports (if any)
# import numpy as np

# Home Assistant imports
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Local imports
from .const import DOMAIN
from .coordinator import AdaptiveThermalCoordinator
```

### 5. Constants

**Define all constants in `const.py`:**

```python
"""Constants for Adaptive Thermal Control."""

# Integration domain
DOMAIN = "adaptive_thermal_control"

# Configuration keys
CONF_ROOM_ID = "room_id"
CONF_HEATING_CIRCUIT = "heating_circuit"
CONF_LEARNING_ENABLED = "learning_enabled"

# Default values
DEFAULT_MIN_TEMP = 10.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_TARGET_TEMP = 20.0
DEFAULT_PRECISION = 0.1

# Update intervals
UPDATE_INTERVAL = timedelta(minutes=5)
FAST_UPDATE_INTERVAL = timedelta(minutes=1)

# Attribute names
ATTR_INLET_TEMP = "inlet_temperature"
ATTR_OUTLET_TEMP = "outlet_temperature"
ATTR_PREDICTED_TEMP = "predicted_temperature"
```

**Never use magic numbers or strings:**

```python
# ✅ Correct
if temp < DEFAULT_MIN_TEMP:
    return DEFAULT_MIN_TEMP

# ❌ Incorrect
if temp < 10.0:
    return 10.0
```

---

## Climate Entity Implementation

### Required Base Class

```python
from homeassistant.components.climate import ClimateEntity

class AdaptiveThermostat(ClimateEntity):
    """Adaptive learning thermostat."""
```

### Mandatory Properties

```python
@property
def hvac_mode(self) -> HVACMode:
    """Return current operation mode."""
    return self._attr_hvac_mode

@property
def hvac_modes(self) -> list[HVACMode]:
    """Return list of available modes."""
    return [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]

@property
def temperature_unit(self) -> str:
    """Return temperature unit."""
    from homeassistant.const import UnitOfTemperature
    return UnitOfTemperature.CELSIUS
```

### HVAC Mode vs Action

**Critical distinction:**
- **Mode** = User's intent (what they want)
- **Action** = Current behavior (what's happening now)

```python
@property
def hvac_mode(self) -> HVACMode:
    """User selected mode."""
    return HVACMode.HEAT  # User wants heating

@property
def hvac_action(self) -> HVACAction:
    """Current action being performed."""
    if self._is_actively_heating:
        return HVACAction.HEATING
    elif self._reached_target:
        return HVACAction.IDLE
    else:
        return HVACAction.OFF
```

### Supported Features

```python
from homeassistant.components.climate import ClimateEntityFeature

@property
def supported_features(self) -> ClimateEntityFeature:
    """Return supported features."""
    return (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
```

### Conditional Properties

**If you support `ClimateEntityFeature.PRESET_MODE`:**

```python
@property
def preset_mode(self) -> str | None:
    """Return current preset mode."""
    return self._attr_preset_mode

@property
def preset_modes(self) -> list[str]:
    """Return available preset modes."""
    return ["eco", "comfort", "boost", "away"]
```

**If you support `ClimateEntityFeature.TARGET_TEMPERATURE_RANGE`:**

```python
@property
def target_temperature_low(self) -> float | None:
    """Return lower target temperature."""
    return self._attr_target_temperature_low

@property
def target_temperature_high(self) -> float | None:
    """Return upper target temperature."""
    return self._attr_target_temperature_high
```

**Built-in validation:** Home Assistant automatically ensures `target_temperature_low ≤ target_temperature_high`.

### Control Methods

```python
async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
    """Set new target hvac mode."""
    self._attr_hvac_mode = hvac_mode
    await self._async_control_heating()
    self.async_write_ha_state()

async def async_set_temperature(self, **kwargs: Any) -> None:
    """Set new target temperature."""
    if (temperature := kwargs.get("temperature")) is not None:
        self._attr_target_temperature = temperature
        await self._async_control_heating()
        self.async_write_ha_state()

async def async_set_preset_mode(self, preset_mode: str) -> None:
    """Set new preset mode."""
    self._attr_preset_mode = preset_mode
    await self._apply_preset()
    self.async_write_ha_state()
```

**Important:**
- Always call `self.async_write_ha_state()` after state changes
- Use async versions of methods
- Implement both sync and async versions if needed (framework calls whichever exists)

### Custom Attributes

```python
@property
def extra_state_attributes(self) -> dict[str, Any]:
    """Return additional state attributes."""
    return {
        ATTR_INLET_TEMP: self._inlet_temperature,
        ATTR_OUTLET_TEMP: self._outlet_temperature,
        ATTR_PREDICTED_TEMP: self._predicted_temperature,
        "learning_mode": self._learning_enabled,
        "heating_curve": self._heating_curve_params,
    }
```

---

## Testing Standards

### Framework

Use **pytest** with Home Assistant test fixtures.

### Required Dependencies

```bash
# Install test requirements
source .venv/bin/activate
pip install pytest pytest-homeassistant-custom-component pytest-cov pytest-asyncio
```

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_config_flow.py      # Config flow tests
├── test_init.py             # Integration setup tests
├── test_climate.py          # Climate entity tests
├── test_coordinator.py      # Coordinator tests
└── fixtures/
    ├── heating_data.json    # Test data
    └── weather_forecast.json
```

### Essential Fixtures

#### conftest.py

```python
"""Fixtures for Adaptive Thermal Control tests."""
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adaptive_thermal_control.const import DOMAIN


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living Room Thermostat",
        data={
            "room_id": "living_room",
            "heating_circuit": 1,
        },
    )


@pytest.fixture
async def mock_adaptive_thermal(hass: HomeAssistant, mock_config_entry):
    """Set up Adaptive Thermal Control integration."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.adaptive_thermal_control.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
```

### Test Examples

#### test_config_flow.py

```python
"""Test config flow."""
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.adaptive_thermal_control.const import DOMAIN


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"room_id": "bedroom", "heating_circuit": 2},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom Thermostat"
    assert result["data"] == {
        "room_id": "bedroom",
        "heating_circuit": 2,
    }


async def test_duplicate_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test duplicate config entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"room_id": "living_room", "heating_circuit": 1},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
```

#### test_climate.py

```python
"""Test climate platform."""
import pytest
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from custom_components.adaptive_thermal_control.const import DOMAIN


async def test_climate_entity_properties(
    hass: HomeAssistant,
    mock_adaptive_thermal,
) -> None:
    """Test climate entity properties."""
    state = hass.states.get("climate.living_room_thermostat")

    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes["temperature"] == 20.0
    assert state.attributes["current_temperature"] == 18.5


async def test_set_temperature(
    hass: HomeAssistant,
    mock_adaptive_thermal,
) -> None:
    """Test setting temperature."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room_thermostat",
            ATTR_TEMPERATURE: 22.0,
        },
        blocking=True,
    )

    state = hass.states.get("climate.living_room_thermostat")
    assert state.attributes["temperature"] == 22.0


async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_adaptive_thermal,
) -> None:
    """Test setting HVAC mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_thermostat",
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    state = hass.states.get("climate.living_room_thermostat")
    assert state.state == HVACMode.HEAT
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_climate.py

# Run with coverage report
pytest tests/ \
    --cov=custom_components.adaptive_thermal_control \
    --cov-report=term-missing \
    --cov-report=html

# Stop on first failure
pytest tests/ -x

# Run specific test
pytest tests/test_climate.py -k test_set_temperature

# Show slowest tests
pytest tests/ --duration=10
```

### Snapshot Testing

For complex state objects:

```python
async def test_climate_state_snapshot(
    hass: HomeAssistant,
    mock_adaptive_thermal,
    snapshot,
) -> None:
    """Test climate entity state matches snapshot."""
    state = hass.states.get("climate.living_room_thermostat")
    assert state == snapshot
```

Generate/update snapshots:
```bash
pytest tests/test_climate.py --snapshot-update
```

**Warning:** Snapshots don't replace functional tests - use them for large structured outputs only.

---

## Documentation Requirements

### 1. Code Documentation

#### Module Docstrings

```python
"""Climate platform for Adaptive Thermal Control.

This module implements the climate entity for controlling floor heating
with predictive learning capabilities based on historical data and
external conditions.
"""
```

#### Class Docstrings

```python
class AdaptiveThermostat(ClimateEntity):
    """Adaptive learning thermostat for floor heating.

    This thermostat learns from historical heating data and adjusts
    the heating curve based on:
    - External temperature and weather forecasts
    - Solar irradiance and room orientation
    - Inter-room thermal influence
    - Heating costs (energy pricing)

    Attributes:
        coordinator: DataUpdateCoordinator managing updates.
        room_id: Unique identifier for the room.
        _attr_target_temperature: User's desired temperature.
    """
```

#### Method Docstrings

```python
async def async_set_temperature(self, **kwargs: Any) -> None:
    """Set new target temperature.

    Args:
        kwargs: Keyword arguments containing:
            - temperature: Target temperature in Celsius
            - target_temp_high: Upper bound for range (optional)
            - target_temp_low: Lower bound for range (optional)
            - hvac_mode: HVAC mode to set (optional)

    Raises:
        ValueError: If temperature is out of valid range.
    """
```

### 2. User Documentation

#### README.md

Must include:
- Installation instructions
- Configuration steps
- Available features
- Example automations
- Troubleshooting guide
- FAQ

#### strings.json

UI-facing strings must be translatable:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Set up Adaptive Thermal Control",
        "description": "Configure your adaptive floor heating thermostat",
        "data": {
          "room_id": "Room ID",
          "heating_circuit": "Heating Circuit Number"
        }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect to heating controller",
      "invalid_room": "Invalid room ID",
      "already_configured": "This room is already configured"
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Adaptive Thermal Control Options",
        "data": {
          "learning_enabled": "Enable learning mode",
          "min_temperature": "Minimum temperature",
          "max_temperature": "Maximum temperature"
        }
      }
    }
  }
}
```

### 3. Inline Comments

```python
# Calculate predicted temperature based on thermal model
# Uses Newton's law of cooling with learned heat transfer coefficient
predicted_temp = self._calculate_thermal_model(
    current_temp=current_temp,
    target_temp=target_temp,
    external_temp=external_temp,
    time_delta=time_delta,
)

# Apply predictive heating if temperature will drop below target
# Account for thermal lag in floor heating (typically 30-60 minutes)
if predicted_temp < target_temp - self._thermal_lag_compensation:
    await self._async_enable_heating()
```

**When to comment:**
- Complex algorithms or calculations
- Non-obvious business logic
- Workarounds for specific issues
- Performance-critical sections

**When NOT to comment:**
```python
# ❌ Obvious comment - don't do this
# Set temperature to 20
self._attr_target_temperature = 20

# ✅ Good - explains WHY
# Use 20°C as fallback when prediction model fails
self._attr_target_temperature = 20
```

---

## Best Practices Checklist

### Before Committing

- [ ] Code formatted with Black
- [ ] All functions have type hints
- [ ] No blocking I/O in properties
- [ ] All async methods use `async_` prefix
- [ ] Error handling implemented
- [ ] Logging uses appropriate levels
- [ ] No log spam on repeated errors
- [ ] Constants defined in `const.py`
- [ ] Tests written and passing
- [ ] Test coverage > 90%
- [ ] Docstrings for all classes and public methods
- [ ] UI strings in `strings.json`
- [ ] No magic numbers or strings

### Before Release

#### Bronze Tier Requirements
- [ ] UI-based config flow implemented
- [ ] Basic automated tests passing
- [ ] Basic documentation (README)
- [ ] Integration can be set up through UI

#### Silver Tier Requirements
- [ ] Code owner assigned
- [ ] Automatic recovery from connection errors
- [ ] Re-authentication handling
- [ ] No log spam
- [ ] Comprehensive documentation

#### Gold Tier Requirements (Target)
- [ ] Device discovery (if applicable)
- [ ] Full test coverage
- [ ] Extensive user documentation
- [ ] UI reconfiguration support
- [ ] Diagnostic tools
- [ ] Full type annotations
- [ ] Fully async codebase
- [ ] Translatable entity names

### Code Review Checklist

- [ ] Follows Home Assistant conventions
- [ ] Async/await used correctly
- [ ] No blocking operations in event loop
- [ ] Properties don't perform I/O
- [ ] Error handling comprehensive
- [ ] Tests cover edge cases
- [ ] Documentation clear and accurate
- [ ] No unnecessary dependencies
- [ ] Performance optimized
- [ ] Security considerations addressed

---

## References

### Official Documentation
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Climate Entity](https://developers.home-assistant.io/docs/core/entity/climate/)
- [Working with Async](https://developers.home-assistant.io/docs/asyncio_working_with_async/)
- [Testing Your Code](https://developers.home-assistant.io/docs/development_testing/)
- [Creating Integration](https://developers.home-assistant.io/docs/creating_component_index/)

### Community Resources
- [Home Assistant GitHub](https://github.com/home-assistant/core)
- [Home Assistant Community Forum](https://community.home-assistant.io/)
- [Home Assistant Discord](https://discord.gg/home-assistant)

### Tools
- [Black Code Formatter](https://black.readthedocs.io/)
- [pytest](https://docs.pytest.org/)
- [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)

---

**Last Updated:** 2025-10-26
**Version:** 1.0
**Target Quality Tier:** Gold
