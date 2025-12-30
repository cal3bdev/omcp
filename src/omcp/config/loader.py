"""Configuration loading from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from omcp.config.env import substitute_env_vars
from omcp.config.models import OMCPConfig
from omcp.utils.errors import ConfigError


def load_config(path: str | Path) -> OMCPConfig:
    """Load and validate OMCP configuration from a YAML file.

    Args:
        path: Path to the config file (omcp.yaml)

    Returns:
        Validated OMCPConfig instance

    Raises:
        ConfigError: If the file cannot be read or config is invalid
    """
    path = Path(path)

    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw_config = _load_yaml(path)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}", details=str(e))

    # Substitute environment variables
    config_data = substitute_env_vars(raw_config)

    # Validate with Pydantic
    try:
        return OMCPConfig.model_validate(config_data)
    except ValidationError as e:
        errors = _format_validation_errors(e)
        raise ConfigError("Invalid configuration", details=errors)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file and return as dict."""
    with path.open() as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ConfigError(f"Empty config file: {path}")

    if not isinstance(data, dict):
        raise ConfigError(f"Config must be a YAML mapping, got {type(data).__name__}")

    return data


def _format_validation_errors(error: ValidationError) -> str:
    """Format Pydantic validation errors for display."""
    lines = []
    for err in error.errors():
        loc = ".".join(str(x) for x in err["loc"])
        msg = err["msg"]
        lines.append(f"  {loc}: {msg}")
    return "\n".join(lines)
