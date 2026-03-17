"""DataUpdateCoordinator for CamillaDSP runtime state and config management.

The coordinator is the central hub between:
- The async HTTP client (:mod:`.api.client`)
- The normalized config document model (:mod:`.config.schema`)
- The entity descriptor pipeline (:mod:`.entities.builder`)

It owns the polling loop, the write-lock for config mutations, and the
debounce timers for slider-style controls.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api.client import CamillaDSPClient
from .api.errors import (
    CamillaDSPConnectionError,
    CamillaDSPError,
    CamillaDSPValidationError,
)
from .api.models import GuiConfig, RuntimeStatus, StoredConfig
from .const import DEBOUNCE_DELAY, DOMAIN, UPDATE_INTERVAL
from .entities.builder import build_descriptors, diff_descriptors
from .entities.descriptors import EntityDescriptor

_LOGGER = logging.getLogger(__name__)


class CamillaDSPCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for CamillaDSP runtime state and config management.

    Responsibilities:
    - Polls runtime status, volume, and mute on UPDATE_INTERVAL.
    - Detects external config-file switches and reloads accordingly.
    - Provides write methods that serialise through a single asyncio lock.
    - Manages debounced writes for high-frequency UI controls (sliders).
    - Rebuilds entity descriptors when the config shape changes and
      notifies listeners so platforms can add/remove entities.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: CamillaDSPClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"CamillaDSP ({entry.data.get('base_url', 'unknown')})",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.client = client
        self.entry = entry

        # ---- Config state ----
        self._config_doc: dict[str, Any] | None = None
        self._active_filename: str | None = None
        self._stored_configs: list[StoredConfig] = []
        self._gui_config: GuiConfig | None = None

        # ---- Runtime state ----
        self._status: RuntimeStatus | None = None
        self._volume: float | None = None
        self._mute: bool | None = None

        # ---- Write coordination ----
        self._write_lock = asyncio.Lock()
        self._debounce_timers: dict[str, asyncio.TimerHandle] = {}

        # ---- Descriptor state ----
        self._descriptors: list[EntityDescriptor] = []
        self._descriptor_listeners: list[
            Callable[
                [
                    list[EntityDescriptor],
                    list[EntityDescriptor],
                    list[EntityDescriptor],
                ],
                None,
            ]
        ] = []

    # ------------------------------------------------------------------
    # Public read-only properties
    # ------------------------------------------------------------------

    @property
    def config_doc(self) -> dict[str, Any] | None:
        """The current normalized config document, or None if not loaded."""
        return self._config_doc

    @property
    def active_filename(self) -> str | None:
        """The name of the currently active config file."""
        return self._active_filename

    @property
    def stored_configs(self) -> list[StoredConfig]:
        """Available stored config files on the backend."""
        return self._stored_configs

    @property
    def gui_config(self) -> GuiConfig | None:
        """GUI feature flags and capabilities."""
        return self._gui_config

    @property
    def status(self) -> RuntimeStatus | None:
        """Current runtime telemetry snapshot."""
        return self._status

    @property
    def volume(self) -> float | None:
        """Current global volume (dB)."""
        return self._volume

    @property
    def mute(self) -> bool | None:
        """Current global mute state."""
        return self._mute

    @property
    def descriptors(self) -> list[EntityDescriptor]:
        """Current entity descriptors derived from the config document."""
        return list(self._descriptors)

    # ------------------------------------------------------------------
    # Initial setup
    # ------------------------------------------------------------------

    async def async_initial_setup(self) -> None:
        """Perform the initial data fetch after coordinator creation.

        This method should be called once during ``async_setup_entry``,
        *before* the first ``async_config_entry_first_refresh``.

        It fetches:
        - GUI config
        - Active config file (name + raw config body)
        - Stored configs
        - Runtime status
        - Volume and mute

        Then normalizes the active config into the internal document model
        and builds the initial set of entity descriptors.

        Raises :class:`UpdateFailed` if the backend is unreachable.
        """
        try:
            # Parallel fetch for independent resources
            gui_config_task = self.client.get_gui_config()
            active_file_task = self.client.get_active_config_file()
            stored_task = self.client.get_stored_configs()
            status_task = self.client.get_status()
            volume_task = self.client.get_volume()
            mute_task = self.client.get_mute()

            results = await asyncio.gather(
                gui_config_task,
                active_file_task,
                stored_task,
                status_task,
                volume_task,
                mute_task,
                return_exceptions=True,
            )

            gui_config, active_file, stored, status, volume, mute = results

            # Raise the first fatal exception (connection errors are fatal)
            for result in results:
                if isinstance(result, CamillaDSPConnectionError):
                    raise result

            # Apply results that succeeded
            if isinstance(gui_config, GuiConfig):
                self._gui_config = gui_config

            if not isinstance(active_file, BaseException):
                self._active_filename = active_file.filename
                self._config_doc = self._normalize_config(
                    active_file.config, active_file.filename
                )

            if isinstance(stored, list):
                self._stored_configs = stored

            if isinstance(status, RuntimeStatus):
                self._status = status

            if isinstance(volume, float):
                self._volume = volume

            if isinstance(mute, bool):
                self._mute = mute

        except CamillaDSPConnectionError as err:
            raise UpdateFailed(f"Cannot connect to CamillaDSP: {err}") from err
        except CamillaDSPError as err:
            _LOGGER.warning("Non-fatal error during initial setup: %s", err)

        # Build initial descriptors from whatever config we have
        self._rebuild_descriptors()

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll runtime status and check for external config changes.

        Runs on every ``UPDATE_INTERVAL``:
        1. Fetch runtime status, volume, and mute.
        2. Check if the active filename changed externally.
        3. If changed, reload config and rebuild descriptors.
        4. Return combined state dict for entity consumption.
        """
        try:
            # Parallel fetch for runtime values
            status_task = self.client.get_status()
            volume_task = self.client.get_volume()
            mute_task = self.client.get_mute()
            active_file_task = self.client.get_active_config_file()

            results = await asyncio.gather(
                status_task,
                volume_task,
                mute_task,
                active_file_task,
                return_exceptions=True,
            )

            status, volume, mute, active_file = results

            # Update status
            if isinstance(status, RuntimeStatus):
                self._status = status
            elif isinstance(status, CamillaDSPConnectionError):
                raise status

            # Update volume
            if isinstance(volume, (int, float)):
                self._volume = float(volume)
            elif isinstance(volume, CamillaDSPConnectionError):
                raise volume

            # Update mute
            if isinstance(mute, bool):
                self._mute = mute
            elif isinstance(mute, CamillaDSPConnectionError):
                raise mute

            # Detect external config file switch
            if not isinstance(active_file, BaseException):
                new_filename = active_file.filename
                if new_filename != self._active_filename:
                    _LOGGER.info(
                        "Active config changed externally: %s → %s",
                        self._active_filename,
                        new_filename,
                    )
                    self._active_filename = new_filename
                    self._config_doc = self._normalize_config(
                        active_file.config, new_filename
                    )
                    # Also refresh stored configs on config change
                    try:
                        self._stored_configs = await self.client.get_stored_configs()
                    except CamillaDSPError as err:
                        _LOGGER.warning("Failed to refresh stored configs: %s", err)
                    self._rebuild_descriptors()
            elif isinstance(active_file, CamillaDSPConnectionError):
                raise active_file

        except CamillaDSPConnectionError as err:
            raise UpdateFailed(f"Cannot connect to CamillaDSP: {err}") from err
        except CamillaDSPError as err:
            _LOGGER.warning("Error during status poll: %s", err)

        return {
            "status": self._status,
            "volume": self._volume,
            "mute": self._mute,
            "active_filename": self._active_filename,
            "config_doc": self._config_doc,
            "stored_configs": self._stored_configs,
        }

    # ------------------------------------------------------------------
    # Config load / reload
    # ------------------------------------------------------------------

    async def async_load_config(self) -> None:
        """Load / reload the active config from the backend and rebuild descriptors."""
        try:
            active_file = await self.client.get_active_config_file()
            self._active_filename = active_file.filename
            self._config_doc = self._normalize_config(
                active_file.config, active_file.filename
            )
            self._stored_configs = await self.client.get_stored_configs()
        except CamillaDSPError as err:
            _LOGGER.error("Failed to load config: %s", err)
            raise

        self._rebuild_descriptors()
        self.async_set_updated_data(self._build_data_dict())

    async def async_reload_config(self) -> None:
        """Force reload from the backend (public alias with logging)."""
        _LOGGER.info("Force-reloading CamillaDSP config")
        await self.async_load_config()

    # ------------------------------------------------------------------
    # Write pipeline
    # ------------------------------------------------------------------

    async def async_apply_value(
        self,
        path: str,
        value: Any,
        save: bool = True,
    ) -> None:
        """Apply a single value mutation through the write pipeline.

        Acquires the write lock, mutates the cached config doc, validates
        and applies the change to the backend.  On success, updates the
        local cache and pushes an update to entities.

        Parameters
        ----------
        path:
            Dot/bracket notation path in the normalized config doc.
        value:
            The new value to set.
        save:
            Whether to persist the change to disk after applying.
        """
        async with self._write_lock:
            if self._config_doc is None:
                raise CamillaDSPError("No config document loaded")
            if self._active_filename is None:
                raise CamillaDSPError("No active config file")

            # Mutate the local copy
            from .config.mutate import set_value

            updated_doc = set_value(self._config_doc, path, value)

            # Denormalize and apply
            await self._apply_config(updated_doc, save)

            # Commit the local mutation
            self._config_doc = updated_doc

        self.async_set_updated_data(self._build_data_dict())

    async def async_apply_batch(
        self,
        operations: list[dict[str, Any]],
        save: bool = True,
    ) -> None:
        """Apply multiple mutations atomically.

        Parameters
        ----------
        operations:
            List of ``{"path": str, "value": Any}`` dicts.
        save:
            Whether to persist the change to disk after applying.
        """
        async with self._write_lock:
            if self._config_doc is None:
                raise CamillaDSPError("No config document loaded")
            if self._active_filename is None:
                raise CamillaDSPError("No active config file")

            from .config.mutate import batch_set_values

            updated_doc = batch_set_values(self._config_doc, operations)

            await self._apply_config(updated_doc, save)
            self._config_doc = updated_doc

        self.async_set_updated_data(self._build_data_dict())

    async def _apply_config(
        self,
        doc: dict[str, Any],
        save: bool,
    ) -> None:
        """Denormalize, validate, and push a config to the backend.

        Must be called while holding ``_write_lock``.
        """
        from .config.normalize import denormalize_config

        raw_config = denormalize_config(doc)

        # Validate first
        result = await self.client.validate_config(raw_config)
        if result != "OK":
            raise CamillaDSPValidationError("Config validation failed", details=result)

        # Apply to running DSP
        assert self._active_filename is not None
        await self.client.set_config(self._active_filename, raw_config)

        # Optionally persist to disk
        if save:
            await self.client.save_config_file(self._active_filename, raw_config)

    # ------------------------------------------------------------------
    # Debounced writes (for sliders / high-frequency controls)
    # ------------------------------------------------------------------

    @callback
    def schedule_debounced_update(
        self,
        path: str,
        value: Any,
        save: bool = True,
    ) -> None:
        """Schedule a debounced value update for slider-style controls.

        Cancels any pending timer for the same path and schedules a new
        one after ``DEBOUNCE_DELAY`` seconds.  This avoids flooding the
        backend with writes while a user is dragging a slider.
        """
        # Cancel existing timer for this path
        existing = self._debounce_timers.pop(path, None)
        if existing is not None:
            existing.cancel()

        # Schedule new timer
        handle = self.hass.loop.call_later(
            DEBOUNCE_DELAY,
            lambda: self.hass.async_create_task(
                self._debounced_apply(path, value, save),
                f"camilladsp_debounce_{path}",
            ),
        )
        self._debounce_timers[path] = handle

    async def _debounced_apply(
        self,
        path: str,
        value: Any,
        save: bool,
    ) -> None:
        """Execute a debounced write. Called after the debounce delay."""
        self._debounce_timers.pop(path, None)
        try:
            await self.async_apply_value(path, value, save)
        except CamillaDSPError as err:
            _LOGGER.warning("Debounced write failed for %s: %s", path, err)

    # ------------------------------------------------------------------
    # Fast-path API shortcuts
    # ------------------------------------------------------------------

    async def async_set_volume(self, value: float) -> None:
        """Set volume via the fast-path API (no config doc mutation)."""
        await self.client.set_volume(value)
        self._volume = value
        self.async_set_updated_data(self._build_data_dict())

    async def async_set_mute(self, value: bool) -> None:
        """Set mute via the fast-path API (no config doc mutation)."""
        await self.client.set_mute(value)
        self._mute = value
        self.async_set_updated_data(self._build_data_dict())

    # ------------------------------------------------------------------
    # Config file management
    # ------------------------------------------------------------------

    async def async_switch_active_config(self, name: str) -> None:
        """Switch the active config file and reload everything."""
        await self.client.set_active_config_file(name)
        _LOGGER.info("Switched active config to %s", name)
        await self.async_load_config()

    async def async_save_config(self) -> None:
        """Explicitly save the current cached config to disk."""
        if self._config_doc is None or self._active_filename is None:
            raise CamillaDSPError("No config document to save")

        from .config.normalize import denormalize_config

        raw_config = denormalize_config(self._config_doc)
        await self.client.save_config_file(self._active_filename, raw_config)
        _LOGGER.info("Config saved to %s", self._active_filename)

    # ------------------------------------------------------------------
    # Descriptor management
    # ------------------------------------------------------------------

    def _rebuild_descriptors(self) -> None:
        """Rebuild entity descriptors from the current config doc.

        Compares with the previous descriptor set and notifies registered
        listeners of additions, removals, and unchanged descriptors.
        """
        old_descriptors = self._descriptors

        if self._config_doc is not None:
            new_descriptors = build_descriptors(
                config_doc=self._config_doc,
                entry_id=self.entry.entry_id,
                stored_configs=self._stored_configs,
                status=self._status,
            )
        else:
            new_descriptors = build_descriptors(
                config_doc={},
                entry_id=self.entry.entry_id,
                stored_configs=self._stored_configs,
                status=self._status,
            )

        self._descriptors = new_descriptors

        # Compute diff and notify listeners
        added, removed, unchanged = diff_descriptors(old_descriptors, new_descriptors)

        if added or removed:
            _LOGGER.debug(
                "Descriptor rebuild: %d added, %d removed, %d unchanged",
                len(added),
                len(removed),
                len(unchanged),
            )

        for listener in self._descriptor_listeners:
            try:
                listener(added, removed, unchanged)
            except Exception:
                _LOGGER.exception("Error in descriptor listener")

    @callback
    def register_descriptor_listener(
        self,
        callback_fn: Callable[
            [list[EntityDescriptor], list[EntityDescriptor], list[EntityDescriptor]],
            None,
        ],
    ) -> Callable[[], None]:
        """Register a callback for descriptor changes.

        The callback receives ``(added, removed, unchanged)`` descriptor
        lists.

        Returns a function that unsubscribes the listener when called.
        """
        self._descriptor_listeners.append(callback_fn)

        @callback
        def _unsubscribe() -> None:
            try:
                self._descriptor_listeners.remove(callback_fn)
            except ValueError:
                pass  # already removed

        return _unsubscribe

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_config(
        raw: dict[str, Any],
        filename: str,
    ) -> dict[str, Any]:
        """Normalize a raw backend config into the internal document model.

        Delegates to :func:`.config.normalize.normalize_config`.  If the
        normalizer module is not yet available (Phase 2 dependency), falls
        back to passing through the raw config with a meta section added.
        """
        try:
            from .config.normalize import normalize_config

            return normalize_config(raw, filename)
        except ImportError:
            _LOGGER.debug(
                "config.normalize not available; using raw config passthrough"
            )
            # Minimal passthrough that satisfies the builder's expectations
            doc: dict[str, Any] = dict(raw)
            doc.setdefault("meta", {"filename": filename})
            return doc

    def _build_data_dict(self) -> dict[str, Any]:
        """Build the data dict returned to entities via ``self.data``."""
        return {
            "status": self._status,
            "volume": self._volume,
            "mute": self._mute,
            "active_filename": self._active_filename,
            "config_doc": self._config_doc,
            "stored_configs": self._stored_configs,
        }
