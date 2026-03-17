"""Common descriptor-backed entity base class for CamillaDSP.

All platform entities (number, switch, select, sensor) inherit from
:class:`CamillaDSPEntity`, which wires up:

- Unique ID, name, icon, entity category, and translation key from the
  descriptor.
- A shared ``device_info`` property so every entity for a given config
  entry appears under a single HA device.
- A ``_get_config_value`` helper that resolves the descriptor's
  ``config_path`` against the coordinator's cached config document.
- An ``available`` property that combines the coordinator's connectivity
  state with the descriptor's ``available`` flag.
- Tracking of *removed* descriptors: when a descriptor rebuild drops
  this entity, it is marked unavailable rather than deleted.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config.paths import resolve_path
from .const import DOMAIN
from .coordinator import CamillaDSPCoordinator
from .entities.descriptors import EntityDescriptor

_LOGGER = logging.getLogger(__name__)


class CamillaDSPEntity(CoordinatorEntity[CamillaDSPCoordinator]):
    """Base class for all descriptor-driven CamillaDSP entities.

    Sub-classes should also inherit from the platform entity class
    (e.g. ``NumberEntity``) using Python MRO::

        class CamillaDSPNumber(CamillaDSPEntity, NumberEntity): ...

    The entity reads its current state from ``self.coordinator`` on
    every coordinator update.  Writes go through the coordinator's
    mutation helpers.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CamillaDSPCoordinator,
        descriptor: EntityDescriptor,
    ) -> None:
        super().__init__(coordinator)
        self.descriptor = descriptor

        # --- HA entity attributes from descriptor ---
        self._attr_unique_id = descriptor.unique_id
        self._attr_name = descriptor.label
        self._attr_icon = descriptor.icon

        if descriptor.entity_category:
            self._attr_entity_category = EntityCategory(descriptor.entity_category)

        if descriptor.translation_key:
            self._attr_translation_key = descriptor.translation_key

        # Track whether the descriptor has been removed in a rebuild.
        self._descriptor_removed = False

    # ------------------------------------------------------------------
    # Device grouping
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info – groups all entities under one HA device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=f"CamillaDSP ({self.coordinator.entry.data.get('host', 'unknown')})",
            manufacturer="CamillaDSP",
            model="DSP Processor",
        )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Entity is available when coordinator is connected and descriptor is live."""
        if self._descriptor_removed:
            return False
        return super().available and self.descriptor.available

    def mark_descriptor_removed(self) -> None:
        """Mark this entity as removed after a descriptor rebuild.

        The entity stays registered in HA (so the user can manually
        delete it or it can come back) but reports ``available=False``.
        """
        self._descriptor_removed = True
        self.async_write_ha_state()

    def mark_descriptor_restored(self, descriptor: EntityDescriptor) -> None:
        """Restore availability after the descriptor reappears."""
        self.descriptor = descriptor
        self._descriptor_removed = False
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Config value helpers
    # ------------------------------------------------------------------

    def _get_config_value(self) -> Any:
        """Read the current value from the normalized config doc.

        Uses the descriptor's ``config_path`` to resolve into the
        coordinator's cached config document.  Returns ``None`` when the
        path is absent or the document is not loaded.
        """
        doc = self.coordinator.config_doc
        if doc is None or self.descriptor.config_path is None:
            return None
        try:
            return resolve_path(doc, self.descriptor.config_path)
        except (KeyError, IndexError, TypeError):
            _LOGGER.debug(
                "Path %s not found in config doc for %s",
                self.descriptor.config_path,
                self.descriptor.unique_id,
            )
            return None
