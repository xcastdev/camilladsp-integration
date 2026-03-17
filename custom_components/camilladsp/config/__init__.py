"""CamillaDSP configuration subpackage.

Public API
----------
- :func:`normalize_config` / :func:`denormalize_config` — transform between
  raw backend configs and the normalized internal representation.
- :func:`get_value` / :func:`set_value` / :func:`delete_value` /
  :func:`batch_set_values` — clone-on-write document mutations.
- :func:`parse_path` / :func:`resolve_path` / :func:`path_exists` /
  :func:`format_path` — path utilities.
- :func:`validate_local` / :func:`validate_and_apply` — validation helpers.
"""

from .mutate import batch_set_values, delete_value, get_value, set_value
from .normalize import denormalize_config, normalize_config
from .paths import format_path, parse_path, path_exists, resolve_path
from .validate import ValidationError, validate_and_apply, validate_local

__all__ = [
    "batch_set_values",
    "delete_value",
    "denormalize_config",
    "format_path",
    "get_value",
    "normalize_config",
    "parse_path",
    "path_exists",
    "resolve_path",
    "set_value",
    "validate_and_apply",
    "validate_local",
    "ValidationError",
]
