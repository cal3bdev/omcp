"""Tests for configuration loading and validation."""

from pathlib import Path

import pytest

from omcp.config import OMCPConfig, load_config
from omcp.config.env import substitute_env_vars
from omcp.utils.errors import ConfigError


FIXTURES = Path(__file__).parent / "fixtures"


class TestConfigLoading:
    """Test configuration loading."""

    def test_load_valid_config(self):
        """Load a valid config file."""
        config = load_config(FIXTURES / "test_config.yaml")
        assert config.name == "Test API"
        assert config.spec == "./openapi.json"
        assert config.base_url == "https://api.example.com"
        assert config.auth.type.value == "bearer"
        assert config.auth.token == "test-token"

    def test_load_missing_file(self):
        """Loading a missing file raises ConfigError."""
        with pytest.raises(ConfigError) as exc:
            load_config(FIXTURES / "nonexistent.yaml")
        assert "not found" in str(exc.value.message)


class TestEnvSubstitution:
    """Test environment variable substitution."""

    def test_env_substitution(self):
        """Environment variables are substituted."""
        import os

        os.environ["TEST_VAR"] = "substituted"
        result = substitute_env_vars({"key": "${TEST_VAR}"})
        assert result["key"] == "substituted"
        del os.environ["TEST_VAR"]

    def test_env_substitution_nested(self):
        """Nested env vars are substituted."""
        import os

        os.environ["NESTED_VAR"] = "nested_value"
        result = substitute_env_vars(
            {"outer": {"inner": "${NESTED_VAR}", "list": ["${NESTED_VAR}"]}}
        )
        assert result["outer"]["inner"] == "nested_value"
        assert result["outer"]["list"][0] == "nested_value"
        del os.environ["NESTED_VAR"]

    def test_env_substitution_missing_var(self):
        """Missing env var remains as placeholder."""
        result = substitute_env_vars({"key": "${NONEXISTENT_VAR}"})
        assert result["key"] == "${NONEXISTENT_VAR}"

    def test_env_substitution_in_list(self):
        """Env vars in lists are substituted."""
        import os

        os.environ["LIST_VAR"] = "list_value"
        result = substitute_env_vars({"items": ["${LIST_VAR}", "static"]})
        assert result["items"][0] == "list_value"
        assert result["items"][1] == "static"
        del os.environ["LIST_VAR"]
