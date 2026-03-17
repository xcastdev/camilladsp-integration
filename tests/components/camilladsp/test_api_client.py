"""Tests for api/client.py – CamillaDSPClient with mocked HTTP transport."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.camilladsp.api.client import CamillaDSPClient
from custom_components.camilladsp.api.errors import (
    CamillaDSPConnectionError,
    CamillaDSPError,
    CamillaDSPPayloadError,
    CamillaDSPTimeoutError,
)
from custom_components.camilladsp.api.models import (
    ActiveConfigFile,
    GuiConfig,
    RuntimeStatus,
    StoredConfig,
)


# ------------------------------------------------------------------
# Test helpers
# ------------------------------------------------------------------


def _mock_response(*, json_data=None, text_data=None, status=200):
    """Create a mock aiohttp response."""
    resp = AsyncMock(spec=aiohttp.ClientResponse)
    resp.status = status
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    if text_data is not None:
        resp.text = AsyncMock(return_value=text_data)
    else:
        resp.text = AsyncMock(return_value="")
    return resp


class MockContextManager:
    """Simulate an async context manager for session.get/post."""

    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *args):
        pass


def _mock_session(get_response=None, post_response=None):
    """Create a mock aiohttp.ClientSession."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.closed = False
    if get_response is not None:
        session.get = MagicMock(return_value=MockContextManager(get_response))
    if post_response is not None:
        session.post = MagicMock(return_value=MockContextManager(post_response))
    return session


# ------------------------------------------------------------------
# get_gui_config
# ------------------------------------------------------------------


class TestGetGuiConfig:
    """Test GET /api/guiconfig parsing."""

    @pytest.mark.asyncio
    async def test_basic_gui_config(self):
        resp = _mock_response(
            json_data={
                "hide_capture_samplerate": True,
                "hide_silence": False,
                "apply_config_automatically": True,
                "status_update_interval": 200,
                "can_update_active_config": True,
                "coeff_dir": "/path/to/coeffs",
            }
        )
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_gui_config()

        assert isinstance(result, GuiConfig)
        assert result.hide_capture_samplerate is True
        assert result.hide_silence is False
        assert result.apply_config_automatically is True
        assert result.status_update_interval == 200
        assert result.coeff_dir == "/path/to/coeffs"

    @pytest.mark.asyncio
    async def test_gui_config_defaults(self):
        resp = _mock_response(json_data={})
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_gui_config()

        assert result.hide_capture_samplerate is False
        assert result.status_update_interval == 100
        assert result.can_update_active_config is True
        assert result.coeff_dir == ""

    @pytest.mark.asyncio
    async def test_gui_config_invalid_payload(self):
        resp = _mock_response(json_data="not_a_dict")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPPayloadError):
            await client.get_gui_config()


# ------------------------------------------------------------------
# get_active_config_file
# ------------------------------------------------------------------


class TestGetActiveConfigFile:
    """Test GET /api/getactiveconfigfile parsing."""

    @pytest.mark.asyncio
    async def test_basic(self):
        resp = _mock_response(
            json_data={
                "configFileName": "myconfig.yml",
                "config": {"devices": {"samplerate": 44100}},
            }
        )
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_active_config_file()

        assert isinstance(result, ActiveConfigFile)
        assert result.filename == "myconfig.yml"
        assert result.config["devices"]["samplerate"] == 44100

    @pytest.mark.asyncio
    async def test_missing_key(self):
        resp = _mock_response(json_data={"wrong_key": "value"})
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPPayloadError):
            await client.get_active_config_file()

    @pytest.mark.asyncio
    async def test_invalid_payload_type(self):
        resp = _mock_response(json_data=[1, 2, 3])
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPPayloadError):
            await client.get_active_config_file()


# ------------------------------------------------------------------
# get_config
# ------------------------------------------------------------------


class TestGetConfig:
    """Test GET /api/getconfig."""

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        resp = _mock_response(json_data={"devices": {"samplerate": 44100}})
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_config()
        assert isinstance(result, dict)
        assert result["devices"]["samplerate"] == 44100

    @pytest.mark.asyncio
    async def test_invalid_payload(self):
        resp = _mock_response(json_data="not_dict")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPPayloadError):
            await client.get_config()


# ------------------------------------------------------------------
# validate_config
# ------------------------------------------------------------------


class TestValidateConfig:
    """Test POST /api/validateconfig."""

    @pytest.mark.asyncio
    async def test_valid_config(self):
        resp = _mock_response(text_data="OK")
        session = _mock_session(post_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.validate_config({"devices": {}})
        assert result == "OK"

    @pytest.mark.asyncio
    async def test_invalid_config(self):
        resp = _mock_response(text_data="ERROR: Missing samplerate")
        session = _mock_session(post_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.validate_config({"devices": {}})
        assert "ERROR" in result


# ------------------------------------------------------------------
# get_stored_configs
# ------------------------------------------------------------------


class TestGetStoredConfigs:
    """Test GET /api/storedconfigs."""

    @pytest.mark.asyncio
    async def test_returns_list(self):
        resp = _mock_response(
            json_data=[
                {"name": "config1.yml", "lastModified": 1234567890.0},
                {"name": "config2.yml"},
            ]
        )
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_stored_configs()
        assert len(result) == 2
        assert isinstance(result[0], StoredConfig)
        assert result[0].name == "config1.yml"
        assert result[0].last_modified == 1234567890.0
        assert result[1].name == "config2.yml"
        assert result[1].last_modified is None

    @pytest.mark.asyncio
    async def test_empty_list(self):
        resp = _mock_response(json_data=[])
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_stored_configs()
        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_payload(self):
        resp = _mock_response(json_data={"not": "a_list"})
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPPayloadError):
            await client.get_stored_configs()


# ------------------------------------------------------------------
# get_status
# ------------------------------------------------------------------


class TestGetStatus:
    """Test GET /api/status."""

    @pytest.mark.asyncio
    async def test_full_status(self):
        resp = _mock_response(
            json_data={
                "state": "Running",
                "captureRate": 44100,
                "rateAdjust": 1.0,
                "clippedSamples": 0,
                "bufferLevel": 512,
                "processingLoad": 5.2,
                "signalRange": -20.0,
                "signalRms": -25.0,
                "captureSignalPeak": [-10.0, -12.0],
                "captureSignalRms": [-20.0, -22.0],
                "playbackSignalPeak": [-5.0, -6.0],
                "playbackSignalRms": [-15.0, -16.0],
            }
        )
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_status()
        assert isinstance(result, RuntimeStatus)
        assert result.state == "Running"
        assert result.capture_rate == 44100
        assert result.processing_load == 5.2
        assert result.capture_signal_peak == [-10.0, -12.0]
        assert result.playback_signal_rms == [-15.0, -16.0]

    @pytest.mark.asyncio
    async def test_status_defaults(self):
        resp = _mock_response(json_data={})
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_status()
        assert result.state == "unknown"
        assert result.capture_rate == 0
        assert result.processing_load == 0.0
        assert result.capture_signal_peak == []

    @pytest.mark.asyncio
    async def test_status_raw_preserved(self):
        data = {"state": "Running", "custom_field": 42}
        resp = _mock_response(json_data=data)
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_status()
        assert result.raw == data

    @pytest.mark.asyncio
    async def test_status_invalid_payload(self):
        resp = _mock_response(json_data="not_dict")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPPayloadError):
            await client.get_status()


# ------------------------------------------------------------------
# get_volume / set_volume
# ------------------------------------------------------------------


class TestVolume:
    """Test GET/POST /api/getparam/volume."""

    @pytest.mark.asyncio
    async def test_get_volume(self):
        resp = _mock_response(text_data="-20.5")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        result = await client.get_volume()
        assert result == -20.5

    @pytest.mark.asyncio
    async def test_get_volume_zero(self):
        resp = _mock_response(text_data="0.0")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        assert await client.get_volume() == 0.0

    @pytest.mark.asyncio
    async def test_get_volume_invalid(self):
        resp = _mock_response(text_data="not_a_number")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPPayloadError):
            await client.get_volume()

    @pytest.mark.asyncio
    async def test_set_volume(self):
        resp = _mock_response(text_data="OK")
        session = _mock_session(post_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        await client.set_volume(-20.0)
        session.post.assert_called_once()


# ------------------------------------------------------------------
# get_mute / set_mute
# ------------------------------------------------------------------


class TestMute:
    """Test GET/POST /api/getparam/mute."""

    @pytest.mark.asyncio
    async def test_get_mute_true(self):
        resp = _mock_response(text_data="True")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        assert await client.get_mute() is True

    @pytest.mark.asyncio
    async def test_get_mute_false(self):
        resp = _mock_response(text_data="False")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        assert await client.get_mute() is False

    @pytest.mark.asyncio
    async def test_get_mute_case_insensitive(self):
        resp = _mock_response(text_data="true")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        assert await client.get_mute() is True

    @pytest.mark.asyncio
    async def test_get_mute_invalid(self):
        resp = _mock_response(text_data="maybe")
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPPayloadError):
            await client.get_mute()

    @pytest.mark.asyncio
    async def test_set_mute(self):
        resp = _mock_response(text_data="OK")
        session = _mock_session(post_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        await client.set_mute(True)
        session.post.assert_called_once()


# ------------------------------------------------------------------
# Connection and timeout errors
# ------------------------------------------------------------------


class TestErrorHandling:
    """Error translation: aiohttp errors → CamillaDSP errors."""

    @pytest.mark.asyncio
    async def test_connection_error_on_get(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        session.closed = False
        session.get = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPConnectionError):
            await client.get_config()

    @pytest.mark.asyncio
    async def test_timeout_error_on_get(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        session.closed = False
        session.get = MagicMock(side_effect=asyncio.TimeoutError())
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPTimeoutError):
            await client.get_config()

    @pytest.mark.asyncio
    async def test_connection_error_on_post(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        session.closed = False
        session.post = MagicMock(side_effect=aiohttp.ClientError("Connection reset"))
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPConnectionError):
            await client.set_config("test.yml", {})

    @pytest.mark.asyncio
    async def test_timeout_error_on_post(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        session.closed = False
        session.post = MagicMock(side_effect=asyncio.TimeoutError())
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPTimeoutError):
            await client.set_config("test.yml", {})

    @pytest.mark.asyncio
    async def test_http_error_status(self):
        resp = _mock_response(status=500, json_data={})
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPError):
            await client.get_config()

    @pytest.mark.asyncio
    async def test_http_404_error(self):
        resp = _mock_response(status=404, json_data={})
        session = _mock_session(get_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPError):
            await client.get_gui_config()

    @pytest.mark.asyncio
    async def test_timeout_is_subclass_of_connection_error(self):
        """CamillaDSPTimeoutError should be catchable as CamillaDSPConnectionError."""
        session = MagicMock(spec=aiohttp.ClientSession)
        session.closed = False
        session.get = MagicMock(side_effect=asyncio.TimeoutError())
        client = CamillaDSPClient("http://localhost:5005", session=session)

        with pytest.raises(CamillaDSPConnectionError):
            await client.get_config()


# ------------------------------------------------------------------
# set_config / save_config_file / set_active_config_file
# ------------------------------------------------------------------


class TestWriteEndpoints:
    """POST endpoints that don't return meaningful data."""

    @pytest.mark.asyncio
    async def test_set_config(self):
        resp = _mock_response(json_data=None, status=200)
        resp.json = AsyncMock(return_value=None)
        session = _mock_session(post_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        await client.set_config("test.yml", {"devices": {}})
        session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_config_file(self):
        resp = _mock_response(json_data=None, status=200)
        resp.json = AsyncMock(return_value=None)
        session = _mock_session(post_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        await client.save_config_file("test.yml", {"devices": {}})
        session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_active_config_file(self):
        resp = _mock_response(json_data=None, status=200)
        resp.json = AsyncMock(return_value=None)
        session = _mock_session(post_response=resp)
        client = CamillaDSPClient("http://localhost:5005", session=session)

        await client.set_active_config_file("myconfig.yml")
        session.post.assert_called_once()


# ------------------------------------------------------------------
# Context manager and session lifecycle
# ------------------------------------------------------------------


class TestClientLifecycle:
    """Client session ownership and cleanup."""

    @pytest.mark.asyncio
    async def test_external_session_not_closed(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        session.closed = False
        client = CamillaDSPClient("http://localhost:5005", session=session)

        await client.close()
        # External session should NOT be closed by the client
        # (owns_session is False since we provided a session)
        # Actually, owns_session is False when session is provided
        session.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_base_url_stored(self):
        client = CamillaDSPClient("http://192.168.1.10:5005")
        assert client._base_url == "http://192.168.1.10:5005"

    @pytest.mark.asyncio
    async def test_base_url_trailing_slash_stripped(self):
        client = CamillaDSPClient("http://localhost:9999/")
        assert client._base_url == "http://localhost:9999"
