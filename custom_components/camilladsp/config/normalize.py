"""Normalize and denormalize CamillaDSP config documents.

:func:`normalize_config` converts a raw backend config dict into the
canonical :class:`~.schema.NormalizedConfig` shape used internally.

:func:`denormalize_config` converts it back to the backend format for
sending via the API.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Top-level keys that have dedicated handling and are NOT sent to ``extra``.
_KNOWN_TOP_KEYS = frozenset(
    {"devices", "filters", "mixers", "processors", "pipeline", "title", "description"}
)

# Filter types whose ``parameters.type`` field denotes a variant/sub-type.
_SUBTYPED_FILTER_TYPES = frozenset({"Biquad", "BiquadCombo", "Conv", "Dither"})

# Known keys *inside* a raw filter entry (anything else → ``extra``).
_KNOWN_FILTER_KEYS = frozenset({"type", "parameters", "description"})

# Known keys inside a raw mixer entry.
_KNOWN_MIXER_KEYS = frozenset({"channels", "mapping", "description"})

# Known keys inside a raw processor entry.
_KNOWN_PROCESSOR_KEYS = frozenset({"type", "parameters", "description"})

# Known keys inside a raw pipeline step.
_KNOWN_PIPELINE_KEYS = frozenset(
    {"type", "name", "channel", "channels", "names", "bypassed", "description"}
)


# ------------------------------------------------------------------
# normalize_config
# ------------------------------------------------------------------


def normalize_config(raw: dict[str, Any], filename: str = "") -> dict[str, Any]:
    """Transform a raw backend config into the normalized internal shape.

    Parameters
    ----------
    raw:
        The config dict as returned by the CamillaDSP backend (YAML-parsed
        JSON).
    filename:
        Optional filename to record in the ``meta`` section.

    Returns
    -------
    dict
        A dict conforming to the :class:`~.schema.NormalizedConfig` shape.
    """
    doc: dict[str, Any] = {}

    # -- meta ----------------------------------------------------------
    doc["meta"] = {
        "filename": filename,
        "title": raw.get("title"),
        "description": raw.get("description"),
    }

    # -- devices (pass-through) ----------------------------------------
    doc["devices"] = copy.deepcopy(raw.get("devices", {}))

    # -- filters -------------------------------------------------------
    doc["filters"] = _normalize_filters(raw.get("filters") or {})

    # -- mixers --------------------------------------------------------
    doc["mixers"] = _normalize_mixers(raw.get("mixers") or {})

    # -- processors ----------------------------------------------------
    doc["processors"] = _normalize_processors(raw.get("processors") or {})

    # -- pipeline ------------------------------------------------------
    doc["pipeline"] = _normalize_pipeline(raw.get("pipeline") or [])

    # -- extra (unknown top-level keys) --------------------------------
    doc["extra"] = {
        k: copy.deepcopy(v) for k, v in raw.items() if k not in _KNOWN_TOP_KEYS
    }

    return doc


# ------------------------------------------------------------------
# Section normalizers
# ------------------------------------------------------------------


def _normalize_filters(
    raw_filters: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Normalize the ``filters`` section."""
    result: dict[str, dict[str, Any]] = {}
    for name, entry in raw_filters.items():
        if not isinstance(entry, dict):
            _LOGGER.warning("Skipping non-dict filter entry %r", name)
            continue

        filter_type = entry.get("type", "Unknown")
        raw_params = copy.deepcopy(entry.get("parameters") or {})

        # Determine variant for subtyped filters.
        variant: str | None = None
        if filter_type in _SUBTYPED_FILTER_TYPES:
            variant = raw_params.get("type")
            # Keep parameters.type in place for round-trip safety.

        # Collect extra (unknown) keys.
        extra = {
            k: copy.deepcopy(v) for k, v in entry.items() if k not in _KNOWN_FILTER_KEYS
        }

        result[name] = {
            "kind": "filter",
            "name": name,
            "filter_type": filter_type,
            "variant": variant,
            "description": entry.get("description"),
            "parameters": raw_params,
            "extra": extra,
        }
    return result


def _normalize_mixers(
    raw_mixers: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Normalize the ``mixers`` section."""
    result: dict[str, dict[str, Any]] = {}
    for name, entry in raw_mixers.items():
        if not isinstance(entry, dict):
            _LOGGER.warning("Skipping non-dict mixer entry %r", name)
            continue

        extra = {
            k: copy.deepcopy(v) for k, v in entry.items() if k not in _KNOWN_MIXER_KEYS
        }

        result[name] = {
            "kind": "mixer",
            "name": name,
            "description": entry.get("description"),
            "channels": copy.deepcopy(entry.get("channels", {})),
            "mapping": copy.deepcopy(entry.get("mapping", [])),
            "extra": extra,
        }
    return result


def _normalize_processors(
    raw_processors: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Normalize the ``processors`` section."""
    result: dict[str, dict[str, Any]] = {}
    for name, entry in raw_processors.items():
        if not isinstance(entry, dict):
            _LOGGER.warning("Skipping non-dict processor entry %r", name)
            continue

        extra = {
            k: copy.deepcopy(v)
            for k, v in entry.items()
            if k not in _KNOWN_PROCESSOR_KEYS
        }

        result[name] = {
            "kind": "processor",
            "name": name,
            "processor_type": entry.get("type", "Unknown"),
            "parameters": copy.deepcopy(entry.get("parameters", {})),
            "extra": extra,
        }
    return result


def _normalize_pipeline(
    raw_pipeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize the ``pipeline`` section."""
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_pipeline):
        if not isinstance(entry, dict):
            _LOGGER.warning("Skipping non-dict pipeline entry at index %d", index)
            continue

        # Normalize singular "channel" to list "channels".
        channels = entry.get("channels")
        if channels is None:
            raw_channel = entry.get("channel")
            if raw_channel is not None:
                channels = (
                    [raw_channel] if not isinstance(raw_channel, list) else raw_channel
                )
        if channels is not None:
            channels = copy.deepcopy(channels)

        extra_keys = {k for k in entry if k not in _KNOWN_PIPELINE_KEYS}
        extra = {k: copy.deepcopy(entry[k]) for k in extra_keys}

        result.append(
            {
                "step_id": f"pipeline_{index}",
                "step_type": entry.get("type", "Unknown"),
                "name": entry.get("name"),
                "channels": channels,
                "names": copy.deepcopy(entry.get("names", [])),
                "bypassed": entry.get("bypassed"),
                "description": entry.get("description"),
                "extra": extra,
            }
        )
    return result


# ------------------------------------------------------------------
# denormalize_config
# ------------------------------------------------------------------


def denormalize_config(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a normalized document back to the backend config format.

    This is the inverse of :func:`normalize_config`.  Internal fields
    (``kind``, ``step_id``, ``extra``, etc.) are stripped and the result
    is suitable for sending to ``CamillaDSPClient.set_config`` /
    ``validate_config``.
    """
    result: dict[str, Any] = {}

    meta = doc.get("meta", {})
    if meta.get("title") is not None:
        result["title"] = meta["title"]
    if meta.get("description") is not None:
        result["description"] = meta["description"]

    # -- devices (pass-through) ----------------------------------------
    if doc.get("devices"):
        result["devices"] = copy.deepcopy(doc["devices"])

    # -- filters -------------------------------------------------------
    raw_filters = _denormalize_filters(doc.get("filters", {}))
    if raw_filters:
        result["filters"] = raw_filters

    # -- mixers --------------------------------------------------------
    raw_mixers = _denormalize_mixers(doc.get("mixers", {}))
    if raw_mixers:
        result["mixers"] = raw_mixers

    # -- processors ----------------------------------------------------
    raw_processors = _denormalize_processors(doc.get("processors", {}))
    if raw_processors:
        result["processors"] = raw_processors

    # -- pipeline ------------------------------------------------------
    raw_pipeline = _denormalize_pipeline(doc.get("pipeline", []))
    if raw_pipeline:
        result["pipeline"] = raw_pipeline

    # -- merge document-level extra back in ----------------------------
    for k, v in doc.get("extra", {}).items():
        result[k] = copy.deepcopy(v)

    return result


# ------------------------------------------------------------------
# Section denormalizers
# ------------------------------------------------------------------


def _denormalize_filters(
    filters: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Denormalize filters back to raw format."""
    result: dict[str, dict[str, Any]] = {}
    for name, node in filters.items():
        raw_entry: dict[str, Any] = {"type": node["filter_type"]}

        params = copy.deepcopy(node.get("parameters", {}))

        # For subtyped filters, ensure parameters.type reflects the variant.
        if (
            node["filter_type"] in _SUBTYPED_FILTER_TYPES
            and node.get("variant") is not None
        ):
            params["type"] = node["variant"]

        if params:
            raw_entry["parameters"] = params

        if node.get("description") is not None:
            raw_entry["description"] = node["description"]

        # Merge extra keys back.
        for k, v in node.get("extra", {}).items():
            raw_entry[k] = copy.deepcopy(v)

        result[name] = raw_entry
    return result


def _denormalize_mixers(
    mixers: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Denormalize mixers back to raw format."""
    result: dict[str, dict[str, Any]] = {}
    for name, node in mixers.items():
        raw_entry: dict[str, Any] = {}

        if node.get("channels"):
            raw_entry["channels"] = copy.deepcopy(node["channels"])
        if node.get("mapping") is not None:
            raw_entry["mapping"] = copy.deepcopy(node["mapping"])
        if node.get("description") is not None:
            raw_entry["description"] = node["description"]

        for k, v in node.get("extra", {}).items():
            raw_entry[k] = copy.deepcopy(v)

        result[name] = raw_entry
    return result


def _denormalize_processors(
    processors: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Denormalize processors back to raw format."""
    result: dict[str, dict[str, Any]] = {}
    for name, node in processors.items():
        raw_entry: dict[str, Any] = {"type": node["processor_type"]}

        if node.get("parameters"):
            raw_entry["parameters"] = copy.deepcopy(node["parameters"])
        if node.get("description") is not None:
            raw_entry["description"] = node["description"]

        for k, v in node.get("extra", {}).items():
            raw_entry[k] = copy.deepcopy(v)

        result[name] = raw_entry
    return result


def _denormalize_pipeline(
    pipeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Denormalize pipeline steps back to raw format."""
    result: list[dict[str, Any]] = []
    for step in pipeline:
        raw_step: dict[str, Any] = {"type": step["step_type"]}

        if step.get("name") is not None:
            raw_step["name"] = step["name"]
        if step.get("channels") is not None:
            raw_step["channels"] = copy.deepcopy(step["channels"])
        if step.get("names"):
            raw_step["names"] = copy.deepcopy(step["names"])
        if step.get("bypassed") is not None:
            raw_step["bypassed"] = step["bypassed"]
        if step.get("description") is not None:
            raw_step["description"] = step["description"]

        for k, v in step.get("extra", {}).items():
            raw_step[k] = copy.deepcopy(v)

        result.append(raw_step)
    return result
