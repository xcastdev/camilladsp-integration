"""Number entity descriptor factories for CamillaDSP.

Walks filters, processors, and mixers in the normalized config document
and emits :class:`EntityDescriptor` instances for every numeric parameter
that should be exposed as an HA ``number`` entity.
"""

from __future__ import annotations

import logging
from typing import Any

from .descriptors import EntityDescriptor, EntityPlatform, MutationStrategy
from .utils import is_tokenized, resolve_config_value, sanitize_id

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------


def build_number_descriptors(
    config_doc: dict[str, Any],
    entry_id: str,
) -> list[EntityDescriptor]:
    """Build number entity descriptors from the normalized config."""
    descriptors: list[EntityDescriptor] = []
    descriptors.extend(_build_filter_numbers(config_doc, entry_id))
    descriptors.extend(_build_processor_numbers(config_doc, entry_id))
    descriptors.extend(_build_mixer_numbers(config_doc, entry_id))

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
            # Frozen dataclass – create a replacement with editable=False
            from dataclasses import replace

            desc = replace(desc, editable=False)
        result.append(desc)
    return result


# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------


def _build_filter_numbers(
    config_doc: dict[str, Any],
    entry_id: str,
) -> list[EntityDescriptor]:
    descriptors: list[EntityDescriptor] = []

    for name, filt in config_doc.get("filters", {}).items():
        filter_type = filt.get("filter_type")
        variant = filt.get("variant")
        params = filt.get("parameters", {})
        sid = sanitize_id(name)

        if filter_type == "Gain":
            descriptors.extend(_gain_filter_numbers(params, entry_id, name, sid))
        elif filter_type == "Volume":
            descriptors.extend(_volume_filter_numbers(params, entry_id, name, sid))
        elif filter_type == "Loudness":
            descriptors.extend(_loudness_filter_numbers(params, entry_id, name, sid))
        elif filter_type == "Delay":
            descriptors.extend(_delay_filter_numbers(params, entry_id, name, sid))
        elif filter_type == "Biquad":
            descriptors.extend(
                _biquad_filter_numbers(params, entry_id, name, sid, variant)
            )
        elif filter_type == "BiquadCombo":
            descriptors.extend(
                _biquadcombo_filter_numbers(params, entry_id, name, sid, variant)
            )
        elif filter_type == "Dither":
            descriptors.extend(
                _dither_filter_numbers(params, entry_id, name, sid, variant)
            )
        elif filter_type == "Conv":
            # Conv filters are coefficient-based; no numeric parameters to expose.
            pass
        elif filter_type == "DiffEq":
            descriptors.extend(_diffeq_filter_numbers(params, entry_id, name, sid))
        else:
            _LOGGER.debug(
                "Skipping unrecognised filter type %r for number descriptors",
                filter_type,
            )

    return descriptors


def _gain_filter_numbers(
    params: dict[str, Any],
    entry_id: str,
    name: str,
    sid: str,
) -> list[EntityDescriptor]:
    """Gain filter: gain (dB), scale."""
    descriptors: list[EntityDescriptor] = []
    if "gain" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_gain",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Gain",
                translation_key="filter_gain",
                config_path=f"filters.{name}.parameters.gain",
                node_type="Gain",
                subtype=None,
                value_type=float,
                unit="dB",
                min_value=-100.0,
                max_value=100.0,
                step=0.1,
                icon="mdi:volume-medium",
            )
        )
    return descriptors


def _volume_filter_numbers(
    params: dict[str, Any],
    entry_id: str,
    name: str,
    sid: str,
) -> list[EntityDescriptor]:
    """Volume filter: ramp_time."""
    descriptors: list[EntityDescriptor] = []
    if "ramp_time" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_ramp_time",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Ramp Time",
                translation_key="filter_ramp_time",
                config_path=f"filters.{name}.parameters.ramp_time",
                node_type="Volume",
                subtype=None,
                value_type=float,
                unit="ms",
                min_value=0.0,
                max_value=10000.0,
                step=1.0,
                icon="mdi:timer-outline",
            )
        )
    return descriptors


def _loudness_filter_numbers(
    params: dict[str, Any],
    entry_id: str,
    name: str,
    sid: str,
) -> list[EntityDescriptor]:
    """Loudness filter: reference_level, high_boost, low_boost."""
    descriptors: list[EntityDescriptor] = []
    if "reference_level" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_reference_level",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Reference Level",
                translation_key="filter_reference_level",
                config_path=f"filters.{name}.parameters.reference_level",
                node_type="Loudness",
                subtype=None,
                value_type=float,
                unit="dB",
                min_value=-100.0,
                max_value=0.0,
                step=0.1,
                icon="mdi:ear-hearing",
            )
        )
    if "high_boost" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_high_boost",
                platform=EntityPlatform.NUMBER,
                label=f"{name} High Boost",
                translation_key="filter_high_boost",
                config_path=f"filters.{name}.parameters.high_boost",
                node_type="Loudness",
                subtype=None,
                value_type=float,
                unit="dB",
                min_value=0.0,
                max_value=20.0,
                step=0.1,
                icon="mdi:equalizer",
            )
        )
    if "low_boost" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_low_boost",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Low Boost",
                translation_key="filter_low_boost",
                config_path=f"filters.{name}.parameters.low_boost",
                node_type="Loudness",
                subtype=None,
                value_type=float,
                unit="dB",
                min_value=0.0,
                max_value=20.0,
                step=0.1,
                icon="mdi:equalizer",
            )
        )
    return descriptors


def _delay_filter_numbers(
    params: dict[str, Any],
    entry_id: str,
    name: str,
    sid: str,
) -> list[EntityDescriptor]:
    """Delay filter: delay, subsample."""
    descriptors: list[EntityDescriptor] = []
    if "delay" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_delay",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Delay",
                translation_key="filter_delay",
                config_path=f"filters.{name}.parameters.delay",
                node_type="Delay",
                subtype=None,
                value_type=float,
                unit=None,  # unit depends on variant (samples, ms, μs)
                min_value=0.0,
                max_value=100000.0,
                step=1.0,
                icon="mdi:timer-sand",
            )
        )
    if "subsample" in params:
        # Boolean-like but sometimes numeric (0/1); treat as switch elsewhere
        pass
    return descriptors


# ------------------------------------------------------------------
# Biquad filter
# ------------------------------------------------------------------

# Maps Biquad param names to (min, max, step, unit, icon).
_BIQUAD_PARAM_SPEC: dict[str, tuple[float, float, float, str | None, str]] = {
    "freq": (1.0, 48000.0, 1.0, "Hz", "mdi:sine-wave"),
    "gain": (-100.0, 100.0, 0.1, "dB", "mdi:volume-medium"),
    "q": (0.01, 100.0, 0.01, None, "mdi:tune-vertical"),
    "bandwidth": (0.01, 100.0, 0.01, None, "mdi:arrow-expand-horizontal"),
    "slope": (0.1, 24.0, 0.1, "dB/oct", "mdi:slope-uphill"),
}


def _biquad_filter_numbers(
    params: dict[str, Any],
    entry_id: str,
    name: str,
    sid: str,
    variant: str | None,
) -> list[EntityDescriptor]:
    """Biquad filter – generates descriptors for standard Biquad variants.

    Covers: Lowpass, Highpass, Lowshelf, Highshelf, Peaking, Notch,
    Bandpass, Allpass, AllpassFirst, LowpassFO, HighpassFO,
    LowshelfFO, HighshelfFO, LinkwitzTransform, Free.
    """
    descriptors: list[EntityDescriptor] = []

    # Standard params (freq, gain, q, bandwidth, slope)
    for param_name, (min_v, max_v, step_v, unit, icon) in _BIQUAD_PARAM_SPEC.items():
        if param_name in params:
            descriptors.append(
                EntityDescriptor(
                    unique_id=f"camilladsp_{entry_id}_filter_{sid}_{param_name}",
                    platform=EntityPlatform.NUMBER,
                    label=f"{name} {param_name.replace('_', ' ').title()}",
                    translation_key=f"filter_biquad_{param_name}",
                    config_path=f"filters.{name}.parameters.{param_name}",
                    node_type="Biquad",
                    subtype=variant,
                    value_type=float,
                    unit=unit,
                    min_value=min_v,
                    max_value=max_v,
                    step=step_v,
                    icon=icon,
                )
            )

    # LinkwitzTransform has special dual-freq/dual-q params
    if variant == "LinkwitzTransform":
        for suffix, label_suffix in [
            ("freq_act", "Actual Freq"),
            ("q_act", "Actual Q"),
            ("freq_target", "Target Freq"),
            ("q_target", "Target Q"),
        ]:
            if suffix in params:
                is_freq = "freq" in suffix
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_{suffix}",
                        platform=EntityPlatform.NUMBER,
                        label=f"{name} {label_suffix}",
                        translation_key=f"filter_biquad_{suffix}",
                        config_path=f"filters.{name}.parameters.{suffix}",
                        node_type="Biquad",
                        subtype="LinkwitzTransform",
                        value_type=float,
                        unit="Hz" if is_freq else None,
                        min_value=1.0 if is_freq else 0.01,
                        max_value=48000.0 if is_freq else 100.0,
                        step=1.0 if is_freq else 0.01,
                        icon="mdi:sine-wave" if is_freq else "mdi:tune-vertical",
                    )
                )

    # GeneralNotch has special params: freq_p, freq_z, q_p
    if variant == "GeneralNotch":
        for suffix, label_suffix, is_freq in [
            ("freq_p", "Pole Freq", True),
            ("freq_z", "Zero Freq", True),
            ("q_p", "Pole Q", False),
        ]:
            if suffix in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_{suffix}",
                        platform=EntityPlatform.NUMBER,
                        label=f"{name} {label_suffix}",
                        translation_key=f"filter_biquad_{suffix}",
                        config_path=f"filters.{name}.parameters.{suffix}",
                        node_type="Biquad",
                        subtype="GeneralNotch",
                        value_type=float,
                        unit="Hz" if is_freq else None,
                        min_value=1.0 if is_freq else 0.01,
                        max_value=48000.0 if is_freq else 100.0,
                        step=1.0 if is_freq else 0.01,
                        icon="mdi:sine-wave" if is_freq else "mdi:tune-vertical",
                    )
                )

    # Free biquad: a1, a2, b0, b1, b2 coefficients
    if variant == "Free":
        for coeff in ("a1", "a2", "b0", "b1", "b2"):
            if coeff in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_{coeff}",
                        platform=EntityPlatform.NUMBER,
                        label=f"{name} {coeff.upper()}",
                        translation_key=f"filter_biquad_{coeff}",
                        config_path=f"filters.{name}.parameters.{coeff}",
                        node_type="Biquad",
                        subtype="Free",
                        value_type=float,
                        unit=None,
                        min_value=-10.0,
                        max_value=10.0,
                        step=0.000001,
                        icon="mdi:math-integral",
                    )
                )

    return descriptors


# ------------------------------------------------------------------
# BiquadCombo filter
# ------------------------------------------------------------------


def _biquadcombo_filter_numbers(
    params: dict[str, Any],
    entry_id: str,
    name: str,
    sid: str,
    variant: str | None,
) -> list[EntityDescriptor]:
    """BiquadCombo filter – Butterworth/LinkwitzRiley/Bessel/Tilt/FivePointPeq/GraphicEqualizer."""
    descriptors: list[EntityDescriptor] = []

    # Common: freq
    if "freq" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_freq",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Frequency",
                translation_key="filter_combo_freq",
                config_path=f"filters.{name}.parameters.freq",
                node_type="BiquadCombo",
                subtype=variant,
                value_type=float,
                unit="Hz",
                min_value=1.0,
                max_value=48000.0,
                step=1.0,
                icon="mdi:sine-wave",
            )
        )

    # Common: order (integer)
    if "order" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_order",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Order",
                translation_key="filter_combo_order",
                config_path=f"filters.{name}.parameters.order",
                node_type="BiquadCombo",
                subtype=variant,
                value_type=int,
                unit=None,
                min_value=1.0,
                max_value=10.0,
                step=1.0,
                icon="mdi:sort-numeric-ascending",
            )
        )

    # Tilt variant: gain
    if "gain" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_gain",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Gain",
                translation_key="filter_combo_gain",
                config_path=f"filters.{name}.parameters.gain",
                node_type="BiquadCombo",
                subtype=variant,
                value_type=float,
                unit="dB",
                min_value=-100.0,
                max_value=100.0,
                step=0.1,
                icon="mdi:volume-medium",
            )
        )

    # FivePointPeq: individual band parameters with fixed flat names
    _FIVE_POINT_BANDS = [
        ("fls", "gls", "qls", "LowShelf"),
        ("fp1", "gp1", "qp1", "Peaking 1"),
        ("fp2", "gp2", "qp2", "Peaking 2"),
        ("fp3", "gp3", "qp3", "Peaking 3"),
        ("fhs", "ghs", "qhs", "HighShelf"),
    ]
    if variant == "FivePointPeq":
        for freq_key, gain_key, q_key, band_label in _FIVE_POINT_BANDS:
            if freq_key in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_{freq_key}",
                        platform=EntityPlatform.NUMBER,
                        label=f"{name} {band_label} Freq",
                        translation_key="filter_combo_five_point_freq",
                        config_path=f"filters.{name}.parameters.{freq_key}",
                        node_type="BiquadCombo",
                        subtype="FivePointPeq",
                        value_type=float,
                        unit="Hz",
                        min_value=1.0,
                        max_value=48000.0,
                        step=1.0,
                        icon="mdi:sine-wave",
                    )
                )
            if gain_key in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_{gain_key}",
                        platform=EntityPlatform.NUMBER,
                        label=f"{name} {band_label} Gain",
                        translation_key="filter_combo_five_point_gain",
                        config_path=f"filters.{name}.parameters.{gain_key}",
                        node_type="BiquadCombo",
                        subtype="FivePointPeq",
                        value_type=float,
                        unit="dB",
                        min_value=-100.0,
                        max_value=100.0,
                        step=0.1,
                        icon="mdi:volume-medium",
                    )
                )
            if q_key in params:
                descriptors.append(
                    EntityDescriptor(
                        unique_id=f"camilladsp_{entry_id}_filter_{sid}_{q_key}",
                        platform=EntityPlatform.NUMBER,
                        label=f"{name} {band_label} Q",
                        translation_key="filter_combo_five_point_q",
                        config_path=f"filters.{name}.parameters.{q_key}",
                        node_type="BiquadCombo",
                        subtype="FivePointPeq",
                        value_type=float,
                        unit=None,
                        min_value=0.01,
                        max_value=100.0,
                        step=0.01,
                        icon="mdi:tune-vertical",
                    )
                )

    # GraphicEqualizer variant: freq_min, freq_max (gains array → service-first)
    if variant == "GraphicEqualizer":
        if "freq_min" in params:
            descriptors.append(
                EntityDescriptor(
                    unique_id=f"camilladsp_{entry_id}_filter_{sid}_freq_min",
                    platform=EntityPlatform.NUMBER,
                    label=f"{name} Freq Min",
                    translation_key="filter_combo_freq_min",
                    config_path=f"filters.{name}.parameters.freq_min",
                    node_type="BiquadCombo",
                    subtype="GraphicEqualizer",
                    value_type=float,
                    unit="Hz",
                    min_value=1.0,
                    max_value=48000.0,
                    step=1.0,
                    icon="mdi:sine-wave",
                )
            )
        if "freq_max" in params:
            descriptors.append(
                EntityDescriptor(
                    unique_id=f"camilladsp_{entry_id}_filter_{sid}_freq_max",
                    platform=EntityPlatform.NUMBER,
                    label=f"{name} Freq Max",
                    translation_key="filter_combo_freq_max",
                    config_path=f"filters.{name}.parameters.freq_max",
                    node_type="BiquadCombo",
                    subtype="GraphicEqualizer",
                    value_type=float,
                    unit="Hz",
                    min_value=1.0,
                    max_value=48000.0,
                    step=1.0,
                    icon="mdi:sine-wave",
                )
            )

    return descriptors


# ------------------------------------------------------------------
# Dither filter
# ------------------------------------------------------------------


def _dither_filter_numbers(
    params: dict[str, Any],
    entry_id: str,
    name: str,
    sid: str,
    variant: str | None,
) -> list[EntityDescriptor]:
    """Dither filter: bits, amplitude."""
    descriptors: list[EntityDescriptor] = []
    if "bits" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_bits",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Bits",
                translation_key="filter_dither_bits",
                config_path=f"filters.{name}.parameters.bits",
                node_type="Dither",
                subtype=variant,
                value_type=int,
                unit=None,
                min_value=1.0,
                max_value=64.0,
                step=1.0,
                icon="mdi:numeric",
            )
        )
    if "amplitude" in params:
        descriptors.append(
            EntityDescriptor(
                unique_id=f"camilladsp_{entry_id}_filter_{sid}_amplitude",
                platform=EntityPlatform.NUMBER,
                label=f"{name} Amplitude",
                translation_key="filter_dither_amplitude",
                config_path=f"filters.{name}.parameters.amplitude",
                node_type="Dither",
                subtype=variant,
                value_type=float,
                unit=None,
                min_value=0.0,
                max_value=10.0,
                step=0.01,
                icon="mdi:waveform",
            )
        )
    return descriptors


# ------------------------------------------------------------------
# DiffEq filter
# ------------------------------------------------------------------


def _diffeq_filter_numbers(
    params: dict[str, Any],
    entry_id: str,
    name: str,
    sid: str,
) -> list[EntityDescriptor]:
    """DiffEq filter: individual a/b coefficient arrays are service-first.

    Only expose scalar parameters if present.
    """
    # DiffEq uses coefficient arrays – not suitable for individual number
    # entities.  Exposed via services instead.
    return []


# ------------------------------------------------------------------
# Processors
# ------------------------------------------------------------------


_COMPRESSOR_PARAM_SPEC: dict[str, tuple[float, float, float, str | None, str]] = {
    "threshold": (-100.0, 0.0, 0.1, "dB", "mdi:gauge"),
    "factor": (1.0, 100.0, 0.1, None, "mdi:tune"),
    "attack": (0.0, 10.0, 0.001, "s", "mdi:timer"),
    "release": (0.0, 10.0, 0.001, "s", "mdi:timer"),
    "makeup_gain": (-100.0, 100.0, 0.1, "dB", "mdi:volume-plus"),
    "clip_limit": (-100.0, 0.0, 0.1, "dB", "mdi:content-cut"),
}


def _build_processor_numbers(
    config_doc: dict[str, Any],
    entry_id: str,
) -> list[EntityDescriptor]:
    descriptors: list[EntityDescriptor] = []

    for name, proc in config_doc.get("processors", {}).items():
        proc_type = proc.get("processor_type")
        params = proc.get("parameters", {})
        sid = sanitize_id(name)

        if proc_type == "Compressor":
            for param_name, (
                min_v,
                max_v,
                step_v,
                unit,
                icon,
            ) in _COMPRESSOR_PARAM_SPEC.items():
                if param_name in params:
                    descriptors.append(
                        EntityDescriptor(
                            unique_id=f"camilladsp_{entry_id}_processor_{sid}_{param_name}",
                            platform=EntityPlatform.NUMBER,
                            label=f"{name} {param_name.replace('_', ' ').title()}",
                            translation_key=f"processor_compressor_{param_name}",
                            config_path=f"processors.{name}.parameters.{param_name}",
                            node_type="Compressor",
                            subtype=None,
                            value_type=float,
                            unit=unit,
                            min_value=min_v,
                            max_value=max_v,
                            step=step_v,
                            icon=icon,
                        )
                    )
        else:
            _LOGGER.debug(
                "Skipping unrecognised processor type %r for number descriptors",
                proc_type,
            )

    return descriptors


# ------------------------------------------------------------------
# Mixers
# ------------------------------------------------------------------


def _build_mixer_numbers(
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
                if "gain" in source:
                    descriptors.append(
                        EntityDescriptor(
                            unique_id=(
                                f"camilladsp_{entry_id}_mixer_{msid}"
                                f"_mapping_{m_idx}_source_{s_idx}_gain"
                            ),
                            platform=EntityPlatform.NUMBER,
                            label=f"{mixer_name} Out {dest} Src {channel} Gain",
                            translation_key="mixer_source_gain",
                            config_path=(
                                f"mixers.{mixer_name}.mapping[{m_idx}]"
                                f".sources[{s_idx}].gain"
                            ),
                            node_type="Mixer",
                            subtype=None,
                            value_type=float,
                            unit="dB",
                            min_value=-100.0,
                            max_value=100.0,
                            step=0.1,
                            icon="mdi:volume-medium",
                        )
                    )

    return descriptors
