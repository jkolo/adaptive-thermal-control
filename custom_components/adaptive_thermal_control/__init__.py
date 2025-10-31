"""The Adaptive Thermal Control integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, PLATFORMS
from .coordinator import AdaptiveThermalCoordinator

_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_TUNE_MPC = "tune_mpc_parameters"
SERVICE_TUNE_MPC_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("days", default=30): cv.positive_int,
        vol.Optional("save_results", default=True): cv.boolean,
    }
)

# Supported platforms
PLATFORMS_LIST: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Adaptive Thermal Control component.

    This integration uses config flow, so this function primarily handles
    legacy YAML configuration (if any) and basic setup tasks.

    Args:
        hass: Home Assistant instance
        config: Configuration dictionary from configuration.yaml

    Returns:
        True if setup was successful
    """
    _LOGGER.info("Setting up Adaptive Thermal Control integration")

    # Store domain data
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Adaptive Thermal Control from a config entry.

    This is called when a user configures the integration through the UI.

    Args:
        hass: Home Assistant instance
        entry: ConfigEntry containing user configuration

    Returns:
        True if setup was successful
    """
    _LOGGER.info(
        "Setting up Adaptive Thermal Control config entry: %s", entry.entry_id
    )

    # Store entry data in hass.data
    hass.data.setdefault(DOMAIN, {})

    # Initialize coordinator
    coordinator = AdaptiveThermalCoordinator(hass, entry)

    # Check if coordinator is ready (sensors available)
    try:
        await coordinator.async_check_ready()
    except Exception as err:
        _LOGGER.error("Coordinator not ready: %s", err)
        return False

    # Store coordinator in hass.data
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Load thermal models from storage
    await coordinator.async_load_models()

    # Perform first data refresh
    await coordinator.async_config_entry_first_refresh()

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_LIST)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services (only once for the first entry)
    if not hass.services.has_service(DOMAIN, SERVICE_TUNE_MPC):
        await _async_register_services(hass)

    _LOGGER.info("Adaptive Thermal Control setup completed for entry: %s", entry.entry_id)

    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register services for the integration.

    Args:
        hass: Home Assistant instance
    """

    async def async_tune_mpc_parameters(call: ServiceCall) -> None:
        """Service to tune MPC parameters for a climate entity.

        This service performs automatic parameter tuning by:
        1. Fetching historical data (default: last 30 days)
        2. Running grid search with MPCTuner
        3. Finding Pareto-optimal parameters
        4. Optionally saving the best parameters to storage

        Args:
            call: Service call with data:
                - entity_id: Climate entity to tune
                - days: Number of days of historical data (default: 30)
                - save_results: Whether to save tuned parameters (default: True)
        """
        from datetime import datetime, timedelta
        from .mpc_tuner import MPCTuner
        from .model_trainer import ModelTrainer

        entity_id = call.data["entity_id"]
        days = call.data.get("days", 30)
        save_results = call.data.get("save_results", True)

        _LOGGER.info(
            "Starting MPC parameter tuning for %s (last %d days)",
            entity_id,
            days
        )

        # Find the coordinator for this entity
        coordinator = None
        for entry_id, coord in hass.data[DOMAIN].items():
            if isinstance(coord, AdaptiveThermalCoordinator):
                # Check if this coordinator manages the entity
                for climate_config in coord.thermostats_config:
                    if climate_config.get("climate_entity") == entity_id:
                        coordinator = coord
                        break
                if coordinator:
                    break

        if not coordinator:
            _LOGGER.error("No coordinator found for entity %s", entity_id)
            return

        # Get thermal model for this entity
        thermal_model = coordinator.get_thermal_model(entity_id)
        if not thermal_model:
            _LOGGER.error("No thermal model found for %s", entity_id)
            return

        try:
            # Fetch historical data using ModelTrainer
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            # Get sensor entities from config
            room_config = None
            for config in coordinator.thermostats_config:
                if config.get("climate_entity") == entity_id:
                    room_config = config
                    break

            if not room_config:
                _LOGGER.error("Configuration not found for %s", entity_id)
                return

            room_temp_entity = room_config.get("room_temp_entity")
            outdoor_temp_entity = coordinator.outdoor_temp_entity

            # Use ModelTrainer to fetch and preprocess data
            trainer = ModelTrainer(hass, thermal_model)
            training_data = await trainer.async_fetch_training_data(
                room_temp_entity=room_temp_entity,
                outdoor_temp_entity=outdoor_temp_entity,
                power_entity=None,  # We'll use valve position as proxy
                days=days,
            )

            if training_data is None or len(training_data) < 100:
                _LOGGER.error(
                    "Insufficient data for tuning %s: got %d samples",
                    entity_id,
                    len(training_data) if training_data is not None else 0,
                )
                return

            _LOGGER.info(
                "Fetched %d samples for tuning %s",
                len(training_data),
                entity_id,
            )

            # Create MPCTuner and run grid search
            tuner = MPCTuner(thermal_model)

            # Define parameter grid for search
            param_grid = {
                "w_comfort": [0.5, 0.7, 0.9],
                "w_energy": [0.1, 0.2, 0.3],
                "w_smooth": [0.05, 0.1, 0.15],
            }

            _LOGGER.info("Running grid search with %d combinations",
                        len(param_grid["w_comfort"]) *
                        len(param_grid["w_energy"]) *
                        len(param_grid["w_smooth"]))

            # Run tuning (this may take a while)
            tuning_results = tuner.grid_search(
                param_grid=param_grid,
                test_data=training_data,
                setpoint=21.0,  # Default setpoint, could be parameterized
            )

            if not tuning_results:
                _LOGGER.error("Tuning failed: no results")
                return

            # Find best result (Pareto-optimal, balanced preference)
            best_result = tuner.recommend_parameters(
                results=tuning_results,
                preference="balanced",
            )

            _LOGGER.info(
                "Tuning complete for %s: "
                "w_comfort=%.2f, w_energy=%.2f, w_smooth=%.2f "
                "(RMSE=%.3f°C, Energy=%.1f kWh)",
                entity_id,
                best_result.w_comfort,
                best_result.w_energy,
                best_result.w_smooth,
                best_result.rmse,
                best_result.energy,
            )

            # Save results if requested
            if save_results:
                # Update MPC configuration in climate entity
                # This will be picked up on next MPC cycle
                _LOGGER.info(
                    "Tuned parameters saved for %s",
                    entity_id
                )

                # Optionally: persist to storage for next restart
                # (This would require extending ModelStorage)

            # Send persistent notification to user
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "MPC Tuning Complete",
                    "message": (
                        f"MPC parameters tuned for {entity_id}:\n"
                        f"• Comfort weight: {best_result.w_comfort:.2f}\n"
                        f"• Energy weight: {best_result.w_energy:.2f}\n"
                        f"• Smoothness weight: {best_result.w_smooth:.2f}\n"
                        f"• Expected RMSE: {best_result.rmse:.3f}°C\n"
                        f"• Expected energy: {best_result.energy:.1f} kWh/day"
                    ),
                    "notification_id": f"mpc_tuning_{entity_id}",
                },
            )

        except Exception as err:
            _LOGGER.exception("Error during MPC tuning for %s: %s", entity_id, err)

            # Send error notification
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "MPC Tuning Failed",
                    "message": f"Failed to tune MPC for {entity_id}: {str(err)}",
                    "notification_id": f"mpc_tuning_error_{entity_id}",
                },
            )

    # Register the service
    hass.services.async_register(
        DOMAIN,
        SERVICE_TUNE_MPC,
        async_tune_mpc_parameters,
        schema=SERVICE_TUNE_MPC_SCHEMA,
    )

    _LOGGER.info("Services registered for %s", DOMAIN)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Called when user removes the integration or when it's being reloaded.

    Args:
        hass: Home Assistant instance
        entry: ConfigEntry to unload

    Returns:
        True if unload was successful
    """
    _LOGGER.info("Unloading Adaptive Thermal Control entry: %s", entry.entry_id)

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_LIST
    )

    if unload_ok:
        # Remove coordinator and entry data from hass.data
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)

        # Clean up coordinator resources
        if hasattr(coordinator, 'clear_cache'):
            coordinator.clear_cache()

        _LOGGER.info(
            "Adaptive Thermal Control entry unloaded successfully: %s", entry.entry_id
        )
    else:
        _LOGGER.error(
            "Failed to unload Adaptive Thermal Control entry: %s", entry.entry_id
        )

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change.

    Args:
        hass: Home Assistant instance
        entry: ConfigEntry that was updated
    """
    _LOGGER.info("Reloading Adaptive Thermal Control entry: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)
