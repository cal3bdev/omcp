"""OMCP error classes."""

from __future__ import annotations


class OMCPError(Exception):
    """Base exception for all OMCP errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class ConfigError(OMCPError):
    """Invalid or missing configuration."""


class SpecLoadError(OMCPError):
    """Failed to load OpenAPI specification."""


class SpecValidationError(OMCPError):
    """OpenAPI specification is invalid."""


class AuthError(OMCPError):
    """Authentication failure."""


class PlanGenerationError(OMCPError):
    """Failed to generate OMCP plan."""


class PlanValidationError(OMCPError):
    """OMCP plan failed validation."""


class ModuleRuntimeError(OMCPError):
    """Module server runtime failure."""


class HubRoutingError(OMCPError):
    """Hub failed to route request to module."""
