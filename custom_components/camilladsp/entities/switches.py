"""Switch entity descriptor factories for CamillaDSP.

Emits descriptors for boolean toggles found in the normalized config:

- **Gain filter**: ``parameters.inverted``, ``parameters.mute``
- **Biquad GeneralNotch**: ``parameters.normalize_at_dc``
- **Pipeline steps**: ``bypassed`` flag
- **Compressor processor**: ``parameters.soft_clip``
- **Mixer sources**: ``mute``, ``inverted``
"""

from __future__ import annotations

import logging
from typing import Any

from .descriptors import EntityDescriptor, EntityPlatform, MutationStrategy
from .utils import is_tokenized, resolve_config_value, sanitize_id

_LOGGER = logging.getLogger(__name__)


def build_switch_descriptors(
    config_doc: dict[str, Any],
    entry_id: str,
) -> list[EntityDescriptor]:
    """Build switch entity descriptors from the normalized config."""
    descriptors: list[EntityDescriptor] = []
    descriptors.extend(_build_filter_switches(config_doc, entry_id))
    descriptors.extend(_build_pipeline_switches(config_doc, entry_id))
    descriptors.extend(_build_processor_switches(config_doc, entry_id))
    descriptors.extend(_build_mixer_switches(config_doc, entry_id))

    # Mark tokenized parameters as non-editable (read-only)
    descriptors = _apply_token_detection(descriptors, config_doc)

    return descriptors


def _apply_token_detection(
    descriptors: list[EntityDescriptor],
    config_doc: dict[str, Any],
) -> list[EntityDescriptor]:
    """Replace descriptors whose backing value is tokenized with non-editable copies."""
    result: list[EntityDescriptor] = []
    for desc in descriptors:
        if desc.config_path and is_tokenized(
            resolve_config_value(config_doc, desc.config_path)
        ):
            _LOGGER.debug(
                "Marking %s as non-editable (tokenized value)", desc.unique_id
            )
            from dataclasses import replace

            desc = replace(desc, editable=False)
        result.append(desc)
    return result


# ------------------------------------------------------------------
# Filter switches
# ------------------------------------------------------------------


def _build_filter_switches(
    config_doc: dict[str, Any],
    entry_id: str,
) -> list[EntityDescriptor]:
    descriptors: list[EntityDescriptor] = []

    for name, filt in config_doc.get("filters", {}).items():
        filter_type = filt.get("filter_type")
        params = filt.get("parameters", {})
        sid = sanitize_id(name)

        # Gain filter: inverted, mute
        if filter_type == "Gain":
            if "inverted" in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_inverted",
                        platform=EntityPlatform.SWITCH,
                        label=f"{name} Inverted",
                        translation_key="filter_gain_inverted",
                        config_path=f"filters.{name}.parameters.inverted",
                        node_type="Gain",
                        subtype=None,
                        value_type=bool,
                        icon="mdi:swap-vertical",
                        entity_category="config",
                    )
                )
            if "mute" in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_mute",
                        platform=EntityPlatform.SWITCH,
                        label=f"{name} Mute",
                        translation_key="filter_gain_mute",
                        config_path=f"filters.{name}.parameters.mute",
                        node_type="Gain",
                        subtype=None,
                        value_type=bool,
                        icon="mdi:volume-off",
                    )
                )

        # Biquad GeneralNotch: normalize_at_dc
        if filter_type == "Biquad" and filt.get("variant") == "GeneralNotch":
            if "normalize_at_dc" in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_normalize_at_dc",
                        platform=EntityPlatform.SWITCH,
                        label=f"{name} Normalize at DC",
                        translation_key="filter_biquad_normalize_at_dc",
                        config_path=f"filters.{name}.parameters.normalize_at_dc",
                        node_type="Biquad",
                        subtype="GeneralNotch",
                        value_type=bool,
                        icon="mdi:tune",
                        entity_category="config",
                    )
                )

    return descriptors


# ------------------------------------------------------------------
# Pipeline step bypass switches
# ------------------------------------------------------------------


def _build_pipeline_switches(
    config_doc: dict[str, Any],
    entry_id: str,
) -> list[EntityDescriptor]:
    descriptors: list[EntityDescriptor] = []

    for step in config_doc.get("pipeline", []):
        # Only emit a bypass switch when the field is explicitly present
        # (some step types don't support bypass).
        if step.get("bypassed") is not None:
            step_id = step.get("step_id", "")
            step_type = step.get("step_type", "unknown")
            step_name = step.get("name") or step.get("step_id", "")
            sid = sanitize_id(step_id)

            descriptors.append(
                EntityDescriptor(
                    unique_id=f"camilladsp_{entry_id}_pipeline_{sid}_bypassed",
                    platform=EntityPlatform.SWITCH,
                    label=f"Pipeline {step_name} Bypass",
                    translation_key="pipeline_step_bypassed",
                    config_path=f"pipeline[{_pipeline_index(config_doc, step_id)}].bypassed",
                    node_type=step_type,
                    subtype=None,
                    value_type=bool,
                    icon="mdi:debug-step-over",
                    entity_category="config",
                )
            )

    return descriptors


def _pipeline_index(config_doc: dict[str, Any], step_id: str) -> int:
    """Resolve a step_id to its integer index in the pipeline list."""
    for idx, step in enumerate(config_doc.get("pipeline", [])):
        if step.get("step_id") == step_id:
            return idx
    return 0  # fallback — should not happen with well-formed data


# ------------------------------------------------------------------
# Processor switches
# ------------------------------------------------------------------


def _build_processor_switches(
    config_doc: dict[str, Any],
    entry_id: str,
) -> list[EntityDescriptor]:
    descriptors: list[EntityDescriptor] = []

    for name, proc in config_doc.get("processors", {}).items():
        proc_type = proc.get("processor_type")
        params = proc.get("parameters", {})
        sid = sanitize_id(name)

        if proc_type == "Compressor":
            if "soft_clip" in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_processor_{sid}_soft_clip",
                        platform=EntityPlatform.SWITCH,
                        label=f"{name} Soft Clip",
                        translation_key="processor_compressor_soft_clip",
                        config_path=f"processors.{name}.parameters.soft_clip",
                        node_type="Compressor",
                        subtype=None,
                        value_type=bool,
                        icon="mdi:content-cut",
                        entity_category="config",
                    )
                )

    return descriptors


# ------------------------------------------------------------------
# Mixer source switches
# ------------------------------------------------------------------


def _build_mixer_switches(
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
                ssid = f"{msid}_mapping_{m_idx}_source_{s_idx}"

                if "mute" in source:
                    descriptors.append(
                        EntityDescriptor(
                            unique_id=f"camilladsp_{entry_id}_mixer_{ssid}_mute",
                            platform=EntityPlatform.SWITCH,
                            label=f"{mixer_name} Out {dest} Src {channel} Mute",
                            translation_key="mixer_source_mute",
                            config_path=(
                                f"mixers.{mixer_name}.mapping[{m_idx}]"
                                f".sources[{s_idx}].mute"
                            ),
                            node_type="Mixer",
                            subtype=None,
                            value_type=bool,
                            icon="mdi:volume-off",
                        )
                    )

                if "inverted" in source:
                    descriptors.append(
                        EntityDescriptor(
                            unique_id=f"camilladsp_{entry_id}_mixer_{ssid}_inverted",
                            platform=EntityPlatform.SWITCH,
                            label=f"{mixer_name} Out {dest} Src {channel} Inverted",
                            translation_key="mixer_source_inverted",
                            config_path=(
                                f"mixers.{mixer_name}.mapping[{m_idx}]"
                                f".sources[{s_idx}].inverted"
                            ),
                            node_type="Mixer",
                            subtype=None,
                            value_type=bool,
                            icon="mdi:swap-vertical",
                            entity_category="config",
                        )
                    )

    return descriptors
