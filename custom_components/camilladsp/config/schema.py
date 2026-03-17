"""TypedDict definitions for the normalized CamillaDSP config document.

These types describe the *internal* representation used by the integration
after :func:`normalize.normalize_config` transforms a raw backend config.
They are deliberately ``TypedDict``-based so the document stays plain-dict
serializable and dict-compatible throughout the codebase.
"""

from __future__ import annotations

from typing import Any, TypedDict


# ------------------------------------------------------------------
# Section types
# ------------------------------------------------------------------


class MetaSection(TypedDict, total=False):
    """Metadata extracted from the config or supplied externally."""

    filename: str
    title: str | None
    description: str | None


class FilterNode(TypedDict, total=False):
    """A single normalized filter entry.

    ``filter_type`` maps the raw ``type`` field (e.g. ``"Biquad"``).
    ``variant`` captures the sub-type from ``parameters.type`` for filters
    that have one (Biquad → Lowshelf, Conv → Raw, Dither → Flat, …).
    """

    kind: str  # always "filter"
    name: str
    filter_type: str
    variant: str | None
    description: str | None
    parameters: dict[str, Any]
    extra: dict[str, Any]


class MixerNode(TypedDict, total=False):
    """A single normalized mixer entry."""

    kind: str  # always "mixer"
    name: str
    description: str | None
    channels: dict[str, int]  # {"in": N, "out": M}
    mapping: list[dict[str, Any]]
    extra: dict[str, Any]


class ProcessorNode(TypedDict, total=False):
    """A single normalized processor entry."""

    kind: str  # always "processor"
    name: str
    processor_type: str
    parameters: dict[str, Any]
    extra: dict[str, Any]


class PipelineStep(TypedDict, total=False):
    """A single normalized pipeline step."""

    step_id: str  # e.g. "pipeline_0"
    step_type: str  # "Mixer", "Filter", "Processor"
    name: str | None  # for Mixer/Processor steps
    channels: list[int] | None  # for Filter steps
    names: list[str]  # for Filter steps (filter names)
    bypassed: bool | None
    description: str | None
    extra: dict[str, Any]


class NormalizedConfig(TypedDict, total=False):
    """Top-level normalized CamillaDSP config document."""

    meta: MetaSection
    devices: dict[str, Any]
    filters: dict[str, FilterNode]
    mixers: dict[str, MixerNode]
    processors: dict[str, ProcessorNode]
    pipeline: list[PipelineStep]
    extra: dict[str, Any]


# ------------------------------------------------------------------
# Type aliases for readability
# ------------------------------------------------------------------

ConfigPath = str
"""A dot-separated path with optional bracket notation, e.g.
``"filters.Bass Control.parameters.gain"`` or ``"pipeline[1].bypassed"``."""

PathSegments = list[str | int]
"""A parsed path as a list of string keys and integer indices."""
