"""Async HTTP client for the CamillaDSP backend API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .errors import (
    CamillaDSPConnectionError,
    CamillaDSPError,
    CamillaDSPPayloadError,
    CamillaDSPTimeoutError,
)
from .models import (
    ActiveConfigFile,
    GuiConfig,
    RuntimeStatus,
    StoredConfig,
)

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)


class CamillaDSPClient:
    """Async HTTP client for CamillaDSP backend API.

    The client wraps *aiohttp* and translates transport-level errors into
    the typed exceptions defined in :mod:`.errors`.  It can optionally own
    its ``ClientSession`` (created lazily) or reuse one provided by the
    caller (e.g. from Home Assistant).

    Usage as an async context manager::

        async with CamillaDSPClient("192.168.1.10", 5005) as client:
            status = await client.get_status()
    """

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self._owns_session = session is None
        self._timeout = timeout or _DEFAULT_TIMEOUT

    # ------------------------------------------------------------------
    # Async context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> CamillaDSPClient:
        await self._ensure_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Return the active session, creating one if needed."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str) -> Any:
        """Perform a GET request and return the parsed JSON body."""
        url = f"{self._base_url}{path}"
        _LOGGER.debug("GET %s", url)
        session = await self._ensure_session()
        try:
            async with session.get(url) as resp:
                _raise_for_status(resp, url)
                return await resp.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise CamillaDSPTimeoutError(f"Timeout on GET {url}") from err
        except aiohttp.ClientError as err:
            raise CamillaDSPConnectionError(
                f"Connection error on GET {url}: {err}"
            ) from err

    async def _get_text(self, path: str) -> str:
        """Perform a GET request and return the raw response text."""
        url = f"{self._base_url}{path}"
        _LOGGER.debug("GET (text) %s", url)
        session = await self._ensure_session()
        try:
            async with session.get(url) as resp:
                _raise_for_status(resp, url)
                return await resp.text()
        except asyncio.TimeoutError as err:
            raise CamillaDSPTimeoutError(f"Timeout on GET {url}") from err
        except aiohttp.ClientError as err:
            raise CamillaDSPConnectionError(
                f"Connection error on GET {url}: {err}"
            ) from err

    async def _post(self, path: str, data: Any) -> Any:
        """POST a JSON payload and return the parsed JSON response."""
        url = f"{self._base_url}{path}"
        _LOGGER.debug("POST %s", url)
        session = await self._ensure_session()
        try:
            async with session.post(url, json=data) as resp:
                _raise_for_status(resp, url)
                return await resp.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise CamillaDSPTimeoutError(f"Timeout on POST {url}") from err
        except aiohttp.ClientError as err:
            raise CamillaDSPConnectionError(
                f"Connection error on POST {url}: {err}"
            ) from err

    async def _post_text(self, path: str, data: str) -> str:
        """POST a plain-text payload and return the raw response text."""
        url = f"{self._base_url}{path}"
        _LOGGER.debug("POST (text) %s", url)
        session = await self._ensure_session()
        try:
            async with session.post(
                url,
                data=data,
                headers={"Content-Type": "text/plain"},
            ) as resp:
                _raise_for_status(resp, url)
                return await resp.text()
        except asyncio.TimeoutError as err:
            raise CamillaDSPTimeoutError(f"Timeout on POST {url}") from err
        except aiohttp.ClientError as err:
            raise CamillaDSPConnectionError(
                f"Connection error on POST {url}: {err}"
            ) from err

    # ------------------------------------------------------------------
    # Public endpoint methods
    # ------------------------------------------------------------------

    async def get_gui_config(self) -> GuiConfig:
        """Fetch GUI feature flags (``GET /api/guiconfig``)."""
        data = await self._get("/api/guiconfig")
        if not isinstance(data, dict):
            raise CamillaDSPPayloadError(
                f"Expected JSON object from /api/guiconfig, got {type(data).__name__}"
            )
        return _parse_gui_config(data)

    async def get_active_config_file(self) -> ActiveConfigFile:
        """Get the currently active config file (``GET /api/getactiveconfigfile``)."""
        data = await self._get("/api/getactiveconfigfile")
        if not isinstance(data, dict):
            raise CamillaDSPPayloadError(
                "Expected JSON object from /api/getactiveconfigfile, "
                f"got {type(data).__name__}"
            )
        try:
            return ActiveConfigFile(
                filename=data["configFileName"],
                config=data.get("config", {}),
            )
        except KeyError as err:
            raise CamillaDSPPayloadError(
                f"Missing key in /api/getactiveconfigfile response: {err}"
            ) from err

    async def get_config(self) -> dict[str, Any]:
        """Return the currently running config document (``GET /api/getconfig``)."""
        data = await self._get("/api/getconfig")
        if not isinstance(data, dict):
            raise CamillaDSPPayloadError(
                f"Expected JSON object from /api/getconfig, got {type(data).__name__}"
            )
        return data

    async def validate_config(self, config: dict[str, Any]) -> str:
        """Validate a config document (``POST /api/validateconfig``).

        Returns ``"OK"`` on success, or the backend error string otherwise.
        """
        url = f"{self._base_url}/api/validateconfig"
        _LOGGER.debug("POST %s", url)
        session = await self._ensure_session()
        try:
            async with session.post(url, json=config) as resp:
                # The backend returns 200 for both valid and invalid configs;
                # the body text distinguishes the two cases.
                _raise_for_status(resp, url)
                return (await resp.text()).strip()
        except asyncio.TimeoutError as err:
            raise CamillaDSPTimeoutError(f"Timeout on POST {url}") from err
        except aiohttp.ClientError as err:
            raise CamillaDSPConnectionError(
                f"Connection error on POST {url}: {err}"
            ) from err

    async def set_config(self, filename: str, config: dict[str, Any]) -> None:
        """Apply a config to the running DSP (``POST /api/setconfig``)."""
        await self._post("/api/setconfig", {"filename": filename, "config": config})

    async def save_config_file(self, filename: str, config: dict[str, Any]) -> None:
        """Persist a config to disk (``POST /api/saveconfigfile``)."""
        await self._post(
            "/api/saveconfigfile", {"filename": filename, "config": config}
        )

    async def get_stored_configs(self) -> list[StoredConfig]:
        """List stored config files (``GET /api/storedconfigs``)."""
        data = await self._get("/api/storedconfigs")
        if not isinstance(data, list):
            raise CamillaDSPPayloadError(
                f"Expected JSON array from /api/storedconfigs, got {type(data).__name__}"
            )
        return [
            StoredConfig(
                name=item.get("name", ""),
                last_modified=item.get("lastModified"),
            )
            for item in data
        ]

    async def set_active_config_file(self, name: str) -> None:
        """Switch the active config file (``POST /api/setactiveconfigfile``)."""
        await self._post("/api/setactiveconfigfile", {"name": name})

    async def get_status(self) -> RuntimeStatus:
        """Fetch runtime telemetry (``GET /api/status``)."""
        data = await self._get("/api/status")
        if not isinstance(data, dict):
            raise CamillaDSPPayloadError(
                f"Expected JSON object from /api/status, got {type(data).__name__}"
            )
        return _parse_runtime_status(data)

    async def get_volume(self) -> float:
        """Get the current global volume (``GET /api/getparam/volume``)."""
        text = await self._get_text("/api/getparam/volume")
        try:
            return float(text.strip())
        except (ValueError, TypeError) as err:
            raise CamillaDSPPayloadError(
                f"Cannot parse volume value: {text!r}"
            ) from err

    async def set_volume(self, value: float) -> None:
        """Set the global volume (``POST /api/setparam/volume``)."""
        await self._post_text("/api/setparam/volume", str(value))

    async def get_mute(self) -> bool:
        """Get the current mute state (``GET /api/getparam/mute``)."""
        text = await self._get_text("/api/getparam/mute")
        normalized = text.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
        raise CamillaDSPPayloadError(f"Cannot parse mute value: {text!r}")

    async def set_mute(self, value: bool) -> None:
        """Set the mute state (``POST /api/setparam/mute``)."""
        await self._post_text("/api/setparam/mute", "true" if value else "false")


# ------------------------------------------------------------------
# Module-private helpers
# ------------------------------------------------------------------


def _raise_for_status(resp: aiohttp.ClientResponse, url: str) -> None:
    """Raise :class:`CamillaDSPError` for non-2xx HTTP status codes."""
    if resp.status >= 400:
        raise CamillaDSPError(f"HTTP {resp.status} from {url}")


def _parse_gui_config(data: dict[str, Any]) -> GuiConfig:
    """Build a :class:`GuiConfig` from a raw JSON dict.

    Applies camelCase → snake_case mapping and safe defaults for any
    missing keys, so the integration keeps working against older backends.
    """
    return GuiConfig(
        hide_capture_samplerate=bool(data.get("hide_capture_samplerate", False)),
        hide_silence=bool(data.get("hide_silence", False)),
        hide_capture_device=bool(data.get("hide_capture_device", False)),
        hide_playback_device=bool(data.get("hide_playback_device", False)),
        apply_config_automatically=bool(data.get("apply_config_automatically", False)),
        save_config_automatically=bool(data.get("save_config_automatically", False)),
        status_update_interval=int(data.get("status_update_interval", 100)),
        can_update_active_config=bool(data.get("can_update_active_config", True)),
        coeff_dir=str(data.get("coeff_dir", "")),
        supported_capture_types=data.get("supported_capture_types"),
        supported_playback_types=data.get("supported_playback_types"),
    )


def _parse_runtime_status(data: dict[str, Any]) -> RuntimeStatus:
    """Build a :class:`RuntimeStatus` from a raw JSON dict.

    Safely extracts known fields and preserves the full payload in ``raw``
    so callers can access any fields not modelled explicitly.
    """
    return RuntimeStatus(
        state=str(data.get("state", "unknown")),
        capture_rate=int(data.get("captureRate", 0)),
        rate_adjust=float(data.get("rateAdjust", 0.0)),
        clipped_samples=int(data.get("clippedSamples", 0)),
        buffer_level=int(data.get("bufferLevel", 0)),
        processing_load=float(data.get("processingLoad", 0.0)),
        signal_range=float(data.get("signalRange", 0.0)),
        signal_rms=float(data.get("signalRms", 0.0)),
        capture_signal_peak=_float_list(data.get("captureSignalPeak")),
        capture_signal_rms=_float_list(data.get("captureSignalRms")),
        playback_signal_peak=_float_list(data.get("playbackSignalPeak")),
        playback_signal_rms=_float_list(data.get("playbackSignalRms")),
        raw=data,
    )


def _float_list(value: Any) -> list[float]:
    """Coerce *value* to a list of floats, returning ``[]`` for ``None``."""
    if value is None:
        return []
    if isinstance(value, list):
        return [float(v) for v in value]
    return []
