"""Tests for config/mutate.py – get_value, set_value, delete_value, batch_set_values."""

from __future__ import annotations

import pytest

from custom_components.camilladsp.config.mutate import (
    batch_set_values,
    delete_value,
    get_value,
    set_value,
)
from custom_components.camilladsp.config.normalize import normalize_config


# ------------------------------------------------------------------
# get_value
# ------------------------------------------------------------------


class TestGetValue:
    """get_value delegates to resolve_path."""

    def test_get_samplerate(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert get_value(doc, "devices.samplerate") == 44100

    def test_get_filter_parameter(self, all_biquads_config):
        doc = normalize_config(all_biquads_config, "test.yml")
        assert get_value(doc, "filters.highpass.parameters.freq") == 1000

    def test_get_mixer_gain(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        val = get_value(doc, "mixers.monomix.mapping[0].sources[0].gain")
        assert val == -6

    def test_get_pipeline_step_type(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert get_value(doc, "pipeline[0].step_type") == "Mixer"

    def test_get_nonexistent_raises_keyerror(self):
        doc = normalize_config({}, "test.yml")
        with pytest.raises(KeyError):
            get_value(doc, "nonexistent.path")

    def test_get_invalid_index_raises_indexerror(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(IndexError):
            get_value(doc, "pipeline[99]")


# ------------------------------------------------------------------
# set_value
# ------------------------------------------------------------------


class TestSetValue:
    """set_value returns a new document; original is unchanged."""

    def test_set_samplerate(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        new_doc = set_value(doc, "devices.samplerate", 48000)
        assert new_doc["devices"]["samplerate"] == 48000
        # Original unchanged
        assert doc["devices"]["samplerate"] == 44100

    def test_set_filter_parameter(self, all_biquads_config):
        doc = normalize_config(all_biquads_config, "test.yml")
        new_doc = set_value(doc, "filters.highpass.parameters.freq", 2000)
        assert new_doc["filters"]["highpass"]["parameters"]["freq"] == 2000
        assert doc["filters"]["highpass"]["parameters"]["freq"] == 1000

    def test_set_mixer_gain(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        path = "mixers.monomix.mapping[0].sources[0].gain"
        new_doc = set_value(doc, path, -3)
        assert get_value(new_doc, path) == -3
        assert get_value(doc, path) == -6

    def test_set_new_key_on_existing_dict(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        new_doc = set_value(doc, "devices.new_key", "new_value")
        assert new_doc["devices"]["new_key"] == "new_value"
        assert "new_key" not in doc["devices"]

    def test_set_pipeline_value(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        new_doc = set_value(doc, "pipeline[0].name", "renamed")
        assert new_doc["pipeline"][0]["name"] == "renamed"
        assert doc["pipeline"][0]["name"] == "monomix"

    def test_set_value_empty_path_raises(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(ValueError, match="Empty path"):
            set_value(doc, "", 42)

    def test_set_value_invalid_parent_raises(self):
        doc = normalize_config({}, "test.yml")
        with pytest.raises((KeyError, IndexError, TypeError)):
            set_value(doc, "nonexistent.deeply.nested.path", 42)

    def test_set_value_returns_new_dict(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        new_doc = set_value(doc, "devices.samplerate", 48000)
        assert new_doc is not doc
        assert new_doc["devices"] is not doc["devices"]

    def test_set_value_nested_deep(self, compressor_config):
        doc = normalize_config(compressor_config, "test.yml")
        new_doc = set_value(doc, "processors.democompr.parameters.threshold", -30)
        assert new_doc["processors"]["democompr"]["parameters"]["threshold"] == -30
        assert doc["processors"]["democompr"]["parameters"]["threshold"] == -20


# ------------------------------------------------------------------
# delete_value
# ------------------------------------------------------------------


class TestDeleteValue:
    """delete_value returns a new document with the path removed."""

    def test_delete_key(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        new_doc = delete_value(doc, "devices.samplerate")
        assert "samplerate" not in new_doc["devices"]
        # Original unchanged
        assert "samplerate" in doc["devices"]

    def test_delete_filter(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        new_doc = delete_value(doc, "filters.lowpass_fir")
        assert "lowpass_fir" not in new_doc["filters"]
        assert "lowpass_fir" in doc["filters"]

    def test_delete_pipeline_step(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        orig_len = len(doc["pipeline"])
        new_doc = delete_value(doc, "pipeline[0]")
        assert len(new_doc["pipeline"]) == orig_len - 1
        assert len(doc["pipeline"]) == orig_len

    def test_delete_nonexistent_raises_keyerror(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(KeyError):
            delete_value(doc, "devices.nonexistent_key")

    def test_delete_empty_path_raises(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(ValueError, match="Empty path"):
            delete_value(doc, "")

    def test_delete_returns_new_dict(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        new_doc = delete_value(doc, "devices.samplerate")
        assert new_doc is not doc

    def test_delete_nested(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        path = "mixers.monomix.mapping[0].sources[0].gain"
        new_doc = delete_value(doc, path)
        assert "gain" not in new_doc["mixers"]["monomix"]["mapping"][0]["sources"][0]
        # Original preserved
        assert doc["mixers"]["monomix"]["mapping"][0]["sources"][0]["gain"] == -6


# ------------------------------------------------------------------
# batch_set_values
# ------------------------------------------------------------------


class TestBatchSetValues:
    """batch_set_values applies multiple mutations atomically."""

    def test_batch_multiple_changes(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        operations = [
            {"path": "devices.samplerate", "value": 48000},
            {"path": "devices.chunksize", "value": 2048},
        ]
        new_doc = batch_set_values(doc, operations)
        assert new_doc["devices"]["samplerate"] == 48000
        assert new_doc["devices"]["chunksize"] == 2048
        # Original unchanged
        assert doc["devices"]["samplerate"] == 44100
        assert doc["devices"]["chunksize"] == 1024

    def test_batch_single_operation(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        operations = [{"path": "devices.samplerate", "value": 96000}]
        new_doc = batch_set_values(doc, operations)
        assert new_doc["devices"]["samplerate"] == 96000

    def test_batch_empty_operations(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        new_doc = batch_set_values(doc, [])
        # Should be a deep copy of original
        assert new_doc is not doc
        assert new_doc["devices"]["samplerate"] == doc["devices"]["samplerate"]

    def test_batch_cross_section_changes(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        operations = [
            {"path": "devices.samplerate", "value": 48000},
            {"path": "mixers.monomix.mapping[0].sources[0].gain", "value": -3},
        ]
        new_doc = batch_set_values(doc, operations)
        assert new_doc["devices"]["samplerate"] == 48000
        assert new_doc["mixers"]["monomix"]["mapping"][0]["sources"][0]["gain"] == -3
        # Originals unchanged
        assert doc["devices"]["samplerate"] == 44100
        assert doc["mixers"]["monomix"]["mapping"][0]["sources"][0]["gain"] == -6

    def test_batch_empty_path_raises(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(ValueError, match="Empty path"):
            batch_set_values(doc, [{"path": "", "value": 42}])

    def test_batch_invalid_path_raises(self):
        doc = normalize_config({}, "test.yml")
        with pytest.raises((KeyError, IndexError)):
            batch_set_values(doc, [{"path": "nonexistent.deep.path", "value": 42}])

    def test_batch_single_deep_copy(self, sample_config):
        """batch_set_values makes one deep copy, not one per operation."""
        doc = normalize_config(sample_config, "test.yml")
        operations = [
            {"path": "devices.samplerate", "value": 48000},
            {"path": "devices.chunksize", "value": 2048},
        ]
        new_doc = batch_set_values(doc, operations)
        # Both changes on the same copy
        assert new_doc["devices"]["samplerate"] == 48000
        assert new_doc["devices"]["chunksize"] == 2048
        assert new_doc is not doc

    def test_batch_sequential_overwrites(self, sample_config):
        """Later operations can overwrite earlier ones."""
        doc = normalize_config(sample_config, "test.yml")
        operations = [
            {"path": "devices.samplerate", "value": 48000},
            {"path": "devices.samplerate", "value": 96000},
        ]
        new_doc = batch_set_values(doc, operations)
        assert new_doc["devices"]["samplerate"] == 96000
