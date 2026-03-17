"""Root-level conftest that stubs out homeassistant dependencies.

The integration's ``__init__.py`` imports ``homeassistant`` which is not
available in the unit-test environment.  We install lightweight stub
modules into ``sys.modules`` *before* any of the custom_components modules
are imported so that the pure-Python modules we actually test can be
loaded without error.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock


def _make_stub_module(name: str) -> ModuleType:
    """Create a stub module that allows arbitrary attribute access."""
    mod = ModuleType(name)
    mod.__path__ = []  # type: ignore[attr-defined]
    mod.__file__ = f"<stub:{name}>"
    mod.__loader__ = None  # type: ignore[attr-defined]
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None, origin=f"<stub:{name}>")
    mod.__package__ = name

    # Allow arbitrary attribute access (return MagicMock for anything not set)
    class _AttrProxy(type(mod)):
        def __getattr__(self, attr: str):
            if attr.startswith("__") and attr.endswith("__"):
                raise AttributeError(attr)
            return MagicMock()

    # Swap the class so attribute lookups fall through to MagicMock
    mod.__class__ = _AttrProxy
    return mod


# Build a mock module tree for homeassistant and its subpackages,
# plus any other third-party HA-ecosystem packages not installed here.
_STUB_MODULES = [
    # homeassistant core
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.typing",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.components",
    "homeassistant.components.number",
    "homeassistant.components.select",
    "homeassistant.components.sensor",
    "homeassistant.components.switch",
    "homeassistant.exceptions",
    "homeassistant.const",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.device_registry",
    # voluptuous (HA validation library)
    "voluptuous",
    "voluptuous.humanize",
]

for _mod_name in _STUB_MODULES:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_stub_module(_mod_name)
