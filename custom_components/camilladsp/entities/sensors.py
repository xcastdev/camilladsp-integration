"""Sensor entity descriptor factories for CamillaDSP.

Emits read-only descriptors for runtime telemetry and status:

- DSP state (Running / Paused / Inactive / …)
- Capture sample rate
- Buffer level
- Clipped samples
- Processing load (%)
- Active config filename
- Volume (read-only display)
- Mute state (read-only display)
"""

from __future__ import annotations

import logging
from typing import Any

from ..api.models import RuntimeStatus
from .descriptors import EntityDescriptor, EntityPlatform, MutationStrategy

_LOGGER = logging.getLogger(__name__)


def build_sensor_descriptors(
    config_doc: dict[str, Any],
    entry_id: str,
    status: RuntimeStatus | None = None,
) -> list[EntityDescriptor]:
    """Build sensor entity descriptors for runtime telemetry.

    Sensors are always emitted regardless of config content – they
    represent the runtime state of the DSP process, not the config
    document.
    """
    return [
        # -- DSP state --
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_status_state",
            platform=EntityPlatform.SENSOR,
            label="DSP State",
            translation_key="status_state",
            config_path=None,
            node_type=None,
            subtype=None,
            value_type=str,
            mutation_strategy=MutationStrategy.READ_ONLY,
            icon="mdi:state-machine",
            entity_category="diagnostic",
        ),
        # -- Capture sample rate --
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_status_capture_rate",
            platform=EntityPlatform.SENSOR,
            label="Capture Rate",
            translation_key="status_capture_rate",
            config_path=None,
            node_type=None,
            subtype=None,
            value_type=int,
            unit="Hz",
            native_unit="Hz",
            mutation_strategy=MutationStrategy.READ_ONLY,
            icon="mdi:metronome",
            entity_category="diagnostic",
            state_class="measurement",
        ),
        # -- Buffer level --
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_status_buffer_level",
            platform=EntityPlatform.SENSOR,
            label="Buffer Level",
            translation_key="status_buffer_level",
            config_path=None,
            node_type=None,
            subtype=None,
            value_type=int,
            mutation_strategy=MutationStrategy.READ_ONLY,
            icon="mdi:buffer",
            entity_category="diagnostic",
            state_class="measurement",
        ),
        # -- Clipped samples --
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_status_clipped_samples",
            platform=EntityPlatform.SENSOR,
            label="Clipped Samples",
            translation_key="status_clipped_samples",
            config_path=None,
            node_type=None,
            subtype=None,
            value_type=int,
            mutation_strategy=MutationStrategy.READ_ONLY,
            icon="mdi:alert-circle-outline",
            entity_category="diagnostic",
            state_class="total_increasing",
        ),
        # -- Processing load --
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_status_processing_load",
            platform=EntityPlatform.SENSOR,
            label="Processing Load",
            translation_key="status_processing_load",
            config_path=None,
            node_type=None,
            subtype=None,
            value_type=float,
            unit="%",
            native_unit="%",
            mutation_strategy=MutationStrategy.READ_ONLY,
            icon="mdi:gauge",
            entity_category="diagnostic",
            state_class="measurement",
        ),
        # -- Active config filename --
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_active_config_filename",
            platform=EntityPlatform.SENSOR,
            label="Active Config File",
            translation_key="active_config_filename",
            config_path=None,
            node_type=None,
            subtype=None,
            value_type=str,
            mutation_strategy=MutationStrategy.READ_ONLY,
            icon="mdi:file-document-outline",
            entity_category="diagnostic",
        ),
        # -- Volume (read-only sensor) --
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_volume_sensor",
            platform=EntityPlatform.SENSOR,
            label="Volume",
            translation_key="volume_sensor",
            config_path=None,
            node_type=None,
            subtype=None,
            value_type=float,
            unit="dB",
            native_unit="dB",
            mutation_strategy=MutationStrategy.READ_ONLY,
            icon="mdi:volume-high",
            state_class="measurement",
        ),
        # -- Mute state (read-only sensor) --
        EntityDescriptor(
            unique_id=f"camilladsp_{entry_id}_mute_sensor",
            platform=EntityPlatform.SENSOR,
            label="Mute",
            translation_key="mute_sensor",
            config_path=None,
            node_type=None,
            subtype=None,
            value_type=bool,
            mutation_strategy=MutationStrategy.READ_ONLY,
            icon="mdi:volume-off",
        ),
    ]
