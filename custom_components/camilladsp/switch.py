"""CamillaDSP switch platform – boolean toggles.

Exposes every boolean parameter from the config document (filter mute,
polarity inversion, pipeline bypass, compressor soft-clip, mixer source
mute/invert), the global mute, and the live-diagnostics toggle as HA
``switch`` entities.

Write strategy:
- ``MUTE_FAST`` → ``coordinator.async_set_mute()`` (fast-path).
- ``LIVE_DIAGNOSTICS`` → ``coordinator.set_live_diagnostics()`` (local).
- ``CONFIG_PATH`` → ``coordinator.async_apply_value()`` (immediate,
  no debounce for booleans).
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
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
    """Set up CamillaDSP switch entities from descriptors."""
    coordinator: CamillaDSPCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[CamillaDSPSwitch] = [
        CamillaDSPSwitch(coordinator, desc)
        for desc in coordinator.descriptors
        if desc.platform == EntityPlatform.SWITCH
    ]
    async_add_entities(entities)

    entity_map: dict[str, CamillaDSPSwitch] = {e.unique_id: e for e in entities}

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

        new_entities: list[CamillaDSPSwitch] = []
        for desc in added:
            if (
                desc.platform == EntityPlatform.SWITCH
                and desc.unique_id not in entity_map
            ):
                ent = CamillaDSPSwitch(coordinator, desc)
                new_entities.append(ent)
                entity_map[desc.unique_id] = ent

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(
        coordinator.register_descriptor_listener(_on_descriptors_changed)
    )


class CamillaDSPSwitch(CamillaDSPEntity, SwitchEntity):
    """Boolean toggle entity for CamillaDSP.

    Reads ``is_on`` from the config doc (or the coordinator's mute
    property for ``MUTE_FAST`` strategy) and writes back through the
    appropriate coordinator method.
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
    def is_on(self) -> bool | None:
        """Return the current switch state."""
        strategy = self.descriptor.mutation_strategy

        if strategy == MutationStrategy.MUTE_FAST:
            # Global mute: the switch represents "muted", so the on-state
            # is True when mute is True.
            return self.coordinator.mute

        if strategy == MutationStrategy.LIVE_DIAGNOSTICS:
            return self.coordinator.live_diagnostics

        # Default: read boolean from config doc.
        value = self._get_config_value()
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        # Handle truthy / falsy edge cases.
        try:
            return bool(value)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._async_set_value(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._async_set_value(False)

    async def _async_set_value(self, value: bool) -> None:
        """Write the boolean value through the coordinator."""
        if not self.descriptor.writable:
            _LOGGER.warning(
                "Ignoring write to non-writable switch entity %s",
                self.descriptor.unique_id,
            )
            return

        strategy = self.descriptor.mutation_strategy

        if strategy == MutationStrategy.MUTE_FAST:
            await self.coordinator.async_set_mute(value)
            return

        if strategy == MutationStrategy.LIVE_DIAGNOSTICS:
            self.coordinator.set_live_diagnostics(value)
            return

        if strategy == MutationStrategy.CONFIG_PATH and self.descriptor.config_path:
            # Boolean writes are immediate – no debounce needed.
            await self.coordinator.async_apply_value(self.descriptor.config_path, value)
