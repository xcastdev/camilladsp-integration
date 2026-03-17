"""Shared utilities for the entity descriptor framework."""

from __future__ import annotations

import re
from typing import Any

_SANITIZE_RE = re.compile(r"[^a-z0-9]+")
_TOKEN_PATTERN = re.compile(r"\$\w+\$")


def sanitize_id(name: str) -> str:
    """Sanitize a name for use in unique IDs.

    Lowercases the input and replaces any run of non-alphanumeric characters
    with a single underscore.  Leading/trailing underscores are stripped.

    >>> sanitize_id("Bass Control (PEQ #1)")
    'bass_control_peq_1'
    """
    return _SANITIZE_RE.sub("_", name.lower()).strip("_")


def is_tokenized(value: Any) -> bool:
    """Check if a value contains CamillaDSP token patterns like ``$samplerate$``.

    Token patterns use the form ``$name$`` and indicate that the parameter
    is dynamically resolved by the DSP engine at runtime and should not be
    editable from the HA UI.

    >>> is_tokenized("$samplerate$")
    True
    >>> is_tokenized(48000)
    False
    >>> is_tokenized("some $token$ in text")
    True
    """
    if isinstance(value, str):
        return bool(_TOKEN_PATTERN.search(value))
    return False


_PATH_SPLIT_RE = re.compile(r"\.|\[|\]")


def resolve_config_value(config_doc: dict[str, Any], path: str) -> Any:
    """Resolve a dot/bracket config path to its current value.

    Supports paths like ``filters.MyFilter.parameters.freq`` or
    ``mixers.Main.mapping[0].sources[1].gain``.

    Returns ``None`` if the path cannot be resolved.

    >>> resolve_config_value({"a": {"b": [10, 20]}}, "a.b[1]")
    20
    """
    parts = [p for p in _PATH_SPLIT_RE.split(path) if p]

    current: Any = config_doc
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


# ------------------------------------------------------------------
# Volume dB ↔ percent helpers
# ------------------------------------------------------------------
# 0 % ≙ -51 dB (silence),  100 % ≙ 0 dB (unity gain).

_VOLUME_DB_MIN: float = -51.0
_VOLUME_DB_MAX: float = 0.0
_VOLUME_DB_RANGE: float = _VOLUME_DB_MAX - _VOLUME_DB_MIN  # 51.0


def db_to_percent(db: float) -> float:
    """Convert a dB value (-51 … 0) to a slider percentage (0 … 100).

    Values outside the -51 … 0 range are clamped.

    >>> db_to_percent(-51.0)
    0.0
    >>> db_to_percent(0.0)
    100.0
    >>> db_to_percent(-25.5)
    50.0
    """
    clamped = max(_VOLUME_DB_MIN, min(_VOLUME_DB_MAX, db))
    return round(((clamped - _VOLUME_DB_MIN) / _VOLUME_DB_RANGE) * 100.0, 1)


def percent_to_db(percent: float) -> float:
    """Convert a slider percentage (0 … 100) to a dB value (-51 … 0).

    Values outside the 0 … 100 range are clamped.

    >>> percent_to_db(0.0)
    -51.0
    >>> percent_to_db(100.0)
    0.0
    >>> percent_to_db(50.0)
    -25.5
    """
    clamped = max(0.0, min(100.0, percent))
    return _VOLUME_DB_MIN + (clamped / 100.0) * _VOLUME_DB_RANGE
