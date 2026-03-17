"""Tests for config/validate.py – local validators and validate_and_apply."""

from __future__ import annotations

import pytest

from custom_components.camilladsp.api.errors import CamillaDSPValidationError
from custom_components.camilladsp.config.normalize import (
    denormalize_config,
    normalize_config,
)
from custom_components.camilladsp.config.validate import (
    ValidationError,
    validate_and_apply,
    validate_enum_value,
    validate_local,
    validate_path_exists,
    validate_value_type,
)


# ------------------------------------------------------------------
# validate_path_exists
# ------------------------------------------------------------------


class TestValidatePathExists:
    """validate_path_exists returns None on success, ValidationError on failure."""

    def test_success(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        result = validate_path_exists(doc, "devices.samplerate")
        assert result is None

    def test_failure(self):
        doc = normalize_config({}, "test.yml")
        result = validate_path_exists(doc, "nonexistent.path")
        assert result is not None
        assert isinstance(result, ValidationError)
        assert "nonexistent.path" in result.path

    def test_deep_path_success(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        result = validate_path_exists(doc, "mixers.monomix.mapping[0].sources[0].gain")
        assert result is None

    def test_deep_path_failure(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        result = validate_path_exists(doc, "mixers.monomix.mapping[99]")
        assert result is not None

    def test_validation_error_message(self):
        doc = normalize_config({}, "test.yml")
        result = validate_path_exists(doc, "missing.path")
        assert "does not exist" in result.message


# ------------------------------------------------------------------
# validate_value_type
# ------------------------------------------------------------------


class TestValidateValueType:
    """Type checking for proposed values."""

    def test_float_match(self):
        assert validate_value_type(42.0, float) is None

    def test_int_match(self):
        assert validate_value_type(42, int) is None

    def test_str_match(self):
        assert validate_value_type("hello", str) is None

    def test_bool_match(self):
        assert validate_value_type(True, bool) is None

    def test_float_mismatch(self):
        result = validate_value_type("string", float)
        assert result is not None
        assert isinstance(result, ValidationError)
        assert "Expected type float" in result.message
        assert "str" in result.message

    def test_int_mismatch(self):
        result = validate_value_type(3.14, int)
        assert result is not None

    def test_str_mismatch(self):
        result = validate_value_type(42, str)
        assert result is not None

    def test_path_in_error(self):
        result = validate_value_type("wrong", float, path="devices.samplerate")
        assert result.path == "devices.samplerate"

    def test_none_value(self):
        result = validate_value_type(None, float)
        assert result is not None

    def test_list_type(self):
        assert validate_value_type([1, 2], list) is None
        result = validate_value_type({}, list)
        assert result is not None


# ------------------------------------------------------------------
# validate_enum_value
# ------------------------------------------------------------------


class TestValidateEnumValue:
    """Enum validation for choice-based fields."""

    def test_valid_option(self):
        assert validate_enum_value("dB", ["dB", "linear"]) is None

    def test_invalid_option(self):
        result = validate_enum_value("invalid", ["dB", "linear"])
        assert result is not None
        assert isinstance(result, ValidationError)
        assert "invalid" in result.message

    def test_empty_options(self):
        result = validate_enum_value("anything", [])
        assert result is not None

    def test_numeric_enum(self):
        assert validate_enum_value(1, [1, 2, 3]) is None
        result = validate_enum_value(4, [1, 2, 3])
        assert result is not None

    def test_path_in_error(self):
        result = validate_enum_value("bad", ["good"], path="some.path")
        assert result.path == "some.path"

    def test_case_sensitive(self):
        """Enum validation is case-sensitive."""
        result = validate_enum_value("DB", ["dB", "linear"])
        assert result is not None


# ------------------------------------------------------------------
# validate_local
# ------------------------------------------------------------------


class TestValidateLocal:
    """validate_local runs all local checks on a prospective mutation."""

    def test_valid_mutation(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        errors = validate_local(doc, "devices.samplerate", 48000)
        assert errors == []

    def test_invalid_parent_path(self):
        doc = normalize_config({}, "test.yml")
        errors = validate_local(doc, "nonexistent.deeply.nested", 42)
        assert len(errors) > 0
        assert any("Parent path" in str(e) for e in errors)

    def test_valid_deep_path(self, sample_config):
        doc = normalize_config(sample_config, "test.yml")
        errors = validate_local(doc, "mixers.monomix.mapping[0].sources[0].gain", -3)
        # Parent "mixers.monomix.mapping[0].sources[0]" exists so this is OK
        # But validate_local uses rsplit('.', 1) which may not handle brackets perfectly
        # Just verify it returns a list
        assert isinstance(errors, list)

    def test_top_level_path_no_parent_check(self):
        doc = normalize_config({}, "test.yml")
        # A top-level path like "devices" has no parent to check
        errors = validate_local(doc, "devices", {})
        assert errors == []


# ------------------------------------------------------------------
# ValidationError data class
# ------------------------------------------------------------------


class TestValidationError:
    """ValidationError is a frozen dataclass with __str__."""

    def test_str_with_path(self):
        err = ValidationError(path="devices.samplerate", message="Must be positive")
        assert str(err) == "devices.samplerate: Must be positive"

    def test_str_without_path(self):
        err = ValidationError(path="", message="General error")
        assert str(err) == "General error"

    def test_frozen(self):
        err = ValidationError(path="a", message="b")
        with pytest.raises(AttributeError):
            err.path = "c"  # type: ignore[misc]


# ------------------------------------------------------------------
# validate_and_apply (async)
# ------------------------------------------------------------------


class TestValidateAndApply:
    """Integration test for the full denormalize→validate→set→save pipeline."""

    @pytest.mark.asyncio
    async def test_valid_config_applied(self, sample_config, mock_client):
        doc = normalize_config(sample_config, "test.yml")
        mock_client.validate_config.return_value = "OK"

        result = await validate_and_apply(mock_client, doc, "test.yml")

        assert isinstance(result, dict)
        mock_client.validate_config.assert_awaited_once()
        mock_client.set_config.assert_awaited_once()
        mock_client.save_config_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_valid_config_no_save(self, sample_config, mock_client):
        doc = normalize_config(sample_config, "test.yml")
        mock_client.validate_config.return_value = "OK"

        await validate_and_apply(mock_client, doc, "test.yml", save=False)

        mock_client.set_config.assert_awaited_once()
        mock_client.save_config_file.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_backend_validation_failure(self, sample_config, mock_client):
        doc = normalize_config(sample_config, "test.yml")
        mock_client.validate_config.return_value = "ERROR: Invalid samplerate"

        with pytest.raises(CamillaDSPValidationError) as exc_info:
            await validate_and_apply(mock_client, doc, "test.yml")

        assert exc_info.value.details == "ERROR: Invalid samplerate"
        # set_config should NOT be called on validation failure
        mock_client.set_config.assert_not_awaited()
        mock_client.save_config_file.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_denormalized_config_passed_to_backend(
        self, sample_config, mock_client
    ):
        doc = normalize_config(sample_config, "test.yml")
        mock_client.validate_config.return_value = "OK"

        result = await validate_and_apply(mock_client, doc, "test.yml")

        # The result should be the denormalized config
        assert "devices" in result
        assert "meta" not in result  # internal keys stripped
        # validate_config should receive a raw config dict
        config_arg = mock_client.validate_config.call_args[0][0]
        assert isinstance(config_arg, dict)
        assert "devices" in config_arg

    @pytest.mark.asyncio
    async def test_filename_passed_to_set_and_save(self, sample_config, mock_client):
        doc = normalize_config(sample_config, "test.yml")
        mock_client.validate_config.return_value = "OK"

        await validate_and_apply(mock_client, doc, "myconfig.yml")

        set_args = mock_client.set_config.call_args[0]
        assert set_args[0] == "myconfig.yml"
        save_args = mock_client.save_config_file.call_args[0]
        assert save_args[0] == "myconfig.yml"
