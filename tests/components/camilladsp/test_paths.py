"""Tests for config/paths.py – parse_path, resolve_path, path_exists, format_path."""

from __future__ import annotations

import pytest

from custom_components.camilladsp.config.normalize import normalize_config
from custom_components.camilladsp.config.paths import (
    format_path,
    parse_path,
    path_exists,
    resolve_path,
)


# ------------------------------------------------------------------
# parse_path
# ------------------------------------------------------------------


class TestParsePath:
    """Path string → segment list conversion."""

    def test_simple_dotted_path(self):
        assert parse_path("filters.Bass.parameters.gain") == [
            "filters",
            "Bass",
            "parameters",
            "gain",
        ]

    def test_bracket_index(self):
        assert parse_path("pipeline[1].bypassed") == ["pipeline", 1, "bypassed"]

    def test_nested_brackets(self):
        assert parse_path("mixers.Stereo.mapping[0].sources[0].gain") == [
            "mixers",
            "Stereo",
            "mapping",
            0,
            "sources",
            0,
            "gain",
        ]

    def test_single_segment(self):
        assert parse_path("devices") == ["devices"]

    def test_empty_path(self):
        assert parse_path("") == []

    def test_multiple_brackets_on_same_key(self):
        # Unusual but syntactically valid: "a[0][1]"
        assert parse_path("a[0][1]") == ["a", 0, 1]

    def test_bracket_only(self):
        # "[0]" - index with no preceding key
        result = parse_path("[0]")
        assert result == [0]

    def test_spaces_in_name(self):
        """Path segments with spaces (e.g. filter names)."""
        assert parse_path("filters.Bass Control.parameters.gain") == [
            "filters",
            "Bass Control",
            "parameters",
            "gain",
        ]

    def test_deeply_nested(self):
        path = "a.b.c.d.e.f"
        assert parse_path(path) == ["a", "b", "c", "d", "e", "f"]

    def test_bracket_at_end(self):
        assert parse_path("pipeline[2]") == ["pipeline", 2]


# ------------------------------------------------------------------
# resolve_path
# ------------------------------------------------------------------


class TestResolvePath:
    """resolve_path traversal into documents."""

    def test_resolve_samplerate(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert resolve_path(doc, "devices.samplerate") == 44100

    def test_resolve_filter_parameter(self, all_biquads_config):
        doc = normalize_config(all_biquads_config, "test.yml")
        assert resolve_path(doc, "filters.highpass.parameters.freq") == 1000

    def test_resolve_pipeline_step(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        step = resolve_path(doc, "pipeline[0]")
        assert step["step_type"] == "Mixer"
        assert step["name"] == "monomix"

    def test_resolve_mixer_source_gain(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        gain = resolve_path(doc, "mixers.monomix.mapping[0].sources[0].gain")
        assert gain == -6

    def test_resolve_meta(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert resolve_path(doc, "meta.filename") == "test.yml"

    def test_resolve_with_segment_list(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        segments = ["devices", "samplerate"]
        assert resolve_path(doc, segments) == 44100

    def test_resolve_missing_key_raises_keyerror(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(KeyError):
            resolve_path(doc, "nonexistent.path")

    def test_resolve_missing_index_raises_indexerror(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(IndexError):
            resolve_path(doc, "pipeline[99]")

    def test_resolve_type_error_on_scalar(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(TypeError):
            resolve_path(doc, "devices.samplerate.deeper")

    def test_resolve_index_on_dict_raises_type_error(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        with pytest.raises(TypeError):
            resolve_path(doc, ["devices", 0])


# ------------------------------------------------------------------
# path_exists
# ------------------------------------------------------------------


class TestPathExists:
    """path_exists returns True/False without raising."""

    def test_exists_true(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert path_exists(doc, "devices.samplerate") is True

    def test_exists_false(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert path_exists(doc, "nonexistent.path") is False

    def test_exists_deep_true(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert path_exists(doc, "mixers.monomix.mapping[0].sources[0].gain") is True

    def test_exists_deep_false(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert path_exists(doc, "mixers.monomix.mapping[99]") is False

    def test_exists_empty_path(self):
        doc = normalize_config({}, "test.yml")
        # Empty path resolves to the doc itself – should be True
        assert path_exists(doc, "") is True

    def test_exists_pipeline_index(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        assert path_exists(doc, "pipeline[0]") is True
        assert path_exists(doc, "pipeline[1]") is True
        assert path_exists(doc, "pipeline[2]") is False

    def test_exists_filter_variant(self, all_biquads_config):
        doc = normalize_config(all_biquads_config, "test.yml")
        assert path_exists(doc, "filters.highpass.variant") is True
        assert path_exists(doc, "filters.highpass.nonexistent") is False


# ------------------------------------------------------------------
# format_path
# ------------------------------------------------------------------


class TestFormatPath:
    """format_path converts segments back to canonical string."""

    def test_simple_path(self):
        assert format_path(["filters", "Bass", "parameters", "gain"]) == (
            "filters.Bass.parameters.gain"
        )

    def test_bracket_path(self):
        assert format_path(["pipeline", 1, "bypassed"]) == "pipeline[1].bypassed"

    def test_nested_brackets(self):
        assert format_path(
            ["mixers", "Stereo", "mapping", 0, "sources", 1, "gain"]
        ) == ("mixers.Stereo.mapping[0].sources[1].gain")

    def test_empty_segments(self):
        assert format_path([]) == ""

    def test_single_segment(self):
        assert format_path(["devices"]) == "devices"

    def test_leading_index(self):
        # Edge case: path starts with an index
        assert format_path([0]) == "[0]"

    def test_roundtrip_simple(self):
        path = "filters.Bass Control.parameters.gain"
        assert format_path(parse_path(path)) == path

    def test_roundtrip_bracketed(self):
        path = "mixers.Stereo.mapping[0].sources[1].gain"
        assert format_path(parse_path(path)) == path

    def test_roundtrip_pipeline(self):
        path = "pipeline[1].bypassed"
        assert format_path(parse_path(path)) == path

    def test_consecutive_indices(self):
        segments = ["data", 0, 1]
        assert format_path(segments) == "data[0][1]"
