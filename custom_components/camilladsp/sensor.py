"""CamillaDSP sensor platform – read-only telemetry and status.

Exposes runtime metrics from the CamillaDSP backend:

- DSP state (Running / Paused / Inactive / …)
- Capture sample rate
- Buffer level
- Clipped samples
- Processing load (%)
- Active config filename (read-only mirror)
- Volume (read-only mirror)
- Mute state (read-only mirror)

All sensors use ``MutationStrategy.READ_ONLY`` – they have no write path.
The sensor reads its value from the coordinator using a mapping from the
descriptor's ``translation_key`` to the corresponding coordinator property
or ``RuntimeStatus`` field.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CamillaDSPCoordinator
from .entities.descriptors import EntityDescriptor, EntityPlatform
from .entity import CamillaDSPEntity

_LOGGER = logging.getLogger(__name__)

# Maps descriptor translation_key → attribute name on RuntimeStatus.
_STATUS_FIELD_MAP: dict[str, str] = {
    "status_state": "state",
    "status_capture_rate": "capture_rate",
    "status_buffer_level": "buffer_level",
    "status_clipped_samples": "clipped_samples",
    "status_processing_load": "processing_load",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CamillaDSP sensor entities from descriptors."""
    coordinator: CamillaDSPCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[CamillaDSPSensor] = [
        CamillaDSPSensor(coordinator, desc)
        for desc in coordinator.descriptors
        if desc.platform == EntityPlatform.SENSOR
    ]
    async_add_entities(entities)

    entity_map: dict[str, CamillaDSPSensor] = {e.unique_id: e for e in entities}

    @callback
    def _on_descriptors_changed(
        added: list[EntityDescriptor],
        removed: list[EntityDescriptor],
        unchanged: list[EntityDescriptor],
    ) -> None:
        """Handle dynamic descriptor changes."""
        for desc in removed:
            entity = entity_map.pop(desc.unique_id, None)
            if entity is not None:
                entity.mark_descriptor_removed()

        for desc in unchanged:
            entity = entity_map.get(desc.unique_id)
            if entity is not None and entity._descriptor_removed:
                entity.mark_descriptor_restored(desc)

        new_entities: list[CamillaDSPSensor] = []
        for desc in added:
            if (
                desc.platform == EntityPlatform.SENSOR
                and desc.unique_id not in entity_map
            ):
                ent = CamillaDSPSensor(coordinator, desc)
                new_entities.append(ent)
                entity_map[desc.unique_id] = ent

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(
        coordinator.register_descriptor_listener(_on_descriptors_changed)
    )


class CamillaDSPSensor(CamillaDSPEntity, SensorEntity):
    """Read-only telemetry entity for CamillaDSP.

    Uses the descriptor's ``translation_key`` to determine which runtime
    field to read from the coordinator.
    """

    def __init__(
        self,
        coordinator: CamillaDSPCoordinator,
        descriptor: EntityDescriptor,
    ) -> None:
        super().__init__(coordinator, descriptor)

        self._attr_native_unit_of_measurement = (
            descriptor.unit or descriptor.native_unit
        )

        if descriptor.device_class:
            self._attr_device_class = descriptor.device_class

        if descriptor.state_class:
            self._attr_state_class = SensorStateClass(descriptor.state_class)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> Any:
        """Return the current sensor value from coordinator data."""
        tkey = self.descriptor.translation_key

        # --- Runtime status fields ---
        if tkey in _STATUS_FIELD_MAP:
            status = self.coordinator.status
            if status is None:
                return None
            value = getattr(status, _STATUS_FIELD_MAP[tkey], None)
            return self._coerce(value)

        # --- Volume (read-only mirror) ---
        if tkey == "volume_sensor":
            vol = self.coordinator.volume
            if vol is not None:
                return round(vol, 1)
            return None

        # --- Mute (read-only mirror) ---
        if tkey == "mute_sensor":
            mute = self.coordinator.mute
            if mute is None:
                return None
            return "On" if mute else "Off"

        # --- Active config filename (read-only mirror) ---
        if tkey == "active_config_filename":
            return self.coordinator.active_filename

        # --- Config-path sensors (future extensibility) ---
        if self.descriptor.config_path:
            return self._coerce(self._get_config_value())

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _coerce(self, value: Any) -> Any:
        """Coerce a raw value to the descriptor's value_type for display.

        Returns None if the value cannot be converted.
        """
        if value is None:
            return None
        vtype = self.descriptor.value_type
        try:
            if vtype is float:
                return round(float(value), 2)
            if vtype is int:
                return int(value)
            if vtype is str:
                return str(value)
            if vtype is bool:
                return "On" if value else "Off"
            return value
        except (TypeError, ValueError):
            return None
