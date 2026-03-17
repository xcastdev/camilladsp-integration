"""CamillaDSP API client subpackage.

Public surface:
    - :class:`CamillaDSPClient` – async HTTP client
    - Model dataclasses: :class:`GuiConfig`, :class:`ActiveConfigFile`,
      :class:`StoredConfig`, :class:`RuntimeStatus`
    - Exception hierarchy rooted at :class:`CamillaDSPError`
"""

from .client import CamillaDSPClient
from .errors import (
    CamillaDSPConnectionError,
    CamillaDSPError,
    CamillaDSPPayloadError,
    CamillaDSPTimeoutError,
    CamillaDSPValidationError,
)
from .models import ActiveConfigFile, GuiConfig, RuntimeStatus, StoredConfig

__all__ = [
    "ActiveConfigFile",
    "CamillaDSPClient",
    "CamillaDSPConnectionError",
    "CamillaDSPError",
    "CamillaDSPPayloadError",
    "CamillaDSPTimeoutError",
    "CamillaDSPValidationError",
    "GuiConfig",
    "RuntimeStatus",
    "StoredConfig",
]
