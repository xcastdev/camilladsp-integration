"""Tests for entities/builder.py and entities/descriptors.py – descriptor generation."""

from __future__ import annotations

import pytest

from custom_components.camilladsp.api.models import RuntimeStatus, StoredConfig
from custom_components.camilladsp.config.normalize import normalize_config
from custom_components.camilladsp.entities.builder import (
    build_descriptors,
    diff_descriptors,
)
from custom_components.camilladsp.entities.descriptors import (
    EntityDescriptor,
    EntityPlatform,
    MutationStrategy,
)
from custom_components.camilladsp.entities.utils import sanitize_id

ENTRY_ID = "test_entry_123"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _build(raw_config, stored_configs=None, status=None):
    """Normalize a raw config and build descriptors."""
    doc = normalize_config(raw_config, "test.yml")
    return build_descriptors(doc, ENTRY_ID, stored_configs, status)


def _descriptor_ids(descriptors):
    """Return the set of unique_ids from descriptors."""
    return {d.unique_id for d in descriptors}


def _descriptors_by_platform(descriptors, platform):
    return [d for d in descriptors if d.platform == platform]


def _descriptors_by_path_contains(descriptors, substring):
    return [d for d in descriptors if d.config_path and substring in d.config_path]


# ------------------------------------------------------------------
# Gain filter descriptors
# ------------------------------------------------------------------


class TestGainFilterDescriptors:
    """Gain filter → number/switch descriptors."""

    def test_gain_produces_number(self, dither_config):
        """Gain filter 'atten' has gain parameter → number entity."""
        descs = _build(dither_config)
        gain_nums = [
            d
            for d in descs
            if d.platform == EntityPlatform.NUMBER and d.node_type == "Gain"
        ]
        assert len(gain_nums) >= 1
        d = gain_nums[0]
        assert "gain" in d.config_path
        assert d.unit == "dB"
        assert d.value_type is float

    def test_gain_inverted_switch(self, dither_config):
        """Gain filter 'atten' with inverted → switch entity."""
        descs = _build(dither_config)
        switches = [
            d
            for d in descs
            if d.platform == EntityPlatform.SWITCH
            and d.node_type == "Gain"
            and "inverted" in d.unique_id
        ]
        assert len(switches) >= 1
        assert switches[0].value_type is bool


# ------------------------------------------------------------------
# Biquad filter descriptors
# ------------------------------------------------------------------


class TestBiquadFilterDescriptors:
    """Biquad filter variants produce correct numeric descriptors."""

    def test_biquad_highpass(self, all_biquads_config):
        descs = _build(all_biquads_config)
        hp_descs = [
            d for d in descs if "highpass" in d.unique_id and d.node_type == "Biquad"
        ]
        # Highpass has freq, q
        param_names = {d.config_path.split(".")[-1] for d in hp_descs if d.config_path}
        assert "freq" in param_names
        assert "q" in param_names

    def test_biquad_peaking(self, all_biquads_config):
        descs = _build(all_biquads_config)
        peaking_descs = [
            d
            for d in descs
            if "peaking_using_q" in d.unique_id and d.node_type == "Biquad"
        ]
        params = {d.config_path.split(".")[-1] for d in peaking_descs if d.config_path}
        assert "freq" in params
        assert "gain" in params
        assert "q" in params

    def test_biquad_free_coefficients(self, all_biquads_config):
        descs = _build(all_biquads_config)
        free_descs = [
            d for d in descs if d.subtype == "Free" and d.node_type == "Biquad"
        ]
        coeff_names = {
            d.config_path.split(".")[-1] for d in free_descs if d.config_path
        }
        assert {"a1", "a2", "b0", "b1", "b2"} == coeff_names

    def test_biquad_linkwitz_transform(self, all_biquads_config):
        descs = _build(all_biquads_config)
        lt_descs = [
            d
            for d in descs
            if d.subtype == "LinkwitzTransform" and d.node_type == "Biquad"
        ]
        params = {d.config_path.split(".")[-1] for d in lt_descs if d.config_path}
        assert "freq_act" in params
        assert "q_act" in params
        assert "freq_target" in params
        assert "q_target" in params

    def test_biquad_general_notch(self, all_biquads_config):
        descs = _build(all_biquads_config)
        gn_descs = [d for d in descs if d.subtype == "GeneralNotch"]
        # Should have number descriptors for freq_p, freq_z, q_p
        # and a switch for normalize_at_dc
        num_descs = [d for d in gn_descs if d.platform == EntityPlatform.NUMBER]
        switch_descs = [d for d in gn_descs if d.platform == EntityPlatform.SWITCH]
        num_params = {d.config_path.split(".")[-1] for d in num_descs if d.config_path}
        assert "freq_p" in num_params
        assert "freq_z" in num_params
        assert "q_p" in num_params
        assert len(switch_descs) >= 1
        assert any("normalize_at_dc" in d.unique_id for d in switch_descs)

    def test_all_biquad_filters_produce_descriptors(self, all_biquads_config):
        """Every Biquad/BiquadCombo filter produces at least one descriptor."""
        doc = normalize_config(all_biquads_config, "test.yml")
        descs = _build(all_biquads_config)
        for name, filt in doc["filters"].items():
            if filt["filter_type"] in ("Biquad", "BiquadCombo"):
                matching = [
                    d
                    for d in descs
                    if d.config_path and f"filters.{name}." in d.config_path
                ]
                assert len(matching) > 0, f"Filter {name!r} produced no descriptors"


# ------------------------------------------------------------------
# BiquadCombo descriptors
# ------------------------------------------------------------------


class TestBiquadComboDescriptors:
    """BiquadCombo filter descriptors."""

    def test_butterworth_freq_order(self, all_biquads_config):
        descs = _build(all_biquads_config)
        bw = [
            d
            for d in descs
            if "butterworth_highpass" in d.unique_id and d.node_type == "BiquadCombo"
        ]
        params = {d.config_path.split(".")[-1] for d in bw if d.config_path}
        assert "freq" in params
        assert "order" in params

    def test_tilt_gain(self, all_biquads_config):
        descs = _build(all_biquads_config)
        tilt = [
            d
            for d in descs
            if "tilt" in d.unique_id.lower() and d.node_type == "BiquadCombo"
        ]
        params = {d.config_path.split(".")[-1] for d in tilt if d.config_path}
        assert "gain" in params

    def test_five_point_peq(self, all_biquads_config):
        descs = _build(all_biquads_config)
        fp = [d for d in descs if d.subtype == "FivePointPeq"]
        params = {d.config_path.split(".")[-1] for d in fp if d.config_path}
        # Should have fls, gls, qls, fp1, gp1, qp1, ... fhs, ghs, qhs
        expected_params = {
            "fls",
            "gls",
            "qls",
            "fp1",
            "gp1",
            "qp1",
            "fp2",
            "gp2",
            "qp2",
            "fp3",
            "gp3",
            "qp3",
            "fhs",
            "ghs",
            "qhs",
        }
        assert expected_params == params

    def test_graphic_equalizer(self, all_biquads_config):
        descs = _build(all_biquads_config)
        ge = [d for d in descs if d.subtype == "GraphicEqualizer"]
        params = {d.config_path.split(".")[-1] for d in ge if d.config_path}
        assert "freq_min" in params
        assert "freq_max" in params


# ------------------------------------------------------------------
# Dither filter descriptors
# ------------------------------------------------------------------


class TestDitherDescriptors:
    """Dither filter → bits and amplitude descriptors."""

    def test_dither_bits(self, dither_config):
        descs = _build(dither_config)
        bits_descs = [
            d
            for d in descs
            if d.node_type == "Dither" and "bits" in (d.config_path or "")
        ]
        assert len(bits_descs) >= 1
        for d in bits_descs:
            assert d.value_type is int

    def test_dither_amplitude(self, dither_config):
        """The 'dithereven' filter (Flat variant) has amplitude parameter."""
        descs = _build(dither_config)
        amp_descs = [
            d
            for d in descs
            if d.node_type == "Dither" and "amplitude" in (d.config_path or "")
        ]
        assert len(amp_descs) >= 1
        assert amp_descs[0].value_type is float

    def test_dither_all_variants_have_bits(self, dither_config):
        """All dither filters have 'bits' parameter."""
        doc = normalize_config(dither_config, "test.yml")
        descs = _build(dither_config)
        dither_names = [
            n for n, f in doc["filters"].items() if f["filter_type"] == "Dither"
        ]
        for name in dither_names:
            matching = [
                d
                for d in descs
                if d.config_path and f"filters.{name}.parameters.bits" == d.config_path
            ]
            assert len(matching) == 1, f"Dither filter {name!r} missing bits descriptor"


# ------------------------------------------------------------------
# Delay filter descriptors
# ------------------------------------------------------------------


class TestDelayDescriptors:
    """Delay filter → delay number descriptor."""

    def test_delay_number(self, gain_config):
        descs = _build(gain_config)
        delay_descs = [
            d
            for d in descs
            if d.node_type == "Delay" and "delay" in (d.config_path or "")
        ]
        assert len(delay_descs) == 1
        assert delay_descs[0].value_type is float


# ------------------------------------------------------------------
# Compressor processor descriptors
# ------------------------------------------------------------------


class TestCompressorDescriptors:
    """Compressor processor → numeric and switch descriptors."""

    def test_compressor_number_params(self, compressor_config):
        descs = _build(compressor_config)
        comp_nums = [
            d
            for d in descs
            if d.platform == EntityPlatform.NUMBER and d.node_type == "Compressor"
        ]
        params = {d.config_path.split(".")[-1] for d in comp_nums if d.config_path}
        assert "threshold" in params
        assert "factor" in params
        assert "attack" in params
        assert "release" in params
        assert "makeup_gain" in params
        assert "clip_limit" in params

    def test_compressor_soft_clip_switch(self, compressor_config):
        descs = _build(compressor_config)
        soft_clip = [
            d
            for d in descs
            if d.platform == EntityPlatform.SWITCH
            and d.node_type == "Compressor"
            and "soft_clip" in d.unique_id
        ]
        assert len(soft_clip) == 1
        assert soft_clip[0].value_type is bool


# ------------------------------------------------------------------
# Mixer descriptors
# ------------------------------------------------------------------


class TestMixerDescriptors:
    """Mixer sources → gain numbers and switches."""

    def test_mixer_source_gain(self, sample_config):
        descs = _build(sample_config)
        mixer_gains = [
            d
            for d in descs
            if d.platform == EntityPlatform.NUMBER
            and d.node_type == "Mixer"
            and "gain" in (d.config_path or "")
        ]
        # simpleconfig has 2 mappings × 2 sources each = 4 gain descriptors
        assert len(mixer_gains) == 4

    def test_mixer_source_inverted_switch(self, sample_config):
        descs = _build(sample_config)
        inv_switches = [
            d
            for d in descs
            if d.platform == EntityPlatform.SWITCH
            and d.node_type == "Mixer"
            and "inverted" in d.unique_id
        ]
        # simpleconfig sources have inverted=false → 4 switches
        assert len(inv_switches) == 4

    def test_no_mixer_descriptors_without_mixers(self, nomixers_config):
        descs = _build(nomixers_config)
        mixer_descs = [d for d in descs if d.node_type == "Mixer"]
        assert len(mixer_descs) == 0


# ------------------------------------------------------------------
# Pipeline bypass switch descriptors
# ------------------------------------------------------------------


class TestPipelineBypassDescriptors:
    """Pipeline steps with bypassed → switch descriptors."""

    def test_no_bypass_without_field(self, sample_config):
        """Pipeline steps without 'bypassed' field produce no switch."""
        descs = _build(sample_config)
        bypass = [
            d
            for d in descs
            if d.platform == EntityPlatform.SWITCH and "bypassed" in d.unique_id
        ]
        assert len(bypass) == 0

    def test_bypass_with_field(self):
        raw = {
            "devices": {"samplerate": 44100},
            "pipeline": [
                {"type": "Filter", "channels": [0], "names": ["f1"], "bypassed": False}
            ],
        }
        descs = _build(raw)
        bypass = [
            d
            for d in descs
            if d.platform == EntityPlatform.SWITCH and "bypassed" in d.unique_id
        ]
        assert len(bypass) == 1
        assert bypass[0].value_type is bool


# ------------------------------------------------------------------
# Sensor descriptors
# ------------------------------------------------------------------


class TestSensorDescriptors:
    """Runtime telemetry sensors are always emitted."""

    def test_sensors_always_present(self, sample_config):
        descs = _build(sample_config)
        sensors = _descriptors_by_platform(descs, EntityPlatform.SENSOR)
        assert (
            len(sensors) >= 6
        )  # state, capture_rate, buffer_level, clipped, load, active_config, volume, mute

    def test_sensor_unique_ids(self, sample_config):
        descs = _build(sample_config)
        sensors = _descriptors_by_platform(descs, EntityPlatform.SENSOR)
        ids = {d.unique_id for d in sensors}
        assert f"camilladsp_{ENTRY_ID}_status_state" in ids
        assert f"camilladsp_{ENTRY_ID}_status_capture_rate" in ids
        assert f"camilladsp_{ENTRY_ID}_status_buffer_level" in ids
        assert f"camilladsp_{ENTRY_ID}_status_clipped_samples" in ids
        assert f"camilladsp_{ENTRY_ID}_status_processing_load" in ids
        assert f"camilladsp_{ENTRY_ID}_active_config_filename" in ids
        assert f"camilladsp_{ENTRY_ID}_volume_sensor" in ids
        assert f"camilladsp_{ENTRY_ID}_mute_sensor" in ids

    def test_sensors_are_read_only(self, sample_config):
        descs = _build(sample_config)
        sensors = _descriptors_by_platform(descs, EntityPlatform.SENSOR)
        for s in sensors:
            assert s.mutation_strategy == MutationStrategy.READ_ONLY

    def test_sensors_with_empty_config(self):
        descs = _build({})
        sensors = _descriptors_by_platform(descs, EntityPlatform.SENSOR)
        # Sensors are emitted even for empty configs
        assert len(sensors) >= 6


# ------------------------------------------------------------------
# Active config select descriptor
# ------------------------------------------------------------------


class TestActiveConfigSelectDescriptor:
    """The active config select is always emitted."""

    def test_active_config_select_present(self, sample_config):
        descs = _build(sample_config)
        selects = _descriptors_by_platform(descs, EntityPlatform.SELECT)
        active = [d for d in selects if "active_config" in d.unique_id]
        assert len(active) == 1
        assert active[0].mutation_strategy == MutationStrategy.ACTIVE_CONFIG

    def test_active_config_with_stored_configs(self, sample_config):
        stored = [
            StoredConfig(name="config1.yml"),
            StoredConfig(name="config2.yml"),
        ]
        descs = _build(sample_config, stored_configs=stored)
        active = [
            d
            for d in descs
            if "active_config" in d.unique_id and d.platform == EntityPlatform.SELECT
        ]
        assert len(active) == 1
        assert sorted(active[0].options) == ["config1.yml", "config2.yml"]

    def test_active_config_no_stored_configs(self, sample_config):
        descs = _build(sample_config, stored_configs=None)
        active = [
            d
            for d in descs
            if "active_config" in d.unique_id and d.platform == EntityPlatform.SELECT
        ]
        assert len(active) == 1
        assert active[0].options == []


# ------------------------------------------------------------------
# Unique ID uniqueness
# ------------------------------------------------------------------


class TestDescriptorUniqueIds:
    """All unique_ids in a descriptor set must be unique."""

    def test_unique_ids_simple_config(self, sample_config):
        descs = _build(sample_config)
        ids = [d.unique_id for d in descs]
        assert len(ids) == len(set(ids)), (
            f"Duplicate unique_ids found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_unique_ids_all_biquads(self, all_biquads_config):
        descs = _build(all_biquads_config)
        ids = [d.unique_id for d in descs]
        assert len(ids) == len(set(ids)), (
            f"Duplicate unique_ids found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_unique_ids_compressor(self, compressor_config):
        descs = _build(compressor_config)
        ids = [d.unique_id for d in descs]
        assert len(ids) == len(set(ids))

    def test_unique_ids_dither(self, dither_config):
        descs = _build(dither_config)
        ids = [d.unique_id for d in descs]
        assert len(ids) == len(set(ids))


# ------------------------------------------------------------------
# diff_descriptors
# ------------------------------------------------------------------


class TestDiffDescriptors:
    """diff_descriptors compares two lists by unique_id."""

    def test_no_changes(self, sample_config):
        descs = _build(sample_config)
        added, removed, unchanged = diff_descriptors(descs, descs)
        assert added == []
        assert removed == []
        assert len(unchanged) == len(descs)

    def test_added_descriptors(self, sample_config):
        descs = _build(sample_config)
        extra = EntityDescriptor(
            unique_id="camilladsp_test_extra",
            platform=EntityPlatform.NUMBER,
            label="Extra",
        )
        new_descs = list(descs) + [extra]
        added, removed, unchanged = diff_descriptors(descs, new_descs)
        assert len(added) == 1
        assert added[0].unique_id == "camilladsp_test_extra"
        assert removed == []
        assert len(unchanged) == len(descs)

    def test_removed_descriptors(self, sample_config):
        descs = _build(sample_config)
        old_descs = list(descs) + [
            EntityDescriptor(
                unique_id="camilladsp_test_removed",
                platform=EntityPlatform.NUMBER,
                label="Removed",
            )
        ]
        added, removed, unchanged = diff_descriptors(old_descs, descs)
        assert added == []
        assert len(removed) == 1
        assert removed[0].unique_id == "camilladsp_test_removed"
        assert len(unchanged) == len(descs)

    def test_all_new(self):
        old = []
        new = [
            EntityDescriptor(unique_id="a", platform=EntityPlatform.NUMBER, label="A"),
            EntityDescriptor(unique_id="b", platform=EntityPlatform.SWITCH, label="B"),
        ]
        added, removed, unchanged = diff_descriptors(old, new)
        assert len(added) == 2
        assert removed == []
        assert unchanged == []

    def test_all_removed(self):
        old = [
            EntityDescriptor(unique_id="a", platform=EntityPlatform.NUMBER, label="A"),
        ]
        added, removed, unchanged = diff_descriptors(old, [])
        assert added == []
        assert len(removed) == 1
        assert unchanged == []

    def test_unchanged_uses_new_instances(self):
        """When unchanged, diff uses the NEW descriptor instances."""
        old = [
            EntityDescriptor(
                unique_id="a",
                platform=EntityPlatform.SELECT,
                label="Old Label",
                options=["x"],
            ),
        ]
        new = [
            EntityDescriptor(
                unique_id="a",
                platform=EntityPlatform.SELECT,
                label="New Label",
                options=["x", "y"],
            ),
        ]
        added, removed, unchanged = diff_descriptors(old, new)
        assert len(unchanged) == 1
        assert unchanged[0].label == "New Label"
        assert unchanged[0].options == ["x", "y"]


# ------------------------------------------------------------------
# sanitize_id utility
# ------------------------------------------------------------------


class TestSanitizeId:
    """sanitize_id normalizes names for use in unique IDs."""

    def test_simple_name(self):
        assert sanitize_id("Bass") == "bass"

    def test_spaces(self):
        assert sanitize_id("Bass Control") == "bass_control"

    def test_special_chars(self):
        assert sanitize_id("Bass Control (PEQ #1)") == "bass_control_peq_1"

    def test_leading_trailing_special(self):
        assert sanitize_id("--test--") == "test"

    def test_numbers(self):
        assert sanitize_id("filter123") == "filter123"

    def test_empty_string(self):
        assert sanitize_id("") == ""

    def test_all_special(self):
        assert sanitize_id("---") == ""

    def test_mixed_case(self):
        assert sanitize_id("MyFilter") == "myfilter"
