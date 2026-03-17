"""Descriptor builder – walks a normalized config and emits EntityDescriptors.

The top-level :func:`build_descriptors` function delegates to per-platform
factories defined in sibling modules (numbers, switches, selects, sensors).
"""

from __future__ import annotations

from typing import Any

from ..api.models import RuntimeStatus, StoredConfig
from .descriptors import EntityDescriptor
from .numbers import build_number_descriptors
from .selects import build_select_descriptors
from .sensors import build_sensor_descriptors
from .switches import build_switch_descriptors
from .utils import sanitize_id


def build_descriptors(
    config_doc: dict[str, Any],
    entry_id: str,
    stored_configs: list[StoredConfig] | None = None,
    status: RuntimeStatus | None = None,
) -> list[EntityDescriptor]:
    """Build all entity descriptors from the normalized config document.

    Parameters
    ----------
    config_doc:
        The normalized config document (see :mod:`config.schema`).
    entry_id:
        The config entry ID (used as part of unique IDs).
    stored_configs:
        Available stored config files – used for the active-config select.
    status:
        Current runtime status – used to seed sensor descriptors.

    Returns
    -------
    list[EntityDescriptor]
        A flat list of descriptors for every entity the current config
        document can expose.
    """
    descriptors: list[EntityDescriptor] = []
    descriptors.extend(build_number_descriptors(config_doc, entry_id))
    descriptors.extend(build_switch_descriptors(config_doc, entry_id))
    descriptors.extend(build_select_descriptors(config_doc, entry_id, stored_configs))
    descriptors.extend(build_sensor_descriptors(config_doc, entry_id, status))
    return descriptors


def diff_descriptors(
    old: list[EntityDescriptor],
    new: list[EntityDescriptor],
) -> tuple[list[EntityDescriptor], list[EntityDescriptor], list[EntityDescriptor]]:
    """Compare two descriptor sets by unique_id.

    Returns
    -------
    tuple
        ``(added, removed, unchanged)`` where each element is a list of
        :class:`EntityDescriptor`.  ``unchanged`` uses the *new* descriptor
        instances (they may carry updated options/ranges even though the ID
        is the same).
    """
    old_by_id = {d.unique_id: d for d in old}
    new_by_id = {d.unique_id: d for d in new}

    added = [d for uid, d in new_by_id.items() if uid not in old_by_id]
    removed = [d for uid, d in old_by_id.items() if uid not in new_by_id]
    unchanged = [d for uid, d in new_by_id.items() if uid in old_by_id]
    return added, removed, unchanged


__all__ = ["build_descriptors", "diff_descriptors", "sanitize_id"]
