"""Tests for config/normalize.py – normalize_config and denormalize_config."""

from __future__ import annotations

import copy

import pytest

from custom_components.camilladsp.config.normalize import (
    denormalize_config,
    normalize_config,
)


# ------------------------------------------------------------------
# Basic structure tests
# ------------------------------------------------------------------


class TestNormalizeStructure:
    """Verify that normalize_config produces all expected top-level sections."""

    def test_all_sections_present(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert "meta" in doc
        assert "devices" in doc
        assert "filters" in doc
        assert "mixers" in doc
        assert "processors" in doc
        assert "pipeline" in doc
        assert "extra" in doc

    def test_missing_sections_filled_with_defaults(self):
        doc = normalize_config({}, "empty.yml")
        assert doc["meta"]["filename"] == "empty.yml"
        assert doc["filters"] == {}
        assert doc["mixers"] == {}
        assert doc["processors"] == {}
        assert doc["pipeline"] == []
        assert doc["devices"] == {}
        assert doc["extra"] == {}

    def test_normalize_empty_config_meta(self):
        doc = normalize_config({}, "empty.yml")
        assert doc["meta"]["filename"] == "empty.yml"
        assert doc["meta"]["title"] is None
        assert doc["meta"]["description"] is None

    def test_normalize_all_example_configs(self, any_valid_config):
        """Every valid example config normalizes without error."""
        doc = normalize_config(any_valid_config, "test.yml")
        assert "meta" in doc
        assert "devices" in doc
        assert isinstance(doc["filters"], dict)
        assert isinstance(doc["mixers"], dict)
        assert isinstance(doc["processors"], dict)
        assert isinstance(doc["pipeline"], list)


# ------------------------------------------------------------------
# Meta section
# ------------------------------------------------------------------


class TestNormalizeMeta:
    """Meta extraction from title/description into doc['meta']."""

    def test_meta_extraction(self, sample_config):
        sample_config["title"] = "Test Config"
        sample_config["description"] = "A test"
        doc = normalize_config(sample_config, "myfile.yml")
        assert doc["meta"]["filename"] == "myfile.yml"
        assert doc["meta"]["title"] == "Test Config"
        assert doc["meta"]["description"] == "A test"

    def test_meta_title_not_in_top_level(self, sample_config):
        sample_config["title"] = "Test Config"
        doc = normalize_config(sample_config, "test.yml")
        # title/description should only be in meta, not as top-level keys
        top_keys = set(doc.keys()) - {"meta"}
        assert "title" not in top_keys
        assert "description" not in top_keys

    def test_meta_filename_preserved(self):
        doc = normalize_config({"devices": {"samplerate": 44100}}, "abc.yml")
        assert doc["meta"]["filename"] == "abc.yml"

    def test_meta_no_title_description(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        # simpleconfig.yml does not have title/description
        assert doc["meta"]["title"] is None
        assert doc["meta"]["description"] is None


# ------------------------------------------------------------------
# Filters section
# ------------------------------------------------------------------


class TestNormalizeFilters:
    """Filter normalization: kind, filter_type, variant extraction."""

    def test_conv_filter(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        f = doc["filters"]["lowpass_fir"]
        assert f["kind"] == "filter"
        assert f["name"] == "lowpass_fir"
        assert f["filter_type"] == "Conv"
        assert f["variant"] == "Raw"  # Conv is subtyped
        assert f["parameters"]["type"] == "Raw"

    def test_gain_filter(self, dither_config):
        doc = normalize_config(dither_config, "test.yml")
        f = doc["filters"]["atten"]
        assert f["kind"] == "filter"
        assert f["filter_type"] == "Gain"
        assert f["variant"] is None  # Gain is not subtyped

    def test_biquad_filter_variant(self, all_biquads_config):
        doc = normalize_config(all_biquads_config, "test.yml")
        hp = doc["filters"]["highpass"]
        assert hp["filter_type"] == "Biquad"
        assert hp["variant"] == "Highpass"
        assert hp["parameters"]["freq"] == 1000
        assert hp["parameters"]["q"] == 1.0

    def test_biquad_free_variant(self, all_biquads_config):
        doc = normalize_config(all_biquads_config, "test.yml")
        f = doc["filters"]["free"]
        assert f["filter_type"] == "Biquad"
        assert f["variant"] == "Free"
        assert "a1" in f["parameters"]
        assert "b0" in f["parameters"]

    def test_biquadcombo_variant(self, all_biquads_config):
        doc = normalize_config(all_biquads_config, "test.yml")
        bh = doc["filters"]["Butterworth_highpass"]
        assert bh["filter_type"] == "BiquadCombo"
        assert bh["variant"] == "ButterworthHighpass"
        assert bh["parameters"]["freq"] == 1000
        assert bh["parameters"]["order"] == 4

    def test_dither_filter_variant(self, dither_config):
        doc = normalize_config(dither_config, "test.yml")
        d = doc["filters"]["dithereven"]
        assert d["filter_type"] == "Dither"
        assert d["variant"] == "Flat"
        assert d["parameters"]["bits"] == 8
        assert d["parameters"]["amplitude"] == 1.0

    def test_delay_filter(self, gain_config):
        doc = normalize_config(gain_config, "test.yml")
        d = doc["filters"]["delay1"]
        assert d["filter_type"] == "Delay"
        assert d["variant"] is None  # Delay is not subtyped
        assert d["parameters"]["delay"] == 500

    def test_filter_extra_keys(self):
        """Unknown keys in a filter entry go to filter's 'extra'."""
        raw = {
            "filters": {
                "test": {
                    "type": "Gain",
                    "parameters": {"gain": 0},
                    "custom_key": "custom_val",
                }
            }
        }
        doc = normalize_config(raw, "test.yml")
        f = doc["filters"]["test"]
        assert f["extra"]["custom_key"] == "custom_val"

    def test_non_dict_filter_skipped(self):
        """Non-dict filter entries are silently skipped."""
        raw = {
            "filters": {
                "bad": "not_a_dict",
                "good": {"type": "Gain", "parameters": {"gain": 0}},
            }
        }
        doc = normalize_config(raw, "test.yml")
        assert "bad" not in doc["filters"]
        assert "good" in doc["filters"]

    def test_all_biquad_variants_normalized(self, all_biquads_config):
        """All biquad variants in the example are correctly typed."""
        doc = normalize_config(all_biquads_config, "test.yml")
        expected_variants = {
            "free": "Free",
            "highpass": "Highpass",
            "lowpass": "Lowpass",
            "highpass_first_order": "HighpassFO",
            "lowpass_first_order": "LowpassFO",
            "highshelf_using_slope": "Highshelf",
            "highshelf_using_q": "Highshelf",
            "lowshelf_using_slope": "Lowshelf",
            "lowshelf_using_q": "Lowshelf",
            "highshelf_first_order": "HighshelfFO",
            "lowshelf_first_order": "LowshelfFO",
            "peaking_using_q": "Peaking",
            "peaking_using_bandwidth": "Peaking",
            "notch_using_q": "Notch",
            "notch_using_bandwidth": "Notch",
            "general_notch": "GeneralNotch",
            "bandpass_using_q": "Bandpass",
            "bandpass_using_bandwidth": "Bandpass",
            "allpass_using_q": "Allpass",
            "allpass_using_bandwidth": "Allpass",
            "allpass_first_order": "AllpassFO",
            "linkwitztransform": "LinkwitzTransform",
        }
        for name, expected_variant in expected_variants.items():
            assert doc["filters"][name]["variant"] == expected_variant, (
                f"Filter {name!r} should have variant {expected_variant!r}"
            )


# ------------------------------------------------------------------
# Mixers section
# ------------------------------------------------------------------


class TestNormalizeMixers:
    """Mixer normalization."""

    def test_mixer_basic_structure(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        m = doc["mixers"]["monomix"]
        assert m["kind"] == "mixer"
        assert m["name"] == "monomix"
        assert m["channels"]["in"] == 2
        assert m["channels"]["out"] == 2
        assert len(m["mapping"]) == 2

    def test_mixer_sources(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        m = doc["mixers"]["monomix"]
        first_mapping = m["mapping"][0]
        assert first_mapping["dest"] == 0
        sources = first_mapping["sources"]
        assert len(sources) == 2
        assert sources[0]["channel"] == 0
        assert sources[0]["gain"] == -6

    def test_mixer_multiple_mixers(self, compressor_config):
        doc = normalize_config(compressor_config, "test.yml")
        assert "to_four" in doc["mixers"]
        assert "to_two" in doc["mixers"]
        assert doc["mixers"]["to_four"]["channels"]["out"] == 4
        assert doc["mixers"]["to_two"]["channels"]["out"] == 2

    def test_no_mixers(self, nomixers_config):
        doc = normalize_config(nomixers_config, "test.yml")
        assert doc["mixers"] == {}


# ------------------------------------------------------------------
# Processors section
# ------------------------------------------------------------------


class TestNormalizeProcessors:
    """Processor normalization."""

    def test_compressor_processor(self, compressor_config):
        doc = normalize_config(compressor_config, "test.yml")
        p = doc["processors"]["democompr"]
        assert p["kind"] == "processor"
        assert p["name"] == "democompr"
        assert p["processor_type"] == "Compressor"
        assert p["parameters"]["threshold"] == -20
        assert p["parameters"]["factor"] == 4.0
        assert p["parameters"]["attack"] == 0.1
        assert p["parameters"]["release"] == 1.0

    def test_no_processors(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert doc["processors"] == {}


# ------------------------------------------------------------------
# Pipeline section
# ------------------------------------------------------------------


class TestNormalizePipeline:
    """Pipeline step normalization."""

    def test_pipeline_step_ids(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        pipeline = doc["pipeline"]
        assert len(pipeline) == 2
        assert pipeline[0]["step_id"] == "pipeline_0"
        assert pipeline[1]["step_id"] == "pipeline_1"

    def test_pipeline_step_type(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert doc["pipeline"][0]["step_type"] == "Mixer"
        assert doc["pipeline"][1]["step_type"] == "Filter"

    def test_pipeline_mixer_step_name(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        step = doc["pipeline"][0]
        assert step["name"] == "monomix"

    def test_pipeline_filter_step_channels(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        step = doc["pipeline"][1]
        assert step["channels"] == [0, 1]
        assert step["names"] == ["lowpass_fir"]

    def test_pipeline_channel_normalization_singular(self):
        """singular 'channel' should become 'channels' list."""
        raw = {"pipeline": [{"type": "Filter", "channel": 0, "names": ["f1"]}]}
        doc = normalize_config(raw, "test.yml")
        assert doc["pipeline"][0]["channels"] == [0]

    def test_pipeline_channel_normalization_already_list(self):
        """'channels' list stays as-is."""
        raw = {"pipeline": [{"type": "Filter", "channels": [0, 1], "names": ["f1"]}]}
        doc = normalize_config(raw, "test.yml")
        assert doc["pipeline"][0]["channels"] == [0, 1]

    def test_pipeline_bypassed_none(self, sample_config):
        """Pipeline steps without bypassed field get None."""
        doc = normalize_config(sample_config, "test.yml")
        for step in doc["pipeline"]:
            assert step["bypassed"] is None

    def test_pipeline_bypassed_present(self):
        raw = {
            "pipeline": [
                {"type": "Filter", "channels": [0], "names": ["f1"], "bypassed": False}
            ]
        }
        doc = normalize_config(raw, "test.yml")
        assert doc["pipeline"][0]["bypassed"] is False

    def test_pipeline_many_steps(self, compressor_config):
        doc = normalize_config(compressor_config, "test.yml")
        assert len(doc["pipeline"]) == 5
        # Verify step_ids are sequential
        for i, step in enumerate(doc["pipeline"]):
            assert step["step_id"] == f"pipeline_{i}"

    def test_pipeline_non_dict_entry_skipped(self):
        raw = {
            "pipeline": [
                {"type": "Filter", "channels": [0], "names": ["f1"]},
                "bad_entry",
            ]
        }
        doc = normalize_config(raw, "test.yml")
        assert len(doc["pipeline"]) == 1

    def test_empty_pipeline(self):
        raw = {"devices": {"samplerate": 44100}}
        doc = normalize_config(raw, "test.yml")
        assert doc["pipeline"] == []


# ------------------------------------------------------------------
# Extra / unknown keys
# ------------------------------------------------------------------


class TestNormalizeExtra:
    """Unknown top-level keys go to 'extra'."""

    def test_unknown_top_key(self):
        raw = {"devices": {"samplerate": 44100}, "custom_field": "value"}
        doc = normalize_config(raw, "test.yml")
        assert doc["extra"]["custom_field"] == "value"

    def test_multiple_unknown_keys(self):
        raw = {"devices": {}, "foo": 1, "bar": [2, 3]}
        doc = normalize_config(raw, "test.yml")
        assert doc["extra"]["foo"] == 1
        assert doc["extra"]["bar"] == [2, 3]

    def test_no_extra_keys(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert doc["extra"] == {}


# ------------------------------------------------------------------
# Deep copy isolation
# ------------------------------------------------------------------


class TestNormalizeCopyIsolation:
    """Verify that normalization deep-copies data from the raw config."""

    def test_modifying_normalized_does_not_affect_raw(self, sample_config):
        raw = copy.deepcopy(sample_config)
        doc = normalize_config(raw, "test.yml")
        doc["devices"]["samplerate"] = 99999
        assert raw["devices"]["samplerate"] == 44100


# ------------------------------------------------------------------
# Denormalize
# ------------------------------------------------------------------


class TestDenormalize:
    """denormalize_config reversal tests."""

    def test_denormalize_produces_valid_raw(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        raw = denormalize_config(doc)
        assert "devices" in raw
        assert "mixers" in raw
        assert "filters" in raw
        assert "pipeline" in raw

    def test_denormalize_strips_internal_keys(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        raw = denormalize_config(doc)
        # Internal keys should not appear
        assert "meta" not in raw
        assert "extra" not in raw or raw.get("extra") is None
        # Check filters don't have 'kind', 'variant', etc.
        for fname, fdata in raw.get("filters", {}).items():
            assert "kind" not in fdata
            assert "variant" not in fdata
            assert "name" not in fdata
            # Should have 'type'
            assert "type" in fdata

    def test_denormalize_strips_pipeline_internals(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        raw = denormalize_config(doc)
        for step in raw.get("pipeline", []):
            assert "step_id" not in step
            assert "step_type" not in step
            assert "type" in step

    def test_denormalize_preserves_meta_title(self):
        raw = {"title": "My Config", "description": "desc", "devices": {}}
        doc = normalize_config(raw, "test.yml")
        result = denormalize_config(doc)
        assert result["title"] == "My Config"
        assert result["description"] == "desc"

    def test_denormalize_empty_config(self):
        doc = normalize_config({}, "empty.yml")
        raw = denormalize_config(doc)
        # Should not have empty sections
        assert raw.get("filters") is None or raw.get("filters") == {}
        assert raw.get("pipeline") is None or raw.get("pipeline") == []

    def test_denormalize_restores_extra(self):
        raw = {"devices": {}, "custom_field": "val"}
        doc = normalize_config(raw, "test.yml")
        result = denormalize_config(doc)
        assert result["custom_field"] == "val"

    def test_denormalize_processor(self, compressor_config):
        doc = normalize_config(compressor_config, "test.yml")
        raw = denormalize_config(doc)
        assert "processors" in raw
        p = raw["processors"]["democompr"]
        assert p["type"] == "Compressor"
        assert "parameters" in p
        assert p["parameters"]["threshold"] == -20

    def test_denormalize_biquad_variant_in_params(self, all_biquads_config):
        doc = normalize_config(all_biquads_config, "test.yml")
        raw = denormalize_config(doc)
        hp = raw["filters"]["highpass"]
        assert hp["type"] == "Biquad"
        assert hp["parameters"]["type"] == "Highpass"


# ------------------------------------------------------------------
# Round-trip
# ------------------------------------------------------------------


class TestRoundTrip:
    """Normalize → denormalize round-trip preserves semantic content."""

    def test_round_trip_all_configs(self, any_valid_config):
        """Normalize then denormalize produces a re-normalizable structure."""
        doc1 = normalize_config(any_valid_config, "test.yml")
        raw = denormalize_config(doc1)
        doc2 = normalize_config(raw, "test.yml")

        # Devices should be identical
        assert doc1["devices"] == doc2["devices"]

        # Same number of filters
        assert set(doc1["filters"].keys()) == set(doc2["filters"].keys())
        for fname in doc1["filters"]:
            assert (
                doc1["filters"][fname]["filter_type"]
                == doc2["filters"][fname]["filter_type"]
            )
            assert (
                doc1["filters"][fname]["variant"] == doc2["filters"][fname]["variant"]
            )

        # Same number of pipeline steps
        assert len(doc1["pipeline"]) == len(doc2["pipeline"])
        for s1, s2 in zip(doc1["pipeline"], doc2["pipeline"]):
            assert s1["step_type"] == s2["step_type"]
            assert s1["step_id"] == s2["step_id"]

        # Same mixers
        assert set(doc1["mixers"].keys()) == set(doc2["mixers"].keys())

        # Same processors
        assert set(doc1["processors"].keys()) == set(doc2["processors"].keys())

    def test_round_trip_preserves_devices(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        raw = denormalize_config(doc)
        doc2 = normalize_config(raw, "test.yml")
        assert doc["devices"] == doc2["devices"]

    def test_round_trip_preserves_mixer_mapping(self, sample_config):
        doc1 = normalize_config(sample_config, "test.yml")
        raw = denormalize_config(doc1)
        doc2 = normalize_config(raw, "test.yml")
        m1 = doc1["mixers"]["monomix"]["mapping"]
        m2 = doc2["mixers"]["monomix"]["mapping"]
        assert m1 == m2
