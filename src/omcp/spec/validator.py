"""OpenAPI specification validation."""

from __future__ import annotations

from typing import Any

from omcp.utils.errors import SpecValidationError


def validate_spec(spec: dict[str, Any]) -> None:
    """Validate that a spec is a valid OpenAPI document.

    Performs basic structural validation - not a full schema check.

    Args:
        spec: Parsed OpenAPI specification

    Raises:
        SpecValidationError: If the spec is invalid
    """
    errors: list[str] = []

    # Check OpenAPI version
    if "openapi" not in spec and "swagger" not in spec:
        errors.append("Missing 'openapi' or 'swagger' version field")
    else:
        version = spec.get("openapi") or spec.get("swagger", "")
        if not _is_supported_version(version):
            errors.append(f"Unsupported OpenAPI version: {version}")

    # Check info section
    if "info" not in spec:
        errors.append("Missing 'info' section")
    elif not isinstance(spec["info"], dict):
        errors.append("'info' must be an object")
    else:
        if "title" not in spec["info"]:
            errors.append("Missing 'info.title'")
        if "version" not in spec["info"]:
            errors.append("Missing 'info.version'")

    # Check paths section
    if "paths" not in spec:
        errors.append("Missing 'paths' section")
    elif not isinstance(spec["paths"], dict):
        errors.append("'paths' must be an object")
    elif len(spec["paths"]) == 0:
        errors.append("'paths' is empty - no endpoints defined")

    if errors:
        details = "\n".join(f"  - {e}" for e in errors)
        raise SpecValidationError("Invalid OpenAPI specification", details=details)


def _is_supported_version(version: str) -> bool:
    """Check if the OpenAPI version is supported."""
    # Support OpenAPI 3.x and Swagger 2.0
    if version.startswith("3."):
        return True
    if version == "2.0":
        return True
    return False


def get_spec_version(spec: dict[str, Any]) -> str:
    """Get the OpenAPI/Swagger version from a spec."""
    return spec.get("openapi") or spec.get("swagger", "unknown")


def get_spec_title(spec: dict[str, Any]) -> str:
    """Get the API title from a spec."""
    info = spec.get("info", {})
    return info.get("title", "Untitled API")
