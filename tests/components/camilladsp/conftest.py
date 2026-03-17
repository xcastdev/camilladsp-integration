"""Shared fixtures for CamillaDSP integration tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

EXAMPLE_CONFIGS_DIR = (
    Path(__file__).parent.parent.parent.parent / "docs" / "refs" / "exampleconfigs"
)


# ------------------------------------------------------------------
# Named config fixtures
# ------------------------------------------------------------------


@pytest.fixture
def sample_config():
    """Load simpleconfig.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "simpleconfig.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def all_biquads_config():
    """Load all_biquads.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "all_biquads.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def compressor_config():
    """Load lf_compressor.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "lf_compressor.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def gain_config():
    """Load gainconfig.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "gainconfig.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def dither_config():
    """Load ditherplay.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "ditherplay.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def tokens_config():
    """Load tokens.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "tokens.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def nofilters_config():
    """Load nofilters.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "nofilters.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def nomixers_config():
    """Load nomixers.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "nomixers.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def broken_config():
    """Load brokenconfig.yml as a dict."""
    with open(EXAMPLE_CONFIGS_DIR / "brokenconfig.yml") as f:
        return yaml.safe_load(f)


# ------------------------------------------------------------------
# Parametrized "every valid config" fixture
# ------------------------------------------------------------------

_VALID_CONFIG_FILES = [
    "simpleconfig.yml",
    "gainconfig.yml",
    "all_biquads.yml",
    "lf_compressor.yml",
    "ditherplay.yml",
    "tokens.yml",
    "nofilters.yml",
    "nomixers.yml",
    "file_capt.yml",
    "file_pb.yml",
    "pulseconfig.yml",
    "resample_file.yml",
    "simpleconfig_plot.yml",
    "simpleconfig_resample.yml",
    "stdio_capt.yml",
    "stdio_inout.yml",
    "stdio_pb.yml",
]


@pytest.fixture(params=_VALID_CONFIG_FILES)
def any_valid_config(request):
    """Parametrized fixture loading every valid example config."""
    with open(EXAMPLE_CONFIGS_DIR / request.param) as f:
        return yaml.safe_load(f)


@pytest.fixture(params=_VALID_CONFIG_FILES)
def any_valid_config_name(request):
    """Parametrized fixture returning (filename, config_dict) tuples."""
    with open(EXAMPLE_CONFIGS_DIR / request.param) as f:
        return request.param, yaml.safe_load(f)


# ------------------------------------------------------------------
# Mock client fixture
# ------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """Create a mock CamillaDSP API client."""
    client = AsyncMock()
    client.get_gui_config = AsyncMock()
    client.get_active_config_file = AsyncMock()
    client.get_config = AsyncMock()
    client.validate_config = AsyncMock(return_value="OK")
    client.set_config = AsyncMock()
    client.save_config_file = AsyncMock()
    client.get_stored_configs = AsyncMock(return_value=[])
    client.set_active_config_file = AsyncMock()
    client.get_status = AsyncMock()
    client.get_volume = AsyncMock(return_value=0.0)
    client.set_volume = AsyncMock()
    client.get_mute = AsyncMock(return_value=False)
    client.set_mute = AsyncMock()
    return client
