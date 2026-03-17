"""Clone-on-write mutation helpers for normalized CamillaDSP config documents.

Every mutation function returns a **new** document; the original is never
modified.  This guarantees that the cached document in the coordinator
stays stable while UI-driven edits build up a candidate document.
"""

from __future__ import annotations

import copy
from typing import Any

from .paths import parse_path, resolve_path


def get_value(doc: dict[str, Any], path: str) -> Any:
    """Get a value from the normalized document by path.

    Parameters
    ----------
    doc:
        The normalized config document.
    path:
        Dot-separated path with optional bracket notation.

    Returns
    -------
    Any
        The resolved value.

    Raises
    ------
    KeyError
        If a dict key in the path does not exist.
    IndexError
        If a list index in the path is out of range.
    """
    return resolve_path(doc, path)


def set_value(doc: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    """Set a value in the document by path (clone-on-write).

    Parameters
    ----------
    doc:
        The normalized config document.
    path:
        Dot-separated path with optional bracket notation.
    value:
        The new value to set.

    Returns
    -------
    dict
        A **new** document with the mutation applied.

    Raises
    ------
    KeyError
        If a parent key in the path does not exist.
    IndexError
        If a parent list index is out of range.
    """
    new_doc = copy.deepcopy(doc)
    segments = parse_path(path)
    if not segments:
        raise ValueError("Empty path")

    # Navigate to the parent of the target.
    parent: Any = new_doc
    for seg in segments[:-1]:
        if isinstance(seg, int):
            parent = parent[seg]
        else:
            parent = parent[seg]

    # Set the value on the parent.
    final = segments[-1]
    if isinstance(final, int):
        parent[final] = value
    else:
        parent[final] = value

    return new_doc


def delete_value(doc: dict[str, Any], path: str) -> dict[str, Any]:
    """Delete a value from the document by path (clone-on-write).

    Parameters
    ----------
    doc:
        The normalized config document.
    path:
        Dot-separated path with optional bracket notation.

    Returns
    -------
    dict
        A **new** document with the value removed.

    Raises
    ------
    KeyError
        If the key does not exist.
    IndexError
        If the list index is out of range.
    """
    new_doc = copy.deepcopy(doc)
    segments = parse_path(path)
    if not segments:
        raise ValueError("Empty path")

    # Navigate to the parent of the target.
    parent: Any = new_doc
    for seg in segments[:-1]:
        if isinstance(seg, int):
            parent = parent[seg]
        else:
            parent = parent[seg]

    # Delete from the parent.
    final = segments[-1]
    if isinstance(final, int):
        del parent[final]
    else:
        del parent[final]

    return new_doc


def batch_set_values(
    doc: dict[str, Any],
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply multiple ``{path, value}`` mutations atomically.

    A single deep-copy is made up front, then all operations are applied
    sequentially on the copy.  If any operation fails, the partially-
    modified copy is discarded (the caller still holds the original).

    Parameters
    ----------
    doc:
        The normalized config document.
    operations:
        A list of dicts, each with ``"path"`` and ``"value"`` keys.

    Returns
    -------
    dict
        A **new** document with all mutations applied.
    """
    new_doc = copy.deepcopy(doc)

    for op in operations:
        path = op["path"]
        value = op["value"]
        segments = parse_path(path)
        if not segments:
            raise ValueError(f"Empty path in batch operation: {op!r}")

        parent: Any = new_doc
        for seg in segments[:-1]:
            if isinstance(seg, int):
                parent = parent[seg]
            else:
                parent = parent[seg]

        final = segments[-1]
        if isinstance(final, int):
            parent[final] = value
        else:
            parent[final] = value

    return new_doc
