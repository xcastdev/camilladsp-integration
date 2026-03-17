"""Select entity descriptor factories for CamillaDSP.

Emits descriptors for choice-based controls:

- **Active config file** – switches between stored config files.
- **Mixer source scale** – ``"dB"`` / ``"linear"`` per source channel.
"""

from __future__ import annotations

import logging
from typing import Any

from ..api.models import StoredConfig
from .descriptors import EntityDescriptor, EntityPlatform, MutationStrategy
from .utils import sanitize_id

_LOGGER = logging.getLogger(__name__)

_SCALE_OPTIONS = ["dB", "linear"]


def build_select_descriptors(
    config_doc: dict[str, Any],
    entry_id: str,
    stored_configs: list[StoredConfig] | None = None,
) -> list[EntityDescriptor]:
    """Build select entity descriptors from the normalized config."""
    descriptors: list[EntityDescriptor] = []
    descriptors.extend(_build_active_config_select(entry_id, stored_configs))
    descriptors.extend(_build_mixer_scale_selects(config_doc, entry_id))
    return descriptors


# ------------------------------------------------------------------
# Active config file selector
# ------------------------------------------------------------------


def _build_active_config_select(
    entry_id: str,
    stored_configs: list[StoredConfig] | None,
) -> list[EntityDescriptor]:
    """Emit a single select for the active config file.

    The options list is populated from the stored configs; if none are
    available yet the entity is still created with an empty options list
    (it will be updated on the next coordinator refresh).
    """
    options: list[str] = []
    if stored_configs:
        options = sorted(cfg.name for cfg in stored_configs if cfg.name)

    return [
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_active_config",
            platform=EntityPlatform.SELECT,
            label="Active Config",
            translation_key="active_config",
            config_path=None,  # not a config-doc field
            node_type=None,
            subtype=None,
            value_type=str,
            options=options,
            mutation_strategy=MutationStrategy.ACTIVE_CONFIG,
            icon="mdi:file-cog-outline",
            entity_category="config",
        )
    ]


# ------------------------------------------------------------------
# Mixer source scale selector
# ------------------------------------------------------------------


def _build_mixer_scale_selects(
    config_doc: dict[str, Any],
    entry_id: str,
) -> list[EntityDescriptor]:
    descriptors: list[EntityDescriptor] = []

    for mixer_name, mixer in config_doc.get("mixers", {}).items():
        msid = sanitize_id(mixer_name)
        for m_idx, mapping in enumerate(mixer.get("mapping", [])):
            dest = mapping.get("dest", m_idx)
            for s_idx, source in enumerate(mapping.get("sources", [])):
                channel = source.get("channel", s_idx)
                if "scale" in source:
                    descriptors.append(
                        EntityDescriptor(
                            unique_id=(
                                f"camilladsp_{entry_id}_mixer_{msid}"
                                f"_mapping_{m_idx}_source_{s_idx}_scale"
                            ),
                            platform=EntityPlatform.SELECT,
                            label=f"{mixer_name} Out {dest} Src {channel} Scale",
                            translation_key="mixer_source_scale",
                            config_path=(
                                f"mixers.{mixer_name}.mapping[{m_idx}]"
                                f".sources[{s_idx}].scale"
                            ),
                            node_type="Mixer",
                            subtype=None,
                            value_type=str,
                            options=list(_SCALE_OPTIONS),
                            icon="mdi:scale-balance",
                            entity_category="config",
                        )
                    )

    return descriptors
