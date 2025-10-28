# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an adaptive Home Assistant integration for floor heating control (Sterowanie ogrzewaniem Podłogowym MCP). The system learns from historical data and predictively controls heating to maintain desired room temperatures.

### Key Algorithm Features
- Machine learning from historical heating data
- External temperature and weather forecast integration
- Inter-room thermal influence modeling (neighboring rooms affect each other)
- Boiler maximum power constraints for heating circuit control
- Water inlet/outlet temperature monitoring per heating circuit
- Solar irradiance integration with room orientation (via solar panel integration)
- Heating cost optimization (via price entity forecasts)

## Development Environment

- **Python Version**: 3.13 (configured in `.venv`)
- **IDE**: PyCharm with Black formatter
- **Virtual Environment**: `.venv/` directory (already set up)

## Development Commands

### Running Tests

**Use the test runner script** (recommended):
```bash
./run_tests.sh                    # Run all tests
./run_tests.sh -v                 # Verbose output
./run_tests.sh tests/test_mpc*    # Run specific test file(s)
./run_tests.sh -k test_name       # Run tests matching pattern
./run_tests.sh --cov              # Run with coverage report
```

The script automatically:
- Activates virtual environment
- Sets PYTHONPATH correctly
- Runs pytest with any arguments you provide
- Deactivates environment after

**Manual testing** (if needed):
```bash
source .venv/bin/activate
PYTHONPATH="." pytest tests/ -v
deactivate
```

### Virtual Environment
```zsh
# Activate virtual environment
source .venv/bin/activate

# Deactivate
deactivate
```

## Project Structure

This is an early-stage project. The main.py currently contains a PyCharm template placeholder. The actual implementation will be a Home Assistant integration with:

- Room thermostat entities (climate entities)
- Predictive heating control algorithms
- Integration with external data sources (weather, solar, pricing)
- Multi-zone heating circuit management
- Learning and adaptation mechanisms

## Home Assistant Integration Context

This will be a custom component for Home Assistant. Future development should consider:

- Home Assistant's integration architecture (`custom_components/`)
- Climate platform implementation for room thermostats
- Sensor entities for temperature monitoring (inlet/outlet water, room temps)
- Binary sensor/switch entities for heating circuit control
- Service calls for manual overrides and configuration
- Configuration flow (config_flow.py)
- State persistence for learned parameters

## Project Task Management

**Full details in [.task/](.task/) directory**

### Quick Reference

**Key files:**
- `.task/README.md` - Project overview and all phases
- `.task/PROJECT_STATUS.md` - Current status (update weekly!)
- `.task/HOW_TO_USE.md` - Complete task management guide
- `.task/phase-N-name.md` - Detailed tasks for each phase

**Check current status:**
```bash
cat .task/PROJECT_STATUS.md
```

**View current phase tasks:**
```bash
cat .task/phase-1-foundation.md
```

### 6 Project Phases

**Timeline:** 6 months total

1. **Phase 1: Foundation** (Month 1) - `.task/phase-1-foundation.md`
   - Custom component structure
   - Config Flow (UI configuration)
   - Basic climate entities
   - Simple PI controller as fallback

2. **Phase 2: Thermal Model** (Month 2) - `.task/phase-2-thermal-model.md`
   - 1R1C model implementation
   - Parameter identification (RLS algorithm)
   - Historical data collection
   - Model validation

3. **Phase 3: MPC Core** (Months 3-4) - `.task/phase-3-mpc-core.md`
   - MPC algorithm implementation
   - Cost function (comfort + energy)
   - 4-8h prediction horizon
   - Performance optimization

4. **Phase 4: Advanced Features** (Month 5) - `.task/phase-4-advanced-features.md`
   - Weather forecast integration
   - Solar irradiance + window orientation
   - Inter-room thermal influence
   - Zone coordination (fair-share)

5. **Phase 5: Cost Optimization** (Month 6) - `.task/phase-5-cost-optimization.md`
   - Energy pricing integration
   - "Heat now, expensive later" strategy
   - Cost dashboard
   - Weight fine-tuning

6. **Phase 6: HACS Publication** (Month 6+) - `.task/phase-6-hacs-publication.md`
   - User documentation
   - Example configurations
   - Translations (EN, PL)
   - HACS publication

### Task Status Symbols

| Symbol | Status | Meaning |
|--------|--------|---------|
| `- [ ]` | 🔴 To do | Task waiting |
| `- [🟡]` | 🟡 In progress | Working on this now |
| `- [x]` | 🟢 Done | Completed and tested |
| `- [⚠️]` | ⚠️ Blocked | Waiting for something |
| `- [🔵]` | 🔵 Review | Ready but needs review |

### Task Workflow

**Daily:**
1. Mark starting tasks with 🟡
2. Commit changes with proper message format
3. Mark completed tasks with ✅

**Weekly:**
1. Update `PROJECT_STATUS.md`:
   - Phase progress (% completed tasks)
   - Code metrics (LOC, coverage)
   - Next steps section
   - Last update date

### Task Naming Convention

Format: `T[Phase].[Section].[Number]`

Examples:
- `T1.1.1` = Phase 1, Section 1, Task 1
- `T3.4.2` = Phase 3, Section 4, Task 2

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
feat(T1.1.1): add manifest.json with dependencies
fix(T2.3.2): correct RLS convergence issue
docs: update README with installation instructions
test: add unit tests for ThermalModel
refactor: simplify MPCController initialization
chore: update dependencies to latest versions
```

**Pattern:** `type(task-id): description`

### Current Project Status

**Phase:** 🔴 Phase 0 - Planning
**Overall Progress:** 0% (0/6 phases)
**Total Tasks:** ~197 tasks across all phases
**Time to v1.0:** ~6 months

**Next immediate steps:**
1. Start Phase 1: Foundation
2. Create `custom_components/adaptive_thermal_control/` structure
3. Implement `manifest.json`
4. Basic `__init__.py`

### Additional Task Files

- `.task/backlog.md` - Future ideas (post v1.0)
- `.task/bugs.md` - Known bugs to fix
- `.task/research.md` - Research notes and experiments

### Working with Tasks

```bash
# Start working on a task
# 1. Choose task from current phase file
cat .task/phase-1-foundation.md

# 2. Mark as "in progress" (change [ ] to [🟡])

# 3. Create branch
git checkout -b feature/T1.1.1-task-name

# 4. Work and commit regularly
git commit -m "feat(T1.1.1): description"

# 5. Mark as completed (change [🟡] to [x])

# 6. Update status weekly
code .task/PROJECT_STATUS.md
```

**Important:** Always reference task IDs in commit messages for traceability!

## Coding Standards Summary

**Full details in [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md)**

### Quality Target: Gold Tier

We aim for Gold-tier integration quality with:
- Full type annotations
- Fully asynchronous codebase
- Complete test coverage (>90%)
- Comprehensive documentation

### Critical Rules

#### 1. Async/Await (MANDATORY)
- ✅ **Always use async methods** for Home Assistant core: `async_setup()`, `async_update()`, `async_set_temperature()`
- ✅ **Properties return cached data only** - NO I/O operations in properties
- ✅ **Use executor for blocking code**: `await hass.async_add_executor_job(blocking_func)`
- ❌ **Never block event loop** - no `time.sleep()`, no synchronous I/O in async context

#### 2. Type Hints (MANDATORY)
- ✅ **All functions must have full type annotations**
- ✅ **Use modern syntax**: `list[str]`, `dict[str, Any]`, `float | None` (Python 3.10+)
- ✅ **Import from typing**: `from typing import Any`

#### 3. Code Organization
- ✅ **Use DataUpdateCoordinator** for data fetching
- ✅ **Define constants in const.py** - no magic numbers/strings
- ✅ **Format with Black** (88 char line length)
- ✅ **Import order**: stdlib → third-party → HA → local

#### 4. Error Handling
- ✅ **Catch specific exceptions** and raise `UpdateFailed` in coordinators
- ✅ **Never spam logs** - log errors once, suppress repeats
- ✅ **Use appropriate log levels**: debug/info/warning/error/exception

#### 5. Climate Entity Specifics
- ✅ **Derive from ClimateEntity**
- ✅ **Required properties**: `hvac_mode`, `hvac_modes`, `temperature_unit`
- ✅ **Distinguish mode vs action**: mode = intent, action = current behavior
- ✅ **Use built-in enums**: `HVACMode`, `HVACAction`, `ClimateEntityFeature`
- ✅ **Call async_write_ha_state()** after state changes

#### 6. Testing
- ✅ **Use pytest** with `pytest-homeassistant-custom-component`
- ✅ **Test config flow, entity setup, and service calls**
- ✅ **Mock external dependencies** - no real API calls in tests
- ✅ **Aim for >90% coverage**

#### 7. File Structure
```
custom_components/adaptive_thermal_control/
├── __init__.py              # Integration setup (async_setup, async_setup_entry)
├── manifest.json            # Metadata (MUST include "version" for custom components)
├── const.py                 # All constants
├── config_flow.py           # UI configuration
├── coordinator.py           # DataUpdateCoordinator
├── climate.py               # Climate entities
├── sensor.py                # Sensor entities
├── strings.json             # Translatable UI strings
└── translations/en.json     # English translations
```

### Quick Reference

**Setup pattern:**
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MyEntity(coordinator)])
```

**Climate entity pattern:**
```python
async def async_set_temperature(self, **kwargs: Any) -> None:
    """Set temperature."""
    if (temp := kwargs.get("temperature")) is not None:
        self._attr_target_temperature = temp
        await self._async_control_heating()
        self.async_write_ha_state()
```

**Update pattern:**
```python
async def async_update(self) -> None:
    """Fetch latest data."""
    self._attr_current_temperature = await self._fetch_temp()
    # Properties return cached values - NO I/O here!
```

**Before each commit:**
- [ ] Black formatting applied
- [ ] Full type hints
- [ ] Tests passing
- [ ] No blocking I/O in properties
- [ ] Error handling implemented
- [ ] No log spam

## Language Note

Project documentation and code comments may be in Polish (as seen in PROJECT.md), as this is a Polish development project.
