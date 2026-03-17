"""CamillaDSP number platform – slider and box controls.

Exposes every numeric parameter from the config document (filter gains,
EQ frequencies, mixer gains, compressor thresholds, …) and the global
volume as HA ``number`` entities.

Write strategy:
- ``VOLUME_FAST`` → ``coordinator.async_set_volume()`` (fast-path).
- ``CONFIG_PATH`` → ``coordinator.schedule_debounced_update()`` for
  slider-friendly debounce by default.
"""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CamillaDSPCoordinator
from .entities.descriptors import EntityDescriptor, EntityPlatform, MutationStrategy
from .entity import CamillaDSPEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CamillaDSP number entities from descriptors."""
    coordinator: CamillaDSPCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    # Build initial entities from current descriptors.
    entities: list[CamillaDSPNumber] = [
        CamillaDSPNumber(coordinator, desc)
        for desc in coordinator.descriptors
        if desc.platform == EntityPlatform.NUMBER
    ]
    async_add_entities(entities)

    # Index live entities by unique_id for the listener.
    entity_map: dict[str, CamillaDSPNumber] = {e.unique_id: e for e in entities}

    @callback
    def _on_descriptors_changed(
        added: list[EntityDescriptor],
        removed: list[EntityDescriptor],
        unchanged: list[EntityDescriptor],
    ) -> None:
        """Handle dynamic descriptor changes."""
        # Mark removed entities as unavailable.
        for desc in removed:
            entity = entity_map.pop(desc.unique_id, None)
            if entity is not None:
                entity.mark_descriptor_removed()

        # Restore entities that reappeared in the unchanged set with
        # potentially updated metadata (new ranges, etc.).
        for desc in unchanged:
            entity = entity_map.get(desc.unique_id)
            if entity is not None and entity._descriptor_removed:
                entity.mark_descriptor_restored(desc)

        # Create new entities for added descriptors.
        new_entities: list[CamillaDSPNumber] = []
        for desc in added:
            if (
                desc.platform == EntityPlatform.NUMBER
                and desc.unique_id not in entity_map
            ):
                ent = CamillaDSPNumber(coordinator, desc)
                new_entities.append(ent)
                entity_map[desc.unique_id] = ent

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(
        coordinator.register_descriptor_listener(_on_descriptors_changed)
    )


class CamillaDSPNumber(CamillaDSPEntity, NumberEntity):
    """Numeric control entity for CamillaDSP.

    Supports both slider-mode (debounced writes) and box-mode (immediate
    writes) depending on the descriptor's ``editable`` flag.
    """

    def __init__(
        self,
        coordinator: CamillaDSPCoordinator,
        descriptor: EntityDescriptor,
    ) -> None:
        super().__init__(coordinator, descriptor)

        self._attr_native_min_value = (
            descriptor.min_value if descriptor.min_value is not None else -100.0
        )
        self._attr_native_max_value = (
            descriptor.max_value if descriptor.max_value is not None else 100.0
        )
        self._attr_native_step = descriptor.step if descriptor.step is not None else 0.1
        self._attr_native_unit_of_measurement = (
            descriptor.unit or descriptor.native_unit
        )
        self._attr_mode = NumberMode.SLIDER if descriptor.editable else NumberMode.BOX

        if descriptor.device_class:
            self._attr_device_class = descriptor.device_class

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> float | None:
        """Return the current numeric value."""
        strategy = self.descriptor.mutation_strategy

        if strategy == MutationStrategy.VOLUME_FAST:
            return self.coordinator.volume

        # Default: read from the config document.
        value = self._get_config_value()
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_set_native_value(self, value: float) -> None:
        """Handle value changes – uses debounce for config-path writes."""
        strategy = self.descriptor.mutation_strategy

        if strategy == MutationStrategy.VOLUME_FAST:
            await self.coordinator.async_set_volume(value)
            return

        if strategy == MutationStrategy.CONFIG_PATH and self.descriptor.config_path:
            # Cast to the descriptor's target type before writing.
            typed_value: int | float = (
                int(value) if self.descriptor.value_type is int else value
            )
            self.coordinator.schedule_debounced_update(
                self.descriptor.config_path, typed_value
            )
