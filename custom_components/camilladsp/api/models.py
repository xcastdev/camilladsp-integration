"""Lightweight dataclasses for CamillaDSP API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GuiConfig:
    """GUI configuration and capabilities from ``/api/guiconfig``.

    Fields mirror the JSON keys returned by the backend, converted to
    snake_case.  Missing keys fall back to safe defaults so the integration
    degrades gracefully against older backend versions.
    """

    hide_capture_samplerate: bool = False
    hide_silence: bool = False
    hide_capture_device: bool = False
    hide_playback_device: bool = False
    apply_config_automatically: bool = False
    save_config_automatically: bool = False
    status_update_interval: int = 100
    can_update_active_config: bool = True
    coeff_dir: str = ""
    supported_capture_types: list[str] | None = None
    supported_playback_types: list[str] | None = None


@dataclass
class ActiveConfigFile:
    """Active config file info from ``/api/getactiveconfigfile``."""

    filename: str
    config: dict[str, Any]


@dataclass
class StoredConfig:
    """Stored config file entry from ``/api/storedconfigs``."""

    name: str
    last_modified: float | None = None


@dataclass
class RuntimeStatus:
    """Runtime telemetry from ``/api/status``.

    The ``raw`` field always contains the full, unparsed JSON dict so
    consumers can access keys that are not yet modelled explicitly.
    """

    state: str = "unknown"
    capture_rate: int = 0
    rate_adjust: float = 0.0
    clipped_samples: int = 0
    buffer_level: int = 0
    processing_load: float = 0.0
    signal_range: float = 0.0
    signal_rms: float = 0.0
    capture_signal_peak: list[float] = field(default_factory=list)
    capture_signal_rms: list[float] = field(default_factory=list)
    playback_signal_peak: list[float] = field(default_factory=list)
    playback_signal_rms: list[float] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
