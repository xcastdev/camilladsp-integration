"""CamillaDSP select platform – choice-based controls.

Exposes:
- **Active config file** selector – switches between stored configs on
  the CamillaDSP backend.
- **Mixer source scale** selectors (``dB`` / ``linear``).

Write strategy:
- ``ACTIVE_CONFIG`` → ``coordinator.async_switch_active_config()``.
- ``CONFIG_PATH`` → ``coordinator.async_apply_value()`` (immediate).
"""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    """Set up CamillaDSP select entities from descriptors."""
    coordinator: CamillaDSPCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[CamillaDSPSelect] = [
        CamillaDSPSelect(coordinator, desc)
        for desc in coordinator.descriptors
        if desc.platform == EntityPlatform.SELECT
    ]
    async_add_entities(entities)

    entity_map: dict[str, CamillaDSPSelect] = {e.unique_id: e for e in entities}

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

        # Unchanged descriptors may carry updated options (e.g. new stored
        # configs appeared).  Push the updated descriptor into the entity.
        for desc in unchanged:
            entity = entity_map.get(desc.unique_id)
            if entity is not None:
                if entity._descriptor_removed:
                    entity.mark_descriptor_restored(desc)
                else:
                    # Refresh descriptor in-place (new options list, etc.).
                    entity.descriptor = desc

        new_entities: list[CamillaDSPSelect] = []
        for desc in added:
            if (
                desc.platform == EntityPlatform.SELECT
                and desc.unique_id not in entity_map
            ):
                ent = CamillaDSPSelect(coordinator, desc)
                new_entities.append(ent)
                entity_map[desc.unique_id] = ent

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(
        coordinator.register_descriptor_listener(_on_descriptors_changed)
    )


class CamillaDSPSelect(CamillaDSPEntity, SelectEntity):
    """Choice-based control entity for CamillaDSP.

    For the active-config selector, ``options`` comes from stored configs
    and ``current_option`` from the coordinator's active filename.
    For config-path selectors, both come from the descriptor and config doc.
    """

    def __init__(
        self,
        coordinator: CamillaDSPCoordinator,
        descriptor: EntityDescriptor,
    ) -> None:
        super().__init__(coordinator, descriptor)

        if descriptor.device_class:
            self._attr_device_class = descriptor.device_class

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        strategy = self.descriptor.mutation_strategy

        if strategy == MutationStrategy.ACTIVE_CONFIG:
            # Dynamic: options are the currently known stored config names.
            configs = self.coordinator.stored_configs
            if configs:
                return sorted(cfg.name for cfg in configs if cfg.name)
            return []

        # Static options from the descriptor (e.g. mixer scale: dB / linear).
        return self.descriptor.options or []

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        strategy = self.descriptor.mutation_strategy

        if strategy == MutationStrategy.ACTIVE_CONFIG:
            return self.coordinator.active_filename

        # Default: read from config doc path.
        value = self._get_config_value()
        if value is not None:
            str_value = str(value)
            # Only return a value that is in the current options list.
            if str_value in (self.descriptor.options or []):
                return str_value
        return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_select_option(self, option: str) -> None:
        """Handle option selection."""
        strategy = self.descriptor.mutation_strategy

        if strategy == MutationStrategy.ACTIVE_CONFIG:
            await self.coordinator.async_switch_active_config(option)
            return

        if strategy == MutationStrategy.CONFIG_PATH and self.descriptor.config_path:
            await self.coordinator.async_apply_value(
                self.descriptor.config_path, option
            )
