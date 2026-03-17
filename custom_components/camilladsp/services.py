"""CamillaDSP service handlers.

Registers HA services for config management operations:
- reload / validate / save the active config
- switch the active config file
- single and batch config value mutations
- add / remove config nodes (filters, mixers, processors, pipeline steps)

All handlers resolve the target coordinator via ``_get_coordinator``,
which supports both single-entry (no ``entry_id`` required) and
multi-entry (``entry_id`` required) setups.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api.errors import CamillaDSPError, CamillaDSPValidationError
from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CamillaDSPCoordinator

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service name constants
# ---------------------------------------------------------------------------

SERVICE_RELOAD_ACTIVE_CONFIG = "reload_active_config"
SERVICE_VALIDATE_ACTIVE_CONFIG = "validate_active_config"
SERVICE_SAVE_ACTIVE_CONFIG = "save_active_config"
SERVICE_SET_ACTIVE_CONFIG_FILE = "set_active_config_file"
SERVICE_SET_CONFIG_VALUE = "set_config_value"
SERVICE_BATCH_SET_CONFIG_VALUES = "batch_set_config_values"
SERVICE_ADD_CONFIG_NODE = "add_config_node"
SERVICE_REMOVE_CONFIG_NODE = "remove_config_node"

_ALL_SERVICES = [
    SERVICE_RELOAD_ACTIVE_CONFIG,
    SERVICE_VALIDATE_ACTIVE_CONFIG,
    SERVICE_SAVE_ACTIVE_CONFIG,
    SERVICE_SET_ACTIVE_CONFIG_FILE,
    SERVICE_SET_CONFIG_VALUE,
    SERVICE_BATCH_SET_CONFIG_VALUES,
    SERVICE_ADD_CONFIG_NODE,
    SERVICE_REMOVE_CONFIG_NODE,
]

# ---------------------------------------------------------------------------
# Voluptuous schemas
# ---------------------------------------------------------------------------

_ENTRY_ID_FIELD = {vol.Optional("entry_id"): cv.string}

SCHEMA_RELOAD_ACTIVE_CONFIG = vol.Schema({**_ENTRY_ID_FIELD})

SCHEMA_VALIDATE_ACTIVE_CONFIG = vol.Schema({**_ENTRY_ID_FIELD})

SCHEMA_SAVE_ACTIVE_CONFIG = vol.Schema({**_ENTRY_ID_FIELD})

SCHEMA_SET_ACTIVE_CONFIG_FILE = vol.Schema(
    {
        **_ENTRY_ID_FIELD,
        vol.Required("name"): cv.string,
    }
)

SCHEMA_SET_CONFIG_VALUE = vol.Schema(
    {
        **_ENTRY_ID_FIELD,
        vol.Required("path"): cv.string,
        vol.Required("value"): object,
        vol.Optional("save", default=True): cv.boolean,
    }
)

SCHEMA_BATCH_SET_CONFIG_VALUES = vol.Schema(
    {
        **_ENTRY_ID_FIELD,
        vol.Required("operations"): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required("path"): cv.string,
                        vol.Required("value"): object,
                    }
                )
            ],
        ),
        vol.Optional("save", default=True): cv.boolean,
    }
)

SCHEMA_ADD_CONFIG_NODE = vol.Schema(
    {
        **_ENTRY_ID_FIELD,
        vol.Required("section"): vol.In(
            ["filters", "mixers", "processors", "pipeline"]
        ),
        vol.Optional("name"): cv.string,
        vol.Required("data"): dict,
        vol.Optional("save", default=True): cv.boolean,
    }
)

SCHEMA_REMOVE_CONFIG_NODE = vol.Schema(
    {
        **_ENTRY_ID_FIELD,
        vol.Required("path"): cv.string,
        vol.Optional("save", default=True): cv.boolean,
    }
)


# ---------------------------------------------------------------------------
# Coordinator resolution
# ---------------------------------------------------------------------------


def _get_coordinator(hass: HomeAssistant, call: ServiceCall) -> CamillaDSPCoordinator:
    """Resolve the coordinator from a service call.

    If ``entry_id`` is provided in the service data, that specific entry is
    used.  Otherwise, if exactly one CamillaDSP entry exists it is used
    automatically.  An error is raised when the resolution is ambiguous.
    """
    entries: dict[str, dict[str, Any]] = hass.data.get(DOMAIN, {})
    entry_id: str | None = call.data.get("entry_id")

    if entry_id:
        entry_data = entries.get(entry_id)
        if not entry_data:
            raise ServiceValidationError(
                f"No CamillaDSP entry found with id '{entry_id}'",
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
            )
        return entry_data[DATA_COORDINATOR]

    if len(entries) == 0:
        raise ServiceValidationError(
            "No CamillaDSP entries configured",
            translation_domain=DOMAIN,
            translation_key="no_entries",
        )

    if len(entries) == 1:
        return next(iter(entries.values()))[DATA_COORDINATOR]

    raise ServiceValidationError(
        "Multiple CamillaDSP entries configured; specify entry_id",
        translation_domain=DOMAIN,
        translation_key="ambiguous_entry",
    )


# ---------------------------------------------------------------------------
# Normalizer helpers for add_config_node
# ---------------------------------------------------------------------------

# Filter types whose parameters.type field denotes a variant/sub-type.
_SUBTYPED_FILTER_TYPES = frozenset({"Biquad", "BiquadCombo", "Conv", "Dither"})


def _normalize_filter_node(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw user-supplied filter data into the normalized shape."""
    filter_type = raw.get("type", "Unknown")
    raw_params = copy.deepcopy(raw.get("parameters") or {})

    variant: str | None = None
    if filter_type in _SUBTYPED_FILTER_TYPES:
        variant = raw_params.get("type")

    _known_keys = frozenset({"type", "parameters", "description"})
    extra = {k: copy.deepcopy(v) for k, v in raw.items() if k not in _known_keys}

    return {
        "kind": "filter",
        "name": name,
        "filter_type": filter_type,
        "variant": variant,
        "description": raw.get("description"),
        "parameters": raw_params,
        "extra": extra,
    }


def _normalize_mixer_node(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw user-supplied mixer data into the normalized shape."""
    _known_keys = frozenset({"channels", "mapping", "description"})
    extra = {k: copy.deepcopy(v) for k, v in raw.items() if k not in _known_keys}

    return {
        "kind": "mixer",
        "name": name,
        "description": raw.get("description"),
        "channels": copy.deepcopy(raw.get("channels", {})),
        "mapping": copy.deepcopy(raw.get("mapping", [])),
        "extra": extra,
    }


def _normalize_processor_node(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw user-supplied processor data into the normalized shape."""
    _known_keys = frozenset({"type", "parameters", "description"})
    extra = {k: copy.deepcopy(v) for k, v in raw.items() if k not in _known_keys}

    return {
        "kind": "processor",
        "name": name,
        "processor_type": raw.get("type", "Unknown"),
        "parameters": copy.deepcopy(raw.get("parameters", {})),
        "extra": extra,
    }


def _normalize_pipeline_step(raw: dict[str, Any], index: int) -> dict[str, Any]:
    """Convert raw user-supplied pipeline step data into the normalized shape."""
    # Normalize singular "channel" to "channels" list.
    channels = raw.get("channels")
    if channels is None:
        raw_channel = raw.get("channel")
        if raw_channel is not None:
            channels = (
                [raw_channel] if not isinstance(raw_channel, list) else raw_channel
            )
    if channels is not None:
        channels = copy.deepcopy(channels)

    _known_keys = frozenset(
        {"type", "name", "channel", "channels", "names", "bypassed", "description"}
    )
    extra = {k: copy.deepcopy(v) for k, v in raw.items() if k not in _known_keys}

    return {
        "step_id": f"pipeline_{index}",
        "step_type": raw.get("type", "Filter"),
        "name": raw.get("name"),
        "channels": channels,
        "names": copy.deepcopy(raw.get("names", [])),
        "bypassed": raw.get("bypassed"),
        "description": raw.get("description"),
        "extra": extra,
    }


# ---------------------------------------------------------------------------
# Service handlers
# ---------------------------------------------------------------------------


async def _handle_reload_active_config(call: ServiceCall) -> None:
    """Re-fetch and re-normalize the active config from the backend."""
    coordinator = _get_coordinator(call.hass, call)
    try:
        await coordinator.async_reload_config()
    except CamillaDSPError as err:
        raise HomeAssistantError(f"Failed to reload config: {err}") from err


async def _handle_validate_active_config(call: ServiceCall) -> None:
    """Run backend validation on the currently cached config document."""
    coordinator = _get_coordinator(call.hass, call)

    if coordinator.config_doc is None:
        raise ServiceValidationError(
            "No config document loaded",
            translation_domain=DOMAIN,
            translation_key="no_config_loaded",
        )

    from .config.normalize import denormalize_config

    raw = denormalize_config(coordinator.config_doc)
    try:
        result = await coordinator.client.validate_config(raw)
    except CamillaDSPError as err:
        raise HomeAssistantError(f"Validation request failed: {err}") from err

    if result != "OK":
        raise HomeAssistantError(f"Config validation failed: {result}")

    _LOGGER.info("CamillaDSP config validation passed")


async def _handle_save_active_config(call: ServiceCall) -> None:
    """Explicitly save the current cached config document to disk."""
    coordinator = _get_coordinator(call.hass, call)
    try:
        await coordinator.async_save_config()
    except CamillaDSPError as err:
        raise HomeAssistantError(f"Failed to save config: {err}") from err


async def _handle_set_active_config_file(call: ServiceCall) -> None:
    """Switch the active config file and reload entities."""
    coordinator = _get_coordinator(call.hass, call)
    name: str = call.data["name"]
    try:
        await coordinator.async_switch_active_config(name)
    except CamillaDSPError as err:
        raise HomeAssistantError(f"Failed to switch config to '{name}': {err}") from err


async def _handle_set_config_value(call: ServiceCall) -> None:
    """Set a single value in the config document by path."""
    coordinator = _get_coordinator(call.hass, call)
    path: str = call.data["path"]
    value: Any = call.data["value"]
    save: bool = call.data.get("save", True)
    try:
        await coordinator.async_apply_value(path, value, save=save)
    except CamillaDSPValidationError as err:
        raise HomeAssistantError(
            f"Validation failed for '{path}': {err.details or err}"
        ) from err
    except (KeyError, IndexError) as err:
        raise ServiceValidationError(
            f"Invalid path '{path}': {err}",
            translation_domain=DOMAIN,
            translation_key="invalid_path",
        ) from err
    except CamillaDSPError as err:
        raise HomeAssistantError(
            f"Failed to set config value at '{path}': {err}"
        ) from err


async def _handle_batch_set_config_values(call: ServiceCall) -> None:
    """Apply multiple config value changes in a single transaction."""
    coordinator = _get_coordinator(call.hass, call)
    operations: list[dict[str, Any]] = call.data["operations"]
    save: bool = call.data.get("save", True)
    try:
        await coordinator.async_apply_batch(operations, save=save)
    except CamillaDSPValidationError as err:
        raise HomeAssistantError(
            f"Batch validation failed: {err.details or err}"
        ) from err
    except (KeyError, IndexError) as err:
        raise ServiceValidationError(
            f"Invalid path in batch operation: {err}",
            translation_domain=DOMAIN,
            translation_key="invalid_path",
        ) from err
    except CamillaDSPError as err:
        raise HomeAssistantError(f"Batch set failed: {err}") from err


async def _handle_add_config_node(call: ServiceCall) -> None:
    """Add a filter, mixer, processor, or pipeline step to the config."""
    coordinator = _get_coordinator(call.hass, call)
    section: str = call.data["section"]
    name: str | None = call.data.get("name")
    node_data: dict[str, Any] = call.data["data"]
    save: bool = call.data.get("save", True)

    if coordinator.config_doc is None:
        raise ServiceValidationError(
            "No config document loaded",
            translation_domain=DOMAIN,
            translation_key="no_config_loaded",
        )

    doc = copy.deepcopy(coordinator.config_doc)

    if section == "pipeline":
        pipeline = doc.get("pipeline", [])
        step = _normalize_pipeline_step(node_data, len(pipeline))
        pipeline.append(step)
        doc["pipeline"] = pipeline

    elif section in ("filters", "mixers", "processors"):
        if not name:
            raise ServiceValidationError(
                f"'name' is required when adding to '{section}'",
                translation_domain=DOMAIN,
                translation_key="name_required",
            )
        section_data: dict[str, Any] = doc.get(section, {})
        if name in section_data:
            raise ServiceValidationError(
                f"'{name}' already exists in {section}",
                translation_domain=DOMAIN,
                translation_key="node_already_exists",
            )
        # Normalize into the internal shape
        if section == "filters":
            section_data[name] = _normalize_filter_node(name, node_data)
        elif section == "mixers":
            section_data[name] = _normalize_mixer_node(name, node_data)
        else:  # processors
            section_data[name] = _normalize_processor_node(name, node_data)
        doc[section] = section_data
    else:
        # Should not happen due to vol.In validation, but be defensive.
        raise ServiceValidationError(
            f"Unknown section: {section}",
            translation_domain=DOMAIN,
            translation_key="unknown_section",
        )

    try:
        async with coordinator._write_lock:
            await coordinator._apply_config(doc, save)
            coordinator._config_doc = doc
        coordinator._rebuild_descriptors()
        coordinator.async_set_updated_data(coordinator._build_data_dict())
    except CamillaDSPValidationError as err:
        raise HomeAssistantError(
            f"Validation failed after adding node: {err.details or err}"
        ) from err
    except CamillaDSPError as err:
        raise HomeAssistantError(f"Failed to add config node: {err}") from err


async def _handle_remove_config_node(call: ServiceCall) -> None:
    """Remove a named node or pipeline step from the config."""
    coordinator = _get_coordinator(call.hass, call)
    path: str = call.data["path"]
    save: bool = call.data.get("save", True)

    if coordinator.config_doc is None:
        raise ServiceValidationError(
            "No config document loaded",
            translation_domain=DOMAIN,
            translation_key="no_config_loaded",
        )

    from .config.mutate import delete_value

    try:
        updated_doc = delete_value(coordinator.config_doc, path)
    except (KeyError, IndexError, ValueError) as err:
        raise ServiceValidationError(
            f"Cannot remove '{path}': {err}",
            translation_domain=DOMAIN,
            translation_key="invalid_path",
        ) from err

    # Re-index pipeline step_ids if a pipeline step was removed
    if path.startswith("pipeline"):
        pipeline = updated_doc.get("pipeline", [])
        for i, step in enumerate(pipeline):
            if isinstance(step, dict):
                step["step_id"] = f"pipeline_{i}"

    try:
        async with coordinator._write_lock:
            await coordinator._apply_config(updated_doc, save)
            coordinator._config_doc = updated_doc
        coordinator._rebuild_descriptors()
        coordinator.async_set_updated_data(coordinator._build_data_dict())
    except CamillaDSPValidationError as err:
        raise HomeAssistantError(
            f"Validation failed after removing node: {err.details or err}"
        ) from err
    except CamillaDSPError as err:
        raise HomeAssistantError(
            f"Failed to remove config node at '{path}': {err}"
        ) from err


# ---------------------------------------------------------------------------
# Registration / teardown
# ---------------------------------------------------------------------------


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register all CamillaDSP services.

    Called during ``async_setup_entry`` for the **first** config entry.
    Subsequent entries reuse the already-registered services.
    """
    # Guard: only register once even if called for multiple entries.
    if hass.services.has_service(DOMAIN, SERVICE_RELOAD_ACTIVE_CONFIG):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_RELOAD_ACTIVE_CONFIG,
        _handle_reload_active_config,
        schema=SCHEMA_RELOAD_ACTIVE_CONFIG,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_VALIDATE_ACTIVE_CONFIG,
        _handle_validate_active_config,
        schema=SCHEMA_VALIDATE_ACTIVE_CONFIG,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_ACTIVE_CONFIG,
        _handle_save_active_config,
        schema=SCHEMA_SAVE_ACTIVE_CONFIG,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_CONFIG_FILE,
        _handle_set_active_config_file,
        schema=SCHEMA_SET_ACTIVE_CONFIG_FILE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONFIG_VALUE,
        _handle_set_config_value,
        schema=SCHEMA_SET_CONFIG_VALUE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BATCH_SET_CONFIG_VALUES,
        _handle_batch_set_config_values,
        schema=SCHEMA_BATCH_SET_CONFIG_VALUES,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_CONFIG_NODE,
        _handle_add_config_node,
        schema=SCHEMA_ADD_CONFIG_NODE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_CONFIG_NODE,
        _handle_remove_config_node,
        schema=SCHEMA_REMOVE_CONFIG_NODE,
    )

    _LOGGER.debug("Registered %d CamillaDSP services", len(_ALL_SERVICES))


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload CamillaDSP services when the last entry is removed."""
    for service_name in _ALL_SERVICES:
        hass.services.async_remove(DOMAIN, service_name)

    _LOGGER.debug("Unloaded CamillaDSP services")
