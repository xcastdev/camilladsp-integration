"""Exception hierarchy for CamillaDSP API communication."""

from __future__ import annotations


class CamillaDSPError(Exception):
    """Base exception for CamillaDSP errors."""


class CamillaDSPConnectionError(CamillaDSPError):
    """Connection to CamillaDSP failed."""


class CamillaDSPTimeoutError(CamillaDSPConnectionError):
    """Connection to CamillaDSP timed out."""


class CamillaDSPValidationError(CamillaDSPError):
    """Config validation failed.

    Attributes:
        details: The raw validation error message returned by the backend.
    """

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.details = details


class CamillaDSPPayloadError(CamillaDSPError):
    """Unexpected response payload from CamillaDSP."""
