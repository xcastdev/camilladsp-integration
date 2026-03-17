"""Local validation and backend validation orchestration.

Local validators return :class:`ValidationError` data objects (not
exceptions) so callers can accumulate multiple issues before presenting
them.  The :func:`validate_and_apply` coroutine coordinates the full
denormalize → validate → set → save pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from custom_components.camilladsp.api.client import CamillaDSPClient
from custom_components.camilladsp.api.errors import CamillaDSPValidationError

from .normalize import denormalize_config
from .paths import path_exists

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Validation error (data object, not an exception)
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationError:
    """A single validation finding tied to a config path."""

    path: str
    message: str

    def __str__(self) -> str:
        if self.path:
            return f"{self.path}: {self.message}"
        return self.message


# ------------------------------------------------------------------
# Local validators
# ------------------------------------------------------------------


def validate_path_exists(doc: dict[str, Any], path: str) -> ValidationError | None:
    """Return an error if *path* does not exist in *doc*."""
    if not path_exists(doc, path):
        return ValidationError(path=path, message="Path does not exist in document")
    return None


def validate_value_type(
    value: Any,
    expected_type: type,
    path: str = "",
) -> ValidationError | None:
    """Return an error if *value* is not an instance of *expected_type*."""
    if not isinstance(value, expected_type):
        return ValidationError(
            path=path,
            message=(
                f"Expected type {expected_type.__name__}, got {type(value).__name__}"
            ),
        )
    return None


def validate_enum_value(
    value: Any,
    valid_options: list[Any],
    path: str = "",
) -> ValidationError | None:
    """Return an error if *value* is not one of *valid_options*."""
    if value not in valid_options:
        return ValidationError(
            path=path,
            message=f"Value {value!r} not in {valid_options!r}",
        )
    return None


def validate_local(
    doc: dict[str, Any],
    path: str,
    value: Any,
) -> list[ValidationError]:
    """Run all local validation checks for a prospective mutation.

    Parameters
    ----------
    doc:
        The current normalized document.
    path:
        The path being mutated.
    value:
        The proposed new value.

    Returns
    -------
    list[ValidationError]
        A (possibly empty) list of validation findings.
    """
    errors: list[ValidationError] = []

    # The parent path must exist (we can't set a deep value if the
    # intermediate containers are missing).
    segments = path.rsplit(".", 1)
    if len(segments) == 2:
        parent_path = segments[0]
        err = validate_path_exists(doc, parent_path)
        if err is not None:
            errors.append(
                ValidationError(
                    path=parent_path,
                    message="Parent path does not exist",
                )
            )

    # Type-specific local checks can be added here in the future
    # (e.g. samplerate must be int > 0, gain must be numeric, etc.).

    return errors


# ------------------------------------------------------------------
# Full validation + apply pipeline
# ------------------------------------------------------------------


async def validate_and_apply(
    client: CamillaDSPClient,
    doc: dict[str, Any],
    filename: str,
    save: bool = True,
) -> dict[str, Any]:
    """Denormalize, validate with the backend, apply, and optionally save.

    Parameters
    ----------
    client:
        An active :class:`CamillaDSPClient` instance.
    doc:
        A normalized config document.
    filename:
        The config filename (used by ``set_config`` and ``save_config_file``).
    save:
        If ``True`` (default), persist to disk after applying.

    Returns
    -------
    dict
        The denormalized config dict that was sent to the backend.

    Raises
    ------
    CamillaDSPValidationError
        If the backend rejects the config.
    """
    raw_config = denormalize_config(doc)
    _LOGGER.debug("Validating config for %s", filename)

    # 1. Backend validation.
    result = await client.validate_config(raw_config)
    if result.strip().upper() != "OK":
        raise CamillaDSPValidationError(
            "Backend config validation failed",
            details=result,
        )

    # 2. Apply to the running DSP.
    _LOGGER.debug("Applying config %s", filename)
    await client.set_config(filename, raw_config)

    # 3. Optionally persist to disk.
    if save:
        _LOGGER.debug("Saving config file %s", filename)
        await client.save_config_file(filename, raw_config)

    return raw_config
