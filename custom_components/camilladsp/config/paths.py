"""Path parsing and resolution for normalized CamillaDSP config documents.

Paths use dot-separated notation with bracket indexing for lists::

    "filters.Bass Control.parameters.gain"
    "pipeline[1].bypassed"
    "mixers.Stereo.mapping[0].sources[0].gain"
"""

from __future__ import annotations

import re
from typing import Any

# Matches either a plain segment or a segment followed by one or more
# bracket indices, e.g. ``"pipeline[1]"`` → group(1)="pipeline", then
# ``[1]`` is captured by findall below.
_BRACKET_RE = re.compile(r"\[(\d+)\]")


def parse_path(path: str) -> list[str | int]:
    """Parse a dot-separated path with bracket notation into segments.

    Examples
    --------
    >>> parse_path("filters.Bass Control.parameters.gain")
    ['filters', 'Bass Control', 'parameters', 'gain']
    >>> parse_path("pipeline[1].bypassed")
    ['pipeline', 1, 'bypassed']
    >>> parse_path("mixers.Stereo.mapping[0].sources[0].gain")
    ['mixers', 'Stereo', 'mapping', 0, 'sources', 0, 'gain']
    >>> parse_path("devices")
    ['devices']
    """
    if not path:
        return []

    segments: list[str | int] = []

    for part in path.split("."):
        if not part:
            continue

        # Check for bracket indices, e.g. "pipeline[1]" or "sources[0]".
        bracket_indices = _BRACKET_RE.findall(part)
        if bracket_indices:
            # The text before the first bracket is the key.
            key = _BRACKET_RE.split(part)[0]
            if key:
                segments.append(key)
            for idx_str in bracket_indices:
                segments.append(int(idx_str))
        else:
            segments.append(part)

    return segments


def resolve_path(doc: dict[str, Any], path: str | list[str | int]) -> Any:
    """Resolve a path to its value in the document.

    Parameters
    ----------
    doc:
        The normalized config document (or any nested dict/list).
    path:
        Either a dot-notation string or an already-parsed list of segments.

    Returns
    -------
    Any
        The resolved value.

    Raises
    ------
    KeyError
        If a dict key is not found.
    IndexError
        If a list index is out of range.
    TypeError
        If traversal hits a non-container type before the path is fully
        consumed.
    """
    segments = parse_path(path) if isinstance(path, str) else path
    current: Any = doc
    for seg in segments:
        if isinstance(seg, int):
            if not isinstance(current, (list, tuple)):
                raise TypeError(
                    f"Expected list at index {seg}, got {type(current).__name__}"
                )
            current = current[seg]  # may raise IndexError
        else:
            if not isinstance(current, dict):
                raise TypeError(
                    f"Expected dict for key {seg!r}, got {type(current).__name__}"
                )
            current = current[seg]  # may raise KeyError
    return current


def path_exists(doc: dict[str, Any], path: str | list[str | int]) -> bool:
    """Check if a path exists in the document.

    Returns ``True`` if every segment resolves successfully, ``False``
    otherwise.
    """
    try:
        resolve_path(doc, path)
    except (KeyError, IndexError, TypeError):
        return False
    return True


def format_path(segments: list[str | int]) -> str:
    """Convert parsed segments back to a canonical path string.

    Integer segments are rendered with bracket notation on the preceding
    key.

    Examples
    --------
    >>> format_path(['pipeline', 1, 'bypassed'])
    'pipeline[1].bypassed'
    >>> format_path(['filters', 'Bass Control', 'parameters', 'gain'])
    'filters.Bass Control.parameters.gain'
    """
    if not segments:
        return ""

    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, int):
            # Append bracket notation to the previous part.
            if parts:
                parts[-1] = f"{parts[-1]}[{seg}]"
            else:
                # Edge case: path starts with an index (unusual).
                parts.append(f"[{seg}]")
        else:
            parts.append(str(seg))

    return ".".join(parts)
