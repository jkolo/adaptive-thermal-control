"""Model parameter storage and persistence.

This module handles saving and loading thermal model parameters to/from
persistent storage. It provides atomic writes, automatic backups, and
versioning support.

Storage location: config/.storage/adaptive_thermal_control_models.json

Data structure:
{
    "climate.room_name": {
        "R": 0.0025,
        "C": 4.5e6,
        "tau": 11250,
        "last_update": "2025-10-27T10:00:00Z",
        "metrics": {"rmse": 0.42, "mae": 0.31, "r_squared": 0.95},
        "version": 1
    }
}
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .thermal_model import ThermalModelParameters

_LOGGER = logging.getLogger(__name__)

# Storage configuration
STORAGE_VERSION = 1
STORAGE_KEY = "adaptive_thermal_control_models"
BACKUP_SUFFIX = ".backup"
MAX_BACKUPS = 10


class ModelStorage:
    """Storage manager for thermal model parameters.

    This class handles persistent storage of trained model parameters,
    including atomic writes, automatic backups, and version management.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize model storage.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {}

        _LOGGER.debug("Initialized ModelStorage")

    async def async_load(self) -> dict[str, Any]:
        """Load model parameters from storage.

        Returns:
            Dictionary mapping entity_id to model parameters
        """
        try:
            data = await self.store.async_load()
            if data is None:
                _LOGGER.info("No stored model parameters found, using empty dict")
                self._data = {}
            else:
                self._data = data
                _LOGGER.info(
                    "Loaded model parameters for %d entities",
                    len(self._data),
                )
        except Exception as e:
            _LOGGER.error("Failed to load model parameters: %s", e)
            self._data = {}

        return self._data

    async def async_save(self) -> None:
        """Save model parameters to storage.

        Uses atomic write (write to temp file, then rename) to prevent
        corruption on write failures.
        """
        try:
            await self.store.async_save(self._data)
            _LOGGER.debug("Saved model parameters for %d entities", len(self._data))
        except Exception as e:
            _LOGGER.error("Failed to save model parameters: %s", e)

    async def async_save_model(
        self,
        entity_id: str,
        parameters: ThermalModelParameters,
        metrics: dict[str, float] | None = None,
    ) -> None:
        """Save model parameters for a specific entity.

        Args:
            entity_id: Entity ID (e.g., "climate.living_room")
            parameters: Thermal model parameters to save
            metrics: Optional training metrics
        """
        # Create backup before modifying
        if entity_id in self._data:
            await self._create_backup(entity_id)

        # Build parameter data
        param_data = {
            "R": parameters.R,
            "C": parameters.C,
            "tau": parameters.time_constant,
            "last_update": datetime.now().isoformat(),
            "version": STORAGE_VERSION,
        }

        # Add metrics if provided
        if metrics:
            param_data["metrics"] = {
                "rmse": round(metrics.get("rmse", 0.0), 3),
                "mae": round(metrics.get("mae", 0.0), 3),
                "r_squared": round(metrics.get("r_squared", 0.0), 4),
            }

        # Store data
        self._data[entity_id] = param_data

        # Save to disk
        await self.async_save()

        _LOGGER.info(
            "Saved model for %s: R=%.6f, C=%.0f, τ=%.1fh",
            entity_id,
            parameters.R,
            parameters.C,
            parameters.time_constant / 3600,
        )

    async def async_load_model(
        self,
        entity_id: str,
    ) -> tuple[ThermalModelParameters | None, dict[str, float] | None]:
        """Load model parameters for a specific entity.

        Args:
            entity_id: Entity ID to load parameters for

        Returns:
            Tuple of (parameters, metrics) or (None, None) if not found
        """
        if entity_id not in self._data:
            _LOGGER.debug("No stored parameters for %s", entity_id)
            return None, None

        data = self._data[entity_id]

        # Extract parameters
        try:
            parameters = ThermalModelParameters(
                R=data["R"],
                C=data["C"],
            )

            # Validate
            if not parameters.validate():
                _LOGGER.warning(
                    "Stored parameters for %s failed validation", entity_id
                )
                return None, None

            # Extract metrics
            metrics = data.get("metrics")

            _LOGGER.info(
                "Loaded model for %s: R=%.6f, C=%.0f, τ=%.1fh",
                entity_id,
                parameters.R,
                parameters.C,
                parameters.time_constant / 3600,
            )

            return parameters, metrics

        except (KeyError, ValueError, TypeError) as e:
            _LOGGER.error(
                "Failed to parse stored parameters for %s: %s", entity_id, e
            )
            return None, None

    async def async_delete_model(self, entity_id: str) -> None:
        """Delete stored parameters for an entity.

        Args:
            entity_id: Entity ID to delete parameters for
        """
        if entity_id in self._data:
            # Create backup before deleting
            await self._create_backup(entity_id)

            del self._data[entity_id]
            await self.async_save()

            _LOGGER.info("Deleted stored parameters for %s", entity_id)

    async def _create_backup(self, entity_id: str) -> None:
        """Create backup of current parameters.

        Args:
            entity_id: Entity ID to backup
        """
        if entity_id not in self._data:
            return

        # Get backup directory
        storage_path = Path(self.hass.config.path(".storage"))
        backup_dir = storage_path / "adaptive_thermal_control_backups"
        backup_dir.mkdir(exist_ok=True, parents=True)

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        entity_safe = entity_id.replace(".", "_")
        backup_file = backup_dir / f"{entity_safe}_{timestamp}.json"

        try:
            # Save entity data to backup
            backup_data = {
                entity_id: self._data[entity_id],
                "_backup_created": datetime.now().isoformat(),
            }

            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2)

            _LOGGER.debug("Created backup for %s: %s", entity_id, backup_file)

            # Clean up old backups
            await self._cleanup_old_backups(entity_id, backup_dir)

        except Exception as e:
            _LOGGER.warning("Failed to create backup for %s: %s", entity_id, e)

    async def _cleanup_old_backups(
        self,
        entity_id: str,
        backup_dir: Path,
    ) -> None:
        """Clean up old backup files, keeping only the most recent.

        Args:
            entity_id: Entity ID to clean backups for
            backup_dir: Directory containing backups
        """
        try:
            entity_safe = entity_id.replace(".", "_")
            pattern = f"{entity_safe}_*.json"

            # Find all backup files for this entity
            backup_files = sorted(
                backup_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # Keep only MAX_BACKUPS most recent
            for old_backup in backup_files[MAX_BACKUPS:]:
                old_backup.unlink()
                _LOGGER.debug("Deleted old backup: %s", old_backup.name)

        except Exception as e:
            _LOGGER.warning("Failed to cleanup old backups: %s", e)

    async def async_restore_from_backup(
        self,
        entity_id: str,
        backup_index: int = 0,
    ) -> bool:
        """Restore parameters from a backup.

        Args:
            entity_id: Entity ID to restore
            backup_index: Index of backup to restore (0 = most recent)

        Returns:
            True if restore succeeded
        """
        storage_path = Path(self.hass.config.path(".storage"))
        backup_dir = storage_path / "adaptive_thermal_control_backups"

        if not backup_dir.exists():
            _LOGGER.error("Backup directory does not exist")
            return False

        try:
            entity_safe = entity_id.replace(".", "_")
            pattern = f"{entity_safe}_*.json"

            # Find backup files
            backup_files = sorted(
                backup_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            if not backup_files:
                _LOGGER.error("No backups found for %s", entity_id)
                return False

            if backup_index >= len(backup_files):
                _LOGGER.error(
                    "Backup index %d out of range (only %d backups available)",
                    backup_index,
                    len(backup_files),
                )
                return False

            # Load backup
            backup_file = backup_files[backup_index]
            with open(backup_file, "r", encoding="utf-8") as f:
                backup_data = json.load(f)

            # Restore data
            if entity_id in backup_data:
                self._data[entity_id] = backup_data[entity_id]
                await self.async_save()

                _LOGGER.info(
                    "Restored parameters for %s from backup: %s",
                    entity_id,
                    backup_file.name,
                )
                return True
            else:
                _LOGGER.error("Entity %s not found in backup", entity_id)
                return False

        except Exception as e:
            _LOGGER.error("Failed to restore from backup: %s", e)
            return False

    def get_all_entities(self) -> list[str]:
        """Get list of all entities with stored parameters.

        Returns:
            List of entity IDs
        """
        return list(self._data.keys())

    def get_model_info(self, entity_id: str) -> dict[str, Any] | None:
        """Get model information for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            Dictionary with model info or None if not found
        """
        if entity_id not in self._data:
            return None

        data = self._data[entity_id].copy()

        # Add computed fields
        if "R" in data and "C" in data:
            data["tau_hours"] = round(data["R"] * data["C"] / 3600, 2)

        return data

    async def async_export_all(self, export_path: Path) -> bool:
        """Export all model parameters to a file.

        Args:
            export_path: Path to export file

        Returns:
            True if export succeeded
        """
        try:
            export_data = {
                "version": STORAGE_VERSION,
                "exported": datetime.now().isoformat(),
                "models": self._data,
            }

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)

            _LOGGER.info("Exported %d models to %s", len(self._data), export_path)
            return True

        except Exception as e:
            _LOGGER.error("Failed to export models: %s", e)
            return False

    async def async_import_all(self, import_path: Path) -> bool:
        """Import model parameters from a file.

        Args:
            import_path: Path to import file

        Returns:
            True if import succeeded
        """
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)

            # Validate format
            if "models" not in import_data:
                _LOGGER.error("Invalid import file format")
                return False

            # Backup current data
            backup_path = Path(str(import_path) + ".backup")
            await self.async_export_all(backup_path)

            # Import models
            self._data = import_data["models"]
            await self.async_save()

            _LOGGER.info("Imported %d models from %s", len(self._data), import_path)
            return True

        except Exception as e:
            _LOGGER.error("Failed to import models: %s", e)
            return False
