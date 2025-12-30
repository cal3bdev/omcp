"""Environment variable substitution for config values."""

from __future__ import annotations

import os
import re
from typing import Any


ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def substitute_env_vars(value: Any) -> Any:
    """Recursively substitute ${VAR} patterns with environment variables.

    Args:
        value: Config value (string, dict, list, or other)

    Returns:
        Value with environment variables substituted
    """
    if isinstance(value, str):
        return _substitute_string(value)
    elif isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_env_vars(item) for item in value]
    return value


def _substitute_string(value: str) -> str:
    """Substitute environment variables in a string."""

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            # Keep original if not found - will fail at validation
            return match.group(0)
        return env_value

    return ENV_PATTERN.sub(replacer, value)
