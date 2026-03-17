"""Diagnostics support for CamillaDSP."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_BASE_URL, DATA_COORDINATOR, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a CamillaDSP config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    # Config shape summary
    config_doc = coordinator.config_doc or {}
    filter_types: dict[str, int] = {}
    for _name, filt in config_doc.get("filters", {}).items():
        ft = filt.get("filter_type", "unknown")
        filter_types[ft] = filter_types.get(ft, 0) + 1

    # Descriptor counts by platform
    descriptor_counts: dict[str, int] = {}
    for desc in coordinator.descriptors:
        platform = desc.platform.value
        descriptor_counts[platform] = descriptor_counts.get(platform, 0) + 1

    return {
        "base_url": entry.data.get(CONF_BASE_URL),
        "active_config_file": coordinator.active_filename,
        "gui_config": (
            {
                "can_update_active_config": (
                    coordinator.gui_config.can_update_active_config
                ),
                "apply_config_automatically": (
                    coordinator.gui_config.apply_config_automatically
                ),
                "save_config_automatically": (
                    coordinator.gui_config.save_config_automatically
                ),
            }
            if coordinator.gui_config
            else None
        ),
        "config_shape": {
            "filter_count": len(config_doc.get("filters", {})),
            "filter_types": filter_types,
            "mixer_count": len(config_doc.get("mixers", {})),
            "processor_count": len(config_doc.get("processors", {})),
            "pipeline_steps": len(config_doc.get("pipeline", [])),
        },
        "descriptor_counts": descriptor_counts,
        "stored_configs": [c.name for c in coordinator.stored_configs],
        "status": {
            "state": (coordinator.status.state if coordinator.status else None),
            "capture_rate": (
                coordinator.status.capture_rate if coordinator.status else None
            ),
        },
    }
