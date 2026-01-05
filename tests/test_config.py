"""Tests for configuration loading and validation."""

from pathlib import Path

import pytest

from omcp.config import OMCPConfig, load_config
from omcp.config.env import substitute_env_vars
from omcp.config.models import AuthConfig, AuthType, JWTValidationConfig, AuthHeaderConfig
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


class TestJWTAuthValidation:
    """Test JWT auth configuration validation."""

    def test_jwt_auth_with_default_headers_allowed(self):
        """JWT auth with default headers should be allowed."""
        config = AuthConfig(
            type=AuthType.JWT,
            validation=JWTValidationConfig(enabled=True),
            header=AuthHeaderConfig(name="Authorization", scheme="Bearer"),
        )
        assert config.type == AuthType.JWT

    def test_jwt_auth_custom_header_name_rejected(self):
        """JWT auth with custom header name should be rejected."""
        with pytest.raises(ValueError) as exc:
            AuthConfig(
                type=AuthType.JWT,
                validation=JWTValidationConfig(enabled=True),
                header=AuthHeaderConfig(name="X-API-Key", scheme="Bearer"),
            )
        assert "Custom header names and schemes are not supported" in str(exc.value)

    def test_jwt_auth_custom_scheme_rejected(self):
        """JWT auth with custom scheme should be rejected."""
        with pytest.raises(ValueError) as exc:
            AuthConfig(
                type=AuthType.JWT,
                validation=JWTValidationConfig(enabled=True),
                header=AuthHeaderConfig(name="Authorization", scheme="Token"),
            )
        assert "Custom header names and schemes are not supported" in str(exc.value)

    def test_jwt_passthrough_mode_allows_custom_headers(self):
        """JWT auth in passthrough mode should allow custom headers."""
        config = AuthConfig(
            type=AuthType.JWT,
            validation=JWTValidationConfig(enabled=False),
            header=AuthHeaderConfig(name="X-API-Key", scheme="Token"),
        )
        assert config.header.name == "X-API-Key"
        assert config.header.scheme == "Token"

    def test_bearer_auth_allows_custom_headers(self):
        """Bearer auth should allow custom headers."""
        config = AuthConfig(
            type=AuthType.BEARER,
            token="test-token",
            header=AuthHeaderConfig(name="X-Custom", scheme="Token"),
        )
        assert config.header.name == "X-Custom"
