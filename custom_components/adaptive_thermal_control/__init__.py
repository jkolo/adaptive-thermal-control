"""The Adaptive Thermal Control integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

# Supported platforms
PLATFORMS_LIST: list[Platform] = [Platform.CLIMATE]


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
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_LIST)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Adaptive Thermal Control setup completed for entry: %s", entry.entry_id)

    return True


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
        # Remove entry data from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)
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
